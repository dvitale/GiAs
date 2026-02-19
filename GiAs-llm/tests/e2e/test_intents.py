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

    # Nearby priority (1)
    ("stabilimenti vicino a Benevento", "ask_nearby_priority",
     ["stabil", "vicin", "km", "benevento"]),
]


class TestIntentsComplete:
    """Test E2E per tutti gli intent principali."""

    @pytest.mark.e2e
    @pytest.mark.parametrize("query,expected_intent,patterns", INTENT_TESTS)
    def test_intent_response(self, api_client, unique_sender, complete_metadata,
                             query, expected_intent, patterns):
        """Test singolo intent con payload frontend completo."""
        response = api_client(query, unique_sender, complete_metadata)

        # Verifica base risposta
        assert "text" in response, (
            f"Response senza 'text'"
            f"\n  Query: {query}"
            f"\n  Expected intent: {expected_intent}"
            f"\n  Response: {response}"
        )

        text = response["text"].lower()
        actual_intent = response.get("custom", {}).get("intent", "N/A")
        confidence = response.get("custom", {}).get("confidence", "N/A")

        # Verifica pattern
        found_patterns = [p for p in patterns if p.lower() in text]
        missing_patterns = [p for p in patterns if p.lower() not in text]

        assert len(found_patterns) > 0, (
            f"\n{'='*60}"
            f"\nINTENT TEST FAILURE"
            f"\n{'='*60}"
            f"\nQuery: {query}"
            f"\nExpected intent: {expected_intent}"
            f"\nActual intent: {actual_intent}"
            f"\nConfidence: {confidence}"
            f"\n{'='*60}"
            f"\nPattern analysis:"
            f"\n  Expected: {patterns}"
            f"\n  Found: {found_patterns}"
            f"\n  Missing: {missing_patterns}"
            f"\n{'='*60}"
            f"\nResponse (first 400 chars):"
            f"\n{text[:400]}..."
            f"\n{'='*60}"
        )

    @pytest.mark.e2e
    def test_greet_response_quality(self, api_client, unique_sender, complete_metadata):
        """Test qualita' risposta saluto."""
        query = "buongiorno"
        response = api_client(query, unique_sender, complete_metadata)

        text = response["text"]
        # Risposta deve essere cordiale e offrire aiuto
        assert len(text) > 20, (
            f"Risposta troppo breve"
            f"\n  Query: {query}"
            f"\n  Response length: {len(text)}"
            f"\n  Response: {text}"
        )
        assert any(w in text.lower() for w in ["posso", "aiuto", "domand"]), (
            f"Risposta non offre aiuto"
            f"\n  Query: {query}"
            f"\n  Response: {text[:300]}..."
        )

    @pytest.mark.e2e
    def test_help_lists_capabilities(self, api_client, unique_sender, complete_metadata):
        """Test che help elenchi le funzionalita'."""
        query = "cosa puoi fare"
        response = api_client(query, unique_sender, complete_metadata)

        text = response["text"].lower()
        # Deve menzionare almeno alcune funzionalita'
        capabilities = ["piano", "controlli", "rischio", "stabiliment"]
        found = [c for c in capabilities if c in text]
        assert len(found) >= 2, (
            f"Help non elenca funzionalita'"
            f"\n  Query: {query}"
            f"\n  Expected capabilities: {capabilities}"
            f"\n  Found: {found} ({len(found)}/4)"
            f"\n  Response: {text[:400]}..."
        )

    @pytest.mark.e2e
    def test_piano_description_has_content(self, api_client, unique_sender,
                                            complete_metadata):
        """Test che descrizione piano abbia contenuto reale."""
        query = "di cosa tratta il piano A1"
        response = api_client(query, unique_sender, complete_metadata)

        text = response["text"]
        # Deve avere contenuto sostanziale
        assert len(text) > 50, (
            f"Descrizione piano troppo breve"
            f"\n  Query: {query}"
            f"\n  Response length: {len(text)}"
            f"\n  Response: {text}"
        )
        # Deve menzionare il piano
        assert "A1" in text or "piano" in text.lower(), (
            f"Risposta non menziona piano"
            f"\n  Query: {query}"
            f"\n  Response: {text[:300]}..."
        )

    @pytest.mark.e2e
    def test_delayed_plans_format(self, api_client, unique_sender, complete_metadata):
        """Test formato risposta piani in ritardo."""
        query = "piani in ritardo"
        response = api_client(query, unique_sender, complete_metadata)

        text = response["text"].lower()
        expected_keywords = ["ritard", "programm", "eseguit", "piano"]
        found = [w for w in expected_keywords if w in text]
        # Deve menzionare ritardo o programmazione
        assert len(found) > 0, (
            f"Risposta non pertinente"
            f"\n  Query: {query}"
            f"\n  Expected keywords: {expected_keywords}"
            f"\n  Found: {found}"
            f"\n  Response: {text[:400]}..."
        )


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
        tested_intents.add("info_procedure")         # integration/test_rag_consistency.py
        # ask_nearby_priority: ora coperto in INTENT_TESTS
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
