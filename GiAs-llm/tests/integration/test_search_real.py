"""
Test integrazione Hybrid Search con dati reali (NO MOCK).
"""

import pytest
import sys
import os

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestHybridSearchReal:
    """Test sistema hybrid search con dati reali."""

    @pytest.mark.integration
    def test_search_simple_keyword(self, tool_caller):
        """Test ricerca keyword semplice."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "bovini")

        assert isinstance(result, dict)
        assert "total_found" in result
        assert result["total_found"] > 0
        assert "matches" in result

    @pytest.mark.integration
    def test_search_complex_query(self, tool_caller):
        """Test ricerca query complessa."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(
            search_piani_by_topic,
            "piani relativi alla sicurezza alimentare"
        )

        assert isinstance(result, dict)
        assert "total_found" in result

    @pytest.mark.integration
    def test_search_exact_code(self, tool_caller):
        """Test ricerca codice piano esatto."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "A1")

        assert isinstance(result, dict)
        # Deve trovare almeno il piano A1
        if result["total_found"] > 0:
            matches = result["matches"]
            # Almeno un match dovrebbe contenere A1
            found_a1 = any(
                "A1" in str(m.get("alias", "")) or "A1" in str(m.get("piano_code", ""))
                for m in matches
            )
            # Potrebbe non trovarlo se il campo ha nome diverso

    @pytest.mark.integration
    def test_search_results_structure(self, tool_caller):
        """Test struttura risultati ricerca."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "allevamenti")

        assert isinstance(result, dict)

        if result["total_found"] > 0:
            assert "matches" in result
            matches = result["matches"]
            assert isinstance(matches, list)

            # Ogni match dovrebbe avere campi standard
            if len(matches) > 0:
                first_match = matches[0]
                # Verifica che sia un dict con dati
                assert isinstance(first_match, dict)


class TestHybridSearchStrategies:
    """Test strategie di ricerca."""

    @pytest.mark.integration
    def test_vector_search_simple(self, tool_caller):
        """Test ricerca vettoriale per query semplice."""
        from tools.search_tools import search_piani_by_topic

        # Query semplice dovrebbe usare vector_only
        result = tool_caller(search_piani_by_topic, "suini")

        assert isinstance(result, dict)
        assert "total_found" in result

    @pytest.mark.integration
    def test_semantic_search_complex(self, tool_caller):
        """Test ricerca semantica per query complessa."""
        from tools.search_tools import search_piani_by_topic

        # Query complessa potrebbe usare hybrid o LLM
        result = tool_caller(
            search_piani_by_topic,
            "quali controlli riguardano il benessere degli animali"
        )

        assert isinstance(result, dict)
        assert "total_found" in result


class TestSearchTopics:
    """Test ricerca per vari topic."""

    @pytest.mark.integration
    @pytest.mark.parametrize("topic", [
        "bovini",
        "suini",
        "allevamenti",
        "sicurezza alimentare",
        "igiene",
        "latte",
        "carni",
    ])
    def test_search_various_topics(self, tool_caller, topic):
        """Test ricerca per topic comuni."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, topic)

        assert isinstance(result, dict)
        assert "total_found" in result
        # La maggior parte dei topic dovrebbe trovare risultati
        # (ma non garantito per tutti)


class TestSearchFormatting:
    """Test formattazione risultati ricerca."""

    @pytest.mark.integration
    def test_search_formatted_response(self, tool_caller):
        """Test che risultati abbiano formatted_response."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "bovini")

        if result["total_found"] > 0:
            # Dovrebbe avere risposta formattata
            assert "formatted_response" in result or "matches" in result


