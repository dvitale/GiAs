"""
Test unitari per il riconoscimento saluti, commiati, heuristiche minimali e gibberish.

Con LLM-First, greet/goodbye/help NON sono piu' nelle heuristiche ma delegati
all'LLM (o al LAYER 6 fallback se LLM non disponibile).
Le heuristiche gestiscono solo: conferme/rifiuti e disambiguazione rischio.
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


class TestMinimalHeuristics:
    """Test che le heuristiche minimali funzionino correttamente."""

    def test_confirm_explicit(self, router):
        """Conferme esplicite devono essere riconosciute via heuristic."""
        confirms = ["sì mostrami", "vediamo tutti", "mostrami i dettagli"]
        for msg in confirms:
            result = router._try_heuristics(msg, has_detail_context=False)
            assert result is not None, f"'{msg}' non riconosciuto come conferma"
            assert result["intent"] == "confirm_show_details"

    def test_decline_explicit(self, router):
        """Rifiuti espliciti devono essere riconosciuti via heuristic."""
        declines = ["no grazie", "basta", "va bene così"]
        for msg in declines:
            result = router._try_heuristics(msg, has_detail_context=False)
            assert result is not None, f"'{msg}' non riconosciuto come rifiuto"
            assert result["intent"] == "decline_show_details"

    def test_confirm_short_with_context(self, router):
        """Conferme brevi riconosciute solo con detail_context."""
        shorts = ["sì", "ok", "vai"]
        for msg in shorts:
            # Senza context → None
            result = router._try_heuristics(msg, has_detail_context=False)
            assert result is None, f"'{msg}' non dovrebbe matchare senza context"
            # Con context → confirm
            result = router._try_heuristics(msg, has_detail_context=True)
            assert result is not None, f"'{msg}' non riconosciuto con context"
            assert result["intent"] == "confirm_show_details"

    def test_decline_short_with_context(self, router):
        """Rifiuti brevi riconosciuti solo con detail_context."""
        result = router._try_heuristics("no", has_detail_context=False)
        assert result is None
        result = router._try_heuristics("no", has_detail_context=True)
        assert result is not None
        assert result["intent"] == "decline_show_details"

    def test_risk_disambiguation_mai_controllati(self, router):
        """Disambiguazione rischio: mai controllati."""
        for msg in ["1", "mai controllati", "non controllati"]:
            result = router._try_heuristics(msg, has_detail_context=False)
            assert result is not None, f"'{msg}' non riconosciuto come disambiguazione rischio"
            assert result["intent"] == "ask_risk_based_priority"
            assert result["slots"]["tipo_analisi_rischio"] == "mai_controllati"

    def test_risk_disambiguation_con_sanzioni(self, router):
        """Disambiguazione rischio: con sanzioni."""
        for msg in ["2", "con sanzioni", "più sanzionati"]:
            result = router._try_heuristics(msg, has_detail_context=False)
            assert result is not None, f"'{msg}' non riconosciuto come disambiguazione rischio"
            assert result["intent"] == "ask_risk_based_priority"
            assert result["slots"]["tipo_analisi_rischio"] == "con_sanzioni"


class TestGreetNotInHeuristics:
    """Test che greet/goodbye/help NON siano nelle heuristiche (delegati a LLM)."""

    @pytest.mark.parametrize("greeting", [
        "ciao", "salve", "buongiorno", "buonasera",
        "buonanotte", "buon pomeriggio",
    ])
    def test_greet_not_heuristic(self, router, greeting):
        """Saluti devono restituire None (delegati a LLM)."""
        result = router._try_heuristics(greeting, has_detail_context=False)
        assert result is None, f"'{greeting}' non dovrebbe essere nelle heuristiche"

    @pytest.mark.parametrize("goodbye", [
        "arrivederci", "alla prossima", "ci vediamo",
    ])
    def test_goodbye_not_heuristic(self, router, goodbye):
        """Commiati devono restituire None (delegati a LLM)."""
        result = router._try_heuristics(goodbye, has_detail_context=False)
        assert result is None, f"'{goodbye}' non dovrebbe essere nelle heuristiche"


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

    @pytest.mark.parametrize("greeting", [
        "ciao", "salve", "buongiorno", "buonasera",
        "hey", "hi", "hello",
    ])
    def test_greet_not_gibberish(self, router, greeting):
        """Saluti NON devono essere rilevati come gibberish."""
        assert not router._is_gibberish(greeting), \
            f"'{greeting}' erroneamente rilevato come gibberish"

    @pytest.mark.parametrize("goodbye", [
        "arrivederci", "bye", "addio",
    ])
    def test_goodbye_not_gibberish(self, router, goodbye):
        """Commiati NON devono essere rilevati come gibberish."""
        assert not router._is_gibberish(goodbye), \
            f"'{goodbye}' erroneamente rilevato come gibberish"

    @pytest.mark.parametrize("gibberish", [
        "asdfghjkl", "xxxyyy", "zzz123", "bla bla bla",
    ])
    def test_real_gibberish_detected(self, router, gibberish):
        """Gibberish vero deve essere ancora rilevato."""
        assert router._is_gibberish(gibberish), \
            f"'{gibberish}' non rilevato come gibberish"

    @pytest.mark.parametrize("long_message", [
        "questa domanda non ha keyword ma è lunga abbastanza",
        "vorrei sapere qualcosa di interessante per il mio lavoro",
    ])
    def test_long_messages_pass_to_llm(self, router, long_message):
        """Messaggi >15 char passano all'LLM (non gibberish)."""
        assert not router._is_gibberish(long_message), \
            f"'{long_message}' non dovrebbe essere gibberish (>15 char)"


class TestFullClassifyGreetings:
    """Test classify() completo per saluti (via LAYER 6 fallback se LLM non disponibile)."""

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
        """classify() deve riconoscere saluti e commiati (LLM o LAYER 6 fallback)."""
        result = router.classify(greeting)
        assert result["intent"] == expected_intent, \
            f"'{greeting}' classificato come {result['intent']} invece di {expected_intent}"
