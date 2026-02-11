"""
DEPRECATED: Enhanced DataRetriever - Use agents.data_agent.DataRetriever instead.
This module is maintained for backward compatibility only.
"""

import pandas as pd
from typing import List, Dict, Any
from .data_agent import DataRetriever, RiskAnalyzer, BusinessLogic

class CachedDataRetriever:
    """
    DEPRECATED: Use DataRetriever from data_agent module instead.
    This class now proxies calls to the main DataRetriever for compatibility.
    """

    @classmethod
    def search_piani_by_keyword(cls, keyword: str, similarity_threshold: float = 0.4) -> List[Dict[str, Any]]:
        """Proxy to DataRetriever.search_piani_by_keyword."""
        return DataRetriever.search_piani_by_keyword(keyword, similarity_threshold)

    @classmethod
    def get_cached_risk_scores(cls) -> pd.DataFrame:
        """Proxy to RiskAnalyzer.calculate_risk_scores."""
        return RiskAnalyzer.calculate_risk_scores()

    @classmethod
    def find_priority_establishments_optimized(cls, asl: str = None, uoc: str = None,
                                              piano_id: str = None, max_results: int = 10) -> pd.DataFrame:
        """
        DEPRECATED: Use BusinessLogic.find_priority_establishments instead.
        This method is kept for backward compatibility.
        """
        # For now, use the OSA analysis approach that was unique to cached version
        osa_df = DataRetriever.get_osa_mai_controllati()
        attivita_df = DataRetriever.get_attivita()

        if osa_df.empty or attivita_df.empty:
            return pd.DataFrame()

        # Normalize keys for joining
        osa_df = osa_df.copy()
        attivita_df = attivita_df.copy()

        # Create normalized activity keys
        osa_df['attivita_norm'] = osa_df['attivita'].str.upper().str.strip()
        attivita_df['attivita_norm'] = attivita_df.get('linea_di_attivita',
                                                       attivita_df.get('LINEA DI ATTIVITA', '')).str.upper().str.strip()

        # Join on normalized activity
        merged_df = pd.merge(
            osa_df,
            attivita_df[['attivita_norm', 'macroarea', 'aggregazione']].drop_duplicates(),
            on='attivita_norm',
            how='inner'
        )

        # Apply filters
        if asl:
            merged_df = merged_df[merged_df['asl'].str.contains(asl, case=False, na=False)]

        if piano_id:
            # Filter by piano if specified
            piano_attivita = attivita_df[
                attivita_df.get('norma', '').str.contains(piano_id, case=False, na=False)
            ]
            if not piano_attivita.empty:
                valid_activities = piano_attivita['attivita_norm'].unique()
                merged_df = merged_df[merged_df['attivita_norm'].isin(valid_activities)]

        # Group by establishment and count activities
        priority_df = merged_df.groupby([
            'asl', 'comune', 'indirizzo', 'num_riconoscimento'
        ]).agg({
            'macroarea': 'first',
            'aggregazione': 'first',
            'attivita': 'count'
        }).rename(columns={'attivita': 'num_attivita'}).reset_index()

        # Sort by number of activities (priority)
        priority_df = priority_df.sort_values('num_attivita', ascending=False)

        return priority_df.head(max_results)

    @classmethod
    def clear_all_caches(cls):
        """Clear all cached data (proxy to main modules)."""
        DataRetriever.clear_cache()
        RiskAnalyzer.clear_risk_cache()
        print("[CachedDataRetriever] All caches cleared via main modules")

    # Legacy method aliases for compatibility
    @classmethod
    def search_piani_by_keyword_cached(cls, keyword: str, similarity_threshold: float = 0.4) -> tuple:
        """Legacy method - returns tuple for LRU cache compatibility."""
        result = cls.search_piani_by_keyword(keyword, similarity_threshold)
        return tuple(result)