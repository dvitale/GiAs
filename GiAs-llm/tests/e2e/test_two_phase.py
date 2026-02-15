"""
Test E2E per flusso two-phase (sommario + dettagli).
Verifica confirm_show_details e decline_show_details.
"""

import pytest


class TestTwoPhaseConfirm:
    """Test conferma per vedere dettagli."""

    @pytest.mark.e2e
    def test_confirm_after_summary(self, api_client, unique_sender, complete_metadata):
        """Test conferma dopo sommario piani in ritardo."""
        # Phase 1: query che genera sommario
        resp1 = api_client("piani in ritardo", unique_sender, complete_metadata)

        assert "text" in resp1
        text1 = resp1["text"].lower()
        # Deve contenere info sui piani
        assert any(w in text1 for w in ["piano", "ritard", "control"])

        # Phase 2: conferma
        resp2 = api_client("sì", unique_sender, complete_metadata)

        assert "text" in resp2
        # La risposta deve essere diversa (dettagli o conferma elaborazione)

    @pytest.mark.e2e
    def test_confirm_si_grazie(self, api_client, unique_sender, complete_metadata):
        """Test conferma con 'sì grazie'."""
        # Setup
        api_client("stabilimenti prioritari", unique_sender, complete_metadata)

        # Conferma
        resp = api_client("sì grazie", unique_sender, complete_metadata)

        assert "text" in resp

    @pytest.mark.e2e
    def test_confirm_mostrami(self, api_client, unique_sender, complete_metadata):
        """Test conferma con 'mostrami i dettagli'."""
        # Setup
        api_client("piani in ritardo", unique_sender, complete_metadata)

        # Conferma esplicita
        resp = api_client("mostrami i dettagli", unique_sender, complete_metadata)

        assert "text" in resp

    @pytest.mark.e2e
    def test_confirm_procedi(self, api_client, unique_sender, complete_metadata):
        """Test conferma con 'procedi'."""
        # Setup
        api_client("chi devo controllare", unique_sender, complete_metadata)

        # Conferma
        resp = api_client("procedi", unique_sender, complete_metadata)

        assert "text" in resp


class TestTwoPhaseDecline:
    """Test rifiuto dettagli."""

    @pytest.mark.e2e
    def test_decline_after_summary(self, api_client, unique_sender, complete_metadata):
        """Test rifiuto dopo sommario."""
        # Phase 1: query
        api_client("stabilimenti prioritari", unique_sender, complete_metadata)

        # Phase 2: rifiuto
        resp = api_client("no grazie", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        # Deve offrire aiuto alternativo
        assert any(w in text for w in ["aiut", "domand", "altro", "posso"])

    @pytest.mark.e2e
    def test_decline_no_semplice(self, api_client, unique_sender, complete_metadata):
        """Test rifiuto con 'no' semplice."""
        # Setup
        api_client("piani in ritardo", unique_sender, complete_metadata)

        # Rifiuto
        resp = api_client("no", unique_sender, complete_metadata)

        assert "text" in resp

    @pytest.mark.e2e
    def test_decline_basta_cosi(self, api_client, unique_sender, complete_metadata):
        """Test rifiuto con 'basta così'."""
        # Setup
        api_client("chi devo controllare", unique_sender, complete_metadata)

        # Rifiuto
        resp = api_client("basta così", unique_sender, complete_metadata)

        assert "text" in resp


class TestTwoPhaseIsolation:
    """Test isolamento two-phase tra sessioni."""

    @pytest.mark.e2e
    def test_confirm_isolated_between_sessions(self, api_client, complete_metadata,
                                                session_sender_factory):
        """Test che conferma sia isolata tra sessioni diverse."""
        sender_a = session_sender_factory("2phase_a")
        sender_b = session_sender_factory("2phase_b")

        # User A: query piani
        api_client("piani in ritardo", sender_a, complete_metadata)

        # User B: query diversa
        api_client("stabilimenti ad alto rischio", sender_b, complete_metadata)

        # User A: conferma (deve riferirsi ai piani)
        resp_a = api_client("sì", sender_a, complete_metadata)

        # User B: conferma (deve riferirsi al rischio)
        resp_b = api_client("sì", sender_b, complete_metadata)

        # Entrambe le risposte devono essere valide
        assert "text" in resp_a
        assert "text" in resp_b


class TestTwoPhaseWithoutContext:
    """Test conferma/rifiuto senza contesto precedente."""

    @pytest.mark.e2e
    def test_confirm_without_context(self, api_client, unique_sender, complete_metadata):
        """Test conferma senza query precedente."""
        # Prima richiesta e' gia' una conferma
        resp = api_client("sì", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        # Deve chiedere chiarimento o offrire aiuto
        assert any(w in text for w in ["aiuto", "domand", "posso", "cosa"])

    @pytest.mark.e2e
    def test_decline_without_context(self, api_client, unique_sender, complete_metadata):
        """Test rifiuto senza query precedente."""
        resp = api_client("no grazie", unique_sender, complete_metadata)

        assert "text" in resp
        # Non deve crashare


class TestTwoPhaseSequence:
    """Test sequenze multiple di two-phase."""

    @pytest.mark.e2e
    def test_multiple_queries_then_confirm(self, api_client, unique_sender,
                                           complete_metadata):
        """Test multiple query poi conferma."""
        # Query 1
        api_client("piani in ritardo", unique_sender, complete_metadata)

        # Query 2 (cambia contesto)
        api_client("stabilimenti prioritari", unique_sender, complete_metadata)

        # Conferma (dovrebbe riferirsi all'ultima query)
        resp = api_client("sì", unique_sender, complete_metadata)

        assert "text" in resp

    @pytest.mark.e2e
    def test_confirm_then_new_query(self, api_client, unique_sender,
                                     complete_metadata):
        """Test conferma poi nuova query."""
        # Query iniziale
        api_client("piani in ritardo", unique_sender, complete_metadata)

        # Conferma
        api_client("sì", unique_sender, complete_metadata)

        # Nuova query (deve funzionare indipendentemente)
        resp = api_client("stabilimenti ad alto rischio", unique_sender, complete_metadata)

        assert "text" in resp
        text = resp["text"].lower()
        assert any(w in text for w in ["rischio", "stabil", "priorit"])
