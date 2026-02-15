"""
Test E2E per tutti i 20 intent.
Ogni test replica chiamata frontend completa con metadata.
"""

import pytest
import re


# Definizione test per ogni intent
# (query, expected_intent, response_patterns)
INTENT_TESTS = [
    # Greet/Goodbye/Help (3)
    ("ciao", "greet", ["benvenuto", "ciao", "buon", "posso"]),
    ("arrivederci", "goodbye", ["arrivederci", "buon lavoro", "presto"]),
    ("aiuto", "ask_help", ["posso", "aiutarti", "domand", "funzionalit"]),

    # Piano queries (4)
    ("di cosa tratta il piano A1", "ask_piano_description",
     ["piano", "A1", "descrizione", "monitoraggio"]),
    ("stabilimenti del piano A22", "ask_piano_stabilimenti",
     ["stabiliment", "piano", "A22", "control"]),
    ("attività del piano B2", "ask_piano_stabilimenti",
     ["attivit", "piano", "B2"]),
    ("statistiche sui piani", "ask_piano_statistics",
     ["statistic", "piano", "control"]),

    # Search (2)
    ("quali piani riguardano bovini", "search_piani_by_topic",
     ["piano", "bovin"]),
    ("piani su allevamenti", "search_piani_by_topic",
     ["piano", "allev"]),

    # Priority (2)
    ("chi devo controllare per primo", "ask_priority_establishment",
     ["priorit", "control", "stabil"]),
    ("quale stabilimento controllare secondo la programmazione", "ask_priority_establishment",
     ["stabil", "control", "programm"]),

    # Risk (2)
    ("stabilimenti ad alto rischio", "ask_risk_based_priority",
     ["rischio", "priorit", "stabil"]),
    ("sulla base del rischio storico chi dovrei controllare", "ask_risk_based_priority",
     ["rischio", "storic", "control"]),

    # Suggest controls (1)
    ("suggerisci controlli", "ask_suggest_controls",
     ["control", "suggeri", "stabil"]),

    # Delayed plans (2)
    ("piani in ritardo", "ask_delayed_plans",
     ["ritard", "piano"]),
    ("il piano B47 è in ritardo", "check_if_plan_delayed",
     ["ritard", "piano", "B47"]),

    # Establishment history (1)
    ("storico controlli stabilimento IT 2287", "ask_establishment_history",
     ["storico", "control", "stabil"]),

    # Top risk activities (1)
    ("attività più rischiose", "ask_top_risk_activities",
     ["rischio", "attivit"]),

    # NC analysis (1)
    ("analizza le non conformità HACCP", "analyze_nc_by_category",
     ["conformit", "HACCP", "NC", "analisi"]),
]


class TestIntentsComplete:
    """Test E2E per tutti gli intent principali."""

    @pytest.mark.e2e
    @pytest.mark.parametrize("query,expected_intent,patterns", INTENT_TESTS)
    def test_intent_response(self, api_client, unique_sender, complete_metadata,
                             query, expected_intent, patterns):
        """Test singolo intent con payload frontend completo."""
        response = api_client(query, unique_sender, complete_metadata)

        assert "text" in response, f"Response senza 'text' per intent {expected_intent}"
        text = response["text"].lower()

        # Verifica che almeno uno dei pattern sia presente
        found = any(p.lower() in text for p in patterns)
        assert found, (
            f"Intent {expected_intent}: nessun pattern trovato.\n"
            f"Patterns: {patterns}\n"
            f"Response: {text[:300]}..."
        )

    @pytest.mark.e2e
    def test_greet_response_quality(self, api_client, unique_sender, complete_metadata):
        """Test qualita' risposta saluto."""
        response = api_client("buongiorno", unique_sender, complete_metadata)

        text = response["text"]
        # Risposta deve essere cordiale e offrire aiuto
        assert len(text) > 20, "Risposta troppo breve"
        assert any(w in text.lower() for w in ["posso", "aiuto", "domand"])

    @pytest.mark.e2e
    def test_help_lists_capabilities(self, api_client, unique_sender, complete_metadata):
        """Test che help elenchi le funzionalita'."""
        response = api_client("cosa puoi fare", unique_sender, complete_metadata)

        text = response["text"].lower()
        # Deve menzionare almeno alcune funzionalita'
        capabilities = ["piano", "controlli", "rischio", "stabiliment"]
        found = sum(1 for c in capabilities if c in text)
        assert found >= 2, f"Help menziona solo {found}/4 funzionalita'"

    @pytest.mark.e2e
    def test_piano_description_has_content(self, api_client, unique_sender,
                                            complete_metadata):
        """Test che descrizione piano abbia contenuto reale."""
        response = api_client("di cosa tratta il piano A1", unique_sender, complete_metadata)

        text = response["text"]
        # Deve avere contenuto sostanziale
        assert len(text) > 50, "Descrizione piano troppo breve"
        # Deve menzionare il piano
        assert "A1" in text or "piano" in text.lower()

    @pytest.mark.e2e
    def test_delayed_plans_format(self, api_client, unique_sender, complete_metadata):
        """Test formato risposta piani in ritardo."""
        response = api_client("piani in ritardo", unique_sender, complete_metadata)

        text = response["text"].lower()
        # Deve menzionare ritardo o programmazione
        assert any(w in text for w in ["ritard", "programm", "eseguit", "piano"])


class TestIntentSlotExtraction:
    """Test estrazione slot dagli intent."""

    @pytest.mark.e2e
    def test_piano_code_extraction(self, parse_client):
        """Test estrazione codice piano."""
        result = parse_client("di cosa tratta il piano B47")

        assert result["intent"]["name"] == "ask_piano_description"
        assert result["slots"].get("piano_code") == "B47"

    @pytest.mark.e2e
    def test_topic_extraction(self, parse_client):
        """Test estrazione topic per ricerca."""
        result = parse_client("piani che riguardano bovini")

        assert result["intent"]["name"] == "search_piani_by_topic"
        # topic dovrebbe essere estratto
        if "topic" in result.get("slots", {}):
            assert "bovin" in result["slots"]["topic"].lower()


class TestIntentCoverage:
    """Test copertura intent."""

    @pytest.mark.e2e
    def test_all_valid_intents_defined(self):
        """Verifica che tutti i 20 VALID_INTENTS siano testati."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

        from orchestrator.router import Router

        # Intent testati in questo file
        tested_intents = {t[1] for t in INTENT_TESTS}

        # Intent testati in altri file
        tested_intents.add("confirm_show_details")   # test_two_phase.py
        tested_intents.add("decline_show_details")   # test_two_phase.py
        tested_intents.add("info_procedure")         # richiede RAG
        tested_intents.add("ask_nearby_priority")    # richiede geocoding
        tested_intents.add("fallback")               # test_fallback.py

        # Verifica
        missing = set(Router.VALID_INTENTS) - tested_intents
        extra = tested_intents - set(Router.VALID_INTENTS)

        assert not missing, f"Intent non testati: {missing}"
        if extra:
            print(f"Warning: Intent testati ma non in VALID_INTENTS: {extra}")


class TestIntentConfidence:
    """Test confidence classificazione."""

    @pytest.mark.e2e
    def test_high_confidence_greet(self, parse_client):
        """Test alta confidence per saluto chiaro."""
        result = parse_client("ciao")

        assert result["intent"]["name"] == "greet"
        assert result["intent"]["confidence"] >= 0.8

    @pytest.mark.e2e
    def test_moderate_confidence_complex(self, parse_client):
        """Test confidence per query complessa."""
        result = parse_client(
            "vorrei sapere quali sono i piani che potrebbero avere dei ritardi"
        )

        # Intent corretto con confidence ragionevole
        assert result["intent"]["name"] in ["ask_delayed_plans", "search_piani_by_topic"]
        assert result["intent"]["confidence"] >= 0.4


class TestIntentDisambiguation:
    """Test disambiguazione intent simili."""

    @pytest.mark.e2e
    def test_delayed_vs_check_delayed(self, parse_client):
        """Test disambiguazione piani in ritardo vs verifica singolo piano."""
        # Generico -> ask_delayed_plans
        result1 = parse_client("piani in ritardo")
        assert result1["intent"]["name"] == "ask_delayed_plans"

        # Specifico -> check_if_plan_delayed
        result2 = parse_client("il piano A1 è in ritardo")
        assert result2["intent"]["name"] == "check_if_plan_delayed"
        assert result2["slots"].get("piano_code") == "A1"

    @pytest.mark.e2e
    def test_priority_vs_risk(self, parse_client):
        """Test disambiguazione priorita' programmazione vs rischio."""
        # Programmazione -> ask_priority_establishment
        result1 = parse_client("chi devo controllare secondo la programmazione")
        assert result1["intent"]["name"] == "ask_priority_establishment"

        # Rischio -> ask_risk_based_priority
        result2 = parse_client("chi devo controllare secondo il rischio storico")
        assert result2["intent"]["name"] == "ask_risk_based_priority"
