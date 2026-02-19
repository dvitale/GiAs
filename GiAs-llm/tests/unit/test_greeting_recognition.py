"""
Test unitari per il riconoscimento saluti e commiati nel Router.
Verifica che pattern espansi e gibberish detector funzionino correttamente.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from orchestrator.router import Router


@pytest.fixture
def router():
    """Router con LLM mock (non serve LLM reale per test heuristic)."""
    return Router()


class TestGreetPatterns:
    """Test che GREET_PATTERNS riconosca tutti i saluti comuni."""

    @pytest.mark.parametrize("greeting", [
        "ciao", "salve", "buongiorno", "buonasera",
        "buondì", "buon pomeriggio", "buonanotte",
        "hey", "hi", "hello", "saluti",
        "ehilà", "ehi", "ben trovato", "ben tornato", "eccomi",
        # Varianti con maiuscole/punteggiatura
        "Ciao", "BUONGIORNO", "Buonasera!",
    ])
    def test_greet_heuristic(self, router, greeting):
        """Saluti comuni devono essere riconosciuti via heuristic."""
        result = router._try_heuristics(greeting, has_detail_context=False)
        assert result is not None, f"'{greeting}' non riconosciuto come saluto via heuristic"
        assert result["intent"] == "greet", f"'{greeting}' classificato come {result['intent']} invece di greet"

    @pytest.mark.parametrize("not_greeting", [
        "buongiorno mi serve aiuto con i piani in ritardo",
        "salve vorrei sapere dei controlli ufficiali",
    ])
    def test_greet_with_long_question_not_heuristic(self, router, not_greeting):
        """Saluto + domanda lunga NON deve matchare come greet via heuristic."""
        result = router._try_heuristics(not_greeting, has_detail_context=False)
        # Deve essere None (passa all'LLM) oppure un intent diverso da greet
        if result is not None:
            assert result["intent"] != "greet", f"'{not_greeting}' erroneamente classificato come greet"


class TestGoodbyePatterns:
    """Test che GOODBYE_PATTERNS riconosca tutti i commiati comuni."""

    @pytest.mark.parametrize("goodbye", [
        "arrivederci", "bye", "addio", "a presto", "buon lavoro",
        "alla prossima", "ci vediamo", "a domani",
        "tanti saluti", "stammi bene",
    ])
    def test_goodbye_heuristic(self, router, goodbye):
        """Commiati comuni devono essere riconosciuti via heuristic."""
        result = router._try_heuristics(goodbye, has_detail_context=False)
        assert result is not None, f"'{goodbye}' non riconosciuto come goodbye via heuristic"
        assert result["intent"] == "goodbye", f"'{goodbye}' classificato come {result['intent']} invece di goodbye"


class TestGibberishBypass:
    """Test che il gibberish detector NON blocchi saluti e convenevoli."""

    @pytest.mark.parametrize("social_message", [
        "buonanotte", "buondì", "buon pomeriggio",
        "tanti saluti", "ben trovato", "ben tornato",
        "come stai", "come va", "ehilà",
        "alla prossima", "ci vediamo", "a domani",
        "grazie", "piacere", "ciao ciao",
        "buona giornata", "buona serata",
    ])
    def test_social_not_gibberish(self, router, social_message):
        """Espressioni sociali NON devono essere rilevate come gibberish."""
        assert not router._is_gibberish(social_message), \
            f"'{social_message}' erroneamente rilevato come gibberish"

    @pytest.mark.parametrize("gibberish", [
        "asdfghjkl", "xxxyyy", "zzz123", "bla bla bla",
    ])
    def test_real_gibberish_detected(self, router, gibberish):
        """Gibberish vero deve essere ancora rilevato."""
        assert router._is_gibberish(gibberish), \
            f"'{gibberish}' non rilevato come gibberish"


class TestFullClassifyGreetings:
    """Test classify() completo per saluti (usa mock LLM)."""

    @pytest.mark.parametrize("greeting,expected_intent", [
        ("ciao", "greet"),
        ("buongiorno", "greet"),
        ("buonanotte", "greet"),
        ("buon pomeriggio", "greet"),
        ("arrivederci", "goodbye"),
        ("tanti saluti", "goodbye"),
        ("alla prossima", "goodbye"),
    ])
    def test_classify_greetings(self, router, greeting, expected_intent):
        """classify() deve riconoscere saluti e commiati."""
        result = router.classify(greeting)
        assert result["intent"] == expected_intent, \
            f"'{greeting}' classificato come {result['intent']} invece di {expected_intent}"
