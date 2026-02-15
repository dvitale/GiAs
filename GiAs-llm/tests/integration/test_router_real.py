"""
Test integrazione Router con LLM reale (NO MOCK).
"""

import pytest
import sys
import os

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestRouterWithRealLLM:
    """Test Router con LLM reale."""

    @pytest.fixture
    def router(self):
        """Router con LLM reale."""
        from orchestrator.router import Router
        from llm.client import LLMClient

        llm = LLMClient()
        return Router(llm)

    @pytest.mark.integration
    def test_classify_greet(self, router):
        """Test classificazione saluto."""
        result = router.classify("ciao")

        assert result["intent"] == "greet"
        assert result["confidence"] >= 0.5

    @pytest.mark.integration
    def test_classify_goodbye(self, router):
        """Test classificazione saluto finale."""
        result = router.classify("arrivederci")

        assert result["intent"] == "goodbye"

    @pytest.mark.integration
    def test_classify_help(self, router):
        """Test classificazione richiesta aiuto."""
        result = router.classify("cosa puoi fare")

        assert result["intent"] == "ask_help"

    @pytest.mark.integration
    def test_classify_piano_with_slot(self, router):
        """Test classificazione con estrazione slot piano."""
        result = router.classify("di cosa tratta il piano A1")

        assert result["intent"] == "ask_piano_description"
        assert result["slots"].get("piano_code") == "A1"

    @pytest.mark.integration
    def test_classify_piano_complex_code(self, router):
        """Test estrazione codice piano complesso."""
        result = router.classify("descrizione piano A11_F")

        assert result["intent"] == "ask_piano_description"
        assert result["slots"].get("piano_code") in ["A11_F", "A11"]

    @pytest.mark.integration
    def test_classify_search_topic(self, router):
        """Test classificazione ricerca per topic."""
        result = router.classify("quali piani riguardano bovini")

        assert result["intent"] == "search_piani_by_topic"

    @pytest.mark.integration
    def test_classify_delayed_plans(self, router):
        """Test classificazione piani in ritardo."""
        result = router.classify("piani in ritardo")

        assert result["intent"] == "ask_delayed_plans"

    @pytest.mark.integration
    def test_classify_check_specific_plan_delayed(self, router):
        """Test classificazione verifica ritardo piano specifico."""
        result = router.classify("il piano B47 è in ritardo")

        assert result["intent"] == "check_if_plan_delayed"
        assert result["slots"].get("piano_code") == "B47"

    @pytest.mark.integration
    def test_classify_priority(self, router):
        """Test classificazione priorita' stabilimenti."""
        result = router.classify("chi devo controllare per primo")

        assert result["intent"] in ["ask_priority_establishment", "ask_risk_based_priority"]

    @pytest.mark.integration
    def test_classify_risk(self, router):
        """Test classificazione rischio storico."""
        result = router.classify("stabilimenti ad alto rischio")

        assert result["intent"] == "ask_risk_based_priority"

    @pytest.mark.integration
    def test_classify_suggest_controls(self, router):
        """Test classificazione suggerimenti controlli."""
        result = router.classify("suggerisci controlli")

        assert result["intent"] == "ask_suggest_controls"

    @pytest.mark.integration
    def test_classify_empty_returns_fallback(self, router):
        """Test messaggio vuoto ritorna fallback."""
        result = router.classify("")

        assert result["intent"] == "fallback"

    @pytest.mark.integration
    def test_classify_nonsense_returns_fallback(self, router):
        """Test query senza senso ritorna fallback."""
        result = router.classify("xyz123 asdfgh qwerty")

        assert result["intent"] == "fallback"


class TestRouterConfidence:
    """Test confidence del Router."""

    @pytest.fixture
    def router(self):
        from orchestrator.router import Router
        from llm.client import LLMClient
        return Router(LLMClient())

    @pytest.mark.integration
    def test_high_confidence_clear_intent(self, router):
        """Test alta confidence per intent chiaro."""
        result = router.classify("ciao")

        assert result["confidence"] >= 0.7

    @pytest.mark.integration
    def test_confidence_in_range(self, router):
        """Test che confidence sia sempre in range valido."""
        queries = [
            "piani in ritardo",
            "chi devo controllare",
            "di cosa tratta il piano A1",
            "query ambigua forse"
        ]

        for query in queries:
            result = router.classify(query)
            conf = result["confidence"]
            assert 0 <= conf <= 1, f"Confidence {conf} fuori range per '{query}'"


class TestRouterSlotExtraction:
    """Test estrazione slot del Router."""

    @pytest.fixture
    def router(self):
        from orchestrator.router import Router
        from llm.client import LLMClient
        return Router(LLMClient())

    @pytest.mark.integration
    def test_extract_piano_code(self, router):
        """Test estrazione codice piano."""
        test_cases = [
            ("piano A1", "A1"),
            ("piano B47", "B47"),
            ("piano A22", "A22"),
        ]

        for query, expected_code in test_cases:
            result = router.classify(f"descrizione {query}")
            assert result["slots"].get("piano_code") == expected_code, \
                f"Failed for {query}"

    @pytest.mark.integration
    def test_extract_topic(self, router):
        """Test estrazione topic."""
        result = router.classify("piani che riguardano bovini")

        # topic dovrebbe essere estratto
        slots = result.get("slots", {})
        if "topic" in slots:
            assert "bovin" in slots["topic"].lower()


class TestRouterHeuristics:
    """Test heuristics del Router."""

    @pytest.fixture
    def router(self):
        from orchestrator.router import Router
        from llm.client import LLMClient
        return Router(LLMClient())

    @pytest.mark.integration
    def test_heuristic_greet_short(self, router):
        """Test heuristic per saluti brevi."""
        short_greets = ["ciao", "hey", "salve"]

        for greet in short_greets:
            result = router.classify(greet)
            assert result["intent"] == "greet", f"Failed for '{greet}'"

    @pytest.mark.integration
    def test_heuristic_help(self, router):
        """Test heuristic per aiuto."""
        help_queries = ["aiuto", "help", "cosa puoi fare"]

        for query in help_queries:
            result = router.classify(query)
            assert result["intent"] == "ask_help", f"Failed for '{query}'"
