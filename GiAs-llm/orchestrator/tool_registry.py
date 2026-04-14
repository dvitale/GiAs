# pyright: reportAttributeAccessIssue=false, reportCallIssue=false
"""
Tool registry per l'agente ReAct.

Espone `build_agent_tools(metadata)` che ritorna una lista di tool LangChain
con metadata utente (ASL, UOS) iniettati via closure. L'LLM vede solo i
parametri che deve effettivamente scegliere (piano_code, anno, ecc.); asl e
user_uos non fanno parte dello schema esposto, quindi l'LLM non puo'
inventarli o chiederli all'utente.

La stessa funzione popola il `DetailStore` (dict in-memory per sessione)
quando un tool restituisce un `detail_formatted` oltre al `formatted_response`
sommario. Il two-phase diventa cosi' un tool esplicito
`mostra_dettagli_completi(context_id)` che l'agente puo' invocare in
risposta a richieste come "fammi vedere tutti", "dettagli", ecc.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from tools._tool_compat import tool, unwrap_tool

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Detail store: popolato dai tool, consumato da `mostra_dettagli_completi`.
# Una istanza per request (viene passata a build_agent_tools).
# ----------------------------------------------------------------------


class DetailStore:
    """In-memory store dei detail_formatted per l'handoff two-phase."""

    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}

    def put(self, payload: Dict[str, Any]) -> str:
        cid = uuid.uuid4().hex[:12]
        self._items[cid] = payload
        return cid

    def get(self, cid: str) -> Optional[Dict[str, Any]]:
        return self._items.get(cid)

    def last(self) -> Optional[Dict[str, Any]]:
        if not self._items:
            return None
        # ultimo inserito
        return next(reversed(self._items.values()))


# ----------------------------------------------------------------------
# Helpers: risoluzione UOS dallo user_id se non presente in metadata.
# ----------------------------------------------------------------------


def _resolve_uos(metadata: Dict[str, Any]) -> Optional[str]:
    user_uos = metadata.get("uos")
    if user_uos:
        return user_uos
    user_id = metadata.get("user_id")
    if not user_id:
        return None
    try:
        from agents.data import get_uos_from_user_id  # type: ignore
        return get_uos_from_user_id(user_id)
    except Exception:
        return None


def _normalize_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# Builder principale
# ----------------------------------------------------------------------


def build_agent_tools(
    metadata: Dict[str, Any],
    detail_store: Optional[DetailStore] = None,
) -> List[Any]:
    """Costruisce i tool per l'agente ReAct con metadata iniettato.

    Args:
        metadata: session metadata (asl, user_id, uos, uoc, ...)
        detail_store: store per il pattern two-phase. Se None, ne crea uno
            locale (ma il chiamante dovrebbe fornirlo per riusarlo tra turni).

    Returns:
        Lista di BaseTool LangChain pronti per `create_react_agent`.
    """
    user_asl = metadata.get("asl")
    user_uoc = metadata.get("uoc")
    user_uos = _resolve_uos(metadata)
    store = detail_store if detail_store is not None else DetailStore()

    # Anno corrente da config.json (default per i tool che filtrano per anno).
    try:
        from configs.config_loader import get_config  # type: ignore
        _default_anno = get_config().get_current_year()
    except Exception:
        from datetime import datetime as _dt
        _default_anno = _dt.now().year

    # ------------------------------------------------------------------
    # 1) statistiche_controlli — conteggio CU eseguiti o programmati
    # ------------------------------------------------------------------
    _stat_desc = (
        f"Conteggio aggregato di controlli ufficiali (CU) eseguiti o programmati. "
        f"Usare quando l'utente chiede 'quanti controlli', 'statistiche controlli', "
        f"'lista dei controlli', 'controlli eseguiti', 'controlli programmati', "
        f"anche filtrati per piano, anno o macroarea. "
        f"IMPORTANTE: NON chiedere mai l'anno all'utente. Se non lo specifica, "
        f"lascia `anno` a None: il tool applica automaticamente l'anno corrente "
        f"({_default_anno}) come default. Passa `anno` SOLO se l'utente ha indicato "
        f"esplicitamente un anno diverso. "
        f"Args: piano_code (es. 'A9_A', 'AO1', opzionale), anno (default {_default_anno}), "
        f"macroarea (opzionale), tipo_conteggio ('eseguiti' default o 'programmati')."
    )

    @tool("statistiche_controlli", description=_stat_desc)
    def statistiche_controlli(
        piano_code: Optional[str] = None,
        anno: Optional[int] = None,
        macroarea: Optional[str] = None,
        tipo_conteggio: str = "eseguiti",
    ) -> Dict[str, Any]:
        """Conteggio CU eseguiti/programmati."""
        from tools.cu_statistics_tools import get_cu_statistics
        result = get_cu_statistics(
            piano_code=piano_code,
            anno=_normalize_int(anno) or _default_anno,
            asl=user_asl,
            macroarea=macroarea,
            user_uos=user_uos,
            tipo_conteggio=tipo_conteggio,
        )
        # two-phase: se il tool ha prodotto un detail_formatted, memorizzalo
        detail = result.pop("detail_formatted", None)
        if detail:
            cid = store.put({"formatted_response": detail, "type": "cu_statistics_detail"})
            result["__detail_context_id"] = cid
            summary = result.get("formatted_response", "")
            if summary and cid:
                result["formatted_response"] = (
                    f"{summary}\n\n"
                    f"Se vuoi l'elenco completo, chiama `mostra_dettagli_completi` con context_id=\"{cid}\"."
                )
        return result

    # ------------------------------------------------------------------
    # 2) descrizione_piano — metadati di un piano specifico
    # ------------------------------------------------------------------
    @tool("descrizione_piano")
    def descrizione_piano(piano_code: str) -> Dict[str, Any]:
        """Restituisce descrizione, categoria e metadati di un piano di controllo.

        Args:
            piano_code: codice piano (es. "A1", "A9_A", "AO1").
        """
        from tools.piano_tools import get_piano_description
        return unwrap_tool(get_piano_description)(piano_code=piano_code)

    # ------------------------------------------------------------------
    # 3) piani_in_ritardo — piani con ritardo programmati-eseguiti
    # ------------------------------------------------------------------
    _delayed_desc = (
        f"Elenco di piani/indicatori/attivita' con ritardo tra controlli "
        f"programmati ed eseguiti. NOTA DOMINIO: nel linguaggio GIAS, "
        f"'indicatore' e 'sotto-piano' sono sinonimi di una sotto-voce del "
        f"piano di controllo (alias_indicatore). Usare questo tool quando "
        f"l'utente chiede 'piani in ritardo', 'indicatori in ritardo', "
        f"'sotto-piani in ritardo', 'attivita in ritardo', 'cosa e in "
        f"ritardo', SENZA chiedere 'di quale piano' se la query e' generica: "
        f"il tool di default analizza tutti i piani/indicatori della UOC "
        f"dell'utente. Chiedi solo se l'utente cita un piano specifico "
        f"(es. 'il piano A1 e in ritardo?'). "
        f"Parametri: `tipo` accetta 'piano' (solo piani macro), 'attivita' "
        f"(solo indicatori/sotto-piani) o 'tutti' (default None = tutti). "
        f"NON chiedere mai l'anno: se non specificato viene usato l'anno "
        f"corrente ({_default_anno}). "
        f"Args: anno (default {_default_anno}), piano_code (opzionale), "
        f"tipo (None/'piano'/'attivita'/'tutti')."
    )

    @tool("piani_in_ritardo", description=_delayed_desc)
    def piani_in_ritardo(
        anno: Optional[int] = None,
        piano_code: Optional[str] = None,
        tipo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Piani in ritardo."""
        from tools.priority_tools import get_delayed_plans
        return unwrap_tool(get_delayed_plans)(
            asl=user_asl,
            uoc=user_uoc,
            uos=user_uos,
            piano_code=piano_code,
            tipo=tipo,
            target_year=_normalize_int(anno) or _default_anno,
        )

    # ------------------------------------------------------------------
    # 4) priorita_ispezione_rischio — stabilimenti prioritari per rischio
    # ------------------------------------------------------------------
    _prio_desc = (
        "Classifica degli STABILIMENTI/OSA singoli da ispezionare prima, "
        "ordinati per probabilita' di NC (predittore ML o statistico). "
        "Granularita': singolo stabilimento/azienda (NON piano/attivita'). "
        "Usa questo tool quando l'utente chiede STABILIMENTI/OSA/AZIENDE/"
        "PRIORITA di ispezione: 'quali stabilimenti ispezionare prima', "
        "'OSA a rischio', 'priorita ispettiva'. "
        "Se l'utente parla di PIANI/ATTIVITA/LINEE a rischio usa invece "
        "`piani_attivita_piu_rischiosi`. "
        "Args: piano_code (opzionale, filtra su un singolo piano)."
    )

    @tool("priorita_ispezione_rischio", description=_prio_desc)
    def priorita_ispezione_rischio(piano_code: Optional[str] = None) -> Dict[str, Any]:
        """Stabilimenti prioritari per rischio."""
        from tools.risk_tools import get_risk_based_priority
        return unwrap_tool(get_risk_based_priority)(
            asl=user_asl,
            piano_code=piano_code,
        )

    # ------------------------------------------------------------------
    # 3b) indicatori_non_completati — programmati > eseguiti (definizione
    #     letterale, NON pro-rata temporis)
    # ------------------------------------------------------------------
    _incompleti_desc = (
        "Elenco di piani/indicatori con avanzamento incompleto: "
        "`programmati > 0 AND eseguiti < programmati`. Definizione "
        "LETTERALE, indipendente dal periodo dell'anno. "
        "Differenza con `piani_in_ritardo`: quest'ultimo usa una definizione "
        "PRO-RATA TEMPORIS (attesi = programmati x frazione_anno_trascorsa) "
        "che a inizio anno considera 'in pari' anche indicatori con "
        "eseguiti=0. Usa `indicatori_non_completati` quando l'utente vuole "
        "vedere TUTTI gli indicatori dove eseguiti < programmati, compresi "
        "quelli con eseguiti=0, indipendentemente dalla frazione d'anno. "
        "Trigger tipici: 'indicatori non completati', 'piani non completati', "
        "'dove eseguiti e minore di programmati', 'indicatori con 0 eseguiti', "
        "'indicatori ancora da fare'. "
        "Filtra di default sulla UOC/UOS dell'utente (iniettate). "
        f"Args: anno (default {_default_anno}), piano_code (opzionale), "
        "tipo (None/'piano'/'attivita'/'tutti', default 'tutti'), "
        "limit (default 30)."
    )

    @tool("indicatori_non_completati", description=_incompleti_desc)
    def indicatori_non_completati(
        anno: Optional[int] = None,
        piano_code: Optional[str] = None,
        tipo: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """Indicatori con eseguiti < programmati (letterale)."""
        from agents.data import diff_prog_eseg_df
        if diff_prog_eseg_df is None or diff_prog_eseg_df.empty:
            return {"formatted_response": "Dati programmazione non disponibili."}

        df = diff_prog_eseg_df
        effective_anno = _normalize_int(anno) or _default_anno
        if "anno" in df.columns:
            df = df[df["anno"] == effective_anno]

        # Scope: UOC dell'utente (obbligatorio nel tool legacy) + UOS se presente
        if user_uoc and "descrizione_uoc" in df.columns:
            df = df[df["descrizione_uoc"].astype(str).str.upper() == user_uoc.upper()]
        if user_uos and "descrizione_uos" in df.columns:
            df = df[df["descrizione_uos"].astype(str).str.upper() == user_uos.upper()]

        if df.empty:
            return {
                "formatted_response": (
                    f"Nessun dato di programmazione trovato per l'anno "
                    f"{effective_anno} nella tua struttura."
                )
            }

        prog = df["programmati"].fillna(0)
        eseg = df["eseguiti"].fillna(0)
        df = df.assign(
            programmati=prog.astype(int),
            eseguiti=eseg.astype(int),
            mancanti=(prog - eseg).clip(lower=0).astype(int),
        )

        # Filtro letterale
        df = df[(df["programmati"] > 0) & (df["eseguiti"] < df["programmati"])]

        # Filtro tipo piano vs attivita (convenzione prefisso ATT)
        if "alias_indicatore" in df.columns and tipo and tipo != "tutti":
            upper = df["alias_indicatore"].astype(str).str.upper()
            is_att = upper.str.startswith("ATT ") | upper.str.startswith("ATT_")
            df = df[is_att] if tipo == "attivita" else df[~is_att]

        if piano_code:
            pc = piano_code.upper()
            df = df[
                df["alias_indicatore"].astype(str).str.upper().str.startswith(pc)
            ]

        if df.empty:
            return {
                "formatted_response": (
                    f"Non ho trovato indicatori non completati (eseguiti < "
                    f"programmati) per l'anno {effective_anno} nella tua "
                    f"struttura con i filtri richiesti."
                )
            }

        # Aggrega su (alias_piano_attivita, alias_indicatore, descrizioni)
        group_cols = [
            "alias_piano_attivita", "alias_indicatore",
            "descrizione_piano", "descrizione_indicatore",
        ]
        agg = (
            df.groupby(group_cols, dropna=False)
            .agg({"programmati": "sum", "eseguiti": "sum", "mancanti": "sum"})
            .reset_index()
            .sort_values("mancanti", ascending=False)
            .head(limit)
        )
        records = agg.to_dict("records")

        lines = [
            f"### Indicatori non completati (anno {effective_anno})",
            "",
            f"Definizione: `eseguiti < programmati`. Top {len(records)} "
            f"ordinati per controlli mancanti:",
            "",
        ]
        for i, r in enumerate(records, 1):
            piano = r.get("alias_piano_attivita") or "—"
            indic = r.get("alias_indicatore") or "—"
            prog_v = int(r.get("programmati", 0))
            eseg_v = int(r.get("eseguiti", 0))
            manc = int(r.get("mancanti", 0))
            desc = r.get("descrizione_indicatore") or ""
            lines.append(
                f"**{i}. {piano} · {indic}** — {eseg_v}/{prog_v} eseguiti "
                f"(**{manc} mancanti**)"
            )
            if desc:
                lines.append(f"   _{desc}_")
        lines.append("")
        lines.append(
            f"Fonte: `cu_diff_programmati_eseguiti` anno {effective_anno}, "
            f"filtro letterale `eseguiti < programmati`."
        )

        return {
            "formatted_response": "\n".join(lines),
            "total": int(len(agg)),
            "anno": effective_anno,
            "data": records,
        }

    # ------------------------------------------------------------------
    # 4b) piani_attivita_piu_rischiosi — top N attivita per risk score
    # ------------------------------------------------------------------
    _top_risk_desc = (
        "Top N linee di attivita'/piani con il risk score piu' alto, "
        "ordinate per probabilita' di non conformita' (NC) storica. "
        "Granularita': PIANO/ATTIVITA' (NON stabilimento). Usa questo tool "
        "quando l'utente chiede, riferendosi a PIANI/ATTIVITA'/LINEE/TIPOLOGIE "
        "(NON a singoli stabilimenti): "
        "'piani/attivita piu rischiosi', 'motivi di ispezione piu rischiosi', "
        "'piani che generano piu NC', 'piani con piu non conformita', "
        "'tipologie di controllo piu problematiche', 'attivita con piu violazioni', "
        "'linee di attivita a maggior rischio', 'ranking rischio piani'. "
        "IMPORTANTE: se l'utente chiede STABILIMENTI/OSA singoli da ispezionare "
        "prima, NON usare questo tool ma `priorita_ispezione_rischio`. "
        "Args: limit (default 10)."
    )

    @tool("piani_attivita_piu_rischiosi", description=_top_risk_desc)
    def piani_attivita_piu_rischiosi(limit: int = 10) -> Dict[str, Any]:
        """Top attivita/piani per risk score."""
        from tools.risk_analysis_tools import get_top_risk_activities
        return unwrap_tool(get_top_risk_activities)(limit=limit)

    # ------------------------------------------------------------------
    # 4c) top_piani_per_nc — classifica piani/indicatori per conteggio NC
    # ------------------------------------------------------------------
    _nc_desc = (
        "Classifica di PIANI e INDICATORI (alias_piano_attivita, alias_indicatore) "
        "ordinati per numero TOTALE di Non Conformita' (NC) GRAVI rilevate dai "
        "controlli ufficiali eseguiti. Conteggio GREZZO, non risk score. "
        "Usare quando l'utente chiede 'piani/attivita che generano piu NC', "
        "'piani con piu non conformita', 'indicatori con piu NC', 'classifica NC "
        "per piano', 'dove si rilevano piu NC'. Filtra automaticamente l'anno "
        f"corrente ({_default_anno}) se non specificato. "
        "Differenze con gli altri tool: "
        "- `piani_attivita_piu_rischiosi` usa Risk Score (tasso probabilistico), "
        "  questo tool usa CONTEGGIO ASSOLUTO di NC gravi. "
        "- `priorita_ispezione_rischio` ritorna STABILIMENTI, questo PIANI. "
        f"Args: anno (default {_default_anno}), tipo_nc ('gravi' default o 'non_gravi' o 'tutte'), limit (default 20)."
    )

    @tool("top_piani_per_nc", description=_nc_desc)
    def top_piani_per_nc(
        anno: Optional[int] = None,
        tipo_nc: str = "gravi",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Top piani/indicatori per conteggio NC."""
        from agents.data import controlli_df
        if controlli_df is None or controlli_df.empty:
            return {"formatted_response": "Dati controlli non disponibili."}

        df = controlli_df
        effective_anno = _normalize_int(anno) or _default_anno
        try:
            anni = df["data_inizio_controllo"].dt.year
            df = df[anni == effective_anno]
        except Exception:
            pass

        if tipo_nc == "non_gravi":
            nc_col = "numero_nc_non_gravi"
            label_nc = "NC non gravi"
        elif tipo_nc == "tutte":
            df = df.assign(_nc_totali=df["numero_nc_gravi"].fillna(0) + df["numero_nc_non_gravi"].fillna(0))
            nc_col = "_nc_totali"
            label_nc = "NC totali"
        else:
            nc_col = "numero_nc_gravi"
            label_nc = "NC gravi"

        filtered = df[df[nc_col] > 0]
        if filtered.empty:
            return {
                "formatted_response": f"Nessun controllo con {label_nc} trovato per l'anno {effective_anno}."
            }

        group_cols = ["alias_piano_attivita", "alias_indicatore",
                      "descrizione_piano", "descrizione_indicatore"]
        grouped = (
            filtered.groupby(group_cols, dropna=False)[nc_col]
            .sum()
            .reset_index()
            .rename(columns={nc_col: "totale_nc"})
            .sort_values("totale_nc", ascending=False)
            .head(limit)
        )

        records = grouped.to_dict("records")

        # Formatta risposta markdown
        lines = [
            f"### Piani/attivita' con piu' {label_nc} (anno {effective_anno})",
            "",
            f"Top {len(records)} combinazioni piano+indicatore ordinate per totale NC rilevate:",
            "",
        ]
        for i, row in enumerate(records, 1):
            piano = row.get("alias_piano_attivita") or "—"
            indic = row.get("alias_indicatore") or "—"
            desc_piano = row.get("descrizione_piano") or ""
            desc_indic = row.get("descrizione_indicatore") or ""
            nc = int(row.get("totale_nc", 0))
            lines.append(f"**{i}. {piano} · {indic}** — {nc} {label_nc}")
            if desc_piano or desc_indic:
                lines.append(f"   _{desc_piano} · {desc_indic}_")
        lines.append("")
        lines.append(f"Fonte: `cu_eseguiti_nc` filtrata anno {effective_anno}, "
                     f"aggregazione per (piano, indicatore), ordine decrescente.")

        return {
            "formatted_response": "\n".join(lines),
            "total_groups": int(len(grouped)),
            "anno": effective_anno,
            "tipo_nc": tipo_nc,
            "data": records,
        }

    # ------------------------------------------------------------------
    # 4d) storico_stabilimento — controlli + NC di un singolo OSA
    # ------------------------------------------------------------------
    @tool("storico_stabilimento")
    def storico_stabilimento(
        num_registrazione: Optional[str] = None,
        numero_riconoscimento: Optional[str] = None,
        partita_iva: Optional[str] = None,
        ragione_sociale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Storico controlli ufficiali e non conformita' di un singolo stabilimento/OSA.

        Usare quando l'utente fornisce un identificativo di stabilimento
        (codice identificativo tipo "U150058BN000649", numero registrazione,
        riconoscimento UE, partita IVA, ragione sociale) e chiede "storico",
        "cronologia controlli", "precedenti ispezioni", "NC passate".
        Almeno UNO dei parametri va valorizzato.

        Args:
            num_registrazione: numero registrazione stabilimento (anche codici
                alfanumerici tipo "U150058BN000649", "IT 123", "UE IT 2287 M").
            numero_riconoscimento: numero riconoscimento UE.
            partita_iva: partita IVA (solo cifre).
            ragione_sociale: parte della ragione sociale (match parziale).
        """
        from tools.establishment_tools import get_establishment_history
        return unwrap_tool(get_establishment_history)(
            num_registrazione=num_registrazione,
            numero_riconoscimento=numero_riconoscimento,
            partita_iva=partita_iva,
            ragione_sociale=ragione_sociale,
        )

    # ------------------------------------------------------------------
    # 5) cerca_piani — ricerca per topic/parole chiave
    # ------------------------------------------------------------------
    @tool("cerca_piani")
    def cerca_piani(query: str, sezione: Optional[str] = None) -> Dict[str, Any]:
        """Cerca piani di controllo per argomento usando ricerca ibrida.

        Args:
            query: testo libero (es. "piani sugli allevamenti avicoli").
            sezione: filtra per sezione del piano (opzionale).
        """
        from tools.search_tools import search_piani_by_topic
        return unwrap_tool(search_piani_by_topic)(query=query, sezione=sezione)

    # ------------------------------------------------------------------
    # 6) mostra_dettagli_completi — handoff two-phase
    # ------------------------------------------------------------------
    @tool("mostra_dettagli_completi")
    def mostra_dettagli_completi(context_id: Optional[str] = None) -> Dict[str, Any]:
        """Mostra i dettagli completi di un risultato precedente.

        Chiamare quando l'utente chiede "mostra tutto", "dettagli", "lista completa",
        "fammi vedere tutti". Se `context_id` non e' specificato, usa l'ultimo
        risultato troncato dalla sessione corrente.
        """
        payload = store.get(context_id) if context_id else store.last()
        if not payload:
            return {
                "formatted_response": "Nessun dettaglio disponibile per questa conversazione."
            }
        return payload

    # ------------------------------------------------------------------
    # 7) aiuto — catalogo capacita'
    # ------------------------------------------------------------------
    @tool("aiuto")
    def aiuto() -> Dict[str, Any]:
        """Elenca le funzionalita' disponibili dell'assistente."""
        try:
            from orchestrator.intent_metadata_service import get_intent_metadata_service
            content = get_intent_metadata_service().get_help_content()
            if content:
                return {"formatted_response": content}
        except Exception:
            pass
        return {
            "formatted_response": (
                "Posso rispondere su: statistiche controlli, descrizione piani, "
                "piani in ritardo, priorita' ispezione per rischio, ricerca piani."
            )
        }

    return [
        statistiche_controlli,
        descrizione_piano,
        piani_in_ritardo,
        indicatori_non_completati,
        priorita_ispezione_rischio,
        piani_attivita_piu_rischiosi,
        top_piani_per_nc,
        storico_stabilimento,
        cerca_piani,
        mostra_dettagli_completi,
        aiuto,
    ]
