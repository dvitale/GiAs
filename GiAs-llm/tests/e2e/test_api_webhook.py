"""
Test E2E per endpoint chat principale (/api/v1/chat).
Replica esattamente le chiamate dal frontend gchat.
"""

import pytest
import requests
import time
import random
import string


class TestChatBasic:
    """Test base per /api/v1/chat."""

    @pytest.mark.e2e
    def test_chat_greet(self, webhook_url, unique_sender, complete_metadata):
        """Test saluto base come frontend."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "text" in data["result"]
        # Verifica risposta di benvenuto
        text = data["result"]["text"].lower()
        assert any(word in text for word in ["benvenuto", "ciao", "buon", "posso aiutarti"])

    @pytest.mark.e2e
    def test_chat_help(self, webhook_url, unique_sender, complete_metadata):
        """Test richiesta aiuto."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        text = data["result"]["text"].lower()
        # Deve elencare funzionalita'
        assert any(word in text for word in ["posso", "aiutarti", "domand", "funzionalit"])

    @pytest.mark.e2e
    def test_chat_goodbye(self, webhook_url, unique_sender, complete_metadata):
        """Test saluto finale."""
        payload = {
            "sender": unique_sender,
            "message": "arrivederci",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        text = data["result"]["text"].lower()
        assert any(word in text for word in ["arrivederci", "buon lavoro", "presto"])


class TestChatMetadata:
    """Test gestione metadata come frontend."""

    @pytest.mark.e2e
    def test_chat_all_metadata_fields(self, webhook_url, unique_sender):
        """Test con tutti i campi metadata come frontend reale."""
        payload = {
            "sender": unique_sender,
            "message": "piani in ritardo",
            "metadata": {
                "asl": "BENEVENTO",
                "asl_id": "202",
                "user_id": "6448",
                "codice_fiscale": "ZZIBRD65R11A783K",
                "username": "mario.rossi"
            }
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        # Risposta deve menzionare piani o ritardi
        text = data["result"]["text"].lower()
        assert any(word in text for word in ["piano", "ritard", "control", "programmazione"])

    @pytest.mark.e2e
    def test_chat_minimal_metadata(self, webhook_url, unique_sender):
        """Test con metadata minimi."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": {"asl": "AVELLINO"}
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data

    @pytest.mark.e2e
    def test_chat_no_metadata(self, webhook_url, unique_sender):
        """Test senza metadata (come chiamata diretta)."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto"
            # NO metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        # Help deve funzionare anche senza metadata
        assert "text" in data["result"]


class TestChatSenderFormat:
    """Test formato sender ID come frontend."""

    @pytest.mark.e2e
    def test_sender_frontend_format(self, webhook_url, complete_metadata):
        """Test che sender formato frontend funzioni."""
        # Formato esatto frontend: user_<timestamp>_<random9>
        timestamp = int(time.time() * 1000)
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
        sender = f"user_{timestamp}_{suffix}"

        payload = {
            "sender": sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        # sender deve corrispondere
        assert data.get("sender") == sender

    @pytest.mark.e2e
    def test_sender_uniqueness(self, webhook_url, complete_metadata,
                               session_sender_factory):
        """Test che sender diversi abbiano sessioni separate."""
        sender1 = session_sender_factory()
        sender2 = session_sender_factory()

        # Prima richiesta con sender1
        resp1 = requests.post(webhook_url, json={
            "sender": sender1,
            "message": "piani in ritardo",
            "metadata": complete_metadata
        }, timeout=75)

        # Prima richiesta con sender2
        resp2 = requests.post(webhook_url, json={
            "sender": sender2,
            "message": "stabilimenti ad alto rischio",
            "metadata": complete_metadata
        }, timeout=75)

        assert resp1.status_code == 200
        assert resp2.status_code == 200


class TestChatResponseFormat:
    """Test formato response V1."""

    @pytest.mark.e2e
    def test_response_is_dict(self, webhook_url, unique_sender, complete_metadata):
        """Verifica che response sia un dict con result e sender."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        assert isinstance(data, dict)
        assert "result" in data
        assert "sender" in data

    @pytest.mark.e2e
    def test_response_result_has_text(self, webhook_url, unique_sender, complete_metadata):
        """Verifica che result abbia campo text."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        result = data["result"]
        assert "text" in result
        assert isinstance(result["text"], str)

    @pytest.mark.e2e
    def test_response_result_has_intent(self, webhook_url, unique_sender, complete_metadata):
        """Test che result abbia campo intent."""
        payload = {
            "sender": unique_sender,
            "message": "piani in ritardo",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        result = data["result"]
        assert "intent" in result
        assert isinstance(result["intent"], str)


class TestChatTimeout:
    """Test gestione timeout come frontend."""

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complex_query_timeout(self, webhook_url, unique_sender, complete_metadata):
        """Test che query complessa risponda entro timeout frontend (75s)."""
        payload = {
            "sender": unique_sender,
            "message": "analizza tutti i piani in ritardo e suggerisci priorita di intervento",
            "metadata": complete_metadata
        }

        start = time.time()
        resp = requests.post(webhook_url, json=payload, timeout=75)
        duration = time.time() - start

        assert resp.status_code == 200
        assert duration < 75, f"Query ha impiegato {duration:.1f}s (>75s)"
