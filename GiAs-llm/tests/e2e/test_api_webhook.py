"""
Test E2E per endpoint webhook principale.
Replica esattamente le chiamate dal frontend gchat.
"""

import pytest
import requests
import time
import random
import string


class TestWebhookBasic:
    """Test base per webhook /webhooks/rest/webhook."""

    @pytest.mark.e2e
    def test_webhook_greet(self, webhook_url, unique_sender, complete_metadata):
        """Test saluto base come frontend."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "text" in data[0]
        # Verifica risposta di benvenuto
        text = data[0]["text"].lower()
        assert any(word in text for word in ["benvenuto", "ciao", "buon", "posso aiutarti"])

    @pytest.mark.e2e
    def test_webhook_help(self, webhook_url, unique_sender, complete_metadata):
        """Test richiesta aiuto."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        text = data[0]["text"].lower()
        # Deve elencare funzionalita'
        assert any(word in text for word in ["posso", "aiutarti", "domand", "funzionalit"])

    @pytest.mark.e2e
    def test_webhook_goodbye(self, webhook_url, unique_sender, complete_metadata):
        """Test saluto finale."""
        payload = {
            "sender": unique_sender,
            "message": "arrivederci",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        text = data[0]["text"].lower()
        assert any(word in text for word in ["arrivederci", "buon lavoro", "presto"])


class TestWebhookMetadata:
    """Test gestione metadata come frontend."""

    @pytest.mark.e2e
    def test_webhook_all_metadata_fields(self, webhook_url, unique_sender):
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
        assert len(data) > 0
        # Risposta deve menzionare piani o ritardi
        text = data[0]["text"].lower()
        assert any(word in text for word in ["piano", "ritard", "control", "programmazione"])

    @pytest.mark.e2e
    def test_webhook_minimal_metadata(self, webhook_url, unique_sender):
        """Test con metadata minimi."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": {"asl": "AVELLINO"}
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    @pytest.mark.e2e
    def test_webhook_no_metadata(self, webhook_url, unique_sender):
        """Test senza metadata (come chiamata diretta)."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto"
            # NO metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # Help deve funzionare anche senza metadata
        assert "text" in data[0]


class TestWebhookSenderFormat:
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
        assert len(data) > 0
        # recipient_id deve corrispondere al sender
        if "recipient_id" in data[0]:
            assert data[0]["recipient_id"] == sender

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


class TestWebhookResponseFormat:
    """Test formato response Rasa-compatible."""

    @pytest.mark.e2e
    def test_response_is_list(self, webhook_url, unique_sender, complete_metadata):
        """Verifica che response sia lista (Rasa format)."""
        payload = {
            "sender": unique_sender,
            "message": "ciao",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_response_has_text(self, webhook_url, unique_sender, complete_metadata):
        """Verifica che ogni response abbia campo text."""
        payload = {
            "sender": unique_sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        for item in data:
            assert "text" in item
            assert isinstance(item["text"], str)

    @pytest.mark.e2e
    def test_response_custom_field(self, webhook_url, unique_sender, complete_metadata):
        """Test che response possa avere campo custom."""
        payload = {
            "sender": unique_sender,
            "message": "piani in ritardo",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)
        data = resp.json()

        # custom e' opzionale ma se presente deve essere dict
        if len(data) > 0 and "custom" in data[0]:
            assert isinstance(data[0]["custom"], dict)


class TestWebhookTimeout:
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
