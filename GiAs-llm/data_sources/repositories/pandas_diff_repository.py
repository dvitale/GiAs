# pyright: reportAttributeAccessIssue=false, reportReturnType=false
"""
PandasDiffRepository — facade thin per cu_diff_programmati_eseguiti.

Delega a `DataRetriever.get_diff_programmati_eseguiti` (per il filtro
struttura) e per get_programmati_for_piano usa direttamente il DataFrame
globale `diff_prog_eseg_df`.

Zero logica nuova. Path default quando flag = "pandas".
"""

from typing import Optional
import pandas as pd


class PandasDiffRepository:
    """Facade in-memory."""

    def get_for_struttura(
        self,
        uoc_name: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
    ) -> pd.DataFrame:
        from agents.data_agent import DataRetriever
        # Chiama il metodo legacy per evitare ricorsione
        method = getattr(
            DataRetriever,
            "_get_diff_programmati_eseguiti_pandas_legacy",
            DataRetriever.get_diff_programmati_eseguiti,
        )
        return method(uoc_name, asl=asl, uos=uos)

    def get_programmati_for_piano(
        self,
        piano_code: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        from agents.data import diff_prog_eseg_df

        if diff_prog_eseg_df is None or diff_prog_eseg_df.empty:
            return pd.DataFrame()

        work = diff_prog_eseg_df

        # Filtro anno
        if year is not None and "anno" in work.columns:
            work = work[work["anno"] == year]

        if "alias_piano_attivita" not in work.columns:
            return pd.DataFrame()

        piano_upper = str(piano_code).upper().strip()
        work = work[work["alias_piano_attivita"].fillna("").astype(str).str.upper() == piano_upper]

        if asl and "descrizione_asl" in work.columns:
            work = work[work["descrizione_asl"].fillna("").astype(str).str.contains(asl, case=False, na=False)]
        if uos and "descrizione_uos" in work.columns:
            work = work[work["descrizione_uos"].fillna("").astype(str).str.contains(uos, case=False, na=False)]

        return work.copy()
