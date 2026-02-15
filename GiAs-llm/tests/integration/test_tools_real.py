"""
Test integrazione Tools con dati reali (NO MOCK).
"""

import pytest
import sys
import os

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestPianoToolsReal:
    """Test piano_tools con dati reali."""

    @pytest.mark.integration
    def test_get_piano_description_real(self, tool_caller):
        """Test get_piano_description con dati reali."""
        from tools.piano_tools import get_piano_description

        result = tool_caller(get_piano_description, "A1")

        assert isinstance(result, dict)
        # Deve avere risposta formattata o errore
        assert "formatted_response" in result or "error" in result

        if "formatted_response" in result:
            assert len(result["formatted_response"]) > 0

    @pytest.mark.integration
    def test_get_piano_description_not_found(self, tool_caller):
        """Test piano inesistente."""
        from tools.piano_tools import get_piano_description

        result = tool_caller(get_piano_description, "ZZZZZ999")

        assert "error" in result
        assert "non trovato" in result["error"].lower()

    @pytest.mark.integration
    def test_get_piano_description_empty_code(self, tool_caller):
        """Test codice piano vuoto."""
        from tools.piano_tools import get_piano_description

        result = tool_caller(get_piano_description, "")

        assert "error" in result
        assert "non specificato" in result["error"].lower()

    @pytest.mark.integration
    def test_piano_tool_description_action(self, tool_caller):
        """Test piano_tool con action description."""
        from tools.piano_tools import piano_tool

        result = tool_caller(piano_tool, action="description", piano_code="A1")

        assert isinstance(result, dict)
        assert "formatted_response" in result or "error" in result

    @pytest.mark.integration
    def test_piano_tool_stabilimenti_action(self, tool_caller):
        """Test piano_tool con action stabilimenti."""
        from tools.piano_tools import piano_tool

        result = tool_caller(piano_tool, action="stabilimenti", piano_code="A22")

        assert isinstance(result, dict)

    @pytest.mark.integration
    def test_piano_tool_invalid_action(self, tool_caller):
        """Test piano_tool con action invalida."""
        from tools.piano_tools import piano_tool

        result = tool_caller(piano_tool, action="invalid_action", piano_code="A1")

        assert "error" in result


class TestSearchToolsReal:
    """Test search_tools con dati reali."""

    @pytest.mark.integration
    def test_search_piani_by_topic_real(self, tool_caller):
        """Test ricerca piani per topic."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "bovini")

        assert isinstance(result, dict)
        assert "total_found" in result

        # Deve trovare risultati per "bovini"
        if result["total_found"] > 0:
            assert "matches" in result
            assert len(result["matches"]) > 0

    @pytest.mark.integration
    def test_search_piani_empty_query(self, tool_caller):
        """Test ricerca con query vuota."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "")

        # Deve gestire gracefully
        assert "error" in result or result.get("total_found", 0) == 0

    @pytest.mark.integration
    def test_search_piani_no_results(self, tool_caller):
        """Test ricerca senza risultati."""
        from tools.search_tools import search_piani_by_topic

        result = tool_caller(search_piani_by_topic, "xyz123_nonexistent_topic")

        assert result["total_found"] == 0

    @pytest.mark.integration
    def test_search_tool_router(self, tool_caller):
        """Test search_tool router."""
        from tools.search_tools import search_tool

        result = tool_caller(search_tool, query="allevamenti")

        assert isinstance(result, dict)
        assert "total_found" in result or "error" in result


class TestPriorityToolsReal:
    """Test priority_tools con dati reali."""

    @pytest.mark.integration
    def test_get_priority_establishment_real(self, tool_caller):
        """Test priority establishment con dati reali."""
        from tools.priority_tools import get_priority_establishment

        result = tool_caller(
            get_priority_establishment,
            asl="AVELLINO",
            uoc="UOC IGIENE URBANA"
        )

        assert isinstance(result, dict)
        # Puo' avere dati o errore per UOC inesistente

    @pytest.mark.integration
    def test_get_priority_missing_asl(self, tool_caller):
        """Test priority senza ASL."""
        from tools.priority_tools import get_priority_establishment

        result = tool_caller(get_priority_establishment, None, "UOC")

        assert "error" in result
        assert "asl" in result["error"].lower()

    @pytest.mark.integration
    def test_get_delayed_plans_real(self, tool_caller):
        """Test piani in ritardo con dati reali."""
        from tools.priority_tools import get_delayed_plans

        result = tool_caller(
            get_delayed_plans,
            asl="AVELLINO",
            uoc="UOC IGIENE URBANA"
        )

        assert isinstance(result, dict)

    @pytest.mark.integration
    def test_suggest_controls_real(self, tool_caller):
        """Test suggerisci controlli."""
        from tools.priority_tools import suggest_controls

        result = tool_caller(suggest_controls, asl="AVELLINO")

        assert isinstance(result, dict)


class TestRiskToolsReal:
    """Test risk_tools con dati reali."""

    @pytest.mark.integration
    def test_get_risk_based_priority_real(self, tool_caller):
        """Test risk priority con dati reali."""
        from tools.risk_tools import get_risk_based_priority

        result = tool_caller(get_risk_based_priority, asl="AVELLINO")

        assert isinstance(result, dict)

    @pytest.mark.integration
    def test_risk_tool_router(self, tool_caller):
        """Test risk_tool router."""
        from tools.risk_tools import risk_tool

        result = tool_caller(risk_tool, asl="AVELLINO", piano_code="A1")

        assert isinstance(result, dict)


class TestEstablishmentToolsReal:
    """Test establishment_tools con dati reali."""

    @pytest.mark.integration
    def test_get_establishment_history(self, tool_caller):
        """Test storico stabilimento."""
        from tools.establishment_tools import get_establishment_history

        # Usa un numero di registrazione che potrebbe esistere
        result = tool_caller(
            get_establishment_history,
            num_registrazione="IT 2287"
        )

        assert isinstance(result, dict)


class TestDataRetrieverReal:
    """Test DataRetriever diretto."""

    @pytest.mark.integration
    def test_data_retriever_piani(self):
        """Test accesso dati piani."""
        from agents.data_agent import DataRetriever

        # get_piano_by_id
        df = DataRetriever.get_piano_by_id("A1")

        assert df is not None
        # Puo' essere vuoto se piano non esiste

    @pytest.mark.integration
    def test_data_retriever_controlli(self):
        """Test accesso dati controlli."""
        from agents.data_agent import DataRetriever

        df = DataRetriever.get_controlli_by_piano("A1")

        assert df is not None
