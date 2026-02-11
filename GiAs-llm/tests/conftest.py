"""
Configurazione pytest e fixtures
"""

import sys
import os
from unittest.mock import Mock
from pathlib import Path

import pytest

# Path setup
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

# Mock dei moduli che richiedono dipendenze esterne
# (solo per test unitari, non per test di integrazione RAG)
sys.modules['langgraph'] = Mock()
sys.modules['langgraph.graph'] = Mock()
sys.modules['langchain_core'] = Mock()
sys.modules['langchain_core.tools'] = Mock()

sys.modules['llm'] = Mock()
sys.modules['llm.client'] = Mock()

sys.modules['agents'] = Mock()
sys.modules['agents.data'] = Mock()
sys.modules['agents.utils'] = Mock()
sys.modules['agents.data_agent'] = Mock()
sys.modules['agents.response_agent'] = Mock()


# ============================================================
# Configurazione markers pytest
# ============================================================

def pytest_configure(config):
    """Registra markers custom."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "rag: marks tests that require RAG server running"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )


# ============================================================
# Fixtures per test RAG
# ============================================================

@pytest.fixture(scope="session")
def rag_api_url():
    """URL dell'API RAG."""
    return os.environ.get("RAG_API_URL", "http://localhost:5005/webhooks/rest/webhook")


@pytest.fixture(scope="session")
def rag_status_url():
    """URL per health check del server RAG."""
    return os.environ.get("RAG_STATUS_URL", "http://localhost:5005/status")


@pytest.fixture(scope="session")
def rag_timeout():
    """Timeout per chiamate API RAG (secondi)."""
    return int(os.environ.get("RAG_TIMEOUT", "60"))


@pytest.fixture
def rag_test_sender():
    """Sender ID per i test RAG."""
    return "pytest_rag_test"


@pytest.fixture(scope="session")
def rag_server_available(rag_status_url):
    """
    Verifica se il server RAG e' disponibile.
    Fixture di sessione - verifica una sola volta.
    """
    try:
        import requests
        resp = requests.get(rag_status_url, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture
def skip_if_no_server(rag_server_available):
    """Skip test se il server non e' disponibile."""
    if not rag_server_available:
        pytest.skip("Server RAG non disponibile")


@pytest.fixture
def rag_api_client(rag_api_url, rag_timeout, rag_test_sender):
    """
    Client per chiamate API RAG.
    Ritorna una funzione che accetta query e ritorna la risposta.
    """
    import requests

    def call_api(query: str, metadata: dict = None) -> dict:
        """Chiama l'API RAG e ritorna la prima risposta."""
        payload = {
            "sender": rag_test_sender,
            "message": query
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(rag_api_url, json=payload, timeout=rag_timeout)
        resp.raise_for_status()

        responses = resp.json()
        if not responses:
            return {"text": "", "custom": {}}
        return responses[0]

    return call_api


# ============================================================
# Fixtures per test cases YAML
# ============================================================

@pytest.fixture(scope="session")
def rag_test_cases_path():
    """Path al file YAML con i test cases."""
    return TEST_DIR / "rag_test_cases.yaml"


@pytest.fixture(scope="session")
def rag_test_cases(rag_test_cases_path):
    """Carica tutti i test cases dal file YAML."""
    import yaml

    if not rag_test_cases_path.exists():
        return []

    with open(rag_test_cases_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("test_cases", [])


@pytest.fixture(scope="session")
def rag_config(rag_test_cases_path):
    """Carica la configurazione dal file YAML."""
    import yaml

    if not rag_test_cases_path.exists():
        return {}

    with open(rag_test_cases_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("config", {})


# ============================================================
# Helpers per validazione
# ============================================================

@pytest.fixture
def keyword_checker():
    """
    Funzione helper per verificare keywords in un testo.
    Ritorna una funzione che accetta (text, keywords) e ritorna
    un dict con found, missing, coverage.
    """
    def check(text: str, keywords: list) -> dict:
        text_lower = text.lower()
        found = [kw for kw in keywords if kw.lower() in text_lower]
        missing = [kw for kw in keywords if kw.lower() not in text_lower]
        coverage = len(found) / len(keywords) if keywords else 1.0

        return {
            "found": found,
            "missing": missing,
            "coverage": coverage,
            "total": len(keywords)
        }

    return check
