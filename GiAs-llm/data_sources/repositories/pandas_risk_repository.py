"""
PandasRiskRepository — facade sui calcoli risk di RiskAnalyzer.

Delega a `RiskAnalyzer.calculate_risk_scores` (mantiene la cache in-process
legacy). Path default quando flag `data_source.repositories.risk` = "pandas".
"""

import pandas as pd


class PandasRiskRepository:
    """Facade in-memory — delega a RiskAnalyzer legacy."""

    def get_risk_scores(self) -> pd.DataFrame:
        # Import lazy per evitare loop circolari a import time.
        # RiskAnalyzer attualmente chiama il repository quando flag=sql
        # (vedi Fase 3 refactor), ma qui siamo SEMPRE nel path pandas.
        # Per evitare ricorsione, importiamo direttamente il metodo
        # originale prima del refactor — salvato come _calculate_risk_scores_pandas.
        from agents.data_agent import RiskAnalyzer
        method = getattr(
            RiskAnalyzer,
            "_calculate_risk_scores_pandas_original",
            RiskAnalyzer.calculate_risk_scores,
        )
        return method()
