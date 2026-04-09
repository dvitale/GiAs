"""
PandasControlliRepository — facade thin sui metodi esistenti di DataRetriever.

Delega a `DataRetriever.get_controlli_by_piano` (regex match piano/attività)
e a `BusinessLogic._count_stabilimenti` (groupby in-memory).

Zero logica nuova. Mantiene compatibilità byte-per-byte quando la flag
`data_source.repositories.controlli` è "pandas" (default).
"""

from typing import Optional
import pandas as pd


class PandasControlliRepository:
    """Facade in-memory che delega al codice legacy basato su controlli_df."""

    def get_by_piano(self, piano_id: str) -> Optional[pd.DataFrame]:
        """Delega al metodo pandas legacy (evita ricorsione)."""
        from agents.data_agent import DataRetriever
        method = getattr(
            DataRetriever,
            "_get_controlli_by_piano_pandas_legacy",
            DataRetriever.get_controlli_by_piano,
        )
        return method(piano_id)

    def count_stabilimenti_by_piano(self, piano_id: str) -> int:
        """Delega a BusinessLogic._count_stabilimenti."""
        from agents.data_agent import BusinessLogic
        return BusinessLogic._count_stabilimenti(piano_id)

    def get_by_asl(self, asl: str) -> pd.DataFrame:
        """Filtro per ASL in-memory sul DataFrame globale controlli_df."""
        from agents.data import controlli_df
        if controlli_df is None or controlli_df.empty or not asl:
            return pd.DataFrame()
        mask = controlli_df["descrizione_asl"].fillna("").str.contains(
            asl, case=False, na=False
        )
        result = controlli_df[mask].copy()
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
