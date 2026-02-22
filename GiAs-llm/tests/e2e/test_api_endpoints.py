"""
Test E2E per endpoint API base.
Verifica health check, status, config, parse.
"""

import pytest
import requests


class TestHealthCheck:
    """Test endpoint / (health check)."""

    @pytest.mark.e2e
    def test_health_check_available(self, server_url):
        """Verifica che il server risponda al health check."""
        resp = requests.get(f"{server_url}/", timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    @pytest.mark.e2e
    def test_health_check_version(self, server_url):
        """Verifica che il server restituisca versione."""
        resp = requests.get(f"{server_url}/", timeout=10)

        data = resp.json()
        assert "version" in data
        assert data["version"]  # Non vuoto

    @pytest.mark.e2e
    def test_health_check_model_loaded(self, server_url):
        """Verifica che il modello LLM sia caricato."""
        resp = requests.get(f"{server_url}/", timeout=10)

        data = resp.json()
        assert "model_loaded" in data
        assert data["model_loaded"] is True


class TestStatusEndpoint:
    """Test endpoint /status."""

    @pytest.mark.e2e
    def test_status_available(self, server_url):
        """Verifica che /status risponda."""
        resp = requests.get(f"{server_url}/status", timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    @pytest.mark.e2e
    def test_status_data_loaded(self, server_url):
        """Verifica che i dati siano caricati."""
        resp = requests.get(f"{server_url}/status", timeout=10)

        data = resp.json()
        assert "data_loaded" in data
        # Verifica che ci siano dati caricati
        data_loaded = data["data_loaded"]
        assert isinstance(data_loaded, dict)
        # Almeno alcuni dataset devono essere caricati
        total_records = sum(data_loaded.values())
        assert total_records > 0, "Nessun dato caricato"

    @pytest.mark.e2e
    def test_status_framework(self, server_url):
        """Verifica framework in uso."""
        resp = requests.get(f"{server_url}/status", timeout=10)

        data = resp.json()
        assert "framework" in data
        assert "langgraph" in data["framework"].lower()


class TestConfigEndpoint:
    """Test endpoint /config."""

    @pytest.mark.e2e
    def test_config_available(self, server_url):
        """Verifica che /config risponda."""
        resp = requests.get(f"{server_url}/config", timeout=10)

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    @pytest.mark.e2e
    def test_config_data_source(self, server_url):
        """Verifica configurazione data source."""
        resp = requests.get(f"{server_url}/config", timeout=10)

        data = resp.json()
        assert "data_source_type" in data
        # Deve essere csv o postgresql
        assert data["data_source_type"] in ["csv", "postgresql"]


class TestParseEndpoint:
    """Test endpoint /api/v1/parse (NLU)."""

    @pytest.mark.e2e
    def test_parse_simple(self, parse_url):
        """Test parsing messaggio semplice."""
        resp = requests.post(
            parse_url,
            json={"text": "ciao"},
            timeout=30
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data
        assert data["intent"] == "greet"

    @pytest.mark.e2e
    def test_parse_with_slot(self, parse_url):
        """Test parsing con estrazione slot."""
        resp = requests.post(
            parse_url,
            json={"text": "di cosa tratta il piano A1"},
            timeout=30
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data
        assert data["intent"] == "ask_piano_description"
        # Verifica slot estratto
        assert "slots" in data
        assert data["slots"].get("piano_code") == "A1"

    @pytest.mark.e2e
    def test_parse_with_metadata(self, parse_url, complete_metadata):
        """Test parsing con metadata."""
        resp = requests.post(
            parse_url,
            json={
                "text": "stabilimenti prioritari",
                "metadata": complete_metadata
            },
            timeout=30
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data

    @pytest.mark.e2e
    def test_parse_confidence(self, parse_url):
        """Test che parse restituisca confidence."""
        resp = requests.post(
            parse_url,
            json={"text": "piani in ritardo"},
            timeout=30
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "intent" in data
        assert "confidence" in data
        # Confidence deve essere tra 0 e 1
        conf = data["confidence"]
        assert 0 <= conf <= 1


class TestErrorHandling:
    """Test gestione errori API."""

    @pytest.mark.e2e
    def test_parse_empty_text(self, parse_url):
        """Test parse con testo vuoto."""
        resp = requests.post(
            parse_url,
            json={"text": ""},
            timeout=10
        )

        # Deve gestire gracefully
        assert resp.status_code in [200, 400]

    @pytest.mark.e2e
    def test_webhook_malformed_json(self, webhook_url):
        """Test webhook con JSON malformato."""
        resp = requests.post(
            webhook_url,
            data="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        assert resp.status_code in [400, 422]

    @pytest.mark.e2e
    def test_webhook_missing_message(self, webhook_url, unique_sender):
        """Test webhook senza campo message."""
        resp = requests.post(
            webhook_url,
            json={"sender": unique_sender},
            timeout=10
        )

        # Deve gestire gracefully
        assert resp.status_code in [200, 400, 422]
