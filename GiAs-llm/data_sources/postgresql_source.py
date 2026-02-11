"""
PostgreSQL data source implementation with SQLAlchemy connection pooling.
"""

import pandas as pd
from data_sources.base import DataSource

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import QueuePool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    print("[PostgreSQLDataSource] Warning: sqlalchemy not installed, using fallback psycopg2")

try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("[PostgreSQLDataSource] Warning: psycopg2 not installed, PostgreSQL support disabled")


class PostgreSQLDataSource(DataSource):
    """PostgreSQL-based data source with SQLAlchemy connection pooling and caching."""

    # Class-level cache for DataFrames (shared across instances)
    _dataframe_cache = {}
    _engine = None

    def __init__(self, config: dict):
        """
        Initialize PostgreSQL data source with SQLAlchemy engine.

        Args:
            config: PostgreSQL configuration dict
        """
        if not SQLALCHEMY_AVAILABLE and not PSYCOPG2_AVAILABLE:
            raise ImportError("SQLAlchemy or psycopg2 is required for PostgreSQL support")

        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "gias_db")
        self.user = config.get("user", "gias_user")
        self.password = config.get("password", "")
        self.tables = config.get("tables", {})
        self.use_sqlalchemy = SQLALCHEMY_AVAILABLE

        # Initialize engine with connection pooling if SQLAlchemy available
        if self.use_sqlalchemy and PostgreSQLDataSource._engine is None:
            connection_string = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
            PostgreSQLDataSource._engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=5,  # Maintain 5 connections in pool
                max_overflow=10,  # Allow up to 10 additional connections
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
                echo=False
            )
            print(f"[PostgreSQLDataSource] Created SQLAlchemy engine with connection pooling")
            print(f"[PostgreSQLDataSource] Connected to {self.database}@{self.host}:{self.port}")

        # Fallback to psycopg2 if SQLAlchemy not available
        self.connection = None

    def _get_connection(self):
        """Get database connection (fallback for psycopg2)."""
        if self.use_sqlalchemy:
            return None  # Not used with SQLAlchemy

        if self.connection is None or self.connection.closed:
            try:
                self.connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    sslmode='disable'
                )
                print(f"[PostgreSQLDataSource] Connected to {self.database}@{self.host}:{self.port}")
            except psycopg2.Error as e:
                print(f"[PostgreSQLDataSource] Connection error: {e}")
                raise
        return self.connection

    def _load_table(self, key: str) -> pd.DataFrame:
        """
        Load table by key with caching using SQLAlchemy or psycopg2.

        Args:
            key: Table key in config

        Returns:
            DataFrame or empty DataFrame on error
        """
        # Check cache first (class-level cache, shared across all instances)
        if key in self._dataframe_cache:
            return self._dataframe_cache[key].copy()  # Return copy to prevent modifications

        table_name = self.tables.get(key)
        if not table_name:
            print(f"[PostgreSQLDataSource] No table configured for key: {key}")
            return pd.DataFrame()

        try:
            # Use SQLAlchemy with connection pooling if available
            if self.use_sqlalchemy and self._engine is not None:
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql_query(query, self._engine)
            else:
                # Fallback to psycopg2
                conn = self._get_connection()
                query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))
                df = pd.read_sql_query(query.as_string(conn), conn)

            # Cache the result at class level
            self._dataframe_cache[key] = df
            print(f"[PostgreSQLDataSource] Loaded and cached {key}: {len(df)} rows from table {table_name}")
            return df.copy()
        except Exception as e:
            print(f"[PostgreSQLDataSource] Error loading {key} from table {table_name}: {e}")
            return pd.DataFrame()

    def load_piani(self) -> pd.DataFrame:
        """
        Load piani_monitoraggio data with deduplication.

        PostgreSQL contains duplicates (5x per record).
        This method deduplicates based on (sezione, alias, alias_indicatore).
        """
        df = self._load_table("piani")
        if not df.empty:
            # Deduplicate keeping first occurrence
            df = df.drop_duplicates(subset=['sezione', 'alias', 'alias_indicatore'], keep='first')
            print(f"[PostgreSQLDataSource] Deduplicated piani: {len(df)} unique records")
        return df

    def load_attivita(self) -> pd.DataFrame:
        """
        Load attivita data with deduplication.

        PostgreSQL contains duplicates (4x per record).
        This method deduplicates based on all columns except 'id'.
        """
        df = self._load_table("attivita")
        if not df.empty:
            # Deduplicate based on all columns except 'id'
            cols_to_check = [col for col in df.columns if col != 'id']
            if cols_to_check:
                df = df.drop_duplicates(subset=cols_to_check, keep='first')
                print(f"[PostgreSQLDataSource] Deduplicated attivita: {len(df)} unique records")
        return df

    def load_controlli(self) -> pd.DataFrame:
        """Load controlli eseguiti data."""
        return self._load_table("controlli")

    def load_osa_mai_controllati(self) -> pd.DataFrame:
        """Load OSA mai controllati data."""
        return self._load_table("osa_mai_controllati")

    def load_ocse(self) -> pd.DataFrame:
        """Load OCSE data."""
        return self._load_table("ocse")

    def load_diff_prog_eseg(self) -> pd.DataFrame:
        """Load diff programmati/eseguiti data."""
        return self._load_table("diff_prog_eseg")

    def load_personale(self) -> pd.DataFrame:
        """
        Load personale data with deduplication.

        PostgreSQL contains duplicates (4x per record).
        This method deduplicates based on user_id.
        """
        df = self._load_table("personale")
        if not df.empty and 'user_id' in df.columns:
            # Deduplicate keeping first occurrence per user_id
            df = df.drop_duplicates(subset=['user_id'], keep='first')
            print(f"[PostgreSQLDataSource] Deduplicated personale: {len(df)} unique users")
        return df

    # Compatibility methods with get_* naming used by current system
    def get_piani(self) -> pd.DataFrame:
        """Get piani_monitoraggio data (compatibility method)."""
        return self.load_piani()

    def get_attivita(self) -> pd.DataFrame:
        """Get attivita data (compatibility method)."""
        return self.load_attivita()

    def get_controlli(self) -> pd.DataFrame:
        """Get controlli data (compatibility method)."""
        return self.load_controlli()

    def get_osa_mai_controllati(self) -> pd.DataFrame:
        """Get OSA mai controllati data (compatibility method)."""
        return self.load_osa_mai_controllati()

    def get_ocse(self) -> pd.DataFrame:
        """Get OCSE data (compatibility method)."""
        return self.load_ocse()

    def get_diff_prog_eseg(self) -> pd.DataFrame:
        """Get diff programmati/eseguiti data (compatibility method)."""
        return self.load_diff_prog_eseg()

    def get_personale(self) -> pd.DataFrame:
        """Get personale data (compatibility method)."""
        return self.load_personale()

    def clear_cache(self):
        """Clear cached DataFrames."""
        self._dataframe_cache.clear()
        print("[PostgreSQLDataSource] Cache cleared")

    @classmethod
    def preload_all_data(cls):
        """
        Preload all datasets into cache at startup.
        Call this during application initialization for optimal performance.
        """
        from configs.config_loader import get_config
        config = get_config()
        pg_config = config.get_postgresql_config()

        instance = cls(pg_config)
        datasets = instance.load_all()

        print(f"[PostgreSQLDataSource] Preloaded {len(datasets)} datasets into cache")
        return datasets

    def close(self):
        """Close database connection (for psycopg2 fallback only)."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            print("[PostgreSQLDataSource] Connection closed")

    @classmethod
    def dispose_engine(cls):
        """Dispose SQLAlchemy engine and close all connections in pool."""
        if cls._engine is not None:
            cls._engine.dispose()
            cls._engine = None
            print("[PostgreSQLDataSource] Engine disposed, all connections closed")

    def __del__(self):
        """Cleanup connection on object destruction."""
        self.close()
