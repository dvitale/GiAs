"""
Abstract base class for data sources.
"""

from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd


# Whitelist colonne per i 3 dataset piu' grandi.
# Le colonne non elencate vengono scartate al load time per ridurre memoria.
# Impatto stimato: ~11.5M celle eliminate (~34 colonne inutilizzate).
# Per riaggiungere una colonna, basta inserirla nella lista — nessun dato
# viene cancellato dalla sorgente (CSV/DB).
KEEP_COLUMNS: Dict[str, List[str]] = {
    "controlli": [
        "id_controllo", "data_inizio_controllo", "macroarea_cu",
        "aggregazione_cu", "attivita_cu", "descrizione_indicatore",
        "descrizione_piano", "descrizione_asl", "descrizione_uoc",
        "descrizione_uos", "sezione", "num_riconoscimento", "norma",
        "alias_piano_attivita", "alias_indicatore",
        "latitudine_stab", "longitudine_stab",
        # PII — mantenute per blacklist check
        "num_registrazione", "ragione_sociale", "partita_iva",
        "codice_fiscale", "nominativo_rappresentante",
        # NC inline (da cu_eseguiti_nc)
        "tipo_non_conformita", "numero_nc_gravi", "numero_nc_non_gravi",
        "oggetto_non_conformita", "comune",
    ],
    "osa_mai_controllati": [
        "ragione_sociale",
        "asl", "macroarea", "aggregazione", "attivita", "comune",
        "indirizzo", "latitudine_stab", "longitudine_stab",
        "num_riconoscimento", "provincia_stab",
        # PII — mantenute per blacklist check
        "partita_iva", "codice_fiscale", "codice_fiscale_rappresentante",
        "nominativo_rappresentante",
    ],
}


def _apply_column_filter(key: str, df: pd.DataFrame) -> pd.DataFrame:
    """Filtra colonne inutilizzate in base alla whitelist KEEP_COLUMNS."""
    if key not in KEEP_COLUMNS or df.empty:
        return df
    keep = [c for c in KEEP_COLUMNS[key] if c in df.columns]
    dropped = len(df.columns) - len(keep)
    if dropped > 0:
        print(f"[DataSource] {key}: scartate {dropped} colonne inutilizzate "
              f"({len(df.columns)} -> {len(keep)})")
    return df[keep]


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
        Applica whitelist colonne ai dataset grandi (controlli, osa).

        Returns:
            Dictionary with all dataframes
        """
        datasets = {
            "piani": self.load_piani(),
            "attivita": self.load_attivita(),
            "controlli": self.load_controlli(),
            "osa_mai_controllati": self.load_osa_mai_controllati(),
            "diff_prog_eseg": self.load_diff_prog_eseg(),
            "personale": self.load_personale(),
        }
        # Filtra colonne inutilizzate per i dataset configurati
        for key in list(datasets.keys()):
            datasets[key] = _apply_column_filter(key, datasets[key])
        return datasets
