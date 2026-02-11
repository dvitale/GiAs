"""
Test per il modulo followup_suggestions.

Import diretto del file per evitare che orchestrator/__init__.py
carichi dipendenze pesanti (graph -> tool_nodes -> pandas).
"""

import sys
import os
import importlib.util

import pytest

# Import diretto del singolo file senza passare per il package
_module_path = os.path.join(
    os.path.dirname(__file__), '..', 'orchestrator', 'followup_suggestions.py'
)
_spec = importlib.util.spec_from_file_location("followup_suggestions", _module_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

FollowUpSuggestionEngine = _mod.FollowUpSuggestionEngine
EXCLUDED_INTENTS = _mod.EXCLUDED_INTENTS
FOLLOWUP_HEADER = _mod.FOLLOWUP_HEADER
MIN_RESPONSE_LENGTH = _mod.MIN_RESPONSE_LENGTH


@pytest.fixture
def engine():
    return FollowUpSuggestionEngine()


def _make_state(intent, slots=None, tool_output=None, has_more_details=False,
                final_response="Risposta lunga di test con abbastanza caratteri per superare il minimo richiesto."):
    """Helper per creare uno state minimo."""
    return {
        "intent": intent,
        "slots": slots or {},
        "tool_output": tool_output or {"type": intent, "data": {"formatted_response": final_response}},
        "has_more_details": has_more_details,
        "final_response": final_response,
    }


# =================================================================
# Test should_append
# =================================================================

class TestShouldAppend:

    def test_excluded_intents_no_suggestions(self, engine):
        """Tutti gli intent esclusi devono restituire False."""
        for intent in EXCLUDED_INTENTS:
            state = _make_state(intent)
            assert engine.should_append(state) is False, f"Intent {intent} dovrebbe essere escluso"

    def test_two_phase_active_no_suggestions(self, engine):
        """Se two-phase e' attivo, niente suggerimenti."""
        state = _make_state("ask_piano_description", has_more_details=True)
        assert engine.should_append(state) is False

    def test_error_response_no_suggestions(self, engine):
        """Se il tool ha restituito un errore, niente suggerimenti."""
        state = _make_state(
            "ask_piano_description",
            tool_output={"type": "piano_description", "data": {"error": "Piano non trovato"}}
        )
        assert engine.should_append(state) is False

    def test_empty_response_no_suggestions(self, engine):
        """Se la risposta e' vuota, niente suggerimenti."""
        state = _make_state("ask_piano_description", final_response="")
        assert engine.should_append(state) is False

    def test_short_response_no_suggestions(self, engine):
        """Se la risposta e' troppo corta, niente suggerimenti."""
        state = _make_state("ask_piano_description", final_response="Breve.")
        assert engine.should_append(state) is False

    def test_empty_intent_no_suggestions(self, engine):
        """Se l'intent e' vuoto, niente suggerimenti."""
        state = _make_state("")
        assert engine.should_append(state) is False

    def test_valid_intent_gets_suggestions(self, engine):
        """Un intent valido con risposta sufficiente deve ricevere suggerimenti."""
        state = _make_state(
            "ask_piano_description",
            slots={"piano_code": "A1"}
        )
        assert engine.should_append(state) is True

    def test_all_non_excluded_intents_pass(self, engine):
        """Tutti gli intent non esclusi devono passare should_append."""
        non_excluded = [
            "ask_piano_description", "ask_piano_stabilimenti", "ask_piano_generic",
            "ask_piano_statistics", "search_piani_by_topic",
            "ask_priority_establishment", "ask_risk_based_priority",
            "ask_suggest_controls", "ask_delayed_plans", "check_if_plan_delayed",
            "ask_establishment_history", "ask_top_risk_activities",
            "analyze_nc_by_category"
        ]
        for intent in non_excluded:
            state = _make_state(intent)
            assert engine.should_append(state) is True, f"Intent {intent} dovrebbe passare"


# =================================================================
# Test get_suggestions
# =================================================================

class TestGetSuggestions:

    def test_piano_description_dynamic(self, engine):
        """Dopo ask_piano_description con piano_code=A1, i suggerimenti contengono A1."""
        suggestions = engine.get_suggestions(
            intent="ask_piano_description",
            slots={"piano_code": "A1"},
            tool_output={"data": {}}
        )
        assert len(suggestions) >= 1
        assert any("A1" in s["text"] for s in suggestions)
        assert any("A1" in s["query"].upper() for s in suggestions)

    def test_piano_stabilimenti_dynamic(self, engine):
        """Dopo ask_piano_stabilimenti, suggerisce descrizione e statistiche."""
        suggestions = engine.get_suggestions(
            intent="ask_piano_stabilimenti",
            slots={"piano_code": "B2"},
            tool_output={"data": {}}
        )
        assert len(suggestions) >= 1
        assert any("B2" in s["text"] for s in suggestions)

    def test_search_piani_with_matches(self, engine):
        """Dopo search con risultati, suggerisce il primo match."""
        suggestions = engine.get_suggestions(
            intent="search_piani_by_topic",
            slots={"topic": "latte"},
            tool_output={"data": {
                "matches": [
                    {"alias": "A32", "description": "Piano latte"},
                    {"alias": "B5", "description": "Altro piano"},
                ]
            }}
        )
        assert len(suggestions) >= 1
        assert any("A32" in s["text"] for s in suggestions)

    def test_search_piani_without_matches(self, engine):
        """Dopo search senza risultati, suggerisce comunque qualcosa."""
        suggestions = engine.get_suggestions(
            intent="search_piani_by_topic",
            slots={"topic": "latte"},
            tool_output={"data": {"matches": []}}
        )
        assert len(suggestions) >= 1

    def test_delayed_plans_with_worst_plan(self, engine):
        """Dopo delayed_plans, suggerisce il piano con piu' ritardo."""
        suggestions = engine.get_suggestions(
            intent="ask_delayed_plans",
            slots={},
            tool_output={"data": {
                "delayed_plans": [
                    {"indicatore": "B47", "ritardo": 15},
                    {"indicatore": "A1", "ritardo": 5},
                ]
            }}
        )
        assert len(suggestions) >= 1
        assert any("B47" in s["text"] for s in suggestions)

    def test_delayed_plans_without_data(self, engine):
        """Dopo delayed_plans senza dati specifici, suggerisce comunque."""
        suggestions = engine.get_suggestions(
            intent="ask_delayed_plans",
            slots={},
            tool_output={"data": {"delayed_plans": []}}
        )
        assert len(suggestions) >= 1

    def test_piano_statistics_with_piano(self, engine):
        """Con piano_code, suggerisce azioni specifiche per quel piano."""
        suggestions = engine.get_suggestions(
            intent="ask_piano_statistics",
            slots={"piano_code": "C3"},
            tool_output={"data": {}}
        )
        assert any("C3" in s["text"] for s in suggestions)

    def test_piano_statistics_without_piano(self, engine):
        """Senza piano_code, suggerisce azioni generali."""
        suggestions = engine.get_suggestions(
            intent="ask_piano_statistics",
            slots={},
            tool_output={"data": {}}
        )
        assert len(suggestions) >= 1
        assert any("ritardo" in s["query"].lower() or "rischiose" in s["query"].lower()
                    for s in suggestions)

    def test_max_3_suggestions(self, engine):
        """Nessun intent genera piu' di 3 suggerimenti."""
        all_intents = [
            "ask_piano_description", "ask_piano_stabilimenti", "ask_piano_generic",
            "ask_piano_statistics", "search_piani_by_topic",
            "ask_priority_establishment", "ask_risk_based_priority",
            "ask_suggest_controls", "ask_delayed_plans", "check_if_plan_delayed",
            "ask_establishment_history", "ask_top_risk_activities",
            "analyze_nc_by_category"
        ]
        for intent in all_intents:
            suggestions = engine.get_suggestions(
                intent=intent,
                slots={"piano_code": "A1", "topic": "test"},
                tool_output={"data": {
                    "matches": [{"alias": "X1"}],
                    "delayed_plans": [{"indicatore": "Y1"}]
                }}
            )
            assert len(suggestions) <= 3, f"Intent {intent} genera {len(suggestions)} suggerimenti (max 3)"

    def test_unknown_intent_no_suggestions(self, engine):
        """Un intent sconosciuto non genera suggerimenti."""
        suggestions = engine.get_suggestions(
            intent="intent_inesistente",
            slots={},
            tool_output={"data": {}}
        )
        assert suggestions == []

    def test_piano_description_no_piano_code(self, engine):
        """Senza piano_code, piano_description non genera suggerimenti."""
        suggestions = engine.get_suggestions(
            intent="ask_piano_description",
            slots={},
            tool_output={"data": {}}
        )
        assert suggestions == []

    def test_static_intents_always_return(self, engine):
        """Gli intent statici (senza slot richiesti) restituiscono sempre suggerimenti."""
        static_intents = [
            "ask_priority_establishment", "ask_risk_based_priority",
            "ask_suggest_controls", "check_if_plan_delayed",
            "ask_establishment_history", "ask_top_risk_activities",
            "analyze_nc_by_category"
        ]
        for intent in static_intents:
            suggestions = engine.get_suggestions(
                intent=intent,
                slots={},
                tool_output={"data": {}}
            )
            assert len(suggestions) >= 1, f"Intent {intent} dovrebbe avere almeno 1 suggerimento"


# =================================================================
# Test format_suggestions
# =================================================================

class TestFormatSuggestions:

    def test_format_markdown_links(self, engine):
        """I suggerimenti sono formattati come link markdown cliccabili."""
        suggestions = [
            {"text": "Stabilimenti del piano A1", "query": "stabilimenti piano A1"},
            {"text": "Piani in ritardo", "query": "piani in ritardo"},
        ]
        result = engine.format_suggestions(suggestions)

        assert FOLLOWUP_HEADER in result
        assert "- [Stabilimenti del piano A1]" in result
        assert "- [Piani in ritardo]" in result

    def test_format_empty_returns_empty(self, engine):
        """Lista vuota produce stringa vuota."""
        assert engine.format_suggestions([]) == ""

    def test_format_single_suggestion(self, engine):
        """Un singolo suggerimento e' formattato correttamente."""
        suggestions = [{"text": "Test", "query": "test query"}]
        result = engine.format_suggestions(suggestions)

        assert "- [Test]" in result
        assert result.count("- [") == 1

    def test_format_starts_with_separator(self, engine):
        """Il blocco inizia con ---."""
        suggestions = [{"text": "Test", "query": "test"}]
        result = engine.format_suggestions(suggestions)
        assert "\n\n---\n" in result
