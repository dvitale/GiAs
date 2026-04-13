# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportArgumentType=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOptionalOperand=false, reportReturnType=false, reportAssignmentType=false, reportPossiblyUnboundVariable=false
"""Statistiche controlli ufficiali eseguiti e programmati."""

from typing import Dict, Any, Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def get_cu_statistics(
    piano_code: Optional[str] = None,
    anno: Optional[int] = None,
    asl: Optional[str] = None,
    macroarea: Optional[str] = None,
    user_uos: Optional[str] = None,
    tipo_conteggio: str = "eseguiti",
) -> Dict[str, Any]:
    """
    Conteggio controlli ufficiali eseguiti o programmati con filtri opzionali.

    Args:
        piano_code: Codice piano/attivita (es. "AO1", "A22")
        anno: Anno di riferimento (default: anno corrente)
        asl: Nome ASL per filtrare
        macroarea: Macroarea CU per filtrare (es. "BENESSERE ANIMALE")
        user_uos: UOS dell'operatore per scope
        tipo_conteggio: "eseguiti" (default) o "programmati"

    Returns:
        Dict con conteggi e formatted_response markdown.
    """
    try:
        from configs.config_loader import get_config
        current_year = anno or get_config().get_current_year()
    except Exception:
        from datetime import datetime as _dt
        current_year = anno or _dt.now().year

    if tipo_conteggio == "programmati":
        return _count_programmati(piano_code, current_year, asl, user_uos)

    return _count_eseguiti(piano_code, current_year, asl, macroarea, user_uos, anno_explicit=anno is not None)


def _count_eseguiti(
    piano_code: Optional[str],
    anno: int,
    asl: Optional[str],
    macroarea: Optional[str],
    user_uos: Optional[str],
    anno_explicit: bool = False,
) -> Dict[str, Any]:
    """Conta controlli eseguiti da cu_eseguiti_nc con filtri."""
    from agents.data import controlli_df
    from agents.utils import filter_by_uos

    if controlli_df is None or controlli_df.empty:
        return {
            "error": "Dati controlli non disponibili",
            "formatted_response": "I dati sui controlli eseguiti non sono al momento disponibili.",
        }

    df = controlli_df.copy()

    # Filtro UOS (scope operatore)
    if user_uos:
        df = filter_by_uos(df, user_uos, "descrizione_uos")

    # Filtro anno
    if "data_inizio_controllo" in df.columns:
        dates = pd.to_datetime(df["data_inizio_controllo"], errors="coerce")
        df = df[dates.dt.year == anno]

    # Filtro ASL
    if asl:
        asl_upper = asl.upper().strip()
        if "descrizione_asl" in df.columns:
            df = df[df["descrizione_asl"].str.upper().str.contains(asl_upper, na=False)]

    # Filtro piano
    if piano_code:
        piano_upper = piano_code.upper().strip()
        if "alias_indicatore" in df.columns:
            import re
            pattern = rf"^(ATT\s+)?{re.escape(piano_upper)}(_|\s|$)"
            mask = df["alias_indicatore"].fillna("").str.upper().str.match(pattern)
            df = df[mask]

    # Filtro macroarea
    if macroarea:
        macroarea_upper = macroarea.upper().strip()
        if "macroarea_cu" in df.columns:
            df = df[df["macroarea_cu"].str.upper().str.contains(macroarea_upper, na=False)]

    total = df["id_controllo"].nunique() if "id_controllo" in df.columns else len(df)

    # Breakdown per macroarea (se non filtrato per macroarea specifica)
    breakdown = None
    breakdown_label = None
    if not macroarea and total > 0 and "macroarea_cu" in df.columns:
        if "id_controllo" in df.columns:
            breakdown = (
                df.groupby("macroarea_cu")["id_controllo"]
                .nunique()
                .reset_index(name="controlli")
                .sort_values("controlli", ascending=False)
            )
        else:
            breakdown = (
                df.groupby("macroarea_cu")
                .size()
                .reset_index(name="controlli")
                .sort_values("controlli", ascending=False)
            )
        breakdown["percentuale"] = (breakdown["controlli"] / total * 100).round(1)
        breakdown_label = "macroarea"
    elif piano_code and total > 0 and "alias_indicatore" in df.columns:
        if "id_controllo" in df.columns:
            breakdown = (
                df.groupby("alias_indicatore")["id_controllo"]
                .nunique()
                .reset_index(name="controlli")
                .sort_values("controlli", ascending=False)
            )
        else:
            breakdown = (
                df.groupby("alias_indicatore")
                .size()
                .reset_index(name="controlli")
                .sort_values("controlli", ascending=False)
            )
        breakdown["percentuale"] = (breakdown["controlli"] / total * 100).round(1)
        breakdown_label = "indicatore"

    # Date range
    data_primo = data_ultimo = None
    if total > 0 and "data_inizio_controllo" in df.columns:
        dates = pd.to_datetime(df["data_inizio_controllo"], errors="coerce")
        data_primo = dates.min()
        data_ultimo = dates.max()

    formatted = _format_eseguiti(
        total, piano_code, anno, asl, macroarea, user_uos,
        breakdown, breakdown_label, data_primo, data_ultimo, anno_explicit,
    )

    # Dettaglio singoli controlli (per two-phase)
    detail_formatted = None
    if total > 0 and "id_controllo" in df.columns:
        detail_formatted = _format_detail_controlli(df, piano_code, anno, asl, user_uos)

    return {
        "tipo_conteggio": "eseguiti",
        "total_controls": total,
        "piano_code": piano_code,
        "anno": anno,
        "asl": asl,
        "macroarea": macroarea,
        "user_uos": user_uos,
        "data_primo_controllo": data_primo.isoformat() if data_primo is not None and pd.notna(data_primo) else None,
        "data_ultimo_controllo": data_ultimo.isoformat() if data_ultimo is not None and pd.notna(data_ultimo) else None,
        "formatted_response": formatted,
        "detail_formatted": detail_formatted,
    }


def _count_programmati(
    piano_code: Optional[str],
    anno: int,
    asl: Optional[str],
    user_uos: Optional[str],
) -> Dict[str, Any]:
    """Conta controlli programmati da cu_diff_programmati_eseguiti."""
    if piano_code:
        # Delega alla funzione esistente in priority_tools
        from tools.priority_tools import get_programmed_controls_summary
        result = get_programmed_controls_summary(
            piano_code=piano_code,
            asl=asl,
            uos=user_uos,
            target_year=anno,
        )
        result["tipo_conteggio"] = "programmati"
        return result

    # Senza piano_code: aggregazione totale
    from agents.data import diff_prog_eseg_df
    from agents.utils import filter_by_uos

    if diff_prog_eseg_df is None or diff_prog_eseg_df.empty:
        return {
            "error": "Dati programmazione non disponibili",
            "formatted_response": "I dati sulla programmazione non sono al momento disponibili.",
        }

    df = diff_prog_eseg_df.copy()

    # Filtro UOS
    if user_uos:
        df = filter_by_uos(df, user_uos, "descrizione_uos")

    # Filtro anno
    if "anno" in df.columns:
        df = df[df["anno"] == anno]

    # Filtro ASL
    if asl:
        asl_upper = asl.upper().strip()
        if "descrizione_asl" in df.columns:
            df = df[df["descrizione_asl"].str.upper().str.contains(asl_upper, na=False)]

    if df.empty:
        scope = f" per il {anno}"
        if asl:
            scope += f" nell'ASL {asl}"
        return {
            "tipo_conteggio": "programmati",
            "programmati": 0,
            "eseguiti": 0,
            "anno": anno,
            "formatted_response": f"Non risultano controlli programmati{scope}.",
        }

    programmati = int(pd.to_numeric(df["programmati"], errors="coerce").fillna(0).sum())
    eseguiti = int(pd.to_numeric(df["eseguiti"], errors="coerce").fillna(0).sum())
    residuo = max(programmati - eseguiti, 0)
    completamento = (eseguiti / programmati * 100) if programmati else 0.0

    # Breakdown per piano
    breakdown = None
    if "alias_piano_attivita" in df.columns:
        breakdown = (
            df.groupby("alias_piano_attivita")
            .agg(programmati=("programmati", "sum"), eseguiti=("eseguiti", "sum"))
            .reset_index()
            .sort_values("programmati", ascending=False)
            .head(10)
        )

    formatted = _format_programmati(
        programmati, eseguiti, residuo, completamento,
        anno, asl, user_uos, breakdown,
    )

    return {
        "tipo_conteggio": "programmati",
        "programmati": programmati,
        "eseguiti": eseguiti,
        "residuo": residuo,
        "completamento_pct": round(completamento, 1),
        "anno": anno,
        "asl": asl,
        "user_uos": user_uos,
        "formatted_response": formatted,
    }


# ---------------------------------------------------------------------------
# Formattazione
# ---------------------------------------------------------------------------

def _format_eseguiti(
    total: int,
    piano_code: Optional[str],
    anno: int,
    asl: Optional[str],
    macroarea: Optional[str],
    user_uos: Optional[str],
    breakdown: Optional[pd.DataFrame],
    breakdown_label: Optional[str],
    data_primo,
    data_ultimo,
    anno_explicit: bool,
) -> str:
    """Formatta risposta per controlli eseguiti."""
    # Header
    title_parts = ["Controlli eseguiti"]
    if piano_code:
        title_parts.append(f"Piano {piano_code.upper()}")
    if macroarea:
        title_parts.append(macroarea.title())
    header = " — ".join(title_parts)
    lines = [f"### 📊 {header}"]

    # Scope line
    scope_bits = []
    if anno_explicit or anno:
        scope_bits.append(f"anno **{anno}**")
    if user_uos:
        scope_bits.append(f"UOS **{user_uos}**")
    if asl:
        scope_bits.append(f"ASL **{asl}**")
    if scope_bits:
        lines.append(f"*{' · '.join(scope_bits)}*")
    lines.append("")

    # Totale
    total_str = f"{total:,}".replace(",", ".")
    if user_uos:
        lines.append(f"**Totale controlli eseguiti (tua UOS):** {total_str}")
    else:
        lines.append(f"**Totale controlli eseguiti:** {total_str}")

    # Periodo
    if data_primo is not None and data_ultimo is not None and pd.notna(data_primo):
        lines.append(f"\n📅 **Periodo:** dal {data_primo.strftime('%d/%m/%Y')} al {data_ultimo.strftime('%d/%m/%Y')}")

    # Breakdown
    if breakdown is not None and not breakdown.empty and len(breakdown) > 1:
        lines.append("")
        if breakdown_label == "macroarea":
            lines.append("**Distribuzione per macroarea:**")
            lines.append("")
            lines.append("| Macroarea | Controlli | % |")
            lines.append("|-----------|-----------|---|")
            for _, row in breakdown.head(8).iterrows():
                name = str(row["macroarea_cu"]).title()
                cnt = f"{int(row['controlli']):,}".replace(",", ".")
                pct = f"{row['percentuale']:.0f}%"
                lines.append(f"| {name} | {cnt} | {pct} |")
        elif breakdown_label == "indicatore":
            lines.append("**Dettaglio per indicatore:**")
            lines.append("")
            lines.append("| Indicatore | Controlli | % |")
            lines.append("|------------|-----------|---|")
            for _, row in breakdown.head(8).iterrows():
                name = str(row["alias_indicatore"]).upper()
                cnt = f"{int(row['controlli']):,}".replace(",", ".")
                pct = f"{row['percentuale']:.0f}%"
                lines.append(f"| {name} | {cnt} | {pct} |")

    return "\n".join(lines)


def _format_programmati(
    programmati: int,
    eseguiti: int,
    residuo: int,
    completamento: float,
    anno: int,
    asl: Optional[str],
    user_uos: Optional[str],
    breakdown: Optional[pd.DataFrame],
) -> str:
    """Formatta risposta per controlli programmati (senza piano specifico)."""
    lines = [f"### 📋 Controlli programmati — {anno}"]

    scope_bits = [f"anno **{anno}**"]
    if user_uos:
        scope_bits.append(f"UOS **{user_uos}**")
    if asl:
        scope_bits.append(f"ASL **{asl}**")
    lines.append(f"*{' · '.join(scope_bits)}*")
    lines.append("")

    lines.append(f"**Controlli programmati:** {programmati:,}".replace(",", "."))
    lines.append(f"**Controlli eseguiti:** {eseguiti:,}".replace(",", "."))
    lines.append(f"**Residuo da eseguire:** {residuo:,}".replace(",", "."))
    lines.append(f"**Completamento:** {completamento:.0f}%")

    if breakdown is not None and not breakdown.empty and len(breakdown) > 1:
        lines.append("")
        lines.append("**Top piani per programmazione:**")
        lines.append("")
        lines.append("| Piano | Programmati | Eseguiti |")
        lines.append("|-------|-------------|----------|")
        for _, row in breakdown.head(8).iterrows():
            piano = str(row["alias_piano_attivita"]).upper()
            prog = int(row["programmati"])
            eseg = int(row["eseguiti"])
            lines.append(f"| {piano} | {prog:,} | {eseg:,} |".replace(",", "."))

    return "\n".join(lines)


def _format_detail_controlli(
    df: pd.DataFrame,
    piano_code: Optional[str],
    anno: int,
    asl: Optional[str],
    user_uos: Optional[str],
) -> str:
    """Formatta elenco dettagliato dei singoli controlli."""
    # Deduplica per id_controllo, tieni la prima riga per ciascuno
    if "id_controllo" in df.columns:
        detail = df.drop_duplicates(subset=["id_controllo"])
    else:
        detail = df

    # Ordina per data
    if "data_inizio_controllo" in detail.columns:
        detail = detail.sort_values("data_inizio_controllo", ascending=False)

    total = len(detail)

    # Header
    title_parts = ["Dettaglio controlli eseguiti"]
    if piano_code:
        title_parts.append(f"Piano {piano_code.upper()}")
    header = " — ".join(title_parts)
    lines = [f"### 📋 {header}"]

    scope_bits = []
    scope_bits.append(f"anno **{anno}**")
    if user_uos:
        scope_bits.append(f"UOS **{user_uos}**")
    if asl:
        scope_bits.append(f"ASL **{asl}**")
    lines.append(f"*{' · '.join(scope_bits)}*")
    lines.append(f"\n**Totale:** {total} controlli\n")

    # Colonne disponibili per la tabella
    has_data = "data_inizio_controllo" in detail.columns
    has_comune = "comune" in detail.columns
    has_rs = "ragione_sociale" in detail.columns
    has_indicatore = "alias_indicatore" in detail.columns
    has_nc_gravi = "numero_nc_gravi" in detail.columns
    has_nc_ng = "numero_nc_non_gravi" in detail.columns

    # Costruisci header tabella dinamicamente
    cols = []
    if has_data:
        cols.append("Data")
    if has_comune:
        cols.append("Comune")
    if has_rs:
        cols.append("Stabilimento")
    if has_indicatore:
        cols.append("Indicatore")
    if has_nc_gravi or has_nc_ng:
        cols.append("NC")

    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")

    for _, row in detail.iterrows():
        cells = []
        if has_data:
            d = pd.to_datetime(row["data_inizio_controllo"], errors="coerce")
            cells.append(d.strftime("%d/%m/%Y") if pd.notna(d) else "—")
        if has_comune:
            cells.append(str(row.get("comune", "—")).title())
        if has_rs:
            rs = str(row.get("ragione_sociale", "—"))
            cells.append(rs[:40] + "…" if len(rs) > 40 else rs)
        if has_indicatore:
            cells.append(str(row.get("alias_indicatore", "—")).upper())
        if has_nc_gravi or has_nc_ng:
            g = int(row.get("numero_nc_gravi", 0) or 0)
            ng = int(row.get("numero_nc_non_gravi", 0) or 0)
            if g + ng == 0:
                cells.append("—")
            else:
                cells.append(f"{g}G {ng}NG" if g else f"{ng}NG")
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)
