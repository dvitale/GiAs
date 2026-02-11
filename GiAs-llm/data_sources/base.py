"""
Abstract base class for data sources.
"""

from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd


class DataSource(ABC):
    """Abstract base class for data source implementations."""

    @abstractmethod
    def load_piani(self) -> pd.DataFrame:
        """Load piani_monitoraggio data."""
        pass

    @abstractmethod
    def load_attivita(self) -> pd.DataFrame:
        """Load attivita (Master list) data."""
        pass

    @abstractmethod
    def load_controlli(self) -> pd.DataFrame:
        """Load controlli eseguiti data."""
        pass

    @abstractmethod
    def load_osa_mai_controllati(self) -> pd.DataFrame:
        """Load OSA mai controllati data."""
        pass

    @abstractmethod
    def load_ocse(self) -> pd.DataFrame:
        """Load OCSE data."""
        pass

    @abstractmethod
    def load_diff_prog_eseg(self) -> pd.DataFrame:
        """Load diff programmati/eseguiti data."""
        pass

    @abstractmethod
    def load_personale(self) -> pd.DataFrame:
        """Load personale data."""
        pass

    def load_all(self) -> Dict[str, pd.DataFrame]:
        """
        Load all datasets.

        Returns:
            Dictionary with all dataframes
        """
        return {
            "piani": self.load_piani(),
            "attivita": self.load_attivita(),
            "controlli": self.load_controlli(),
            "osa_mai_controllati": self.load_osa_mai_controllati(),
            "ocse": self.load_ocse(),
            "diff_prog_eseg": self.load_diff_prog_eseg(),
            "personale": self.load_personale()
        }
