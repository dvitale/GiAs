"""
Test per FewShotRetriever (P4)

Testa:
- Diversity limit (max 2 per intent)
- Graceful fallback quando Qdrant non disponibile
- Formato output
- Cache behavior
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.few_shot_retriever import FewShotRetriever, get_few_shot_retriever


class TestFewShotRetriever:
    """Test per FewShotRetriever"""

    def test_singleton_pattern(self):
        """Test che FewShotRetriever sia singleton"""
        r1 = FewShotRetriever()
        r2 = FewShotRetriever()
        assert r1 is r2

    def test_retriever_graceful_fallback_no_qdrant(self):
        """Test graceful degradation quando Qdrant non disponibile"""
        # Reset singleton per test isolato
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        # Mock import per simulare Qdrant non disponibile
        with patch.dict('sys.modules', {'qdrant_client': None}):
            retriever = FewShotRetriever()
            # Forza path inesistente
            retriever.QDRANT_PATH = "/path/che/non/esiste"

            result = retriever.retrieve("stabilimenti a rischio")

            # Deve restituire lista vuota, non sollevare eccezione
            assert result == []
            assert retriever.is_available() is False

        # Cleanup
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_retriever_empty_query(self):
        """Test che query vuota restituisca lista vuota"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()

        assert retriever.retrieve("") == []
        assert retriever.retrieve("   ") == []
        assert retriever.retrieve(None) == []

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_format_for_prompt_empty(self):
        """Test formato prompt con lista vuota"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()
        result = retriever.format_for_prompt([])

        assert result == ""

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_format_for_prompt_with_examples(self):
        """Test formato prompt con esempi"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()
        examples = [
            {"text": "stabilimenti a rischio", "intent": "ask_risk_based_priority", "score": 0.95},
            {"text": "attività rischiose", "intent": "ask_top_risk_activities", "score": 0.88},
        ]

        result = retriever.format_for_prompt(examples)

        assert "ESEMPI SIMILI:" in result
        assert "stabilimenti a rischio" in result
        assert "ask_risk_based_priority" in result
        assert "attività rischiose" in result

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_get_stats(self):
        """Test metodo get_stats"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()
        stats = retriever.get_stats()

        assert "available" in stats
        assert "cache_size" in stats
        assert "cache_max_size" in stats
        assert "collection" in stats
        assert stats["collection"] == "intent_examples"

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_clear_cache(self):
        """Test clear_cache"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()

        # Aggiungi qualcosa alla cache manualmente
        retriever._cache["test_key"] = [{"text": "test", "intent": "greet", "score": 1.0}]
        assert len(retriever._cache) == 1

        retriever.clear_cache()
        assert len(retriever._cache) == 0

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False


class TestFewShotRetrieverWithMockedQdrant:
    """Test con Qdrant mockato"""

    def test_retriever_diversity_limit(self):
        """Test che max 2 esempi per intent vengano restituiti"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()

        # Mock Qdrant client e embedding model
        mock_qdrant = MagicMock()
        mock_model = MagicMock()

        retriever._qdrant_client = mock_qdrant
        retriever._embedding_model = mock_model
        retriever._available = True

        # Mock embedding con oggetto che ha .tolist()
        import numpy as np
        mock_model.encode.return_value = np.array([0.1] * 384)

        # Mock risultati Qdrant con 4 risultati stesso intent
        mock_point1 = MagicMock()
        mock_point1.payload = {"text": "esempio 1", "intent": "ask_risk_based_priority"}
        mock_point1.score = 0.95

        mock_point2 = MagicMock()
        mock_point2.payload = {"text": "esempio 2", "intent": "ask_risk_based_priority"}
        mock_point2.score = 0.90

        mock_point3 = MagicMock()
        mock_point3.payload = {"text": "esempio 3", "intent": "ask_risk_based_priority"}
        mock_point3.score = 0.85

        mock_point4 = MagicMock()
        mock_point4.payload = {"text": "esempio 4", "intent": "ask_top_risk_activities"}
        mock_point4.score = 0.80

        mock_results = MagicMock()
        mock_results.points = [mock_point1, mock_point2, mock_point3, mock_point4]
        mock_qdrant.query_points.return_value = mock_results

        result = retriever.retrieve("test query", max_per_intent=2)

        # Dovrebbe avere max 2 per ask_risk_based_priority + 1 per ask_top_risk_activities
        risk_based = [r for r in result if r["intent"] == "ask_risk_based_priority"]
        top_risk = [r for r in result if r["intent"] == "ask_top_risk_activities"]

        assert len(risk_based) <= 2, f"Troppi esempi per ask_risk_based_priority: {len(risk_based)}"
        assert len(top_risk) <= 2, f"Troppi esempi per ask_top_risk_activities: {len(top_risk)}"

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

    def test_retriever_cache_hit(self):
        """Test che cache funzioni"""
        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False

        retriever = FewShotRetriever()

        mock_qdrant = MagicMock()
        mock_model = MagicMock()

        retriever._qdrant_client = mock_qdrant
        retriever._embedding_model = mock_model
        retriever._available = True

        # Mock embedding con oggetto che ha .tolist()
        import numpy as np
        mock_model.encode.return_value = np.array([0.1] * 384)

        mock_point = MagicMock()
        mock_point.payload = {"text": "esempio", "intent": "greet"}
        mock_point.score = 0.95

        mock_results = MagicMock()
        mock_results.points = [mock_point]
        mock_qdrant.query_points.return_value = mock_results

        # Prima chiamata
        result1 = retriever.retrieve("ciao")
        assert len(result1) == 1

        # Seconda chiamata - dovrebbe usare cache
        result2 = retriever.retrieve("ciao")
        assert len(result2) == 1

        # query_points dovrebbe essere chiamato solo 1 volta
        assert mock_qdrant.query_points.call_count == 1

        FewShotRetriever._instance = None
        FewShotRetriever._initialized = False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
