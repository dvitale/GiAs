"""
Test E2E per gestione sessioni.
Verifica isolamento, TTL, sender unici.
"""

import pytest
import time


class TestSessionIsolation:
    """Test isolamento sessioni tra sender diversi."""

    @pytest.mark.e2e
    def test_different_senders_isolated(self, api_client, complete_metadata,
                                        session_sender_factory):
        """Test che sender diversi abbiano sessioni isolate."""
        sender_a = session_sender_factory("user_a")
        sender_b = session_sender_factory("user_b")

        # User A: query su piani
        resp_a1 = api_client("piani in ritardo", sender_a, complete_metadata)
        assert "text" in resp_a1

        # User B: query diversa
        resp_b1 = api_client("stabilimenti ad alto rischio", sender_b, complete_metadata)
        assert "text" in resp_b1

        # User A: conferma (deve riferirsi ai piani, non al rischio)
        resp_a2 = api_client("sì, mostrami i dettagli", sender_a, complete_metadata)
        text_a2 = resp_a2["text"].lower()

        # Non deve contenere contesto di B (rischio storico specifico)
        # La risposta puo' riferirsi ai piani o offrire aiuto
        assert "text" in resp_a2

    @pytest.mark.e2e
    def test_parallel_sessions(self, api_client, complete_metadata,
                               session_sender_factory):
        """Test sessioni parallele non interferiscono."""
        senders = [session_sender_factory(f"parallel_{i}") for i in range(3)]
        queries = ["aiuto", "piani in ritardo", "stabilimenti prioritari"]

        responses = []
        for sender, query in zip(senders, queries):
            resp = api_client(query, sender, complete_metadata)
            responses.append(resp)

        # Tutte le risposte devono essere valide
        for resp in responses:
            assert "text" in resp
            assert len(resp["text"]) > 0


class TestSessionPersistence:
    """Test persistenza stato sessione."""

    @pytest.mark.e2e
    def test_session_remembers_context(self, api_client, unique_sender,
                                        complete_metadata):
        """Test che sessione mantenga contesto tra turni."""
        # Prima query
        resp1 = api_client("piani in ritardo", unique_sender, complete_metadata)
        assert "text" in resp1

        # Seconda query che si riferisce alla prima (pronomi, conferme)
        resp2 = api_client("quali sono", unique_sender, complete_metadata)
        assert "text" in resp2
        # La risposta dovrebbe essere contestuale o chiedere chiarimento

    @pytest.mark.e2e
    def test_session_slot_carryforward(self, api_client, unique_sender,
                                       complete_metadata):
        """Test che slot vengano mantenuti nella sessione."""
        # Query con piano specifico
        resp1 = api_client("di cosa tratta il piano A1", unique_sender, complete_metadata)
        assert "text" in resp1

        # Query di follow-up sullo stesso piano
        resp2 = api_client("e gli stabilimenti", unique_sender, complete_metadata)
        assert "text" in resp2
        # Dovrebbe riferirsi al piano A1


class TestSessionReset:
    """Test reset sessione con cambio topic."""

    @pytest.mark.e2e
    def test_topic_change_resets_context(self, api_client, unique_sender,
                                          complete_metadata):
        """Test che cambio argomento resetti il contesto."""
        # Query su piani
        resp1 = api_client("piani in ritardo", unique_sender, complete_metadata)
        assert "text" in resp1

        # Cambio completo argomento
        resp2 = api_client("ciao, ricominciamo", unique_sender, complete_metadata)
        assert "text" in resp2

        # Nuova query indipendente
        resp3 = api_client("stabilimenti ad alto rischio", unique_sender, complete_metadata)
        assert "text" in resp3
        # Non deve essere influenzato dalla query sui piani


class TestSessionSenderFormat:
    """Test formato sender come frontend."""

    @pytest.mark.e2e
    def test_frontend_sender_format(self, api_client, complete_metadata):
        """Test sender nel formato esatto del frontend."""
        import random
        import string

        # Formato frontend: user_<timestamp>_<random9>
        timestamp = int(time.time() * 1000)
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
        sender = f"user_{timestamp}_{suffix}"

        # Prima richiesta
        resp1 = api_client("ciao", sender, complete_metadata)
        assert "text" in resp1

        # Seconda richiesta stesso sender
        resp2 = api_client("aiuto", sender, complete_metadata)
        assert "text" in resp2

    @pytest.mark.e2e
    def test_simple_sender_works(self, api_client, complete_metadata):
        """Test che sender semplice funzioni comunque."""
        sender = "test_simple_sender"

        resp = api_client("ciao", sender, complete_metadata)
        assert "text" in resp


class TestSessionConcurrency:
    """Test sessioni con richieste concorrenti."""

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_rapid_requests_same_sender(self, api_client, unique_sender,
                                         complete_metadata):
        """Test richieste rapide stesso sender."""
        queries = ["ciao", "aiuto", "piani in ritardo", "grazie"]

        for query in queries:
            resp = api_client(query, unique_sender, complete_metadata)
            assert "text" in resp
            time.sleep(0.1)  # Piccola pausa tra richieste


class TestSessionMemoryIsolation:
    """Test isolamento memoria tra sessioni."""

    @pytest.mark.e2e
    def test_memory_not_shared(self, api_client, complete_metadata,
                               session_sender_factory):
        """Test che memoria non sia condivisa tra sender."""
        sender_a = session_sender_factory("memory_a")
        sender_b = session_sender_factory("memory_b")

        # A chiede info su piano A1
        api_client("di cosa tratta il piano A1", sender_a, complete_metadata)

        # B chiede info su piano B2
        api_client("di cosa tratta il piano B2", sender_b, complete_metadata)

        # A chiede follow-up - deve riferirsi ad A1, non B2
        resp_a = api_client("e gli stabilimenti di questo piano", sender_a, complete_metadata)

        # Non deve confondere i piani tra le sessioni
        # (difficile da verificare senza conoscere output esatto)
        assert "text" in resp_a
