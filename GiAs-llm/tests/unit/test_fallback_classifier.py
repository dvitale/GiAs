"""
Test unitari per llm/fallback_classifier.py.

Verifica:
1. Riconoscimento saluti (greet)
2. Riconoscimento commiati (goodbye)
3. Riconoscimento conferme e rifiuti
4. Estrazione codice piano e selezione intent corretto
5. Classificazione per keyword
6. Ricerca piani per topic
7. Fallback per testo non riconoscibile
8. Comportamento con input vuoto
9. generate_response()
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from llm.fallback_classifier import classify, generate_response


def _parse(prompt: str) -> dict:
    """Chiama classify() e deserializza il JSON restituito."""
    raw = classify(prompt)
    return json.loads(raw)


def _wrap(message: str) -> str:
    """Avvolge il messaggio nel formato prompt atteso dal classifier."""
    return f'**Messaggio utente:** "{message}"'


class TestClassifyGreetings:
    """Saluti devono essere classificati come 'greet'."""

    @pytest.mark.parametrize("greeting", [
        "ciao",
        "salve",
        "buongiorno",
        "buonasera",
        "buonanotte",
        "hello",
        "hey",
        "hi",
    ])
    def test_standard_greetings_classified_as_greet(self, greeting):
        """Saluti standard devono restituire intent 'greet'."""
        result = _parse(_wrap(greeting))
        assert result["intent"] == "greet", \
            f"'{greeting}' classificato come '{result['intent']}' invece di 'greet'"

    def test_greet_has_empty_slots(self):
        """Il saluto non deve produrre slot."""
        result = _parse(_wrap("ciao"))
        assert result["slots"] == {}

    def test_greet_no_clarification_needed(self):
        """Un saluto non richiede chiarimento."""
        result = _parse(_wrap("buongiorno"))
        assert result["needs_clarification"] is False

    def test_greet_with_exclamation(self):
        """Saluto con punto esclamativo deve essere riconosciuto."""
        result = _parse(_wrap("ciao!"))
        assert result["intent"] == "greet"

    def test_come_stai_is_greet(self):
        """'come stai' rientra nel pattern di saluto."""
        result = _parse(_wrap("come stai"))
        assert result["intent"] == "greet"

    def test_come_va_is_greet(self):
        """'come va' rientra nel pattern di saluto."""
        result = _parse(_wrap("come va"))
        assert result["intent"] == "greet"


class TestClassifyGoodbye:
    """Commiati devono essere classificati come 'goodbye'."""

    @pytest.mark.parametrize("farewell", [
        "arrivederci",
        "addio",
        "bye",
        "ciao ciao",
        "alla prossima",
        "ci vediamo",
        "a domani",
    ])
    def test_standard_farewells_classified_as_goodbye(self, farewell):
        """Commiati standard devono restituire intent 'goodbye'."""
        result = _parse(_wrap(farewell))
        assert result["intent"] == "goodbye", \
            f"'{farewell}' classificato come '{result['intent']}' invece di 'goodbye'"

    def test_goodbye_has_empty_slots(self):
        """Il commiato non deve produrre slot."""
        result = _parse(_wrap("arrivederci"))
        assert result["slots"] == {}

    def test_goodbye_no_clarification_needed(self):
        """Un commiato non richiede chiarimento."""
        result = _parse(_wrap("bye"))
        assert result["needs_clarification"] is False


class TestClassifyConfirmDecline:
    """Conferme e rifiuti devono essere classificati correttamente."""

    @pytest.mark.parametrize("confirmation", [
        "sì",
        "si",
        "ok",
        "va bene",
        "mostra",
        "dettagli",
        "tutti",
        "yes",
    ])
    def test_confirmations_classified_correctly(self, confirmation):
        """Conferme devono restituire intent 'confirm_show_details'."""
        result = _parse(_wrap(confirmation))
        assert result["intent"] == "confirm_show_details", \
            f"'{confirmation}' classificato come '{result['intent']}'"

    @pytest.mark.parametrize("denial", [
        "no",
        "non",
        "niente",
        "basta",
    ])
    def test_denials_classified_correctly(self, denial):
        """Rifiuti devono restituire intent 'decline_show_details'."""
        result = _parse(_wrap(denial))
        assert result["intent"] == "decline_show_details", \
            f"'{denial}' classificato come '{result['intent']}'"

    def test_va_bene_cosi_is_decline(self):
        """'va bene così' deve essere classificato come rifiuto."""
        result = _parse(_wrap("va bene così"))
        assert result["intent"] == "decline_show_details"

    def test_confirm_has_empty_slots(self):
        """La conferma non deve produrre slot."""
        result = _parse(_wrap("sì"))
        assert result["slots"] == {}


class TestClassifyPianoCode:
    """Piano code nel messaggio: selezione intent e slot extraction."""

    def test_piano_code_extracted_as_slot(self):
        """Un codice piano deve essere estratto come slot piano_code."""
        result = _parse(_wrap("piano A1"))
        assert result["slots"].get("piano_code") == "A1"

    def test_piano_code_uppercase_normalized(self):
        """Il codice piano deve essere normalizzato in maiuscolo."""
        result = _parse(_wrap("dimmi del piano a1"))
        assert result["slots"].get("piano_code") == "A1"

    def test_piano_code_delay_context_returns_check_if_plan_delayed(self):
        """Piano + 'ritardo' → check_if_plan_delayed."""
        result = _parse(_wrap("il piano A1 è in ritardo?"))
        assert result["intent"] == "check_if_plan_delayed"
        assert result["slots"].get("piano_code") == "A1"

    def test_piano_code_descrizione_context_returns_ask_piano_description(self):
        """Piano + 'descrizione' → ask_piano_description."""
        result = _parse(_wrap("descrizione del piano B2"))
        assert result["intent"] == "ask_piano_description"
        assert result["slots"].get("piano_code") == "B2"

    def test_piano_code_stabilimenti_context_returns_ask_piano_stabilimenti(self):
        """Piano + 'stabilimenti' → ask_piano_stabilimenti."""
        result = _parse(_wrap("stabilimenti del piano C3"))
        assert result["intent"] == "ask_piano_stabilimenti"
        assert result["slots"].get("piano_code") == "C3"

    def test_piano_code_no_context_defaults_to_ask_piano_stabilimenti(self):
        """Piano code senza contesto specifico → ask_piano_stabilimenti (default)."""
        result = _parse(_wrap("piano A2"))
        assert result["intent"] == "ask_piano_stabilimenti"
        assert result["slots"].get("piano_code") == "A2"

    def test_piano_code_cosa_e_returns_ask_piano_description(self):
        """Piano + 'cosa è' → ask_piano_description.

        Nota: la variante con apostrofo ("cos'è") viene troncata dall'estrattore
        del prompt perché il regex [^"'] si ferma all'apostrofo. Si usa quindi
        la forma senza apostrofo, che è presente nel mapping del classifier.
        """
        result = _parse(_wrap("cosa è il piano A3?"))
        assert result["intent"] == "ask_piano_description"

    @pytest.mark.parametrize("piano_code", ["A1", "B2", "C3", "D10", "F99"])
    def test_various_piano_codes_extracted(self, piano_code):
        """Codici piano di varie forme devono essere estratti correttamente."""
        result = _parse(_wrap(f"piano {piano_code}"))
        assert result["slots"].get("piano_code") == piano_code.upper()


class TestClassifyKeywords:
    """Keyword-based intents: ogni keyword deve mappare all'intent corretto."""

    @pytest.mark.parametrize("message,expected_intent", [
        ("stabilimenti a rischio", "ask_risk_based_priority"),
        ("non conformità più frequenti", "ask_risk_based_priority"),
        ("nc negli stabilimenti", "ask_risk_based_priority"),
        ("stabilimenti priorità", "ask_priority_establishment"),
        ("urgenti da controllare", "ask_priority_establishment"),
        ("mai controllati", "ask_suggest_controls"),
        ("stabilimenti da controllare", "ask_suggest_controls"),
        ("piani in ritardo", "ask_delayed_plans"),
        ("ritardi nella programmazione", "ask_delayed_plans"),
        ("stabilimenti vicino", "ask_nearby_priority"),
        ("dintorni dell'ASL", "ask_nearby_priority"),
        ("storico dei controlli", "ask_establishment_history"),
        ("come si fa un'ispezione", "info_procedure"),
        ("procedura da seguire", "info_procedure"),
        ("statistiche sui piani", "ask_piano_statistics"),
        ("quanti piani ci sono", "ask_piano_statistics"),
        ("aiuto", "ask_help"),
        ("help", "ask_help"),
        ("cosa sai fare", "ask_help"),
    ])
    def test_keyword_maps_to_correct_intent(self, message, expected_intent):
        """Ogni messaggio con keyword specifica deve mapparsi all'intent atteso."""
        result = _parse(_wrap(message))
        assert result["intent"] == expected_intent, \
            f"'{message}' → '{result['intent']}', atteso '{expected_intent}'"

    def test_keyword_intent_has_empty_slots(self):
        """Intent da keyword non devono avere slot estratti."""
        result = _parse(_wrap("piani in ritardo"))
        assert result["slots"] == {}

    def test_attivita_rischiose_maps_to_top_risk(self):
        """'attività rischiose' deve mappare a ask_top_risk_activities (priorità più alta)."""
        result = _parse(_wrap("attività più rischiose"))
        assert result["intent"] == "ask_top_risk_activities"

    def test_top_risk_has_priority_over_generic_risk(self):
        """'linee di attività' deve mappare a ask_top_risk_activities, non ask_risk_based_priority."""
        result = _parse(_wrap("classifica attività per rischio"))
        assert result["intent"] == "ask_top_risk_activities"


class TestClassifySearch:
    """Trigger di ricerca + topic → search_piani_by_topic con slot topic."""

    def test_search_trigger_returns_search_intent(self):
        """'cerca piani' senza topic deve restituire search_piani_by_topic."""
        result = _parse(_wrap("cerca piani"))
        assert result["intent"] == "search_piani_by_topic"

    def test_search_with_topic_extracts_topic_slot(self):
        """'cerca piani bovini' deve estrarre 'bovini' come topic."""
        result = _parse(_wrap("cerca piani bovini"))
        assert result["intent"] == "search_piani_by_topic"
        assert "bovini" in result["slots"].get("topic", "")

    def test_search_with_multiple_topics(self):
        """Più topic nel messaggio devono essere tutti inclusi nello slot topic."""
        result = _parse(_wrap("quali piani riguardano bovini e suini"))
        assert result["intent"] == "search_piani_by_topic"
        topic = result["slots"].get("topic", "")
        assert "bovini" in topic
        assert "suini" in topic

    @pytest.mark.parametrize("trigger", [
        "cerca", "ricerca", "trova piani", "quali piani", "piani di",
    ])
    def test_various_search_triggers(self, trigger):
        """Ogni trigger di ricerca deve attivare search_piani_by_topic."""
        result = _parse(_wrap(f"{trigger} qualcosa"))
        assert result["intent"] == "search_piani_by_topic"

    def test_search_without_topic_has_empty_slots(self):
        """Ricerca senza topic riconoscibile deve avere slots vuoti."""
        result = _parse(_wrap("cerca piani di controllo"))
        assert result["intent"] == "search_piani_by_topic"
        assert result["slots"] == {}

    @pytest.mark.parametrize("topic", [
        "bovini", "suini", "avicoli", "latte", "carne", "salmonella",
        "api", "acquacoltura", "equini",
    ])
    def test_search_recognizes_domain_topics(self, topic):
        """Termini di dominio veterinario devono essere estratti come topic."""
        result = _parse(_wrap(f"piani per {topic}"))
        assert result["intent"] == "search_piani_by_topic"
        assert topic in result["slots"].get("topic", "")


class TestClassifyFallback:
    """Testo non riconoscibile deve restituire intent 'fallback'."""

    def test_unrecognizable_text_returns_fallback(self):
        """Testo generico senza keyword deve restituire 'fallback'."""
        result = _parse(_wrap("lorem ipsum dolor sit amet"))
        assert result["intent"] == "fallback"

    def test_fallback_sets_needs_clarification(self):
        """Il fallback deve richiedere chiarimento."""
        result = _parse(_wrap("lorem ipsum"))
        assert result["needs_clarification"] is True

    def test_random_numbers_return_fallback(self):
        """Sequenza di numeri casuali deve restituire 'fallback'."""
        result = _parse(_wrap("12345 67890"))
        assert result["intent"] == "fallback"

    def test_short_unrecognized_text_returns_fallback(self):
        """Testo breve non riconoscibile deve restituire 'fallback'."""
        result = _parse(_wrap("xyz"))
        assert result["intent"] == "fallback"

    def test_special_characters_return_fallback(self):
        """Stringa di soli caratteri speciali deve restituire 'fallback'."""
        result = _parse(_wrap("@@@ ### ???"))
        assert result["intent"] == "fallback"


class TestClassifyEmpty:
    """Input vuoto deve essere gestito senza eccezioni."""

    def test_empty_string_returns_fallback(self):
        """Stringa vuota come prompt deve restituire 'fallback'."""
        result = _parse("")
        assert result["intent"] == "fallback"

    def test_empty_string_sets_needs_clarification(self):
        """Stringa vuota deve impostare needs_clarification=True."""
        result = _parse("")
        assert result["needs_clarification"] is True

    def test_empty_string_has_empty_slots(self):
        """Stringa vuota non deve produrre slot."""
        result = _parse("")
        assert result["slots"] == {}

    def test_classify_returns_valid_json_always(self):
        """classify() deve sempre restituire JSON valido, anche con input insoliti."""
        for prompt in ["", "   ", _wrap(""), _wrap("ciao"), _wrap("piano A1")]:
            raw = classify(prompt)
            parsed = json.loads(raw)  # Non deve sollevare eccezioni
            assert "intent" in parsed
            assert "slots" in parsed
            assert "needs_clarification" in parsed

    def test_classify_result_has_required_keys(self):
        """Il risultato JSON deve sempre avere le chiavi obbligatorie."""
        result = _parse(_wrap("piani in ritardo"))
        assert "intent" in result
        assert "slots" in result
        assert "needs_clarification" in result


class TestGenerateResponse:
    """Test per generate_response()."""

    def test_empty_prompt_returns_generic_message(self):
        """Prompt vuoto deve restituire messaggio generico di benvenuto."""
        response = generate_response("")
        assert len(response) > 0
        assert isinstance(response, str)

    def test_none_like_empty_returns_generic(self):
        """Prompt vuoto (falsy) deve restituire risposta generica."""
        response = generate_response("")
        assert "piani di monitoraggio" in response.lower() or "aiutarti" in response.lower()

    def test_prompt_with_formatted_response_extracts_it(self):
        """Prompt con RISULTATI OTTENUTI e formatted_response deve estrarre la risposta."""
        prompt = (
            "Analizza i risultati.\n"
            "**RISULTATI OTTENUTI:** {'formatted_response': 'Ecco i dati trovati.'}\n"
            "Rispondi in italiano."
        )
        response = generate_response(prompt)
        assert "Ecco i dati trovati." in response

    def test_prompt_with_data_section_returns_data_content(self):
        """Prompt con sezione RISULTATI OTTENUTI ma senza formatted_response deve includere i dati."""
        prompt = (
            "**RISULTATI OTTENUTI:** Lista di stabilimenti a rischio\n"
            "**Istruzioni:** Rispondere in italiano"
        )
        response = generate_response(prompt)
        assert len(response) > 0

    def test_generate_response_returns_string(self):
        """generate_response deve sempre restituire una stringa."""
        for prompt in ["", "qualsiasi testo", "**RISULTATI OTTENUTI:** {}"]:
            assert isinstance(generate_response(prompt), str)

    def test_formatted_response_truncated_at_2000_chars(self):
        """La risposta estratta non deve superare i 2000 caratteri."""
        long_text = "X" * 3000
        prompt = f"**RISULTATI OTTENUTI:** {{'formatted_response': '{long_text}'}}"
        response = generate_response(prompt)
        assert len(response) <= 2000
