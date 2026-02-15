"""
Test per il Router di classificazione intent (architettura ibrida)
"""

import pytest
import json
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from GiAs_llm.orchestrator.router import Router
except ImportError:
    import importlib.util
    router_path = os.path.join(os.path.dirname(__file__), '..', 'orchestrator', 'router.py')
    spec = importlib.util.spec_from_file_location("router", router_path)
    router_module = importlib.util.module_from_spec(spec)

    llm_path = os.path.join(os.path.dirname(__file__), '..', 'llm', 'client.py')
    llm_spec = importlib.util.spec_from_file_location("llm.client", llm_path)
    llm_module = importlib.util.module_from_spec(llm_spec)
    sys.modules['llm'] = type(sys)('llm')
    sys.modules['llm.client'] = llm_module
    llm_spec.loader.exec_module(llm_module)

    spec.loader.exec_module(router_module)
    Router = router_module.Router


class TestRouter:
    """Test per la classe Router"""

    def test_valid_intents_list(self):
        """Verifica che la lista di intent validi sia definita correttamente"""
        assert len(Router.VALID_INTENTS) == 20
        assert "greet" in Router.VALID_INTENTS
        assert "ask_piano_description" in Router.VALID_INTENTS
        assert "ask_priority_establishment" in Router.VALID_INTENTS
        assert "ask_risk_based_priority" in Router.VALID_INTENTS
        assert "ask_delayed_plans" in Router.VALID_INTENTS
        assert "check_if_plan_delayed" in Router.VALID_INTENTS
        assert "ask_establishment_history" in Router.VALID_INTENTS
        assert "ask_top_risk_activities" in Router.VALID_INTENTS
        assert "analyze_nc_by_category" in Router.VALID_INTENTS
        assert "confirm_show_details" in Router.VALID_INTENTS
        assert "decline_show_details" in Router.VALID_INTENTS
        assert "fallback" in Router.VALID_INTENTS

    def test_empty_message_returns_fallback(self):
        """Messaggio vuoto deve restituire fallback"""
        mock_llm = Mock()
        router = Router(mock_llm)

        result = router.classify("")

        assert result["intent"] == "fallback"
        assert "error" in result
        assert result["slots"] == {}
        assert result["needs_clarification"] is False

    # =========================================================================
    # TEST HEURISTICS (bypass LLM)
    # =========================================================================

    def test_heuristic_greet(self):
        """Test heuristic per saluti - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        for phrase in ["ciao", "buongiorno", "salve", "hey"]:
            result = router.classify(phrase)
            assert result["intent"] == "greet", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_heuristic_goodbye(self):
        """Test heuristic per saluti finali - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        for phrase in ["arrivederci", "grazie e arrivederci"]:
            result = router.classify(phrase)
            assert result["intent"] == "goodbye", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_heuristic_help(self):
        """Test heuristic per aiuto - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        for phrase in ["aiuto", "cosa puoi fare", "help"]:
            result = router.classify(phrase)
            assert result["intent"] == "ask_help", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_heuristic_delayed_plans(self):
        """Test per piani in ritardo - heuristic essenziale, NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "piani in ritardo",
            "quali sono i piani in ritardo",
            "quali piani sono in ritardo",
        ]
        for phrase in test_cases:
            mock_llm.reset_mock()
            result = router.classify(phrase)
            assert result["intent"] == "ask_delayed_plans", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_heuristic_check_plan_delayed(self):
        """Test per ritardo piano specifico - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            ("Ritardo del piano A1", "check_if_plan_delayed", "A1"),
            ("il piano B47 è in ritardo?", "check_if_plan_delayed", "B47"),
            ("piano A1 in ritardo", "check_if_plan_delayed", "A1"),
            ("quanto ritardo ha il piano B2", "check_if_plan_delayed", "B2"),
            ("verifica ritardo piano C3", "check_if_plan_delayed", "C3"),
        ]
        for phrase, expected_intent, expected_piano in test_cases:
            mock_llm.query.return_value = json.dumps({
                "intent": expected_intent,
                "slots": {"piano_code": expected_piano},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == expected_intent, f"Failed for: '{phrase}' → got {result['intent']}"
            assert result["slots"].get("piano_code") == expected_piano, f"Missing piano_code for: '{phrase}'"

    def test_heuristic_never_controlled(self):
        """Test per mai controllati - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_suggest_controls",
            "slots": {},
            "needs_clarification": False,
            "confidence": 0.95
        })
        router = Router(mock_llm)

        result = router.classify("stabilimenti mai controllati")
        assert result["intent"] == "ask_suggest_controls"

    def test_heuristic_risk(self):
        """Test per rischio - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        for phrase in ["stabilimenti a rischio", "più rischiosi"]:
            mock_llm.query.return_value = json.dumps({
                "intent": "ask_risk_based_priority",
                "slots": {},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == "ask_risk_based_priority", f"Failed for: {phrase}"

    def test_heuristic_top_risk_activities(self):
        """Test per top attività rischiose - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_top_risk_activities",
            "slots": {},
            "needs_clarification": False,
            "confidence": 0.95
        })
        router = Router(mock_llm)

        result = router.classify("attività più rischiose")
        assert result["intent"] == "ask_top_risk_activities"

    def test_heuristic_analyze_nc_by_category(self):
        """Test per analisi NC per categoria - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "NC per categoria HACCP",
            "non conformità categoria igiene",
            "analizza le non conformità",
            "analizza NC",
            "problemi di HACCP",
            "problemi igiene",
            "non conformità HACCP",
            "NC di tipo struttura",
        ]
        for phrase in test_cases:
            mock_llm.query.return_value = json.dumps({
                "intent": "analyze_nc_by_category",
                "slots": {},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == "analyze_nc_by_category", f"Failed for: '{phrase}'"

    def test_heuristic_priority(self):
        """Test per priorità - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        for phrase in ["chi devo controllare", "cosa devo fare oggi"]:
            mock_llm.query.return_value = json.dumps({
                "intent": "ask_priority_establishment",
                "slots": {},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == "ask_priority_establishment", f"Failed for: {phrase}"

    def test_heuristic_piano_statistics(self):
        """Test per statistiche piani - P3: con MINIMAL_HEURISTICS=True, usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "statistiche sui piani",
            "statistiche dei piani",
            "piani più usati",
            "piani più frequenti",
            "quanti piani",
            "frequenza piani",
            "quale piano è più frequente",
        ]
        for phrase in test_cases:
            mock_llm.query.return_value = json.dumps({
                "intent": "ask_piano_statistics",
                "slots": {},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == "ask_piano_statistics", f"Failed for: '{phrase}'"

    def test_heuristic_nearby_priority(self):
        """Test per prossimità geografica - heuristic essenziale, NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            ("stabilimenti vicino a Napoli", {"location": "Napoli"}, False),
            ("vicino a Piazza Garibaldi", {"location": "Piazza Garibaldi"}, False),
            ("nei dintorni di Benevento", {"location": "Benevento"}, False),
            ("nei pressi di Avellino", {"location": "Avellino"}, False),
            ("zona di Caserta", {"location": "Caserta"}, False),
            ("entro 5 km da Salerno", {"location": "Salerno", "radius_km": 5.0}, False),
            ("intorno a Via Roma", {"location": "Via Roma"}, False),
            ("nelle vicinanze", {}, True),  # Senza location -> needs_clarification
            ("stabilimenti vicino a me", {}, True),  # Senza location -> needs_clarification
        ]
        for phrase, expected_slots, expected_clarification in test_cases:
            mock_llm.reset_mock()
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed for: '{phrase}'"
            assert result["needs_clarification"] == expected_clarification, \
                f"Clarification mismatch for: '{phrase}', expected {expected_clarification}, got {result['needs_clarification']}"
            mock_llm.query.assert_not_called()

    def test_slot_extraction_radius_km(self):
        """Test estrazione radius_km da frasi con 'entro X km' - P3: usa LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            ("stabilimenti entro 5 km da Napoli", 5.0),
            ("controlli entro 10 km dalla stazione", 10.0),
            ("entro 3 km da Via Roma", 3.0),
        ]
        for phrase, expected_radius in test_cases:
            mock_llm.query.return_value = json.dumps({
                "intent": "ask_nearby_priority",
                "slots": {"radius_km": expected_radius},
                "needs_clarification": False,
                "confidence": 0.95
            })
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed intent for: '{phrase}'"
            if result["slots"].get("radius_km"):
                assert result["slots"]["radius_km"] == expected_radius, \
                    f"Failed radius for: '{phrase}', expected {expected_radius}, got {result['slots'].get('radius_km')}"

    # =========================================================================
    # TEST CONFIRM/DECLINE CON CONTESTO
    # =========================================================================

    def test_heuristic_confirm_with_context(self):
        """Test heuristic conferma con detail_context - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)
        metadata = {"detail_context": {"some": "context"}}

        for phrase in ["sì", "si", "ok", "mostrami", "vediamo"]:
            result = router.classify(phrase, metadata)
            assert result["intent"] == "confirm_show_details", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_heuristic_decline_with_context(self):
        """Test heuristic rifiuto con detail_context - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)
        metadata = {"detail_context": {"some": "context"}}

        for phrase in ["no", "no grazie", "basta"]:
            result = router.classify(phrase, metadata)
            assert result["intent"] == "decline_show_details", f"Failed for: {phrase}"
            mock_llm.query.assert_not_called()

    def test_yes_without_context_is_not_confirm(self):
        """Test che 'sì' SENZA detail_context NON venga classificato come confirm_show_details.
        Bare 'sì' senza sessione attiva deve andare al LLM o fallback, non conferma."""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "fallback",
            "slots": {},
            "needs_clarification": False
        })
        router = Router(mock_llm)

        result = router.classify("sì")  # Nessun metadata
        assert result["intent"] != "confirm_show_details"

    def test_yes_with_context_is_confirm(self):
        """Test che 'sì' CON detail_context venga classificato come confirm_show_details"""
        mock_llm = Mock()
        router = Router(mock_llm)

        result = router.classify("sì", metadata={"detail_context": {"some": "context"}})
        assert result["intent"] == "confirm_show_details"
        mock_llm.query.assert_not_called()  # Heuristic, no LLM

    # =========================================================================
    # TEST PRE-PARSING SLOT
    # =========================================================================

    def test_preparsing_piano_code(self):
        """Test estrazione piano_code via regex"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_piano_description",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("descrizione piano A1")

        # Pre-parsing dovrebbe aver estratto piano_code
        assert result["slots"].get("piano_code") == "A1"

    def test_preparsing_piano_code_lowercase(self):
        """Test normalizzazione piano_code in maiuscolo"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_piano_description",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("descrizione piano a1")

        assert result["slots"]["piano_code"] == "A1"

    def test_preparsing_asl(self):
        """Test estrazione ASL via regex"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_priority_establishment",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("priorità per NA1")

        assert result["slots"].get("asl") == "NA1"

    def test_preparsing_num_registrazione(self):
        """Test estrazione numero registrazione (con IT)"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_establishment_history",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("storico IT 2287")

        assert "num_registrazione" in result["slots"]
        assert "IT" in result["slots"]["num_registrazione"]

    # =========================================================================
    # TEST POST-VALIDATION
    # =========================================================================

    def test_post_validation_missing_piano_code(self):
        """Test post-validation: manca piano_code obbligatorio"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_piano_description",
            "slots": {},
            "needs_clarification": False  # LLM dice false erroneamente
        })

        router = Router(mock_llm)
        result = router.classify("dimmi del piano")

        # Post-validation deve forzare clarification
        assert result["needs_clarification"] is True
        assert result["slots"] == {}

    def test_post_validation_has_piano_code(self):
        """Test post-validation: piano_code presente"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_piano_description",
            "slots": {"piano_code": "A1"},
            "needs_clarification": True  # LLM dice true erroneamente
        })

        router = Router(mock_llm)
        result = router.classify("descrizione piano A1")

        # Post-validation NON deve forzare clarification se slot presente
        assert result["needs_clarification"] is False
        assert result["slots"]["piano_code"] == "A1"

    def test_post_validation_self_sufficient_intents(self):
        """Test post-validation: intent self-sufficient sempre clarification=false"""
        mock_llm = Mock()

        # Simula LLM che restituisce clarification=true per intent self-sufficient
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_delayed_plans",
            "slots": {},
            "needs_clarification": True  # Errato
        })

        router = Router(mock_llm)
        result = router.classify("mostrami i piani in ritardo per favore")

        # Post-validation corregge
        assert result["needs_clarification"] is False

    def test_post_validation_establishment_needs_identifier(self):
        """Test post-validation: storico stabilimento richiede almeno un identificativo"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_establishment_history",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("storico stabilimento")

        assert result["needs_clarification"] is True

    # =========================================================================
    # TEST LLM FALLBACK
    # =========================================================================

    def test_classify_with_valid_json_response(self):
        """Test classificazione con risposta JSON valida"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "search_piani_by_topic",
            "slots": {"topic": "allevamenti"},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("piani su allevamenti bovini")

        assert result["intent"] == "search_piani_by_topic"

    def test_classify_with_invalid_intent(self):
        """Intent non valido deve restituire fallback"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "invalid_intent",
            "slots": {},
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("messaggio generico")

        assert result["intent"] == "fallback"
        assert "error" in result

    def test_classify_with_malformed_json(self):
        """JSON malformato deve restituire fallback"""
        mock_llm = Mock()
        mock_llm.query.return_value = "not a json"

        router = Router(mock_llm)
        result = router.classify("messaggio generico")

        assert result["intent"] == "fallback"
        assert "error" in result

    def test_llm_exception_handling(self):
        """Eccezioni LLM devono essere gestite"""
        mock_llm = Mock()
        mock_llm.query.side_effect = Exception("LLM Error")

        router = Router(mock_llm)
        result = router.classify("messaggio generico")

        assert result["intent"] == "fallback"
        assert "error" in result
        assert "LLM Error" in result["error"]

    # =========================================================================
    # TEST SLOT FILTERING E NORMALIZZAZIONE
    # =========================================================================

    def test_filter_invented_slots(self):
        """Test filtraggio slot inventati dal modello"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_piano_description",
            "slots": {
                "piano_code": "A1",
                "invented_slot": "should_be_removed",
                "another_fake": "also_removed"
            },
            "needs_clarification": False
        })

        router = Router(mock_llm)
        result = router.classify("descrizione piano A1")

        assert result["slots"]["piano_code"] == "A1"
        assert "invented_slot" not in result["slots"]
        assert "another_fake" not in result["slots"]

    def test_valid_slot_keys_defined(self):
        """Test che VALID_SLOT_KEYS contenga tutte le chiavi previste"""
        expected_keys = {"piano_code", "asl", "topic", "num_registrazione", "numero_riconoscimento",
                        "partita_iva", "ragione_sociale", "categoria",
                        "location", "radius_km"}
        assert Router.VALID_SLOT_KEYS == expected_keys

    # =========================================================================
    # TEST CACHE
    # =========================================================================

    def test_cache_hit_skips_llm(self):
        """Test che cache hit non chiami LLM"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "search_piani_by_topic",
            "slots": {"topic": "mangimi"},
            "needs_clarification": False
        })

        router = Router(mock_llm, enable_cache=True)

        # Query che non matcha nessuna heuristic (va al LLM)
        query = "quanto costa il servizio di ispezione"

        # Prima chiamata - LLM (cache miss)
        result1 = router.classify(query)

        # Debug: verifica cosa è stato restituito
        assert result1["intent"] == "search_piani_by_topic", f"Got: {result1}"
        assert mock_llm.query.call_count == 1, "LLM should be called once"

        # Verifica cache stats
        stats = router.get_cache_stats()
        assert stats["cache_size"] == 1, f"Cache should have 1 entry, got: {stats}"

        # Seconda chiamata - cache hit (LLM non chiamato)
        result2 = router.classify(query)
        assert mock_llm.query.call_count == 1, "LLM should still be 1 (cache hit)"
        assert result2["intent"] == "search_piani_by_topic"

    def test_cache_key_with_context(self):
        """Test che chiave cache consideri detail_context"""
        mock_llm = Mock()
        router = Router(mock_llm, enable_cache=True)

        key_no_ctx = router._build_cache_key("sì", False)
        key_with_ctx = router._build_cache_key("sì", True)

        assert key_no_ctx != key_with_ctx
        assert "__ctx__" in key_with_ctx


    # =========================================================================
    # TEST PROMPT V2 (P1)
    # =========================================================================

    def test_parse_llm_response_with_new_fields(self):
        """Test che nuovi campi V2 (reasoning, confidence) non causino errori"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "reasoning": "stabilimenti con alto rischio basato su NC",
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False,
            "confidence": 0.95
        })

        router = Router(mock_llm)
        result = router.classify("stabilimenti a rischio")

        assert result["intent"] == "ask_risk_based_priority"
        assert result["needs_clarification"] is False
        # Nuovi campi ignorati gracefully (non sollevano errore)
        assert "error" not in result

    def test_prompt_token_budget(self):
        """Test che prompt V2 rispetti budget ~600 parole (700-750 token)"""
        prompt = Router.CLASSIFICATION_SYSTEM_PROMPT
        word_count = len(prompt.split())

        # Budget: ~600 parole max (stima ~1.2 token/parola = ~700-750 token)
        assert word_count < 600, f"Prompt troppo lungo: {word_count} parole (max 600)"
        # Minimo ragionevole per contenere tutti gli esempi
        assert word_count > 300, f"Prompt troppo corto: {word_count} parole (min 300)"

    # =========================================================================
    # TEST CONFIDENCE (P2)
    # =========================================================================

    def test_heuristic_confidence(self):
        """Test che heuristics essenziali abbiano confidence 0.99"""
        mock_llm = Mock()
        router = Router(mock_llm)

        # Heuristics essenziali (attive anche con MINIMAL_HEURISTICS=True)
        test_cases = [
            ("ciao", "greet"),
            ("arrivederci", "goodbye"),
            ("aiuto", "ask_help"),
            ("piani in ritardo", "ask_delayed_plans"),
        ]
        for phrase, expected_intent in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == expected_intent, f"Failed for: {phrase}"
            assert result.get("confidence") == 0.99, \
                f"Heuristic '{phrase}' should have confidence 0.99, got {result.get('confidence')}"
            mock_llm.query.assert_not_called()

    def test_parse_confidence_valid(self):
        """Test parsing confidence valida dal LLM"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "reasoning": "test",
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False,
            "confidence": 0.85
        })

        router = Router(mock_llm)
        result = router.classify("query che va al llm senza match heuristic xyz")

        assert result.get("confidence") == 0.85

    def test_parse_confidence_invalid(self):
        """Test fallback confidence quando LLM restituisce valore non numerico"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False,
            "confidence": "alta"  # Non numerico
        })

        router = Router(mock_llm)
        result = router.classify("query che va al llm senza match heuristic xyz")

        # Dovrebbe fare fallback a 0.70
        assert result.get("confidence") == 0.70

    def test_parse_confidence_missing(self):
        """Test fallback confidence quando LLM non restituisce confidence"""
        mock_llm = Mock()
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False
            # No confidence field
        })

        router = Router(mock_llm)
        result = router.classify("query che va al llm senza match heuristic xyz")

        # Dovrebbe fare fallback a 0.70
        assert result.get("confidence") == 0.70

    def test_parse_confidence_clamped(self):
        """Test che confidence venga clampata a [0, 1]"""
        mock_llm = Mock()
        router = Router(mock_llm)

        # Test valore > 1
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False,
            "confidence": 1.5
        })
        result = router.classify("query test 1")
        assert result.get("confidence") == 1.0

        # Test valore < 0
        mock_llm.query.return_value = json.dumps({
            "intent": "ask_risk_based_priority",
            "slots": {},
            "needs_clarification": False,
            "confidence": -0.5
        })
        result = router.classify("query test 2 diversa")
        assert result.get("confidence") == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
