"""
SqlDiffRepository — query dirette su cu_diff_programmati_eseguiti.

Le query sono SEMPRE filtrate (almeno UOC) per evitare scaricare l'intera
tabella (~69K righe). Tutti i parametri sono passati via prepared statements.
"""

from typing import Optional
import pandas as pd

try:
    from sqlalchemy import text as _sa_text  # type: ignore
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False
    _sa_text = lambda s: s  # type: ignore


# Colonne contrattuali (devono includere quelle usate da
# BusinessLogic.calculate_delayed_plans e dai tool consumer)
_DIFF_COLUMNS = [
    "anno", "alias_piano_attivita", "alias_indicatore",
    "descrizione_indicatore", "descrizione_piano",
    "descrizione_asl", "descrizione_uoc", "descrizione_uos",
    "programmati", "eseguiti",
]


class SqlDiffRepository:
    """Repository SQL diretto su cu_diff_programmati_eseguiti."""

    def __init__(self, table_name: Optional[str] = None):
        if table_name is None:
            try:
                from configs.config_loader import get_config
                pg_cfg = get_config().get_postgresql_config()
                table_name = pg_cfg.get("tables", {}).get(
                    "diff_prog_eseg", "cu_diff_programmati_eseguiti"
                )
            except Exception:
                table_name = "cu_diff_programmati_eseguiti"
        self.table_name = table_name
        self._engine = None
        self._cols_cache: Optional[set] = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SqlDiffRepository richiede sqlalchemy")
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
        wanted = [c for c in _DIFF_COLUMNS if c in cols]
        return ", ".join(f'"{c}"' for c in wanted) if wanted else "*"

    def _read_sql(self, sql: str, params: dict) -> pd.DataFrame:
        try:
            return pd.read_sql_query(_sa_text(sql), self._get_engine(), params=params)
        except Exception as e:
            print(f"[SqlDiffRepository] Query error: {e}")
            return pd.DataFrame()

    def get_for_struttura(
        self,
        uoc_name: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Replica DataRetriever.get_diff_programmati_eseguiti.

        Semantica:
          - UOC: substring match case-insensitive (ILIKE %x%)
          - ASL: substring match (UPPER LIKE)
          - UOS: substring match con "soft fallback" — se applicare il filtro
            UOS porta a 0 risultati, mantieni il dataset filtrato per UOC+ASL
            (replica del comportamento pandas in get_diff_programmati_eseguiti).
        """
        if not uoc_name:
            return pd.DataFrame()

        cols = self._select_expr()
        params: dict = {"uoc": f"%{uoc_name}%"}
        sql = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE descrizione_uoc ILIKE :uoc
        """
        if asl:
            sql += " AND UPPER(COALESCE(descrizione_asl, '')) LIKE :asl"
            params["asl"] = f"%{asl.upper().strip()}%"

        df = self._read_sql(sql, params)
        if df.empty:
            return df

        # Soft fallback UOS: applica filtro solo se non azzera il risultato
        if uos:
            uos_upper = uos.upper().strip()
            mask = df["descrizione_uos"].fillna("").astype(str).str.upper().str.contains(uos_upper, regex=False)
            uos_filtered = df[mask]
            if not uos_filtered.empty:
                df = uos_filtered  # type: ignore[assignment]

        return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)

    def get_programmati_for_piano(
        self,
        piano_code: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Recupera righe per un piano filtrato per ASL/UOS/anno.

        Filtro su `alias_piano_attivita` (NON `alias_indicatore`) per
        aggregare anche i sotto-indicatori dello stesso piano (es. A14_A,
        A14_B per piano "A14"). Usato da get_programmed_controls_summary.
        """
        if not piano_code:
            return pd.DataFrame()

        cols = self._select_expr()
        params: dict = {"piano": piano_code.upper().strip()}
        sql = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE UPPER(COALESCE(alias_piano_attivita, '')) = :piano
        """
        if year is not None:
            sql += " AND anno = :year"
            params["year"] = year
        if asl:
            sql += " AND descrizione_asl ILIKE :asl"
            params["asl"] = f"%{asl.strip()}%"
        if uos:
            sql += " AND descrizione_uos ILIKE :uos"
            params["uos"] = f"%{uos.strip()}%"

        return self._read_sql(sql, params)
