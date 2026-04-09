"""
PandasOsaRepository — facade sui metodi legacy di DataRetriever per osa_mai_controllati.
"""

from typing import Optional
import pandas as pd


class PandasOsaRepository:
    """Facade in-memory — delega al calcolo legacy."""

    def get_all(
        self,
        asl: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        # Chiama il metodo legacy (preservato durante il refactor per evitare
        # ricorsione: `DataRetriever.get_osa_mai_controllati` delega a questo
        # repository).
        from agents.data_agent import DataRetriever
        method = getattr(
            DataRetriever,
            "_get_osa_mai_controllati_pandas_legacy",
            None,
        )
        if method is not None:
            return method(asl=asl, limit=limit)
        # Fallback legacy (prima del refactor)
        return DataRetriever.get_osa_mai_controllati(asl=asl, limit=limit)
