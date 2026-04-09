"""
Test unitari per orchestrator/two_phase.py.

Verifica:
1. Trigger two-phase quando item_count > threshold
2. Nessuna modifica quando item_count <= threshold
3. Nessuna modifica quando result non ha 'formatted_response'
4. Uso di full_formatted_response in detail_context
5. Soglia di default (5) per intent sconosciuti
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import orchestrator.two_phase as tp
from orchestrator.two_phase import apply_two_phase_check, TWO_PHASE_SUFFIX


def _make_state() -> dict:
    """Costruisce uno stato conversazione minimale per i test."""
    return {
        "intent": "test_intent",
        "slots": {},
        "has_more_details": False,
        "detail_context": None,
    }


def _make_result(formatted_response: str = "Risposta completa.") -> dict:
    """Costruisce un risultato tool minimale per i test."""
    return {"formatted_response": formatted_response, "data": []}


@pytest.fixture(autouse=True)
def patch_thresholds():
    """Imposta soglie di test prima di ogni test e ripristina dopo."""
    original = tp.TWO_PHASE_THRESHOLDS
    tp.TWO_PHASE_THRESHOLDS = {"test_intent": 3, "strict_intent": 1}
    yield
    tp.TWO_PHASE_THRESHOLDS = original


class TestTwoPhaseTriggered:
    """item_count > threshold: state e result devono essere modificati."""

    def test_has_more_details_set_true(self):
        """has_more_details deve diventare True quando il trigger scatta."""
        state = _make_state()
        apply_two_phase_check(state, "test_intent", _make_result(), item_count=4, summary_text="Sommario.")
        assert state["has_more_details"] is True

    def test_detail_context_populated(self):
        """detail_context deve contenere intent e item_count."""
        state = _make_state()
        apply_two_phase_check(state, "test_intent", _make_result(), item_count=4, summary_text="Sommario.")
        ctx = state["detail_context"]
        assert ctx is not None
        assert ctx["intent"] == "test_intent"
        assert ctx["item_count"] == 4

    def test_detail_context_contains_formatted_response(self):
        """detail_context.formatted_response deve corrispondere alla risposta originale."""
        state = _make_state()
        result = _make_result("Risposta originale lunga.")
        apply_two_phase_check(state, "test_intent", result, item_count=4, summary_text="Sommario.")
        assert state["detail_context"]["formatted_response"] == "Risposta originale lunga."

    def test_result_formatted_response_replaced_with_summary_and_suffix(self):
        """formatted_response nel result deve essere sostituita con sommario + suffix."""
        state = _make_state()
        result = _make_result("Risposta originale lunga.")
        apply_two_phase_check(state, "test_intent", result, item_count=4, summary_text="Sommario breve.")
        assert result["formatted_response"] == "Sommario breve." + TWO_PHASE_SUFFIX

    def test_two_phase_suffix_content(self):
        """Il suffix deve contenere la domanda di conferma dettagli."""
        assert "Vuoi che ti mostri tutti i dettagli?" in TWO_PHASE_SUFFIX

    def test_other_result_keys_preserved(self):
        """Le chiavi extra del result non devono essere alterate."""
        state = _make_state()
        result = {"formatted_response": "Risposta.", "data": [1, 2, 3], "count": 4}
        apply_two_phase_check(state, "test_intent", result, item_count=10, summary_text="Sommario.")
        assert result["data"] == [1, 2, 3]
        assert result["count"] == 4

    def test_trigger_at_exactly_threshold_plus_one(self):
        """Il trigger deve scattare a threshold+1 (> non >=)."""
        state = _make_state()
        result = _make_result()
        # threshold per test_intent = 3, quindi 4 deve triggerare
        apply_two_phase_check(state, "test_intent", result, item_count=4, summary_text="Sommario.")
        assert state["has_more_details"] is True

    def test_strict_intent_triggers_at_two(self):
        """Intent con soglia=1 deve triggerare con item_count=2."""
        state = _make_state()
        result = _make_result()
        apply_two_phase_check(state, "strict_intent", result, item_count=2, summary_text="Sommario.")
        assert state["has_more_details"] is True

    def test_returns_modified_result(self):
        """apply_two_phase_check deve restituire il result (modificato)."""
        state = _make_state()
        result = _make_result()
        returned = apply_two_phase_check(state, "test_intent", result, item_count=4, summary_text="S.")
        assert returned is result


class TestTwoPhaseNotTriggered:
    """item_count <= threshold: nessuna modifica a state o result."""

    def test_state_unchanged_at_threshold(self):
        """item_count == threshold non deve triggerare (controllo > non >=)."""
        state = _make_state()
        result = _make_result("Risposta.")
        apply_two_phase_check(state, "test_intent", result, item_count=3, summary_text="Sommario.")
        assert state["has_more_details"] is False
        assert state["detail_context"] is None

    def test_state_unchanged_below_threshold(self):
        """item_count < threshold non deve triggerare."""
        state = _make_state()
        result = _make_result("Risposta.")
        apply_two_phase_check(state, "test_intent", result, item_count=1, summary_text="Sommario.")
        assert state["has_more_details"] is False
        assert state["detail_context"] is None

    def test_result_unchanged_below_threshold(self):
        """formatted_response nel result non deve essere modificata."""
        state = _make_state()
        original_response = "Risposta originale."
        result = _make_result(original_response)
        apply_two_phase_check(state, "test_intent", result, item_count=2, summary_text="Sommario.")
        assert result["formatted_response"] == original_response

    def test_returns_result_unchanged(self):
        """Il result restituito deve essere identico all'originale."""
        state = _make_state()
        result = _make_result("Risposta.")
        returned = apply_two_phase_check(state, "test_intent", result, item_count=0, summary_text="S.")
        assert returned is result
        assert returned["formatted_response"] == "Risposta."

    def test_item_count_zero(self):
        """item_count=0 non deve mai triggerare."""
        state = _make_state()
        apply_two_phase_check(state, "test_intent", _make_result(), item_count=0, summary_text="S.")
        assert state["has_more_details"] is False


class TestTwoPhaseNoFormattedResponse:
    """result senza chiave 'formatted_response': nessuna modifica."""

    def test_state_unchanged_without_formatted_response(self):
        """State non deve essere modificato se result non ha formatted_response."""
        state = _make_state()
        result = {"data": ["a", "b", "c", "d", "e"]}  # nessuna formatted_response
        apply_two_phase_check(state, "test_intent", result, item_count=10, summary_text="S.")
        assert state["has_more_details"] is False
        assert state["detail_context"] is None

    def test_result_unchanged_without_formatted_response(self):
        """result senza formatted_response non deve essere modificato."""
        state = _make_state()
        result = {"only_data": True}
        original_result = dict(result)
        apply_two_phase_check(state, "test_intent", result, item_count=100, summary_text="S.")
        assert result == original_result

    def test_returns_result_without_formatted_response(self):
        """Il result viene comunque restituito anche senza formatted_response."""
        state = _make_state()
        result = {"only_data": True}
        returned = apply_two_phase_check(state, "test_intent", result, item_count=100, summary_text="S.")
        assert returned is result

    def test_empty_result_dict(self):
        """Result vuoto non deve causare errori."""
        state = _make_state()
        result = {}
        apply_two_phase_check(state, "test_intent", result, item_count=10, summary_text="S.")
        assert state["has_more_details"] is False


class TestTwoPhaseFullFormattedResponse:
    """full_formatted_response fornita: usata in detail_context al posto di result['formatted_response']."""

    def test_full_formatted_response_stored_in_detail_context(self):
        """detail_context deve contenere full_formatted_response quando fornita."""
        state = _make_state()
        result = _make_result("Risposta troncata (100 item).")
        full_response = "Risposta completa con tutti i 200 item elencati."
        apply_two_phase_check(
            state, "test_intent", result,
            item_count=4, summary_text="Sommario.",
            full_formatted_response=full_response
        )
        assert state["detail_context"]["formatted_response"] == full_response

    def test_result_formatted_response_replaced_with_summary(self):
        """La formatted_response nel result deve essere sostituita con il sommario anche con full."""
        state = _make_state()
        result = _make_result("Risposta troncata.")
        apply_two_phase_check(
            state, "test_intent", result,
            item_count=4, summary_text="Sommario compatto.",
            full_formatted_response="Risposta estesa."
        )
        assert result["formatted_response"] == "Sommario compatto." + TWO_PHASE_SUFFIX

    def test_without_full_formatted_response_uses_result(self):
        """Se full_formatted_response è None, detail_context usa result['formatted_response']."""
        state = _make_state()
        result = _make_result("Risposta dal result.")
        apply_two_phase_check(
            state, "test_intent", result,
            item_count=4, summary_text="Sommario.",
            full_formatted_response=None
        )
        assert state["detail_context"]["formatted_response"] == "Risposta dal result."

    def test_full_formatted_response_default_is_none(self):
        """Il parametro full_formatted_response deve essere opzionale (default None)."""
        state = _make_state()
        result = _make_result("Risposta.")
        # Non deve sollevare eccezioni se il parametro è omesso
        apply_two_phase_check(state, "test_intent", result, item_count=4, summary_text="S.")
        assert state["detail_context"]["formatted_response"] == "Risposta."


class TestTwoPhaseDefaultThreshold:
    """Intent sconosciuto deve usare la soglia di default (5)."""

    def test_unknown_intent_uses_default_threshold_5(self):
        """item_count=6 deve triggerare con un intent non presente nel dizionario."""
        state = _make_state()
        result = _make_result()
        apply_two_phase_check(state, "intent_sconosciuto", result, item_count=6, summary_text="S.")
        assert state["has_more_details"] is True

    def test_unknown_intent_no_trigger_at_5(self):
        """item_count=5 NON deve triggerare (soglia default è 5, il controllo è >)."""
        state = _make_state()
        result = _make_result("Risposta.")
        apply_two_phase_check(state, "intent_sconosciuto", result, item_count=5, summary_text="S.")
        assert state["has_more_details"] is False

    def test_unknown_intent_no_trigger_below_default(self):
        """item_count < 5 non deve triggerare per intent sconosciuto."""
        state = _make_state()
        result = _make_result("Risposta.")
        apply_two_phase_check(state, "intent_non_registrato", result, item_count=3, summary_text="S.")
        assert state["has_more_details"] is False
        assert result["formatted_response"] == "Risposta."

    def test_multiple_unknown_intents_all_use_default(self):
        """Tutti gli intent non in dizionario devono usare la stessa soglia di default."""
        for intent_name in ["xyz", "qualcosa", "nuovo_intent_futuro"]:
            state = _make_state()
            result = _make_result()
            apply_two_phase_check(state, intent_name, result, item_count=6, summary_text="S.")
            assert state["has_more_details"] is True, \
                f"intent '{intent_name}' non ha usato la soglia di default"
