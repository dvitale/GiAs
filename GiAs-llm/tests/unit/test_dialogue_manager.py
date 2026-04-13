"""
Test unitari per il Dialogue Manager.

Verifica le regole decisionali di evaluate() e le funzioni helper
senza dipendenze da DB, LLM o tool_nodes.

Strategia di isolamento:
- _load_dm_metadata viene patchato per iniettare SELF_SUFFICIENT_INTENTS
  e REQUIRED_SLOTS controllati.
- _resolve_tool viene patchato per evitare l'import di tool_nodes.
- get_intent_metadata viene patchato per evitare query al DB.
"""

import sys
import os
import time
import pytest
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import orchestrator.dialogue_manager as dm_module
from orchestrator.dialogue_manager import (
    evaluate,
    is_oppure,
    is_refinement,
    is_vague,
    _get_missing_slots,
    DialogueManagerResult,
    CONFIDENCE_HIGH,
    CONFIDENCE_MIN,
    CONFIDENCE_AMBIGUITY_DELTA,
)

# ---------------------------------------------------------------------------
# Test metadata injected for all tests
# ---------------------------------------------------------------------------

_TEST_SELF_SUFFICIENT = {
    "greet",
    "goodbye",
    "ask_help",
    "ask_delayed_plans",
}

_TEST_REQUIRED_SLOTS: Dict[str, List[str]] = {
    "ask_piano_description": ["piano_code"],
    "search_piani_by_topic": ["topic"],
    "ask_establishment_history": [
        "num_registrazione",
        "numero_riconoscimento",
        "partita_iva",
        "ragione_sociale",
    ],
}


def _fresh_state(**overrides) -> Dict[str, Any]:
    """Crea un DialogueState pulito con campi minimi."""
    base: Dict[str, Any] = {
        "turn_count": 0,
        "timestamp": time.time(),
        "slots": {},
        "confirmed_intent": None,
        "missing_slots": None,
        "last_tool_intent": None,
        "last_tool_slots": None,
        "filters": {},
        "confirmed_strategy_id": None,
        "intent_candidates": [],
    }
    base.update(overrides)
    return base


def _cand(intent: str, confidence: float, slots: Dict[str, Any] = None) -> Dict[str, Any]:
    """Scorciatoia per creare un IntentCandidate."""
    return {"intent": intent, "confidence": confidence, "slots": slots or {}}


# ---------------------------------------------------------------------------
# Fixture comune: patcha tutto ciò che dipende da DB/tool_nodes
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_dm_externals():
    """
    Resetta i globali lazy e patcha le dipendenze esterne prima di ogni test.
    Autouse=True: attivo per ogni test nella sessione.
    """
    dm_module.SELF_SUFFICIENT_INTENTS = None
    dm_module.REQUIRED_SLOTS = None

    with patch.object(
        dm_module, "_load_dm_metadata",
        return_value=(_TEST_SELF_SUFFICIENT, _TEST_REQUIRED_SLOTS),
    ), patch.object(
        dm_module, "_resolve_tool",
        side_effect=lambda intent: f"{intent}_tool",
    ), patch(
        "orchestrator.intent_metadata.get_intent_metadata",
        return_value=None,
    ), patch(
        "configs.config.AppConfig.is_pre_execution_confirmation_enabled",
        return_value=False,
    ):
        yield

    # Assicura reset post-test per evitare contaminazione tra suite
    dm_module.SELF_SUFFICIENT_INTENTS = None
    dm_module.REQUIRED_SLOTS = None


# ===========================================================================
# 1. TestHelperFunctions
# ===========================================================================

class TestHelperFunctions:
    """Verifica is_oppure, is_refinement, is_vague."""

    # --- is_oppure ---

    def test_oppure_exact(self):
        assert is_oppure("oppure") is True

    def test_oppure_con_punto_interrogativo(self):
        assert is_oppure("oppure?") is True

    def test_oppure_alternative(self):
        assert is_oppure("alternative") is True

    def test_oppure_altrimenti(self):
        assert is_oppure("altrimenti") is True

    def test_oppure_invece(self):
        assert is_oppure("invece") is True

    def test_oppure_false_frase_lunga(self):
        assert is_oppure("oppure potresti dirmi altro?") is False

    def test_oppure_false_parola_normale(self):
        assert is_oppure("piani in ritardo") is False

    def test_oppure_case_insensitive(self):
        assert is_oppure("OPPURE") is True

    # --- is_refinement ---

    def test_refinement_nel_comune(self):
        assert is_refinement("mostrami solo nel comune di Napoli") is True

    def test_refinement_primi_n(self):
        assert is_refinement("mostrami i primi 10") is True

    def test_refinement_top_n(self):
        assert is_refinement("top 5 per rischio") is True

    def test_refinement_rifai_ricerca(self):
        assert is_refinement("rifai la ricerca") is True

    def test_refinement_false_query_normale(self):
        assert is_refinement("piani in ritardo per Napoli") is False

    def test_refinement_false_saluto(self):
        assert is_refinement("ciao") is False

    # --- is_vague ---

    def test_vague_come_mi_organizzo(self):
        assert is_vague("come mi organizzo?") is True

    def test_vague_cosa_devo_fare(self):
        assert is_vague("cosa devo fare?") is True

    def test_vague_da_dove_inizio(self):
        assert is_vague("da dove inizio?") is True

    def test_vague_aiutami_a_capire(self):
        assert is_vague("aiutami a capire") is True

    def test_vague_consigli(self):
        assert is_vague("consigli") is True

    def test_vague_false_query_specifica(self):
        assert is_vague("piani in ritardo per l'ASL di Napoli") is False

    def test_vague_false_saluto(self):
        assert is_vague("ciao") is False


# ===========================================================================
# 2. TestGetMissingSlots
# ===========================================================================

class TestGetMissingSlots:
    """Verifica _get_missing_slots per i diversi intent."""

    def test_no_required_slots(self):
        """Intent senza slot obbligatori: sempre lista vuota."""
        missing = _get_missing_slots("ask_delayed_plans", {})
        assert missing == []

    def test_required_slot_present(self):
        missing = _get_missing_slots("ask_piano_description", {"piano_code": "A1"})
        assert missing == []

    def test_required_slot_absent(self):
        missing = _get_missing_slots("ask_piano_description", {})
        assert "piano_code" in missing

    def test_required_slot_empty_string_counts_as_missing(self):
        missing = _get_missing_slots("ask_piano_description", {"piano_code": ""})
        assert "piano_code" in missing

    def test_establishment_history_no_slots_returns_all(self):
        """ask_establishment_history richiede almeno UN identificatore."""
        missing = _get_missing_slots("ask_establishment_history", {})
        assert len(missing) == 4  # tutti e quattro gli identificatori

    def test_establishment_history_one_slot_sufficient(self):
        """Un solo identificatore valido soddisfa ask_establishment_history."""
        missing = _get_missing_slots(
            "ask_establishment_history", {"ragione_sociale": "Rossi SRL"}
        )
        assert missing == []

    def test_establishment_history_partita_iva_sufficient(self):
        missing = _get_missing_slots(
            "ask_establishment_history", {"partita_iva": "01234567890"}
        )
        assert missing == []

    def test_unknown_intent_no_required(self):
        """Intent non in REQUIRED_SLOTS non ha slot obbligatori."""
        missing = _get_missing_slots("intent_inesistente", {})
        assert missing == []


# ===========================================================================
# 3. TestEvaluateHighConfidence
# ===========================================================================

class TestEvaluateHighConfidence:
    """Confidence >= CONFIDENCE_HIGH e slot presenti → action='execute'."""

    def test_high_confidence_no_slots_required(self):
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.intent == "ask_delayed_plans"
        assert result.target_tool == "ask_delayed_plans_tool"

    def test_high_confidence_updates_turn_count(self):
        state = _fresh_state(turn_count=2)
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, state)

        assert result.updated_state["turn_count"] == 3

    def test_high_confidence_sets_confirmed_intent(self):
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.updated_state["confirmed_intent"] == "ask_delayed_plans"

    def test_high_confidence_slots_from_candidate_merged(self):
        """Slot del candidato vengono mergiati nello stato."""
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH, {"piano_code": "A1"})]
        result = evaluate("descrivimi il piano A1", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.slots.get("piano_code") == "A1"

    def test_high_confidence_slots_from_extracted_merged(self):
        """extracted_slots vengono mergiati con quelli del candidato."""
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH, {})]
        result = evaluate(
            "descrivimi il piano B2",
            candidates,
            {"piano_code": "B2"},
            _fresh_state(),
        )
        assert result.action == "execute"
        assert result.slots.get("piano_code") == "B2"

    def test_high_confidence_above_threshold_boundary(self):
        """Confidence esattamente uguale a CONFIDENCE_HIGH è sufficiente."""
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani ritardo", candidates, {}, _fresh_state())
        assert result.action == "execute"


# ===========================================================================
# 4. TestEvaluateMissingSlots
# ===========================================================================

class TestEvaluateMissingSlots:
    """Alta confidence ma slot mancante → action='ask_user'."""

    def test_missing_required_slot_triggers_ask(self):
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("descrivi il piano", candidates, {}, _fresh_state())

        assert result.action == "ask_user"
        assert result.question is not None
        assert len(result.question) > 0

    def test_missing_slot_stored_in_state(self):
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("descrivi il piano", candidates, {}, _fresh_state())

        assert "piano_code" in result.updated_state["missing_slots"]

    def test_confirmed_intent_stored_when_slot_missing(self):
        """L'intent viene salvato nello stato anche quando mancano slot."""
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("descrivi il piano", candidates, {}, _fresh_state())

        assert result.updated_state["confirmed_intent"] == "ask_piano_description"

    def test_establishment_history_missing_all_identifiers(self):
        """ask_establishment_history chiede identificatore se nessuno è presente."""
        candidates = [_cand("ask_establishment_history", CONFIDENCE_HIGH)]
        result = evaluate("storico stabilimento", candidates, {}, _fresh_state())

        assert result.action == "ask_user"
        # La domanda deve menzionare almeno uno degli identificatori
        assert result.question is not None


# ===========================================================================
# 5. TestEvaluateSelfSufficient
# ===========================================================================

class TestEvaluateSelfSufficient:
    """Intent self-sufficient → esegue anche senza slot."""

    def test_greet_executes_without_slots(self):
        candidates = [_cand("greet", CONFIDENCE_HIGH)]
        result = evaluate("ciao", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.intent == "greet"

    def test_goodbye_executes_without_slots(self):
        candidates = [_cand("goodbye", CONFIDENCE_HIGH)]
        result = evaluate("arrivederci", candidates, {}, _fresh_state())

        assert result.action == "execute"

    def test_ask_delayed_plans_self_sufficient(self):
        """ask_delayed_plans è self-sufficient nel set di test."""
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.target_tool == "ask_delayed_plans_tool"

    def test_self_sufficient_with_medium_confidence(self):
        """Self-sufficient + confidence media (sopra MIN ma sotto HIGH) → execute nel default path."""
        medium = (CONFIDENCE_HIGH + CONFIDENCE_MIN) / 2
        candidates = [_cand("greet", medium)]
        result = evaluate("ciao", candidates, {}, _fresh_state())
        # Con medium confidence, cade nel default path che esegue comunque per self-sufficient
        assert result.action == "execute"


# ===========================================================================
# 6. TestEvaluateLowConfidence
# ===========================================================================

class TestEvaluateLowConfidence:
    """Confidence < CONFIDENCE_MIN → action='fallback'."""

    def test_below_min_confidence_fallback(self):
        low = CONFIDENCE_MIN - 0.05
        candidates = [_cand("ask_piano_description", low)]
        result = evaluate("boh", candidates, {}, _fresh_state())

        assert result.action == "fallback"

    def test_zero_confidence_fallback(self):
        candidates = [_cand("ask_delayed_plans", 0.0)]
        result = evaluate("???", candidates, {}, _fresh_state())

        assert result.action == "fallback"

    def test_exactly_at_min_is_not_fallback(self):
        """Confidence esattamente a CONFIDENCE_MIN: non è fallback (cade nel default path)."""
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_MIN)]
        result = evaluate("piani", candidates, {}, _fresh_state())

        # Con un solo candidato a CONFIDENCE_MIN, _rule_ambiguous non scatta
        # e il default path esegue per intent self-sufficient
        assert result.action == "execute"


# ===========================================================================
# 7. TestEvaluateAmbiguous
# ===========================================================================

class TestEvaluateAmbiguous:
    """Due candidati con delta confidence < AMBIGUITY_DELTA → disambiguazione."""

    def test_ambiguous_two_candidates_close_confidence(self):
        top = CONFIDENCE_MIN + 0.10
        second = top - (CONFIDENCE_AMBIGUITY_DELTA / 2)  # delta stretto
        candidates = [
            _cand("ask_piano_description", top),
            _cand("search_piani_by_topic", second),
        ]
        result = evaluate("piani A1", candidates, {}, _fresh_state())

        assert result.action == "ask_user"
        assert result.question is not None

    def test_ambiguous_stores_candidates_in_state(self):
        top = CONFIDENCE_MIN + 0.10
        second = top - (CONFIDENCE_AMBIGUITY_DELTA / 2)
        candidates = [
            _cand("ask_piano_description", top),
            _cand("search_piani_by_topic", second),
        ]
        result = evaluate("piani A1", candidates, {}, _fresh_state())

        stored = result.updated_state.get("intent_candidates", [])
        assert len(stored) >= 2

    def test_not_ambiguous_when_delta_large_enough(self):
        """Se il delta è >= AMBIGUITY_DELTA, il top intent vince."""
        top = CONFIDENCE_HIGH
        second = top - CONFIDENCE_AMBIGUITY_DELTA - 0.05  # delta ampio
        candidates = [
            _cand("ask_delayed_plans", top),
            _cand("search_piani_by_topic", second),
        ]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.intent == "ask_delayed_plans"

    def test_ambiguous_requires_at_least_two_candidates(self):
        """Un solo candidato non può essere ambiguo."""
        top = CONFIDENCE_MIN + 0.10
        candidates = [_cand("ask_delayed_plans", top)]
        result = evaluate("piani", candidates, {}, _fresh_state())

        # Non ambiguo → esegue (self-sufficient)
        assert result.action == "execute"

    def test_ambiguous_stabilimenti_vs_statistics(self):
        """Disambiguazione controlli per piano: stabilimenti vs statistiche."""
        candidates = [
            _cand("ask_piano_stabilimenti", 0.65, {"piano_code": "AO1"}),
            _cand("ask_piano_statistics", 0.55, {"piano_code": "AO1"}),
        ]
        result = evaluate("controlli fatti per AO1", candidates, {"piano_code": "AO1"}, _fresh_state())

        assert result.action == "ask_user"
        assert result.question is not None
        # Lo stato deve conservare i candidati
        stored = result.updated_state.get("intent_candidates", [])
        assert len(stored) >= 2

    def test_ambiguous_suggestions_include_piano_code(self):
        """I suggerimenti pill includono il piano_code per ri-estrazione."""
        candidates = [
            _cand("ask_piano_stabilimenti", 0.65, {"piano_code": "AO1"}),
            _cand("ask_piano_statistics", 0.55, {"piano_code": "AO1"}),
        ]
        result = evaluate("controlli fatti per AO1", candidates, {"piano_code": "AO1"}, _fresh_state())

        assert result.suggestions is not None
        # Ogni suggerimento pill deve contenere AO1 nella query
        for s in result.suggestions:
            assert "AO1" in s["query"], f"Piano code mancante nella query: {s['query']}"

    def test_ambiguous_clears_intent_candidates_on_next_turn(self):
        """intent_candidates viene pulito al turno successivo."""
        state = _fresh_state(
            intent_candidates=[
                _cand("ask_piano_stabilimenti", 0.65),
                _cand("ask_piano_statistics", 0.55),
            ]
        )
        candidates = [_cand("ask_piano_statistics", 0.90)]
        result = evaluate("statistiche piano AO1", candidates, {"piano_code": "AO1"}, state)

        # intent_candidates deve essere stato pulito
        assert result.updated_state.get("intent_candidates") is None


# ===========================================================================
# 8. TestSlotContinuation
# ===========================================================================

class TestSlotContinuation:
    """
    Slot continuation (REGOLA 0): utente fornisce uno slot richiesto
    dopo che il DM ha posto la domanda nel turno precedente.
    """

    def test_slot_continuation_executes_tool(self):
        """Stato con confirmed_intent + missing_slots + nuovo slot fornito → execute."""
        state = _fresh_state(
            confirmed_intent="ask_piano_description",
            missing_slots=["piano_code"],
            slots={},
        )
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate(
            "A1",
            candidates,
            {"piano_code": "A1"},  # slot appena estratto
            state,
        )

        assert result.action == "execute"
        assert result.intent == "ask_piano_description"
        assert result.slots.get("piano_code") == "A1"

    def test_slot_continuation_clears_missing_slots(self):
        """Dopo continuazione riuscita, missing_slots deve essere None."""
        state = _fresh_state(
            confirmed_intent="ask_piano_description",
            missing_slots=["piano_code"],
            slots={},
        )
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("A1", candidates, {"piano_code": "A1"}, state)

        assert result.updated_state.get("missing_slots") is None

    def test_slot_continuation_not_triggered_without_confirmed_intent(self):
        """Nessun confirmed_intent nello stato → la regola non si attiva."""
        state = _fresh_state(
            confirmed_intent=None,
            missing_slots=["piano_code"],
            slots={},
        )
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("A1", candidates, {"piano_code": "A1"}, state)

        # Regola slot_continuation non si attiva, ma high_confidence_execute sì
        assert result.action == "execute"

    def test_slot_continuation_not_triggered_without_missing_slots(self):
        """Nessun missing_slots nello stato → la regola non si attiva."""
        state = _fresh_state(
            confirmed_intent="ask_piano_description",
            missing_slots=None,
            slots={"piano_code": "A1"},
        )
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH)]
        result = evaluate("A1", candidates, {}, state)

        # high_confidence_execute gestisce la chiamata normalmente
        assert result.action == "execute"

    def test_slot_continuation_still_missing_asks_user(self):
        """
        Se dopo il merge rimangono ancora slot mancanti,
        la regola non completa la continuazione: cede ad altri handler.
        """
        state = _fresh_state(
            confirmed_intent="search_piani_by_topic",
            missing_slots=["topic"],
            slots={},
        )
        # Forniamo un altro slot non rilevante
        candidates = [_cand("search_piani_by_topic", CONFIDENCE_HIGH)]
        result = evaluate("qualcosa", candidates, {"piano_code": "A1"}, state)

        # topic ancora mancante → ask_user
        assert result.action == "ask_user"


# ===========================================================================
# 9. TestEvaluateNoCandidates
# ===========================================================================

class TestEvaluateNoCandidates:
    """Lista candidati vuota → action='fallback'."""

    def test_empty_candidates_fallback(self):
        result = evaluate("testo qualunque", [], {}, _fresh_state())

        assert result.action == "fallback"

    def test_empty_candidates_state_updated(self):
        """Anche con fallback, lo stato viene aggiornato (turn_count incrementato)."""
        state = _fresh_state(turn_count=1)
        result = evaluate("testo qualunque", [], {}, state)

        assert result.updated_state["turn_count"] == 2

    def test_empty_candidates_context_rules_still_run(self):
        """
        Con candidati vuoti ma confirmed_intent + missing_slots + slot estratto,
        la REGOLA 0 (slot continuation) si attiva prima del controllo candidati.
        """
        state = _fresh_state(
            confirmed_intent="ask_piano_description",
            missing_slots=["piano_code"],
            slots={},
        )
        result = evaluate("A1", [], {"piano_code": "A1"}, state)

        # Regola 0 deve eseguire il tool anche senza candidati dal router
        assert result.action == "execute"
        assert result.intent == "ask_piano_description"


# ===========================================================================
# 10. TestPreExecutionConfirmation
# ===========================================================================

class TestPreExecutionConfirmation:
    """Conferma pre-esecuzione: intercetta execute per intent funzionali."""

    @pytest.fixture(autouse=True)
    def enable_confirmation(self):
        """Abilita la conferma pre-esecuzione per questi test."""
        with patch(
            "configs.config.AppConfig.is_pre_execution_confirmation_enabled",
            return_value=True,
        ):
            yield

    def test_functional_intent_gets_confirmation(self):
        """Intent funzionale con alta confidence → ask_user (conferma)."""
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.action == "ask_user"
        assert "Ho capito" in result.question
        assert result.updated_state.get("pending_confirmation") is True
        assert result.updated_state.get("pending_confirmation_intent") == "ask_delayed_plans"

    def test_non_functional_intent_skips_confirmation(self):
        """Intent non-funzionale (greet) → execute diretto."""
        candidates = [_cand("greet", CONFIDENCE_HIGH)]
        result = evaluate("ciao", candidates, {}, _fresh_state())

        assert result.action == "execute"
        assert result.intent == "greet"

    def test_confirmation_shows_slots(self):
        """Il messaggio di conferma include i parametri estratti."""
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH, {"piano_code": "A1"})]
        result = evaluate(
            "descrivimi il piano A1", candidates, {}, _fresh_state(),
            user_metadata={"asl": "NAPOLI 1 CENTRO"},
        )

        assert result.action == "ask_user"
        assert "A1" in result.question
        assert "NAPOLI 1 CENTRO" in result.question

    def test_confirmation_accepted_executes_tool(self):
        """Utente dice 'sì' → esegui il tool pending."""
        state = _fresh_state(
            pending_confirmation=True,
            pending_confirmation_intent="ask_delayed_plans",
            pending_confirmation_tool="ask_delayed_plans_tool",
            pending_confirmation_slots={},
        )
        candidates = [_cand("confirm_show_details", 0.60)]
        result = evaluate("sì", candidates, {}, state)

        assert result.action == "execute"
        assert result.intent == "ask_delayed_plans"
        assert result.target_tool == "ask_delayed_plans_tool"

    def test_confirmation_rejected_cancels(self):
        """Utente dice 'no' → annulla."""
        state = _fresh_state(
            pending_confirmation=True,
            pending_confirmation_intent="ask_delayed_plans",
            pending_confirmation_tool="ask_delayed_plans_tool",
            pending_confirmation_slots={},
        )
        candidates = [_cand("fallback", 0.30)]
        result = evaluate("no", candidates, {}, state)

        assert result.action == "ask_user"
        assert "annullato" in result.question.lower()
        assert result.updated_state.get("pending_confirmation") is None

    def test_confirmation_ignored_new_message_falls_through(self):
        """Messaggio diverso da conferma/annulla → fall-through a regole normali.

        Il vecchio pending viene cancellato da _rule_pending_confirmation,
        poi il nuovo intent funzionale ottiene a sua volta la conferma.
        """
        state = _fresh_state(
            pending_confirmation=True,
            pending_confirmation_intent="ask_delayed_plans",
            pending_confirmation_tool="ask_delayed_plans_tool",
            pending_confirmation_slots={},
        )
        # Nuovo messaggio con intent diverso
        candidates = [_cand("ask_piano_description", CONFIDENCE_HIGH, {"piano_code": "B2"})]
        result = evaluate("descrivimi il piano B2", candidates, {"piano_code": "B2"}, state)

        # Il vecchio pending è stato sostituito dal nuovo intent
        assert result.action == "ask_user"
        # La conferma è ora per il nuovo intent
        assert result.updated_state.get("pending_confirmation_intent") == "ask_piano_description"

    def test_confirmation_suggestions_present(self):
        """Il messaggio di conferma include suggerimenti (pill buttons)."""
        candidates = [_cand("ask_delayed_plans", CONFIDENCE_HIGH)]
        result = evaluate("piani in ritardo", candidates, {}, _fresh_state())

        assert result.suggestions is not None
        assert len(result.suggestions) == 2
        queries = [s["query"] for s in result.suggestions]
        assert "si" in queries
        assert "annulla" in queries
