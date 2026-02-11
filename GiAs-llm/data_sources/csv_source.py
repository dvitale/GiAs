"""
CSV data source implementation.
"""

import os
import pandas as pd
from data_sources.base import DataSource


class CSVDataSource(DataSource):
    """CSV-based data source."""

    def __init__(self, config: dict):
        """
        Initialize CSV data source.

        Args:
            config: CSV configuration dict with 'directory' and 'files'
        """
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, config.get("directory", "dataset"))
        self.files = config.get("files", {})
        self.personale_sep = config.get("personale_separator", "|")
        self.ocse_sep = config.get("ocse_separator", ",")

    def _load_csv(self, key: str, **kwargs) -> pd.DataFrame:
        """
        Load CSV file by key.

        Args:
            key: File key in config
            **kwargs: Additional arguments for pd.read_csv

        Returns:
            DataFrame or empty DataFrame on error
        """
        filename = self.files.get(key)
        if not filename:
            print(f"[CSVDataSource] No filename configured for key: {key}")
            return pd.DataFrame()

        filepath = os.path.join(self.data_dir, filename)

        try:
            df = pd.read_csv(filepath, low_memory=False, **kwargs)
            print(f"[CSVDataSource] Loaded {key}: {len(df)} rows from {filename}")
            return df
        except FileNotFoundError:
            print(f"[CSVDataSource] File not found: {filepath}")
            return pd.DataFrame()
        except Exception as e:
            print(f"[CSVDataSource] Error loading {key} from {filepath}: {e}")
            return pd.DataFrame()

    def load_piani(self) -> pd.DataFrame:
        """Load piani_monitoraggio data."""
        return self._load_csv("piani")

    def load_attivita(self) -> pd.DataFrame:
        """Load attivita (Master list) data."""
        return self._load_csv("attivita")

    def load_controlli(self) -> pd.DataFrame:
        """Load controlli eseguiti data."""
        return self._load_csv("controlli")

    def load_osa_mai_controllati(self) -> pd.DataFrame:
        """Load OSA mai controllati data."""
        return self._load_csv("osa_mai_controllati")

    def load_ocse(self) -> pd.DataFrame:
        """Load OCSE data."""
        return self._load_csv("ocse", sep=self.ocse_sep)

    def load_diff_prog_eseg(self) -> pd.DataFrame:
        """Load diff programmati/eseguiti data."""
        return self._load_csv("diff_prog_eseg")

    def load_personale(self) -> pd.DataFrame:
        """Load personale data."""
        return self._load_csv("personale", sep=self.personale_sep)
