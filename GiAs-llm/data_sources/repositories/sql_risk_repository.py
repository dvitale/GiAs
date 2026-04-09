# pyright: reportAttributeAccessIssue=false
"""
SqlRiskRepository — lettura diretta dalla view `v_risk_score_per_attivita`.

La view è già definita in `sql/risk_score_view.sql` e calcola:
  - tot_nc_gravi, tot_nc_non_gravi, tot_nc_totali (aggregate NC)
  - numero_controlli_totali (COUNT DISTINCT id_controllo)
  - prob_nc = NC totali / controlli
  - impatto = NC gravi / controlli
  - risk_score = prob_nc * impatto * 100
  - risk_category: ALTO/MEDIO/BASSO/MINIMO

Il repository rinomina `risk_score` → `punteggio_rischio_totale` per
mantenere il contract con il codice consumer (RiskAnalyzer, risk_tools).
"""

from typing import Optional
import pandas as pd

try:
    from sqlalchemy import text as _sa_text  # type: ignore
    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False
    _sa_text = lambda s: s  # type: ignore


class SqlRiskRepository:
    """Legge v_risk_score_per_attivita e rinomina le colonne per compat."""

    def __init__(self, view_name: str = "v_risk_score_per_attivita"):
        self.view_name = view_name
        self._engine = None
        self._cache: Optional[pd.DataFrame] = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SqlRiskRepository richiede sqlalchemy")
        from data_sources.postgresql_source import PostgreSQLDataSource
        from configs.config_loader import get_config
        if PostgreSQLDataSource._engine is None:
            PostgreSQLDataSource(get_config().get_postgresql_config())
        self._engine = PostgreSQLDataSource._engine
        return self._engine

    def get_risk_scores(self) -> pd.DataFrame:
        """
        Legge la view e proietta le colonne con i nomi contrattuali attesi.

        Colonne output:
          macroarea, aggregazione, linea_attivita, tot_nc_gravi, tot_nc_non_gravi,
          tot_nc_totali, numero_controlli_totali, prob_nc, impatto,
          punteggio_rischio_totale

        Cache in-memory: sessione del processo. Per invalidare, chiamare
        clear_cache() (esiste per symmetry con il legacy RiskAnalyzer).
        """
        if self._cache is not None:
            return self._cache

        sql = f"""
            SELECT
                macroarea,
                aggregazione,
                linea_attivita,
                tot_nc_gravi,
                tot_nc_non_gravi,
                tot_nc_totali,
                numero_controlli_totali,
                prob_nc,
                impatto,
                risk_score AS punteggio_rischio_totale
            FROM {self.view_name}
            WHERE risk_score > 0
            ORDER BY risk_score DESC NULLS LAST
        """
        try:
            df = pd.read_sql_query(_sa_text(sql), self._get_engine())
        except Exception as e:
            print(f"[SqlRiskRepository] Errore lettura view: {e}")
            return pd.DataFrame()

        # Coerzione numerica (la view ritorna NUMERIC, pd convertirebbe a float)
        for col in ["tot_nc_gravi", "tot_nc_non_gravi", "tot_nc_totali",
                    "numero_controlli_totali"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
        for col in ["prob_nc", "impatto", "punteggio_rischio_totale"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        self._cache = df
        return df

    def clear_cache(self) -> None:
        self._cache = None
