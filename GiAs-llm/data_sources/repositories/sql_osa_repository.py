"""
SqlOsaRepository — query diretta su osa_mai_controllati.

Filtro ASL opzionale (match esatto case-insensitive, compatibile con la
semantica di `agents.utils.filter_by_asl`).
"""

from typing import Optional
import pandas as pd

try:
    from sqlalchemy import text as _sa_text  # type: ignore
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False
    _sa_text = lambda s: s  # type: ignore


# Allineato a KEEP_COLUMNS["osa_mai_controllati"] in data_sources/base.py
_OSA_COLUMNS = [
    "ragione_sociale",
    "asl", "macroarea", "aggregazione", "attivita", "comune",
    "indirizzo", "latitudine_stab", "longitudine_stab",
    "num_riconoscimento", "n_reg", "provincia_stab",
    "data_inizio_attivita", "codice_norma",
    "partita_iva", "codice_fiscale", "codice_fiscale_rappresentante",
    "nominativo_rappresentante",
]


class SqlOsaRepository:
    """Repository SQL diretto su osa_mai_controllati."""

    def __init__(self, table_name: Optional[str] = None):
        if table_name is None:
            try:
                from configs.config_loader import get_config
                pg_cfg = get_config().get_postgresql_config()
                table_name = pg_cfg.get("tables", {}).get(
                    "osa_mai_controllati", "osa_mai_controllati"
                )
            except Exception:
                table_name = "osa_mai_controllati"
        self.table_name = table_name
        self._engine = None
        self._cols_cache: Optional[set] = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SqlOsaRepository richiede sqlalchemy")
        from data_sources.postgresql_source import PostgreSQLDataSource
        from configs.config_loader import get_config
        if PostgreSQLDataSource._engine is None:
            PostgreSQLDataSource(get_config().get_postgresql_config())
        self._engine = PostgreSQLDataSource._engine
        return self._engine

    def _get_columns(self) -> set:
        if self._cols_cache is not None:
            return self._cols_cache
        try:
            probe = pd.read_sql_query(
                _sa_text(f"SELECT * FROM {self.table_name} LIMIT 0"),
                self._get_engine(),
            )
            self._cols_cache = set(probe.columns)
        except Exception:
            self._cols_cache = set()
        return self._cols_cache

    def _select_expr(self) -> str:
        cols = self._get_columns()
        if not cols:
            return "*"
        wanted = [c for c in _OSA_COLUMNS if c in cols]
        return ", ".join(f'"{c}"' for c in wanted) if wanted else "*"

    def get_all(
        self,
        asl: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        cols = self._select_expr()
        params: dict = {}
        where = ""
        if asl:
            where = " WHERE UPPER(asl) = :asl"
            params["asl"] = asl.upper().strip()
        limit_clause = ""
        if limit and limit > 0:
            limit_clause = f" LIMIT {int(limit)}"
        sql = f"SELECT {cols} FROM {self.table_name}{where}{limit_clause}"
        try:
            return pd.read_sql_query(_sa_text(sql), self._get_engine(), params=params)
        except Exception as e:
            print(f"[SqlOsaRepository] Query error: {e}")
            return pd.DataFrame()
