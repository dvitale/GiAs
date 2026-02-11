"""
Configuration loader for GiAs-llm system.
"""

import json
import os
from typing import Dict, Any


class Config:
    """Configuration manager for data sources."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config.json in the same directory as this file
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_path):
            print(f"[Config] Config file not found: {self.config_path}, using defaults")
            return self._get_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"[Config] Loaded configuration from {self.config_path}")
                return config
        except Exception as e:
            print(f"[Config] Error loading config: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "current_year": 2025,
            "data_source": {
                "type": "csv",
                "csv": {
                    "directory": "dataset",
                    "files": {
                        "piani": "piani_monitoraggio.csv",
                        "attivita": "Master list rev 11_filtered.csv",
                        "controlli": "vw_2025_eseguiti_filtered.csv",
                        "osa_mai_controllati": "osa_mai_controllati_con_linea_852-3_filtered.csv",
                        "ocse": "OCSE_ISP_SEMP_2025_filtered_v2.csv",
                        "diff_prog_eseg": "vw_diff_programmmati_eseguiti.csv",
                        "personale": "personale_filtered.csv"
                    },
                    "personale_separator": "|"
                },
                "postgresql": {
                    "enabled": False
                }
            }
        }

    def get_data_source_type(self) -> str:
        """Get configured data source type (csv or postgresql)."""
        return self.config.get("data_source", {}).get("type", "csv")

    def get_csv_config(self) -> Dict[str, Any]:
        """Get CSV configuration."""
        return self.config.get("data_source", {}).get("csv", {})

    def get_postgresql_config(self) -> Dict[str, Any]:
        """Get PostgreSQL configuration."""
        return self.config.get("data_source", {}).get("postgresql", {})

    def is_postgresql_enabled(self) -> bool:
        """Check if PostgreSQL is enabled."""
        ds_type = self.get_data_source_type()
        if ds_type == "postgresql":
            return self.get_postgresql_config().get("enabled", False)
        return False

    def get_current_year(self) -> int:
        """Get configured current year for analysis."""
        return self.config.get("current_year", 2025)


# Global config instance
_config_instance = None


def get_config() -> Config:
    """Get singleton config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
