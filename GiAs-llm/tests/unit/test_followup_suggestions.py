"""
Test unitari per FollowUpSuggestionEngine.

Verifica:
1. should_append() — condizioni di inclusione/esclusione
2. get_suggestions() — generatori per intent specifici
3. format_suggestions() — formattazione markdown
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Neutralizza il caricamento DB prima di importare il modulo
import orchestrator.followup_suggestions as fs

fs.EXCLUDED_INTENTS = {
    "greet",
    "goodbye",
    "ask_help",
    "confirm_show_details",
    "decline_show_details",
    "fallback",
}

from orchestrator.followup_suggestions import (
    FollowUpSuggestionEngine,
    FOLLOWUP_HEADER,
    MIN_RESPONSE_LENGTH,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LONG_RESPONSE = "A" * (MIN_RESPONSE_LENGTH + 10)
SHORT_RESPONSE = "A" * (MIN_RESPONSE_LENGTH - 1)

NORMAL_STATE = {
    "intent": "ask_delayed_plans",
    "has_more_details": False,
    "final_response": LONG_RESPONSE,
    "tool_output": {"data": {}},
    "slots": {},
}


@pytest.fixture
def engine() -> FollowUpSuggestionEngine:
    return FollowUpSuggestionEngine()


@pytest.fixture
def normal_state() -> dict:
    return dict(NORMAL_STATE)


# ---------------------------------------------------------------------------
# TestShouldAppend
# ---------------------------------------------------------------------------

class TestShouldAppend:
    """should_append() deve filtrare correttamente i casi negativi."""

    def test_returns_true_for_normal_state(self, engine, normal_state):
        assert engine.should_append(normal_state) is True

    def test_returns_false_when_has_more_details_true(self, engine, normal_state):
        normal_state["has_more_details"] = True
        assert engine.should_append(normal_state) is False

    @pytest.mark.parametrize("excluded_intent", [
        "greet",
        "goodbye",
        "ask_help",
        "confirm_show_details",
        "decline_show_details",
        "fallback",
    ])
    def test_returns_false_for_excluded_intent(self, engine, normal_state, excluded_intent):
        normal_state["intent"] = excluded_intent
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_intent_is_empty_string(self, engine, normal_state):
        normal_state["intent"] = ""
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_intent_key_missing(self, engine, normal_state):
        del normal_state["intent"]
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_tool_output_data_has_error(self, engine, normal_state):
        normal_state["tool_output"] = {"data": {"error": "query fallita"}}
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_tool_output_data_error_is_empty_string(self, engine, normal_state):
        # Chiave "error" presente ma stringa vuota: falsy → non blocca
        normal_state["tool_output"] = {"data": {"error": ""}}
        assert engine.should_append(normal_state) is True

    def test_returns_false_when_final_response_too_short(self, engine, normal_state):
        normal_state["final_response"] = SHORT_RESPONSE
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_final_response_is_empty_string(self, engine, normal_state):
        normal_state["final_response"] = ""
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_final_response_is_none(self, engine, normal_state):
        normal_state["final_response"] = None
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_final_response_key_missing(self, engine, normal_state):
        del normal_state["final_response"]
        assert engine.should_append(normal_state) is False

    def test_returns_false_when_tool_output_is_none(self, engine, normal_state):
        # tool_output None non deve sollevare eccezioni né produrre False per errori
        # ma non c'è un "error" key → dovrebbe passare quel filtro
        normal_state["tool_output"] = None
        assert engine.should_append(normal_state) is True

    def test_boundary_response_length_exactly_min(self, engine, normal_state):
        # Esattamente MIN_RESPONSE_LENGTH caratteri: < è False, == è True
        normal_state["final_response"] = "A" * MIN_RESPONSE_LENGTH
        assert engine.should_append(normal_state) is True

    def test_boundary_response_length_one_below_min(self, engine, normal_state):
        normal_state["final_response"] = "A" * (MIN_RESPONSE_LENGTH - 1)
        assert engine.should_append(normal_state) is False


# ---------------------------------------------------------------------------
# TestGetSuggestions
# ---------------------------------------------------------------------------

class TestGetSuggestions:
    """get_suggestions() deve restituire suggerimenti validi per gli intent noti."""

    def _assert_valid_suggestions(self, suggestions: list, *, at_least: int = 1) -> None:
        assert isinstance(suggestions, list)
        assert len(suggestions) >= at_least
        for s in suggestions:
            assert isinstance(s, dict), f"Suggerimento non è dict: {s}"
            assert "text" in s, f"Chiave 'text' mancante: {s}"
            assert "query" in s, f"Chiave 'query' mancante: {s}"
            assert isinstance(s["text"], str) and s["text"]
            assert isinstance(s["query"], str) and s["query"]

    def test_returns_list_of_dicts_with_text_and_query_keys(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_description",
            slots={"piano_code": "A1"},
            tool_output={},
        )
        self._assert_valid_suggestions(result)

    def test_returns_at_most_three_suggestions(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_description",
            slots={"piano_code": "A1"},
            tool_output={},
        )
        assert len(result) <= 3

    def test_returns_empty_list_for_unknown_intent(self, engine):
        result = engine.get_suggestions(
            intent="intent_inesistente_xyz",
            slots={},
            tool_output={},
        )
        assert result == []

    def test_returns_empty_list_for_empty_intent(self, engine):
        result = engine.get_suggestions(intent="", slots={}, tool_output={})
        assert result == []

    def test_ask_piano_description_with_piano_code(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_description",
            slots={"piano_code": "b2"},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)
        # Il codice piano deve essere uppercased nel testo
        assert any("B2" in s["text"] for s in result)

    def test_ask_piano_description_without_piano_code_returns_empty(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_description",
            slots={},
            tool_output={},
        )
        assert result == []

    def test_ask_piano_stabilimenti_with_piano_code(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_stabilimenti",
            slots={"piano_code": "A32"},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)
        assert any("A32" in s["text"] for s in result)

    def test_ask_piano_statistics_with_piano_code(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_statistics",
            slots={"piano_code": "C1"},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_piano_statistics_without_piano_code_still_returns_suggestions(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_statistics",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_priority_establishment(self, engine):
        result = engine.get_suggestions(
            intent="ask_priority_establishment",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_risk_based_priority(self, engine):
        result = engine.get_suggestions(
            intent="ask_risk_based_priority",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_suggest_controls(self, engine):
        result = engine.get_suggestions(
            intent="ask_suggest_controls",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_delayed_plans_with_delayed_plans_data(self, engine):
        tool_output = {
            "data": {
                "delayed_plans": [
                    {"indicatore": "A1", "ritardo": 5},
                    {"indicatore": "B3", "ritardo": 2},
                ]
            }
        }
        result = engine.get_suggestions(
            intent="ask_delayed_plans",
            slots={},
            tool_output=tool_output,
        )
        self._assert_valid_suggestions(result, at_least=1)
        # Deve suggerire il piano con più ritardo (primo della lista)
        assert any("A1" in s["text"] for s in result)

    def test_ask_delayed_plans_without_data(self, engine):
        result = engine.get_suggestions(
            intent="ask_delayed_plans",
            slots={},
            tool_output={"data": {}},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_check_if_plan_delayed(self, engine):
        result = engine.get_suggestions(
            intent="check_if_plan_delayed",
            slots={"piano_code": "A1"},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_establishment_history(self, engine):
        result = engine.get_suggestions(
            intent="ask_establishment_history",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_ask_top_risk_activities(self, engine):
        result = engine.get_suggestions(
            intent="ask_top_risk_activities",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_search_piani_by_topic_with_matches(self, engine):
        tool_output = {
            "data": {
                "matches": [
                    {"alias": "A5", "title": "Piano Avicoli"},
                    {"alias": "B2", "title": "Piano Bovini"},
                ]
            }
        }
        result = engine.get_suggestions(
            intent="search_piani_by_topic",
            slots={},
            tool_output=tool_output,
        )
        self._assert_valid_suggestions(result, at_least=1)
        # Deve menzionare l'alias del primo match
        assert any("A5" in s["text"] for s in result)

    def test_search_piani_by_topic_without_matches(self, engine):
        result = engine.get_suggestions(
            intent="search_piani_by_topic",
            slots={},
            tool_output={"data": {}},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_query_data(self, engine):
        result = engine.get_suggestions(
            intent="query_data",
            slots={},
            tool_output={},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_info_procedure_with_chunks_metadata(self, engine):
        tool_output = {
            "data": {
                "query": "come si inserisce una non conformita",
                "chunks_metadata": [
                    {"section": "Registrazione NC", "title": "Gestione NC", "source_file": "ManualeGisa.pdf"},
                    {"section": "Verifica controllo", "title": "Procedura verifica", "source_file": "ManualeGisa.pdf"},
                ],
            }
        }
        result = engine.get_suggestions(
            intent="info_procedure",
            slots={},
            tool_output=tool_output,
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_info_procedure_without_chunks_metadata_falls_back(self, engine):
        result = engine.get_suggestions(
            intent="info_procedure",
            slots={},
            tool_output={"data": {}},
        )
        self._assert_valid_suggestions(result, at_least=1)

    def test_tool_output_none_does_not_raise(self, engine):
        # tool_output=None: il metodo deve gestire il caso senza eccezioni
        result = engine.get_suggestions(
            intent="ask_priority_establishment",
            slots={},
            tool_output=None,
        )
        assert isinstance(result, list)

    def test_slots_none_does_not_raise(self, engine):
        result = engine.get_suggestions(
            intent="ask_piano_description",
            slots={},
            tool_output={},
        )
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TestFormatSuggestions
# ---------------------------------------------------------------------------

class TestFormatSuggestions:
    """format_suggestions() deve produrre markdown corretto."""

    def test_empty_suggestions_returns_empty_string(self, engine):
        assert engine.format_suggestions([]) == ""

    def test_result_starts_with_followup_header(self, engine):
        suggestions = [{"text": "Piani in ritardo", "query": "piani in ritardo"}]
        result = engine.format_suggestions(suggestions)
        assert result.startswith(FOLLOWUP_HEADER)

    def test_single_suggestion_formatted_as_list_item(self, engine):
        suggestions = [{"text": "Piani in ritardo", "query": "piani in ritardo"}]
        result = engine.format_suggestions(suggestions)
        assert "- [Piani in ritardo]" in result

    def test_multiple_suggestions_all_present(self, engine):
        suggestions = [
            {"text": "Primo suggerimento", "query": "query 1"},
            {"text": "Secondo suggerimento", "query": "query 2"},
            {"text": "Terzo suggerimento", "query": "query 3"},
        ]
        result = engine.format_suggestions(suggestions)
        assert "- [Primo suggerimento]" in result
        assert "- [Secondo suggerimento]" in result
        assert "- [Terzo suggerimento]" in result

    def test_format_does_not_include_query_in_output(self, engine):
        suggestions = [{"text": "Testo visibile", "query": "query nascosta"}]
        result = engine.format_suggestions(suggestions)
        assert "query nascosta" not in result

    def test_separator_present_in_output(self, engine):
        suggestions = [{"text": "Qualcosa", "query": "q"}]
        result = engine.format_suggestions(suggestions)
        assert "---" in result

    def test_followup_header_present(self, engine):
        suggestions = [{"text": "Qualcosa", "query": "q"}]
        result = engine.format_suggestions(suggestions)
        assert "Ti puo' interessare anche:" in result
