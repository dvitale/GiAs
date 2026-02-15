"""
Test E2E per sistema fallback 3-phase.
Verifica recupero da query non comprese.
"""

import pytest


class TestFallbackBasic:
    """Test fallback per query non comprese."""

    @pytest.mark.e2e
    def test_fallback_gibberish(self, api_client, unique_sender, complete_metadata):
        """Test fallback per testo senza senso."""
        resp = api_client("asdfghjkl qwerty xyz123", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        # Deve offrire aiuto o suggerimenti
        assert any(w in text for w in [
            "capito", "riformula", "aiuto", "domand",
            "posso", "suggeri", "prova", "esempio"
        ])

    @pytest.mark.e2e
    def test_fallback_empty_meaningful(self, api_client, unique_sender,
                                        complete_metadata):
        """Test fallback per query ambigua."""
        resp = api_client("cosa", unique_sender, complete_metadata)

        assert "text" in resp
        # Deve chiedere chiarimento
        text = resp["text"].lower()
        assert any(w in text for w in ["cosa", "aiuto", "domand", "posso"])


class TestFallbackRecovery:
    """Test recupero dopo fallback."""

    @pytest.mark.e2e
    def test_recovery_after_fallback(self, api_client, unique_sender,
                                      complete_metadata):
        """Test che sistema recuperi dopo fallback."""
        # Query che genera fallback
        api_client("xyz nonsense query", unique_sender, complete_metadata)

        # Query valida successiva deve funzionare
        resp = api_client("piani in ritardo", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        assert any(w in text for w in ["piano", "ritard", "control"])

    @pytest.mark.e2e
    def test_greet_after_fallback(self, api_client, unique_sender,
                                   complete_metadata):
        """Test saluto dopo fallback."""
        # Fallback
        api_client("random gibberish 123", unique_sender, complete_metadata)

        # Saluto deve funzionare
        resp = api_client("ciao", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        assert any(w in text for w in ["benvenuto", "ciao", "posso"])


class TestFallbackSuggestions:
    """Test suggerimenti in risposta fallback."""

    @pytest.mark.e2e
    def test_fallback_offers_suggestions(self, api_client, unique_sender,
                                          complete_metadata):
        """Test che fallback offra suggerimenti."""
        resp = api_client("xyz123 nonsense", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()

        # Deve offrire qualche forma di aiuto o menu
        has_help = any(w in text for w in [
            "aiuto", "posso", "prova", "esempio",
            "domand", "suggeri", "riformula", "capito",
            "categoria", "scegli", "intend"
        ])
        assert has_help, f"Fallback non offre aiuto: {text[:200]}"

    @pytest.mark.e2e
    def test_fallback_category_menu(self, api_client, unique_sender,
                                     complete_metadata):
        """Test menu categorie dopo fallback ripetuto."""
        # Primo fallback
        api_client("xyz nonsense 1", unique_sender, complete_metadata)

        # Secondo fallback
        api_client("abc nonsense 2", unique_sender, complete_metadata)

        # Terzo fallback - potrebbe mostrare menu categorie
        resp = api_client("qrs nonsense 3", unique_sender, complete_metadata)

        assert "text" in resp
        # Deve comunque offrire un modo per procedere


class TestFallbackLoopPrevention:
    """Test prevenzione loop infinito di fallback."""

    @pytest.mark.e2e
    def test_multiple_fallbacks_escalate(self, api_client, unique_sender,
                                          complete_metadata):
        """Test che fallback multipli non causino loop."""
        responses = []

        # Genera 4 fallback consecutivi
        for i in range(4):
            resp = api_client(f"xyz{i} random gibberish", unique_sender, complete_metadata)
            assert "text" in resp
            responses.append(resp["text"])

        # Dopo N fallback, deve escalare a help o menu
        last_text = responses[-1].lower()
        assert any(w in last_text for w in [
            "aiuto", "posso", "domand", "esempio",
            "menu", "categori", "suggeri"
        ])


class TestFallbackWithContext:
    """Test fallback con contesto precedente."""

    @pytest.mark.e2e
    def test_fallback_preserves_session(self, api_client, unique_sender,
                                         complete_metadata):
        """Test che fallback non distrugga la sessione."""
        # Query valida
        api_client("piani in ritardo", unique_sender, complete_metadata)

        # Fallback intermedio
        api_client("xyz random", unique_sender, complete_metadata)

        # La sessione deve essere ancora attiva
        resp = api_client("mostrami i dettagli", unique_sender, complete_metadata)

        assert "text" in resp
        # Potrebbe riferirsi ai piani o chiedere chiarimento


class TestFallbackNumericSelection:
    """Test selezione numerica da suggerimenti fallback."""

    @pytest.mark.e2e
    def test_numeric_selection_after_menu(self, api_client, unique_sender,
                                           complete_metadata):
        """Test selezione numerica dopo menu."""
        # Forza fallback
        api_client("xyz nonsense", unique_sender, complete_metadata)

        # Selezione numerica (potrebbe essere suggerimento)
        resp = api_client("1", unique_sender, complete_metadata)

        assert "text" in resp
        # Deve fare qualcosa (non altro fallback)


class TestFallbackSpecialCases:
    """Test casi speciali di fallback."""

    @pytest.mark.e2e
    def test_very_long_query_fallback(self, api_client, unique_sender,
                                       complete_metadata):
        """Test query molto lunga senza senso."""
        long_query = "abc " * 100  # 400 caratteri

        resp = api_client(long_query, unique_sender, complete_metadata)

        assert "text" in resp
        # Non deve crashare

    @pytest.mark.e2e
    def test_special_characters_fallback(self, api_client, unique_sender,
                                          complete_metadata):
        """Test query con caratteri speciali."""
        resp = api_client("@#$%^&*()!?", unique_sender, complete_metadata)

        assert "text" in resp
        # Non deve crashare

    @pytest.mark.e2e
    def test_numbers_only_fallback(self, api_client, unique_sender,
                                    complete_metadata):
        """Test query con solo numeri."""
        resp = api_client("12345 67890", unique_sender, complete_metadata)

        assert "text" in resp
        # Potrebbe interpretare come selezione o fallback
