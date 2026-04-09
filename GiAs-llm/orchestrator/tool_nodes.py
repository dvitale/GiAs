"""
Tool nodes per il grafo LangGraph.

Ogni funzione è un nodo del grafo che:
1. Estrae slot/metadata dallo state
2. Chiama la funzione tool corrispondente
3. Applica two-phase check se necessario
4. Setta state["tool_output"]
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, get_establishments_with_sanctions
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from tools.proximity_tools import get_nearby_priority
    from agents.response_agent import ResponseFormatter
    from configs.config import RiskPredictorConfig
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.piano_tools import piano_tool, get_piano_statistics
    from tools.priority_tools import priority_tool, suggest_controls
    from tools.risk_tools import risk_tool, get_establishments_with_sanctions
    from tools.search_tools import search_tool
    from tools.establishment_tools import get_establishment_history
    from tools.risk_analysis_tools import get_top_risk_activities
    from tools.predictor_tools import get_ml_risk_prediction
    from tools.proximity_tools import get_nearby_priority
    from agents.response_agent import ResponseFormatter
    from configs.config import RiskPredictorConfig

from .two_phase import apply_two_phase_check, TWO_PHASE_THRESHOLDS

logger = logging.getLogger(__name__)


def _unwrap_tool(tool_ref) -> Any:
    """Unwrap LangChain @tool decorated function to get the raw callable.

    Ritorna ``Any`` per evitare diagnostici Pyright ``reportCallIssue``:
    con ``langchain_core`` installato, ``@tool`` ritorna ``BaseTool`` che
    Pyright considera non-chiamabile (il ``__call__`` esiste ma via
    ``Runnable`` abstract). Il valore restituito è sempre chiamabile a
    runtime (``BaseTool.func`` o la funzione pura del fallback stub).
    """
    return tool_ref.func if hasattr(tool_ref, 'func') else tool_ref


def _pseudo_query(table: str, columns: str = "*", where: Optional[dict] = None, extra: str = "") -> str:
    """Genera una pseudo-query SQL leggibile per la debug page."""
    sql = f"SELECT {columns} FROM {table}"
    conditions = []
    if where:
        for col, val in where.items():
            if val is not None and str(val).strip():
                conditions.append(f"{col} = '{val}'")
    # extra potrebbe contenere "WHERE ..." o "GROUP BY ..." o "ORDER BY ..."
    extra_stripped = extra.strip()
    if extra_stripped.upper().startswith("WHERE "):
        extra_conditions = extra_stripped[6:]  # rimuovi "WHERE "
        conditions.append(extra_conditions)
        extra_stripped = ""
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if extra_stripped:
        sql += " " + extra_stripped
    return sql


def _query_descriptor_to_pseudo_sql(descriptor) -> str:
    """
    Serializza un QueryDescriptor in SQL pseudo-leggibile per la debug page.

    Riflette fedelmente ciò che SafeQueryExecutor esegue sul DataFrame:
    - nome tabella reale preso dal SchemaCatalog (fallback TABLE_ALIASES canonico)
    - operazione tradotta in SELECT/COUNT/SUM/…
    - filtri con operatore (contains → ILIKE '%val%', eq/gte/lte, in)
    - alias colonne (anno/asl/uoc/…) risolti come fa _preprocess_filters
    - GROUP BY, ORDER BY, LIMIT
    """
    COLUMN_ALIASES: Dict[str, Dict[str, str]]
    try:
        from tools.query_builder_tools import COLUMN_ALIASES as _COL_ALIASES
        COLUMN_ALIASES = _COL_ALIASES  # type: ignore[assignment]
    except Exception:
        COLUMN_ALIASES = {}

    # Mappa canonica table_key (es. "controlli") → nome tabella reale nel DB.
    # Preferita rispetto all'inversione di TABLE_ALIASES (che contiene
    # varianti come cu_eseguiti_x).
    _CANONICAL_TABLE_NAMES = {
        "controlli": "cu_eseguiti_nc",
        "programmazione": "cu_diff_programmati_eseguiti",
        "piani": "piani_monitoraggio",
        "masterlist": "masterlist",
        "mai_controllati": "osa_mai_controllati",
        "personale": "personale",
    }

    table_in = (descriptor.table or "").strip().lower()
    # 1) Prova via SchemaCatalog (DB-first), 2) mappa canonica, 3) fallback literal
    table: Optional[str] = None
    try:
        from orchestrator.schema_catalog import get_schema_catalog
        entry = get_schema_catalog().get_full_schema(table_in) if table_in else {}
        if isinstance(entry, dict) and entry.get("table_name"):
            table = entry["table_name"]
    except Exception:
        pass
    if not table:
        table = _CANONICAL_TABLE_NAMES.get(table_in, descriptor.table or "")

    # Risolvi alias colonne per la tabella (coerente con _preprocess_filters)
    table_key = table_in if table_in in _CANONICAL_TABLE_NAMES else None
    # Inversione TABLE_ALIASES: se non è un key, potrebbe essere già un nome reale
    if table_key is None:
        for k, real in _CANONICAL_TABLE_NAMES.items():
            if real == table_in:
                table_key = k
                break
    col_aliases: Dict[str, str] = (
        COLUMN_ALIASES.get(table_key, {}) if table_key else {}
    )

    op = (descriptor.operation or "").lower()
    group_by_raw = list(descriptor.group_by or [])
    group_by: List[str] = [str(col_aliases.get(g, g) or g) for g in group_by_raw]
    order_by = descriptor.order_by
    limit = descriptor.limit

    if op == "count":
        select_clause = "COUNT(*) AS count"
    elif op == "group_count":
        cols = ", ".join(group_by) if group_by else "*"
        select_clause = f"{cols}, COUNT(*) AS count"
    elif op == "sum":
        cols = (", ".join(group_by) + ", ") if group_by else ""
        select_clause = f"{cols}SUM(<numeric_columns>)"
    elif op == "mean":
        cols = (", ".join(group_by) + ", ") if group_by else ""
        select_clause = f"{cols}AVG(<numeric_columns>)"
    elif op == "distinct":
        col = group_by[0] if group_by else "*"
        select_clause = f"DISTINCT {col}"
    else:  # top_n, filter, unknown
        select_clause = "*"

    # Filtri → condizioni WHERE (replicano _preprocess_filters)
    conditions: List[str] = []
    for f in (descriptor.filters or []):
        raw_col = f.column
        fop = (f.op or "eq").lower()
        val = f.value

        # 1) Caso speciale "anno"/"year"
        if raw_col in ("anno", "year"):
            try:
                year = int(val)
            except (TypeError, ValueError):
                year = val
            if table_key == "controlli":
                conditions.append(
                    f"data_inizio_controllo >= '{year}-01-01' "
                    f"AND data_inizio_controllo <= '{year}-12-31'"
                )
            else:
                conditions.append(f"anno = {year}")
            continue

        # 2) Risolvi alias colonna
        col = col_aliases.get(raw_col, raw_col)

        # 3) Normalizza operatore/valore come fa il preprocessor
        if isinstance(val, str) and col in ("descrizione_asl",):
            import re as _re
            m = _re.match(r'^(?:ASL|Asl|asl)\s+(?:di\s+)?(.+)$', val.strip(), _re.IGNORECASE)
            if m:
                val = m.group(1).strip()
        # eq su stringhe è promosso a contains dall'esecutore
        if fop == "eq" and isinstance(val, str):
            fop = "contains"

        if fop == "contains":
            conditions.append(f"{col} ILIKE '%{val}%'")
        elif fop == "eq":
            conditions.append(f"{col} = {val}")
        elif fop == "neq":
            conditions.append(f"{col} <> '{val}'" if isinstance(val, str) else f"{col} <> {val}")
        elif fop == "gte":
            conditions.append(f"{col} >= '{val}'" if isinstance(val, str) else f"{col} >= {val}")
        elif fop == "lte":
            conditions.append(f"{col} <= '{val}'" if isinstance(val, str) else f"{col} <= {val}")
        elif fop == "in" and isinstance(val, list):
            inner = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in val)
            conditions.append(f"{col} IN ({inner})")
        elif fop == "not_in" and isinstance(val, list):
            inner = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in val)
            conditions.append(f"{col} NOT IN ({inner})")
        else:
            conditions.append(f"{col} {fop} {val!r}")

    sql = f"SELECT {select_clause}\nFROM {table}"
    if conditions:
        sql += "\nWHERE " + "\n  AND ".join(conditions)
    if group_by and op in ("group_count", "sum", "mean"):
        sql += f"\nGROUP BY {', '.join(group_by)}"
    if order_by is not None:
        direction = getattr(order_by, "direction", "desc").upper()
        sql += f"\nORDER BY {order_by.column} {direction}"
    if limit:
        sql += f"\nLIMIT {limit}"
    return sql + ";"


def _build_delayed_pseudo_query(
    asl: Optional[str] = None,
    uoc: Optional[str] = None,
    uos: Optional[str] = None,
    tipo: Optional[str] = None,
    target_year: Optional[int] = None,
    piano_code: Optional[str] = None,
) -> str:
    """
    Pseudo-query SQL per la debug page degli intent di ritardo
    (ask_delayed_plans, check_if_plan_delayed).

    Riflette fedelmente la logica di BusinessLogic.calculate_delayed_plans:
      - filtri ASL/UOC/UOS via LIKE substring (come pandas .str.contains)
      - filtro `anno = target_year` (default da config / anno corrente)
      - filtro `tipo_piano_attivita IN ('piano','attivita')` invece del fragile
        prefisso `alias_indicatore LIKE 'ATT%'`
      - quota proporzionale: per anno corrente `attesi = ROUND(programmati * frazione_anno)`,
        altrimenti `attesi = programmati`
      - record in ritardo: `eseguiti < attesi`
    """
    from datetime import datetime as _dt
    import calendar

    resolved_year = target_year
    if resolved_year is None:
        try:
            from configs.config_loader import get_config
            resolved_year = get_config().get_current_year()
        except Exception:
            resolved_year = _dt.now().year

    now = _dt.now()
    if resolved_year == now.year:
        days_in_year = 366 if calendar.isleap(resolved_year) else 365
        yday = now.timetuple().tm_yday
        fraction = yday / days_in_year
        attesi_expr = f"ROUND(programmati * {fraction:.4f})"
        header_note = (
            f"-- Anno corrente {resolved_year}: frazione anno trascorsa = "
            f"{yday}/{days_in_year} ≈ {fraction:.4f} ({fraction*100:.1f}%)\n"
            "-- attesi proporzionali = ROUND(programmati * frazione)\n"
        )
    else:
        attesi_expr = "programmati"
        header_note = (
            f"-- Anno {resolved_year} (passato): attesi = programmati (anno completo)\n"
        )

    conditions: List[str] = [f"anno = {resolved_year}"]
    if asl and str(asl).strip():
        conditions.append(f"descrizione_asl ILIKE '%{asl}%'")
    if uoc and str(uoc).strip():
        conditions.append(f"descrizione_uoc ILIKE '%{uoc}%'")
    if uos and str(uos).strip():
        conditions.append(f"descrizione_uos ILIKE '%{uos}%'")
    if tipo == "piano":
        conditions.append("tipo_piano_attivita = 'piano'")
    elif tipo == "attivita":
        conditions.append("tipo_piano_attivita = 'attivita'")
    if piano_code and str(piano_code).strip():
        conditions.append(f"UPPER(alias_indicatore) = '{str(piano_code).upper()}'")

    where_clause = "\n  AND ".join(conditions)
    return (
        header_note
        + "SELECT alias_indicatore, programmati, eseguiti,\n"
        + f"       {attesi_expr} AS attesi,\n"
        + f"       GREATEST(0, {attesi_expr} - eseguiti) AS ritardo\n"
        + "FROM cu_diff_programmati_eseguiti\n"
        + f"WHERE {where_clause}\n"
        + f"  AND eseguiti < {attesi_expr}\n"
        + "ORDER BY ritardo DESC;"
    )


# =============================================================================
# SIMPLE TOOLS (no DB queries)
# =============================================================================

def greet_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    buddy_mode = bool(metadata.get("buddy_mode"))
    if buddy_mode:
        greeting = "Ehi, ciao! 👋 Sono il tuo assistente GiAs per il monitoraggio veterinario. Chiedimi pure quello che ti serve — piani di controllo, priorita', stabilimenti a rischio... sono tutto orecchie! 😊"
    else:
        greeting = "Ciao! Sono l'assistente GiAs per il monitoraggio veterinario. Dimmi pure cosa ti serve — posso aiutarti con piani di controllo, priorita' di ispezione, stabilimenti a rischio e molto altro."
    state["tool_output"] = {
        "type": "greet",
        "data": {"formatted_response": greeting}
    }
    return state


def goodbye_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    buddy_mode = bool(metadata.get("buddy_mode"))
    if buddy_mode:
        farewell = "Ci vediamo! 👋 Buon lavoro e in bocca al lupo! Se ti serve una mano, sai dove trovarmi. 💪"
    else:
        farewell = "Alla prossima, buon lavoro! Se ti serve altro, sono qui."
    state["tool_output"] = {
        "type": "goodbye",
        "data": {"formatted_response": farewell}
    }
    return state


_HARDCODED_HELP = (
    "**Come posso aiutarti?**\n\n"
    "Ecco cosa posso fare, con esempi di domande:\n\n"
    "**📋 Piani di Controllo**\n"
    "- [Di cosa tratta il piano A1?]\n"
    "- [Quali stabilimenti sono controllati per l'indicatore A1_A?]\n"
    "- [Quanti indicatori ha il piano A1?]\n"
    "\n**🔍 Ricerca Piani**\n"
    "- [Cerca piani sulla sicurezza alimentare]\n"
    "- [Piani sul benessere animale]\n"
    "\n**⏰ Ritardi**\n"
    "- [Piani in ritardo]\n"
    "- [Quali indicatori del piano A1 sono in ritardo?]\n"
    "\n**⚠️ Priorità e Rischio**\n"
    "- [Stabilimenti prioritari]\n"
    "- [Stabilimenti a rischio]\n"
    "- [Stabilimenti mai controllati]\n"
    "- [Quali sono i motivi di ispezione più rischiosi?]\n"
    "\n**📍 Ricerca per Prossimità**\n"
    "- [Stabilimenti vicino a Piazza Risorgimento, Benevento]\n"
    "- [Controlli nei dintorni di Via Roma 15, Napoli entro 3 km]\n"
    "\n**📜 Storico e Analisi**\n"
    "- [Storico controlli stabilimento]\n"
    "\n**📋 Procedure Operative**\n"
    "- [Qual e' la procedura per ispezione semplice?]\n"
    "- [Come si esegue un controllo ufficiale?]\n"
)


def help_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    try:
        from orchestrator.intent_metadata_service import get_intent_metadata_service
        service = get_intent_metadata_service()
        formatted_response = service.get_help_content()
    except Exception:
        formatted_response = ""

    if not formatted_response:
        formatted_response = _HARDCODED_HELP

    state["tool_output"] = {
        "type": "help",
        "data": {
            "formatted_response": formatted_response
        }
    }
    return state


def confirm_details_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """Gestisce la conferma per visualizzare i dettagli (two-phase)."""
    detail_context = state.get("metadata", {}).get("detail_context", {})

    if detail_context:
        state["tool_output"] = {
            "type": "confirm_details",
            "data": {
                "confirmed": True,
                "detail_context": detail_context,
                "formatted_response": detail_context.get("formatted_response",
                    "Ecco i dettagli richiesti.")
            }
        }
    else:
        # Sessione scaduta o contesto perso: guida l'utente a ripetere la domanda
        state["tool_output"] = {
            "type": "confirm_details",
            "data": {
                "confirmed": False,
                "detail_context": None,
                "formatted_response": (
                    "La sessione è scaduta e non ho più il contesto della richiesta precedente.\n\n"
                    "Per favore, ripeti la domanda originale. Ecco alcuni esempi:\n"
                    "- [[Stabilimenti a rischio]]\n"
                    "- [[Stabilimenti prioritari]]\n"
                    "- [[Piani che trattano di sicurezza alimentare]]"
                )
            }
        }
    return state


def decline_details_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """Gestisce il rifiuto dei dettagli (two-phase)."""
    state["tool_output"] = {
        "type": "decline_details",
        "data": {
            "confirmed": False,
            "formatted_response": "Va bene! Se hai altre domande, sono qui per aiutarti."
        }
    }
    return state


# =============================================================================
# PIANO TOOLS
# =============================================================================

def piano_description_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    piano_code = state["slots"].get("piano_code")
    result = piano_tool(action="description", piano_code=piano_code)
    state["tool_output"] = {"type": "piano_description", "data": result,
        "pseudo_query": _pseudo_query("piani_monitoraggio", "alias_piano_attivita, descrizione_piano_attivita, descrizione_indicatore, sezione",
            {"alias_piano_attivita": piano_code})}
    return state


def piano_stabilimenti_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "piano_stabilimenti_tool",
            "message": "Consultando il database dei piani..."
        })

    from agents.data import get_uos_from_user_id

    piano_code = state["slots"].get("piano_code")
    entity_hint = state["slots"].get("entity_hint")
    user_uos = (state.get("metadata") or {}).get("uos")
    # Fallback: risolvi UOS da user_id via personale_df se metadata non la contiene
    if not user_uos:
        user_id = (state.get("metadata") or {}).get("user_id")
        if user_id:
            user_uos = get_uos_from_user_id(user_id)
    result = piano_tool(action="stabilimenti", piano_code=piano_code, entity_hint=entity_hint, user_uos=user_uos)

    # Two-phase check
    if isinstance(result, dict) and "formatted_response" in result:
        import pandas as pd
        unique_establishments = result.get("unique_establishments", 0)
        if unique_establishments > TWO_PHASE_THRESHOLDS.get("ask_piano_stabilimenti", 2):
            top_stab_data = result.get("top_stabilimenti", [])
            top_stab_df = pd.DataFrame(top_stab_data) if isinstance(top_stab_data, list) else top_stab_data
            summary_text = ResponseFormatter.format_stabilimenti_analysis_summary(
                piano_id=result.get("piano_code", piano_code),
                piano_desc=result.get("piano_description", ""),
                top_stabilimenti=top_stab_df,
                total_controls=result.get("total_controls", 0),
                unique_establishments=unique_establishments,
                entity_type=result.get("entity_type", "piano"),
                anno=result.get("anno"),
                user_uos=result.get("user_uos"),
                total_controls_all=result.get("total_controls_all"),
            )
            # Propaga il warning di mismatch entity_hint anche nella sintesi two-phase
            from tools.piano_tools import _build_mismatch_prefix
            mismatch_prefix = _build_mismatch_prefix(
                result.get("entity_hint"),
                result.get("entity_type", "piano"),
                result.get("piano_code", piano_code or ""),
            )
            if mismatch_prefix:
                summary_text = mismatch_prefix + summary_text
            result = apply_two_phase_check(
                state, "ask_piano_stabilimenti", result, unique_establishments, summary_text
            )

    entity_type = result.get("entity_type", "piano") if isinstance(result, dict) else "piano"
    anno = result.get("anno") if isinstance(result, dict) else None

    # Pseudo-query ricostruita fedelmente rispetto alla catena effettiva:
    #   DataRetriever.get_controlli_by_piano(piano_code)  ← filtro piano
    #   + filtro anno corrente su data_inizio_controllo
    #   + filter_by_uos(descrizione_uos == user_uos)      ← scope operativo
    # La forma stringa evita gli artefatti di quoting del helper _pseudo_query
    # quando si usano clausole LIKE/regex (vedi bug precedente sulle doppie quote).
    pq_lines = [
        "SELECT macroarea_cu, aggregazione_cu, attivita_cu, COUNT(*) AS controlli",
        "FROM cu_eseguiti_nc",
    ]
    if entity_type == "attivita":
        # Attività: match via descrizione_indicatore LIKE 'ATT_<base>%'
        base = piano_code[4:] if piano_code and piano_code.upper().startswith("ATT ") else (piano_code or "")
        pq_lines.append(
            f"WHERE UPPER(descrizione_indicatore) LIKE 'ATT\\_{base.upper()}%' ESCAPE '\\'"
        )
    else:
        # Piano: regex su alias_indicatore con ramo ATT opzionale
        piano_up = (piano_code or "").upper()
        pq_lines.append(
            f"WHERE UPPER(alias_indicatore) ~ '^(ATT\\s+)?{piano_up}(_|\\s|$)'"
        )
    if anno:
        pq_lines.append(f"  AND EXTRACT(YEAR FROM data_inizio_controllo) = {anno}")
    if user_uos:
        pq_lines.append(f"  AND descrizione_uos ILIKE '%{user_uos}%'")
    else:
        pq_lines.append("  -- UOS operatore non disponibile: scope non applicato")
    pq_lines.append("GROUP BY macroarea_cu, aggregazione_cu, attivita_cu")
    pq_lines.append("ORDER BY COUNT(*) DESC")
    pq = "\n".join(pq_lines)

    state["tool_output"] = {"type": "piano_stabilimenti", "data": result, "pseudo_query": pq}
    return state


def piano_statistics_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    from agents.data import get_uos_from_user_id

    asl = state["metadata"].get("asl")
    piano_code = state["slots"].get("piano_code")
    message = state.get("message", "").lower()

    # Scope UOS dell'operatore collegato. Contratto di dominio: le query su
    # "controlli eseguiti" DEVONO essere filtrate sulla UOS dell'utente.
    # Priorità: metadata esplicito → risoluzione da user_id.
    user_uos = state["metadata"].get("uos")
    if not user_uos:
        user_id = state["metadata"].get("user_id")
        if user_id:
            user_uos = get_uos_from_user_id(user_id)

    if piano_code:
        # Propaga user_uos al tool: get_piano_attivita applicherà filter_by_uos
        # sul DataFrame controlli prima di conteggiare.
        result = piano_tool(
            action="stabilimenti",
            piano_code=piano_code,
            user_uos=user_uos,
        )

        count_keywords = ["quanti", "quante", "numero di", "conta", "totale controlli"]
        is_count_query = any(kw in message for kw in count_keywords)

        if is_count_query and result.get("total_controls") is not None:
            from agents.data_agent import DataRetriever
            from agents.utils import filter_by_uos
            import pandas as pd

            # total_controls è già scopato per UOS (applicato in get_piano_attivita).
            # total_controls_all è il totale regionale — lo manteniamo per confronto
            # ma lo chiariamo nella risposta.
            total_uos = result.get("total_controls", 0)
            total_regional = result.get("total_controls_all", total_uos)
            piano_desc = result.get("piano_description", piano_code.upper())

            # Second fetch per derivare il periodo temporale (date min/max).
            # Applichiamo lo STESSO filtro UOS per coerenza col conteggio primario.
            controlli_df = DataRetriever.get_controlli_by_piano(piano_code)
            if user_uos and controlli_df is not None and not controlli_df.empty:
                controlli_df = filter_by_uos(controlli_df, user_uos, "descrizione_uos")

            data_primo = None
            data_ultimo = None
            if controlli_df is not None and not controlli_df.empty and 'data_inizio_controllo' in controlli_df.columns:
                dates = pd.to_datetime(controlli_df['data_inizio_controllo'], errors='coerce')
                data_primo = dates.min()
                data_ultimo = dates.max()

            # Formattazione: mostriamo solo il totale scopato UOS (scope
            # operativo dell'operatore). Il totale regionale è volutamente
            # rimosso: rappresenta una popolazione diversa (tutta la regione,
            # non filtrata per UOS) e produceva confronti fuorvianti tra
            # numeratore scopato e denominatore non scopato.
            total_uos_str = f"{total_uos:,}".replace(",", ".")
            formatted = f"Per il piano **{piano_code.upper()}** sono stati inseriti:\n\n"
            if user_uos:
                formatted += f"🏥 **Nella tua UOS ({user_uos}):** {total_uos_str} controlli\n"
            else:
                formatted += f"📊 **Totale controlli eseguiti:** {total_uos_str}\n"
                formatted += "_⚠️ UOS utente non disponibile: conteggio non scopato._\n"

            if data_primo is not None and data_ultimo is not None and pd.notna(data_primo):
                formatted += f"\n📅 **Periodo:** dal {data_primo.strftime('%d/%m/%Y')} al {data_ultimo.strftime('%d/%m/%Y')}\n"

            formatted += f"\n📋 *{piano_desc}*"

            result = {
                "piano_code": piano_code.upper(),
                "total_controls": total_uos,
                "total_controls_regional": total_regional,
                "user_uos": user_uos,
                "data_primo_controllo": data_primo.isoformat() if data_primo is not None and pd.notna(data_primo) else None,
                "data_ultimo_controllo": data_ultimo.isoformat() if data_ultimo is not None and pd.notna(data_ultimo) else None,
                "formatted_response": formatted
            }

        # Pseudo-query riflette la query reale: filtro piano + UOS + anno.
        # Nota: usiamo alias_indicatore con pattern regex (non filtro semplice =)
        # perché DataRetriever.get_controlli_by_piano matcha sottopiani.
        uos_clause = f"descrizione_uos ILIKE '%{user_uos}%'" if user_uos else "-- UOS non disponibile, scope non applicato"
        pq = (
            "SELECT COUNT(*) AS total_controls,\n"
            "       MIN(data_inizio_controllo) AS periodo_start,\n"
            "       MAX(data_inizio_controllo) AS periodo_end\n"
            "FROM cu_eseguiti_nc\n"
            f"WHERE UPPER(alias_indicatore) ~ '^(ATT\\s+)?{piano_code.upper()}(_|\\s|$)'\n"
            f"  AND EXTRACT(YEAR FROM data_inizio_controllo) = <current_year>\n"
            f"  AND {uos_clause}"
        )
        state["tool_output"] = {"type": "piano_statistics", "data": result, "pseudo_query": pq}
        return state

    stats_func = _unwrap_tool(get_piano_statistics)
    result = stats_func(asl=asl, top_n=10)
    # Pseudo-query per statistiche aggregate (senza piano specifico): filtro ASL
    # ma NON UOS (query di overview, non scopata per operatore)
    pq = _pseudo_query(
        "cu_eseguiti_nc",
        "alias_indicatore, COUNT(*) AS num_controlli",
        {"descrizione_asl": asl},
        "GROUP BY alias_indicatore ORDER BY num_controlli DESC LIMIT 10",
    )
    state["tool_output"] = {"type": "piano_statistics", "data": result, "pseudo_query": pq}
    return state


def search_piani_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    topic = state["slots"].get("topic")
    sezione = state["slots"].get("sezione")
    result = search_tool(query=topic, sezione=sezione)

    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        matches = result.get("matches", [])
        if total_found > TWO_PHASE_THRESHOLDS.get("search_piani_by_topic", 5):
            search_term = result.get("search_term", topic or "")
            summary_text = ResponseFormatter.format_search_results_summary(
                search_term=search_term,
                matches=matches
            )
            # Genera risposta completa senza limiti per detail_context
            full_response = ResponseFormatter.format_search_results(
                search_term=search_term,
                matches=matches,
                max_display=None
            )
            result = apply_two_phase_check(
                state, "search_piani_by_topic", result, total_found, summary_text,
                full_formatted_response=full_response
            )

    where = {}
    if sezione:
        where["sezione"] = f"SEZIONE {sezione}"
    pq = _pseudo_query("piani_monitoraggio", "alias_piano_attivita, descrizione_piano_attivita, descrizione_indicatore",
        where, f"WHERE descrizione_piano_attivita ILIKE '%{topic}%' OR descrizione_indicatore ILIKE '%{topic}%'" if topic else "")
    state["tool_output"] = {"type": "search_piani", "data": result, "pseudo_query": pq}
    return state


# =============================================================================
# PRIORITY & RISK TOOLS
# =============================================================================

def priority_establishment_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id, get_uos_from_user_id

    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "priority_establishment_tool",
            "message": "Calcolando priorità controlli..."
        })

    asl = state["metadata"].get("asl")
    uoc = state["metadata"].get("uoc")
    uos = state["metadata"].get("uos")

    if not uoc and state["metadata"].get("user_id"):
        uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

    if not uos and state["metadata"].get("user_id"):
        uos = get_uos_from_user_id(state["metadata"].get("user_id"))

    piano_code = state["slots"].get("piano_code")
    slot_anno = state.get("slots", {}).get("anno")
    target_year = int(slot_anno) if slot_anno else None
    result = priority_tool(asl=asl, uoc=uoc, piano_code=piano_code, uos=uos, target_year=target_year)

    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        if total_found > TWO_PHASE_THRESHOLDS.get("ask_priority_establishment", 5):
            import pandas as pd
            summary_text = ResponseFormatter.format_priority_establishments_summary(result)
            # Genera risposta completa senza limiti per detail_context
            priority_data = result.get("priority_establishments", [])
            priority_df_full = pd.DataFrame(priority_data) if isinstance(priority_data, list) else priority_data
            full_response = ResponseFormatter.format_priority_establishments(
                user_asl=result.get("user_asl", result.get("asl", "N/D")),
                uoc_name=result.get("uoc_name", result.get("uoc", "N/D")),
                piano_id=result.get("piano_code"),
                delayed_count=result.get("delayed_plans_count", 0),
                total_found=total_found,
                priority_df_display=priority_df_full,
                max_display=None
            )
            result = apply_two_phase_check(
                state, "ask_priority_establishment", result, total_found, summary_text,
                full_formatted_response=full_response
            )

    pq = _pseudo_query("cu_diff_programmati_eseguiti JOIN osa_mai_controllati",
        "alias_indicatore, ritardo, ragione_sociale, comune",
        {"descrizione_asl": asl, "descrizione_uoc": uoc, "descrizione_uos": uos},
        "WHERE ritardo > 0 ORDER BY ritardo DESC")
    state["tool_output"] = {"type": "priority_establishment", "data": result, "pseudo_query": pq}
    return state


def risk_predictor_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    """Nodo risk predictor configurabile (ML o statistico).

    Gestisce disambiguazione tra:
    - mai_controllati: stabilimenti mai controllati (default)
    - con_sanzioni: stabilimenti con più NC storiche
    """
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "risk_predictor_tool",
            "message": "Analizzando rischio stabilimenti..."
        })

    asl = state["metadata"].get("asl")
    piano_code = state["slots"].get("piano_code")
    tipo_analisi = state["slots"].get("tipo_analisi_rischio")

    # Se tipo_analisi non specificato, chiedi disambiguazione
    if not tipo_analisi:
        disambiguation_response = (
            "**🎯 Stabilimenti a Rischio**\n\n"
            "Quale tipo di analisi preferisci?\n\n"
            "**1. Mai controllati** 🔍\n"
            "   Stabilimenti che non hanno mai ricevuto controlli,\n"
            "   ordinati per rischio dell'attività svolta\n\n"
            "**2. Con più sanzioni** ⚠️\n"
            "   Stabilimenti con più non conformità (NC) storiche\n"
            "   riportate nei controlli effettuati"
        )
        state["tool_output"] = {
            "type": "disambiguation",
            "data": {
                "formatted_response": disambiguation_response,
                "pending_intent": "ask_risk_based_priority",
                "options": ["mai_controllati", "con_sanzioni"]
            }
        }
        state["pending_question"] = True
        state["needs_clarification"] = True
        state["suggestions"] = [
            {"text": "🔍 Mai controllati", "query": "mai controllati"},
            {"text": "⚠️ Con più sanzioni", "query": "con sanzioni"},
        ]
        return state

    # Tipo analisi: con_sanzioni
    if tipo_analisi == "con_sanzioni":
        if event_callback:
            event_callback({
                "type": "reasoning",
                "node": "risk_predictor_tool",
                "message": "Cercando stabilimenti con più sanzioni..."
            })

        sanctions_func = _unwrap_tool(get_establishments_with_sanctions)
        result = sanctions_func(asl=asl, limit=20)
        output_type = "sanctions_analysis"

        if isinstance(result, dict):
            total = result.get("total", 0)
            if total > TWO_PHASE_THRESHOLDS.get("ask_risk_based_priority", 5):
                summary_text = (
                    f"Ho trovato **{total} stabilimenti** con non conformità "
                    f"per l'ASL **{asl or 'Regione'}**.\n\n"
                    "Vuoi vedere i dettagli dei top 10?"
                )
                result = apply_two_phase_check(
                    state, "ask_risk_based_priority", result, total, summary_text
                )

        state["tool_output"] = {"type": output_type, "data": result}
        return state

    # Tipo analisi: mai_controllati (default)
    predictor_type = RiskPredictorConfig.get_predictor_type()

    if predictor_type == "ml":
        ml_func = _unwrap_tool(get_ml_risk_prediction)
        result = ml_func(asl=asl, piano_code=piano_code)
        output_type = "ml_risk_prediction"
    else:
        result = risk_tool(asl=asl, piano_code=piano_code)
        output_type = "statistical_risk_prediction"

    if isinstance(result, dict):
        result["predictor_type"] = predictor_type

        total_risky = result.get("total_risky", 0)
        if total_risky > TWO_PHASE_THRESHOLDS.get("ask_risk_based_priority", 5):
            mapped_result = {
                "user_asl": result.get("asl", "N/D"),
                "piano_code": result.get("piano_code"),
                "osa_total_count": result.get("total_never_controlled", 0),
                "osa_risky_count": total_risky,
                "activities_count": result.get("activities_at_risk", 0),
                "osa_rischiosi": result.get("risky_establishments", []),
            }
            summary_text = ResponseFormatter.format_risk_based_priority_summary(mapped_result)
            # Genera risposta completa senza limiti per detail_context
            import pandas as pd
            risky_data = result.get("risky_establishments", [])
            risky_df = pd.DataFrame(risky_data) if isinstance(risky_data, list) else risky_data
            full_response = ResponseFormatter.format_risk_based_priority(
                user_asl=result.get("asl", "N/D"),
                piano_id=result.get("piano_code"),
                osa_total_count=result.get("total_never_controlled", 0),
                osa_risky_count=total_risky,
                activities_count=result.get("activities_at_risk", 0),
                osa_rischiosi=risky_df,
                max_display=None
            )
            result = apply_two_phase_check(
                state, "ask_risk_based_priority", result, total_risky, summary_text,
                full_formatted_response=full_response
            )

    # Pseudo-query: riflette il modello dati post-migrazione Hybrid (Fase 3).
    # Il risk score viene dalla view `v_risk_score_per_attivita` (vedi
    # sql/risk_score_view.sql) che pre-aggrega NC ed espone prob_nc, impatto,
    # punteggio_rischio_totale per (macroarea, aggregazione, linea_attivita).
    # Gli OSA mai controllati sono filtrati per ASL e congiunti alle attività
    # a rischio. Quando flag `repositories.risk = "pandas"` il calcolo è
    # equivalente in-memory su cu_eseguiti_nc, ma la forma dei dati è la stessa.
    pq = (
        "SELECT osa.ragione_sociale, osa.macroarea, osa.comune,\n"
        "       rsk.punteggio_rischio_totale, rsk.tot_nc_gravi, rsk.tot_nc_non_gravi\n"
        "FROM osa_mai_controllati AS osa\n"
        "INNER JOIN v_risk_score_per_attivita AS rsk\n"
        "  ON rsk.macroarea = osa.macroarea\n"
        " AND rsk.aggregazione = osa.aggregazione\n"
        " AND rsk.linea_attivita = osa.attivita\n"
        + (f"WHERE UPPER(osa.asl) = '{str(asl).upper()}'\n" if asl else "")
        + "ORDER BY rsk.punteggio_rischio_totale DESC"
    )
    state["tool_output"] = {"type": output_type, "data": result, "pseudo_query": pq}
    return state


def suggest_controls_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    asl = state["metadata"].get("asl")

    suggest_func = _unwrap_tool(suggest_controls)
    result = suggest_func(asl=asl, limit=20)

    if isinstance(result, dict):
        total_never_controlled = result.get("total_never_controlled", 0)
        if total_never_controlled > TWO_PHASE_THRESHOLDS.get("ask_suggest_controls", 5):
            import pandas as pd
            summary_text = ResponseFormatter.format_suggest_controls(
                asl=asl,
                filtered_count=total_never_controlled,
                sample_df=pd.DataFrame(result.get("suggested_establishments", [])[:5]),
                limit=5
            )
            result = apply_two_phase_check(
                state, "ask_suggest_controls", result, total_never_controlled, summary_text
            )

    pq = _pseudo_query("osa_mai_controllati", "ragione_sociale, macroarea, comune",
        {"asl": asl}, "LIMIT 20")
    state["tool_output"] = {"type": "suggest_controls", "data": result, "pseudo_query": pq}
    return state


def delayed_plans_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id, get_uos_from_user_id

    asl = state["metadata"].get("asl")
    uoc = state["metadata"].get("uoc")
    uos = state["metadata"].get("uos")

    if not uoc and state["metadata"].get("user_id"):
        uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

    if not uos and state["metadata"].get("user_id"):
        uos = get_uos_from_user_id(state["metadata"].get("user_id"))

    # Determina se l'utente chiede piani, attività o entrambi dal messaggio
    msg = (state.get("message") or "").lower()
    tipo = state.get("slots", {}).get("tipo")
    if not tipo:
        if "attivit" in msg and "pian" not in msg:
            tipo = "attivita"
        elif "pian" in msg and "attivit" not in msg:
            tipo = "piano"
        elif "attivit" in msg and "pian" in msg:
            tipo = "tutti"
        else:
            tipo = "piano"

    # Propaga slot anno dall'utente ai tool downstream
    slot_anno = state.get("slots", {}).get("anno")
    target_year = int(slot_anno) if slot_anno else None

    result = priority_tool(asl=asl, uoc=uoc, action="delayed_plans", uos=uos, tipo=tipo, target_year=target_year)
    pq = _build_delayed_pseudo_query(
        asl=asl, uoc=uoc, uos=uos, tipo=tipo, target_year=target_year
    )
    state["tool_output"] = {"type": "delayed_plans", "data": result, "pseudo_query": pq}
    return state


def check_plan_delayed_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    from agents.data import get_uoc_from_user_id, get_uos_from_user_id
    from tools.priority_tools import get_delayed_plans, get_programmed_controls_summary

    asl = state["metadata"].get("asl")
    uoc = state["metadata"].get("uoc")
    uos = state["metadata"].get("uos")
    piano_code = state["slots"].get("piano_code")
    message = (state.get("message") or "").lower()

    if not uoc and state["metadata"].get("user_id"):
        uoc = get_uoc_from_user_id(state["metadata"].get("user_id"))

    if not uos and state["metadata"].get("user_id"):
        uos = get_uos_from_user_id(state["metadata"].get("user_id"))

    slot_anno = state.get("slots", {}).get("anno")
    target_year = int(slot_anno) if slot_anno else None

    # Sub-flow "programmati": quando l'utente chiede esplicitamente i controlli
    # programmati per un piano specifico, rispondiamo con l'aggregato
    # SUM(programmati)/SUM(eseguiti) filtrato per ASL + UOS (scope utente),
    # senza richiedere la UOC. Replica la query di dominio su
    # cu_diff_programmati_eseguiti filtrando per alias_piano_attivita.
    import re as _re
    is_programmati_query = bool(_re.search(r"\bprogramm(?:at[oiae]|azione)\b", message))
    if is_programmati_query and piano_code:
        result = get_programmed_controls_summary(
            piano_code=piano_code, asl=asl, uos=uos, target_year=target_year
        )
        pq = _pseudo_query(
            "cu_diff_programmati_eseguiti",
            "SUM(programmati), SUM(eseguiti)",
            {
                "anno": result.get("anno"),
                "alias_piano_attivita": piano_code,
                "descrizione_asl": f"ILIKE '%{asl}%'" if asl else None,
                "descrizione_uos": f"ILIKE '%{uos}%'" if uos else None,
            },
        )
        state["tool_output"] = {
            "type": "piano_programmati",
            "data": result,
            "pseudo_query": pq,
        }
        return state

    delayed_func = _unwrap_tool(get_delayed_plans)
    result = delayed_func(asl=asl, uoc=uoc, piano_code=piano_code, uos=uos, target_year=target_year)
    pq = _build_delayed_pseudo_query(
        asl=asl, uoc=uoc, uos=uos, tipo=None, target_year=target_year, piano_code=piano_code
    )
    state["tool_output"] = {"type": "check_plan_delayed", "data": result, "pseudo_query": pq}
    return state


def establishment_history_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    num_registrazione = state["slots"].get("num_registrazione")
    numero_riconoscimento = state["slots"].get("numero_riconoscimento")
    partita_iva = state["slots"].get("partita_iva")
    ragione_sociale = state["slots"].get("ragione_sociale")

    history_func = _unwrap_tool(get_establishment_history)
    result = history_func(
        num_registrazione=num_registrazione,
        numero_riconoscimento=numero_riconoscimento,
        partita_iva=partita_iva,
        ragione_sociale=ragione_sociale
    )

    if isinstance(result, dict):
        total_controls = result.get("total_controls", 0)
        if total_controls > TWO_PHASE_THRESHOLDS.get("ask_establishment_history", 5):
            summary_text = ResponseFormatter.format_establishment_history_summary(result)
            # Genera risposta completa senza limiti per detail_context
            import pandas as pd
            history_data = result.get("history", [])
            history_df = pd.DataFrame(history_data) if isinstance(history_data, list) else history_data
            full_response = ResponseFormatter.format_establishment_history(
                history_df=history_df,
                num_registrazione=num_registrazione,
                numero_riconoscimento=numero_riconoscimento,
                partita_iva=partita_iva,
                ragione_sociale=ragione_sociale,
                max_display=None
            )
            result = apply_two_phase_check(
                state, "ask_establishment_history", result, total_controls, summary_text,
                full_formatted_response=full_response
            )

    where = {}
    if num_registrazione: where["num_registrazione"] = num_registrazione
    if numero_riconoscimento: where["num_riconoscimento"] = numero_riconoscimento
    if partita_iva: where["partita_iva"] = partita_iva
    if ragione_sociale: where["ragione_sociale"] = f"ILIKE '%{ragione_sociale}%'"
    pq = _pseudo_query("cu_eseguiti_nc", "data_inizio_controllo, descrizione_piano, alias_indicatore, tipo_non_conformita",
        where, "ORDER BY data_inizio_controllo DESC")
    state["tool_output"] = {"type": "establishment_history", "data": result, "pseudo_query": pq}
    return state


def top_risk_activities_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    limit = state["slots"].get("limit", 10)

    top_risk_func = _unwrap_tool(get_top_risk_activities)
    result = top_risk_func(limit=limit)

    pq = _pseudo_query("cu_eseguiti_nc", "attivita_cu, COUNT(*) AS controlli, SUM(numero_nc_gravi + numero_nc_non_gravi) AS nc_totali",
        {}, f"GROUP BY attivita_cu ORDER BY nc_totali DESC LIMIT {limit}")
    state["tool_output"] = {"type": "top_risk_activities", "data": result, "pseudo_query": pq}
    return state


def info_procedure_tool(state: Dict[str, Any], **_) -> Dict[str, Any]:
    """RAG tool per informazioni su procedure operative documentate."""
    query = state.get("message", "")

    # Contesto conversazionale dalla sessione
    conversation_context = ""
    session_summary = state.get("metadata", {}).get("_session_summary", "")
    if session_summary:
        conversation_context = session_summary

    from tools.procedure_tools import get_procedure_info
    func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
    result = func(query=query, conversation_context=conversation_context)

    state["tool_output"] = {"type": "info_procedure", "data": result}
    return state


def query_data_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    """Tool per interrogazioni dati su misura non coperte dagli intent specifici."""
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "query_data_tool",
            "message": "Analizzando la richiesta dati..."
        })

    message = state.get("message", "")
    metadata = state.get("metadata", {})

    # Percorso specializzato: "stabilimenti più controllati nelle vicinanze"
    import re as _re
    if _re.search(r'\bpi[uù]\s+controllat[ie]\b', message, _re.IGNORECASE):
        try:
            from tools.query_builder_tools import query_most_controlled_nearby
            result = query_most_controlled_nearby(
                asl=metadata.get("asl"),
                device_lat=metadata.get("latitude"),
                device_lon=metadata.get("longitude"),
                radius_km=float(state.get("slots", {}).get("radius_km", 10)),
            )
            if not result.get("error"):
                state["tool_output"] = result
                return state
            # Se la funzione specializzata fallisce, prosegui col flusso generico
        except Exception as e:
            logger.warning(f"[QueryData] Nearby most-controlled fallback: {e}")

    try:
        from tools.query_builder_tools import build_query_with_llm, SafeQueryExecutor
        from llm.client import LLMClient

        # 1. LLM genera Operation Descriptor (con contesto utente per filtri impliciti)
        llm_client = LLMClient()
        user_context = ""
        asl = state.get("metadata", {}).get("asl")
        if asl:
            user_context = f"\nCONTESTO UTENTE: ASL={asl}"
        descriptor = build_query_with_llm(message, llm_client, user_context=user_context)
        if descriptor:
            logger.info(f"[QueryData] Descriptor LLM: table={descriptor.table}, op={descriptor.operation}, "
                        f"filters={[f'{f.column} {f.op} {f.value}' for f in descriptor.filters]}, "
                        f"group_by={descriptor.group_by}")

        if descriptor is None:
            state["tool_output"] = {
                "type": "query_data",
                "data": {
                    "error": True,
                    "formatted_response": (
                        "Non sono riuscito a interpretare la tua richiesta come interrogazione dati.\n\n"
                        "Prova a riformulare specificando:\n"
                        "- **Quale tabella** vuoi interrogare (controlli, piani, stabilimenti)\n"
                        "- **Quale operazione** (conteggio, distribuzione, top N)\n"
                        "- **Eventuali filtri** (ASL, anno, macroarea)"
                    )
                }
            }
            return state

        # 2. Esegui query sicura
        executor = SafeQueryExecutor()
        result = executor.execute(descriptor)

        if result.get("error"):
            state["tool_output"] = {
                "type": "query_data",
                "data": {
                    "error": True,
                    "formatted_response": f"Errore nell'interrogazione: {result['error']}"
                }
            }
            return state

        # 3. Formatta risultato
        data_records = result.get("data", [])
        total = result.get("total", 0)
        showing = result.get("showing", total)

        pseudo_query = _query_descriptor_to_pseudo_sql(descriptor)

        # Se nessun risultato, mostra messaggio con diagnostica
        if not data_records and result.get("message"):
            state["tool_output"] = {
                "type": "query_data",
                "data": {
                    "formatted_response": result["message"],
                    "query_descriptor": descriptor.model_dump(),
                },
                "pseudo_query": pseudo_query,
            }
            return state

        # Formatta come tabella markdown
        formatted = _format_query_data_response(
            descriptor.table, descriptor.operation, data_records, total, showing
        )

        logger.info(f"[QueryData] Risultato: {len(data_records)} record, total={total}")

        state["tool_output"] = {
            "type": "query_data",
            "data": {
                "query_descriptor": descriptor.model_dump(),
                "records": data_records[:20],  # max 20 nel payload
                "total": total,
                "formatted_response": formatted
            },
            "pseudo_query": pseudo_query,
        }

    except Exception as e:
        logger.error(f"[QueryData] Errore: {e}")
        state["tool_output"] = {
            "type": "query_data",
            "data": {
                "error": True,
                "formatted_response": f"Errore nell'elaborazione della query: {str(e)}"
            }
        }

    return state


def _format_query_data_response(table: str, operation: str, records: list, total: int, showing: int) -> str:
    """Formatta i risultati della query in markdown leggibile."""
    if not records:
        return "Nessun risultato trovato per la query specificata."

    lines = [f"**Risultati interrogazione** ({operation} su `{table}`):\n"]

    if operation == "count":
        count = records[0].get("count", 0)
        lines.append(f"📊 **Totale:** {count:,} record\n")

    elif operation in ("group_count", "sum", "mean", "top_n", "filter"):
        # Genera tabella markdown
        if records:
            cols = list(records[0].keys())
            # Header
            lines.append("| " + " | ".join(str(c) for c in cols) + " |")
            lines.append("| " + " | ".join("---" for _ in cols) + " |")
            # Righe
            for r in records[:20]:
                values = []
                for c in cols:
                    v = r.get(c, "")
                    if isinstance(v, float):
                        v = f"{v:,.2f}"
                    elif isinstance(v, int):
                        v = f"{v:,}"
                    values.append(str(v))
                lines.append("| " + " | ".join(values) + " |")

        if showing and showing < total:
            lines.append(f"\n*Mostrati {showing} di {total:,} risultati totali*")

    elif operation == "distinct":
        if records and "values" in records[0]:
            col = records[0].get("column", "")
            values = records[0].get("values", [])
            total_distinct = records[0].get("total_distinct", len(values))
            lines.append(f"📋 **Valori unici** di `{col}` ({total_distinct} totali):\n")
            for v in values[:30]:
                lines.append(f"- {v}")

    return "\n".join(lines)


def nearby_priority_tool(state: Dict[str, Any], event_callback=None, **_) -> Dict[str, Any]:
    """Tool per ricerca stabilimenti per prossimità geografica."""
    if event_callback:
        event_callback({
            "type": "reasoning",
            "node": "nearby_priority_tool",
            "message": "Geocodificando indirizzo e cercando stabilimenti vicini..."
        })

    location = state["slots"].get("location")
    radius_km = state["slots"].get("radius_km", 5.0)
    asl = state["metadata"].get("asl")

    # REQ: [GP-13] Use device GPS coordinates if available
    device_lat = state["metadata"].get("latitude")
    device_lon = state["metadata"].get("longitude")

    nearby_func = _unwrap_tool(get_nearby_priority)
    result = nearby_func(
        location=location, radius_km=radius_km, asl=asl,
        device_lat=device_lat, device_lon=device_lon
    )

    # Two-phase check se troppi risultati
    if isinstance(result, dict):
        total_found = result.get("total_found", 0)
        if total_found > TWO_PHASE_THRESHOLDS.get("ask_nearby_priority", 10):
            summary_text = ResponseFormatter.format_nearby_priority_summary(result)
            # Genera risposta completa senza limiti per detail_context
            import pandas as pd
            nearby_data = result.get("nearby_establishments", [])
            nearby_df = pd.DataFrame(nearby_data) if isinstance(nearby_data, list) else nearby_data
            full_response = ResponseFormatter.format_nearby_priority(
                location=result.get("location", "N/D"),
                center_coords=result.get("center_coords", (0, 0)),
                radius_km=result.get("radius_km", 5.0),
                nearby_df=nearby_df,
                total_found=total_found
            )
            result = apply_two_phase_check(
                state, "ask_nearby_priority", result, total_found, summary_text,
                full_formatted_response=full_response
            )

    state["tool_output"] = {"type": "nearby_priority", "data": result}
    return state


# =============================================================================
# TOOL REGISTRY: mappa nome nodo → funzione
# =============================================================================

TOOL_REGISTRY = {
    "greet_tool": greet_tool,
    "goodbye_tool": goodbye_tool,
    "help_tool": help_tool,
    "piano_description_tool": piano_description_tool,
    "piano_stabilimenti_tool": piano_stabilimenti_tool,
    "piano_statistics_tool": piano_statistics_tool,
    "search_piani_tool": search_piani_tool,
    "priority_establishment_tool": priority_establishment_tool,
    "risk_predictor_tool": risk_predictor_tool,
    "suggest_controls_tool": suggest_controls_tool,
    "nearby_priority_tool": nearby_priority_tool,
    "delayed_plans_tool": delayed_plans_tool,
    "check_plan_delayed_tool": check_plan_delayed_tool,
    "establishment_history_tool": establishment_history_tool,
    "top_risk_activities_tool": top_risk_activities_tool,
    "info_procedure_tool": info_procedure_tool,
    "query_data_tool": query_data_tool,
    "confirm_details_tool": confirm_details_tool,
    "decline_details_tool": decline_details_tool,
}

# Mapping intent → nome nodo tool (caricato da DB via IntentMetadataService)
def _get_intent_to_tool() -> dict:
    try:
        from .intent_metadata_service import get_intent_metadata_service
        return get_intent_metadata_service().get_intent_to_tool()
    except Exception:
        # Fallback hardcoded se DB non disponibile
        return {
            "greet": "greet_tool", "goodbye": "goodbye_tool", "ask_help": "help_tool",
            "ask_piano_description": "piano_description_tool",
            "ask_piano_stabilimenti": "piano_stabilimenti_tool",
            "ask_piano_statistics": "piano_statistics_tool",
            "search_piani_by_topic": "search_piani_tool",
            "ask_priority_establishment": "priority_establishment_tool",
            "ask_risk_based_priority": "risk_predictor_tool",
            "ask_suggest_controls": "suggest_controls_tool",
            "ask_nearby_priority": "nearby_priority_tool",
            "ask_delayed_plans": "delayed_plans_tool",
            "check_if_plan_delayed": "check_plan_delayed_tool",
            "ask_establishment_history": "establishment_history_tool",
            "ask_top_risk_activities": "top_risk_activities_tool",
            "info_procedure": "info_procedure_tool",
            "query_data": "query_data_tool",
            "confirm_show_details": "confirm_details_tool",
            "decline_show_details": "decline_details_tool",
        }

INTENT_TO_TOOL = None

def get_intent_to_tool_map() -> dict:
    """Accessor lazy per INTENT_TO_TOOL."""
    global INTENT_TO_TOOL
    if INTENT_TO_TOOL is None:
        INTENT_TO_TOOL = _get_intent_to_tool()
    return INTENT_TO_TOOL
