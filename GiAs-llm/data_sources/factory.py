"""
Data source factory with singleton caching.
"""

from data_sources.base import DataSource
from data_sources.csv_source import CSVDataSource
from data_sources.postgresql_source import PostgreSQLDataSource
from configs.config_loader import get_config
from typing import Optional

# Global singleton instance
_data_source_instance: Optional[DataSource] = None


def get_data_source() -> DataSource:
    """
    Factory method to create appropriate data source based on configuration.
    Uses singleton pattern to avoid recreating data sources.

    Returns:
        DataSource instance (CSV or PostgreSQL)
    """
    global _data_source_instance

    # Return existing instance if available
    if _data_source_instance is not None:
        return _data_source_instance

    config = get_config()
    ds_type = config.get_data_source_type()

    if ds_type == "postgresql" and config.is_postgresql_enabled():
        print("[DataSource Factory] Creating PostgreSQL data source (singleton)")
        pg_config = config.get_postgresql_config()
        _data_source_instance = PostgreSQLDataSource(pg_config)
    else:
        print("[DataSource Factory] Creating CSV data source (singleton)")
        csv_config = config.get_csv_config()
        _data_source_instance = CSVDataSource(csv_config)

    return _data_source_instance


def clear_data_source_cache():
    """Clear cached data source instance (for testing/reload)."""
    global _data_source_instance
    if _data_source_instance and hasattr(_data_source_instance, 'close'):
        _data_source_instance.close()
    _data_source_instance = None
