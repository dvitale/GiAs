"""
SqlControlliRepository — query dirette su `cu_eseguiti_nc`.

Sostituisce l'accesso al DataFrame globale `controlli_df` (~3.3M righe) con
SELECT mirate. Replica esattamente la semantica di
`DataRetriever.get_controlli_by_piano`:

  - Per PIANO (codice senza "ATT "): match su `alias_indicatore` con
    pattern regex `^(ATT[_ ])?<base>([_ ]|$)` (case-insensitive).
  - Per ATTIVITA (prefix "ATT "): primo tentativo su
    `descrizione_indicatore ILIKE 'ATT_<base>%'` (le righe attività hanno
    spesso `alias_indicatore` NULL); fallback al regex su `alias_indicatore`
    se il primo tentativo non trova nulla.

Sicurezza: tutte le query usano prepared statements (`text(:param)`) — il
piano_id viene sempre passato come parametro, mai concatenato.
"""

from typing import Optional
import re
import pandas as pd

try:
    from sqlalchemy import text as _sa_text  # type: ignore
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False
    _sa_text = lambda s: s  # type: ignore


# Colonne contrattuali — devono coincidere con quelle attese dai consumer
# di controlli_df (priority_tools, risk_tools, piano_tools).
# Mantengono la whitelist di KEEP_COLUMNS["controlli"] in data_sources/base.py.
_CONTROLLI_COLUMNS = [
    "id_controllo", "data_inizio_controllo", "macroarea_cu",
    "aggregazione_cu", "attivita_cu", "descrizione_indicatore",
    "descrizione_piano", "descrizione_asl", "descrizione_uoc",
    "descrizione_uos", "sezione", "num_riconoscimento", "norma",
    "alias_piano_attivita", "alias_indicatore",
    "campionamento", "tipo_piano_attivita",
    "latitudine_stab", "longitudine_stab",
    "num_registrazione", "ragione_sociale", "partita_iva",
    "codice_fiscale", "nominativo_rappresentante",
    "tipo_non_conformita", "numero_nc_gravi", "numero_nc_non_gravi",
    "oggetto_non_conformita", "comune",
]


class SqlControlliRepository:
    """Repository SQL diretto su cu_eseguiti_nc."""

    def __init__(self, table_name: Optional[str] = None):
        if table_name is None:
            try:
                from configs.config_loader import get_config
                pg_cfg = get_config().get_postgresql_config()
                table_name = pg_cfg.get("tables", {}).get("controlli", "cu_eseguiti_nc")
            except Exception:
                table_name = "cu_eseguiti_nc"
        self.table_name = table_name
        self._engine = None
        self._available_columns = None  # cache colonne effettive della tabella

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SqlControlliRepository richiede sqlalchemy")
        from data_sources.postgresql_source import PostgreSQLDataSource
        from configs.config_loader import get_config
        if PostgreSQLDataSource._engine is None:
            PostgreSQLDataSource(get_config().get_postgresql_config())
        self._engine = PostgreSQLDataSource._engine
        return self._engine

    def _get_columns(self) -> set:
        """Probe colonne disponibili (1 round-trip, cached)."""
        if self._available_columns is not None:
            return self._available_columns
        try:
            probe = pd.read_sql_query(
                _sa_text(f"SELECT * FROM {self.table_name} LIMIT 0"),
                self._get_engine(),
            )
            self._available_columns = set(probe.columns)
        except Exception as e:
            print(f"[SqlControlliRepository] Probe colonne fallita: {e}")
            self._available_columns = set()
        return self._available_columns

    def _select_expr(self) -> str:
        """SELECT delle sole colonne whitelist effettivamente presenti."""
        cols = self._get_columns()
        if not cols:
            return "*"
        wanted = [c for c in _CONTROLLI_COLUMNS if c in cols]
        if not wanted:
            return "*"
        return ", ".join(f'"{c}"' for c in wanted)

    def _read_sql(self, sql: str, params: dict) -> pd.DataFrame:
        try:
            return pd.read_sql_query(_sa_text(sql), self._get_engine(), params=params)
        except Exception as e:
            print(f"[SqlControlliRepository] Query error: {e}")
            return pd.DataFrame()

    def get_by_piano(self, piano_id: str) -> Optional[pd.DataFrame]:
        """
        Recupera controlli per un piano/attività.

        Distingue piano (no prefix) vs attività (prefix "ATT ") con la stessa
        logica di DataRetriever.get_controlli_by_piano.
        """
        if not piano_id:
            return None

        piano_upper = piano_id.upper().strip()
        is_attivita = piano_upper.startswith("ATT ")
        cols = self._select_expr()

        if is_attivita:
            # Attività: primo tentativo su descrizione_indicatore con prefix
            # "ATT_<base>" (es. "ATT_B47 ISPEZIONI"). Escape underscore LIKE
            # così non è trattato come wildcard.
            base = piano_upper[4:]  # rimuovi "ATT "
            att_prefix = f"ATT_{base}".replace("_", r"\_")
            sql1 = f"""
                SELECT {cols} FROM {self.table_name}
                WHERE UPPER(descrizione_indicatore) LIKE :prefix ESCAPE '\\'
            """
            df = self._read_sql(sql1, {"prefix": f"{att_prefix}%"})
            if not df.empty:
                return df

            # Fallback: regex su alias_indicatore. In modalità attività
            # il prefix ATT può essere seguito da underscore O spazio
            # (replica di pandas pattern `^(ATT[_ ])?...`).
            pg_pattern = f"^(ATT[_ ])?{re.escape(base)}([_ ]|$)"
            sql2 = f"""
                SELECT {cols} FROM {self.table_name}
                WHERE UPPER(alias_indicatore) ~* :pattern
            """
            df = self._read_sql(sql2, {"pattern": pg_pattern})
            return df if not df.empty else None
        else:
            # Piano: regex su alias_indicatore. In modalità piano il prefix
            # ATT ammette solo spazio (pandas `^(ATT\s+)?...`).
            pg_pattern = f"^(ATT +)?{re.escape(piano_upper)}([_ ]|$)"
            sql = f"""
                SELECT {cols} FROM {self.table_name}
                WHERE UPPER(alias_indicatore) ~* :pattern
            """
            df = self._read_sql(sql, {"pattern": pg_pattern})
            return df if not df.empty else None

    def get_by_asl(self, asl: str) -> pd.DataFrame:
        """SELECT filtrato per ASL (substring match case-insensitive)."""
        if not asl:
            return pd.DataFrame()
        cols = self._select_expr()
        sql = f"""
            SELECT {cols} FROM {self.table_name}
            WHERE descrizione_asl ILIKE :asl
        """
        return self._read_sql(sql, {"asl": f"%{asl}%"})

    def count_stabilimenti_by_piano(self, piano_id: str) -> int:
        """
        Conta tipologie (macroarea_cu, aggregazione_cu) distinte per un piano.
        Implementato come SQL COUNT(DISTINCT) per evitare di scaricare il dataset.
        """
        if not piano_id:
            return 0

        piano_upper = piano_id.upper().strip()
        is_attivita = piano_upper.startswith("ATT ")

        if is_attivita:
            base = piano_upper[4:]
            pg_pattern = f"^(ATT[_ ])?{re.escape(base)}([_ ]|$)"
            sql = f"""
                SELECT COUNT(DISTINCT (macroarea_cu, aggregazione_cu)) AS n
                FROM {self.table_name}
                WHERE UPPER(alias_indicatore) ~* :pattern
            """
            params = {"pattern": pg_pattern}
        else:
            pg_pattern = f"^(ATT +)?{re.escape(piano_upper)}([_ ]|$)"
            sql = f"""
                SELECT COUNT(DISTINCT (macroarea_cu, aggregazione_cu)) AS n
                FROM {self.table_name}
                WHERE UPPER(alias_indicatore) ~* :pattern
            """
            params = {"pattern": pg_pattern}

        try:
            engine = self._get_engine()
            assert engine is not None
            with engine.connect() as conn:
                row = conn.execute(_sa_text(sql), params).fetchone()
            return int(row[0]) if row else 0
        except Exception as e:
            print(f"[SqlControlliRepository] count error: {e}")
            return 0
