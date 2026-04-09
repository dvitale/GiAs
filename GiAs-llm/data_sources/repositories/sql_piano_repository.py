"""
SqlPianoRepository — implementazione SQL-first del PianoRepository.

Emette query SQL parametriche su `piani_mv` (materialized view creata da
sql/create_materialized_views.sql), riutilizzando l'engine SQLAlchemy già
creato da `PostgreSQLDataSource`.

Contract invariant: restituisce DataFrame con le **stesse colonne** che
ritornerebbe `piani_df` in memoria, così il codice chiamante non deve
fare branching.

Fallback `find_by_alias`: replica il triplo fallback di
`DataRetriever.get_piano_by_id` usando il pattern matching PostgreSQL `~*`:
  1. Match esatto su alias_piano_attivita OR alias_indicatore
  2. Retry con prefix "ATT " automatico
  3. Retry con regex prefix pattern (spazi o underscore dopo "ATT ")
"""

from typing import List, Dict, Any, Optional
import re
import pandas as pd

try:
    from sqlalchemy import text as _sa_text  # type: ignore
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False
    _sa_text = lambda s: s  # type: ignore


# Colonne lette dalla MV (o fallback tabella). Devono combaciare con quelle
# esposte da piani_df in-memory — contract test verifica invariance.
_PIANO_COLUMNS = [
    "sezione",
    "alias_piano_attivita",
    "alias_indicatore",
    "descrizione_piano_attivita",
    "descrizione_indicatore",
    "campionamento",
    "tipo_piano_attivita",
    "anno",
]


class SqlPianoRepository:
    """Repository SQL diretto su piani_mv."""

    def __init__(self, table_name: Optional[str] = None):
        """
        Args:
            table_name: Nome della relation da interrogare.
                Default: legge `data_source.repositories.piano_table` da config
                (default "piani_monitoraggio", che è già una MATERIALIZED VIEW
                creata da sql/create_normalized_views.sql).
        """
        if table_name is None:
            try:
                from configs.config_loader import get_config
                cfg = get_config().config  # type: ignore[attr-defined]
                table_name = (
                    cfg.get("data_source", {})
                    .get("repositories", {})
                    .get("piano_table", "piani_monitoraggio")
                )
            except Exception:
                table_name = "piani_monitoraggio"
        self.table_name = table_name
        self._engine = None

    def _get_engine(self):
        """Lazy fetch dell'engine SQLAlchemy (condiviso con PostgreSQLDataSource)."""
        if self._engine is not None:
            return self._engine
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy non disponibile: SqlPianoRepository richiede sqlalchemy")
        from data_sources.postgresql_source import PostgreSQLDataSource
        from configs.config_loader import get_config
        if PostgreSQLDataSource._engine is None:
            # Istanzia per inizializzare l'engine classe-level
            PostgreSQLDataSource(get_config().get_postgresql_config())
        self._engine = PostgreSQLDataSource._engine
        return self._engine

    def _select_columns_expr(self) -> str:
        """Colonne proiettate in SELECT, con virgolette per reserved words."""
        return ", ".join(f'"{c}"' for c in _PIANO_COLUMNS)

    def _read_sql(self, sql: str, params: Dict[str, Any]) -> pd.DataFrame:
        """Esegue la query e ritorna DataFrame. Ritorna DF vuoto in caso di errore."""
        try:
            return pd.read_sql_query(_sa_text(sql), self._get_engine(), params=params)
        except Exception as e:
            print(f"[SqlPianoRepository] Query error: {e}")
            return pd.DataFrame()

    def _current_year(self) -> Optional[int]:
        """Anno corrente da config (per filtro temporale su piani_monitoraggio)."""
        try:
            from configs.config_loader import get_config
            return int(get_config().get_current_year())
        except Exception:
            return None

    def _year_filter(self) -> str:
        """Clausola WHERE per filtrare anno corrente. Stringa vuota se non disponibile."""
        yr = self._current_year()
        return f" AND anno = {yr}" if yr else ""

    def find_by_alias(self, piano_id: str) -> Optional[pd.DataFrame]:
        """
        Replica DataRetriever.get_piano_by_id con 3 fallback successivi.

        Returns:
            DataFrame non vuoto o None.
        """
        if not piano_id:
            return None

        pid = piano_id.upper().strip()
        cols = self._select_columns_expr()
        yf = self._year_filter()

        # Fallback 1: match diretto su alias_piano_attivita o alias_indicatore
        sql1 = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE (UPPER(alias_piano_attivita) = :pid
                OR UPPER(alias_indicatore) = :pid){yf}
        """
        df = self._read_sql(sql1, {"pid": pid})
        if not df.empty:
            return df

        # Fallback 2: prefix "ATT " automatico (es. "AO5_A" → "ATT AO5_A")
        if not pid.startswith("ATT "):
            sql2 = f"""
                SELECT {cols} FROM {self.table_name}
                WHERE UPPER(alias_indicatore) = :att_pid{yf}
            """
            df = self._read_sql(sql2, {"att_pid": f"ATT {pid}"})
            if not df.empty:
                return df

        # Fallback 3: regex prefix con spazio/underscore intercambiabili
        # Python regex: rf'^ATT[_ ]{base}(?:[_ ]|$)'
        base = pid[4:] if pid.startswith("ATT ") else pid
        pg_pattern = f"^ATT[_ ]{re.escape(base)}([_ ]|$)"
        sql3 = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE UPPER(alias_indicatore) ~* :pattern{yf}
        """
        df = self._read_sql(sql3, {"pattern": pg_pattern})
        return df if not df.empty else None

    def search(
        self,
        query: str,
        sezione: Optional[str] = None,
        campionamento: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca full-text su descrizioni. Equivalente SQL di
        DataRetriever.search_piani_by_db.

        Semantica:
          - Se `sezione` e `query` entrambi valorizzati → filtro combinato su
            sezione + LIKE nelle descrizioni
          - Se solo `sezione` → tutti i piani della sezione
          - Se solo `query` → LIKE nelle descrizioni senza filtro sezione
          - Se `campionamento` valorizzato → filtro aggiuntivo
        """
        where_clauses = []
        params: Dict[str, Any] = {}

        if sezione:
            sezione_upper = sezione.strip().upper()
            where_clauses.append("UPPER(sezione) ~* :sezione_pattern")
            params["sezione_pattern"] = f"^SEZIONE {re.escape(sezione_upper)}( |$)"

        if query and query.strip():
            search_term = f"%{query.strip()}%"
            where_clauses.append(
                "(descrizione_piano_attivita ILIKE :q "
                "OR descrizione_indicatore ILIKE :q)"
            )
            params["q"] = search_term

        if campionamento is not None:
            where_clauses.append("campionamento = :camp")
            params["camp"] = bool(campionamento)

        # Filtro anno corrente (coerente con load_piani)
        yr = self._current_year()
        if yr:
            where_clauses.append("anno = :year")
            params["year"] = yr

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        cols = self._select_columns_expr()
        sql = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE {where_sql}
            ORDER BY alias_piano_attivita, alias_indicatore
        """

        df = self._read_sql(sql, params)
        if df.empty:
            return []

        # Dedup su (alias_piano_attivita, alias_indicatore) per coerenza
        # con il comportamento pandas di search_piani_by_db
        df = df.drop_duplicates(
            subset=["alias_piano_attivita", "alias_indicatore"],
            keep="first",
        )

        return df.to_dict(orient="records")

    def count_attivita(self, piano_id: str) -> int:
        """
        Replica BusinessLogic._count_attivita:
          count = (righe con descrizione_piano_attivita non-NULL)
                + (righe con descrizione_indicatore non-NULL)
        """
        rows = self.find_by_alias(piano_id)
        if rows is None or rows.empty:
            return 0

        count = 0
        if "descrizione_piano_attivita" in rows.columns:
            count += int(rows["descrizione_piano_attivita"].notna().sum())
        if "descrizione_indicatore" in rows.columns:
            count += int(rows["descrizione_indicatore"].notna().sum())
        return count
