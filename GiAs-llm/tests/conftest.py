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

# NOTA: I mock globali sono stati rimossi perché interferivano con i test.
# Ogni test che necessita di mock deve usare @patch localmente.
# I moduli reali vengono importati normalmente.

# Mock minimale solo per langgraph/langchain se non installati
try:
    import langgraph
except ImportError:
    sys.modules['langgraph'] = Mock()
    sys.modules['langgraph.graph'] = Mock()

try:
    import langchain_core
except ImportError:
    sys.modules['langchain_core'] = Mock()
    sys.modules['langchain_core.tools'] = Mock()


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
        "markers", "integration: marks integration tests (require database connection)"
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
# Fixture per test_server.py (TestContext)
# ============================================================

@pytest.fixture
def ctx():
    """
    Fixture per test_server.py che richiede TestContext.
    Importa dinamicamente da test_server per evitare dipendenze circolari.
    """
    try:
        from tests.test_server import TestContext
        return TestContext(
            quick_mode=True,
            verbose=False,
            json_output=False,
            auto_start=False
        )
    except ImportError:
        # Se non riesce a importare, skip il test
        pytest.skip("TestContext non disponibile")


# ============================================================
# Helpers per tool invocation
# ============================================================

def call_tool(tool, *args, **kwargs):
    """
    Helper per chiamare un tool LangChain sia che sia decorato con @tool
    sia che sia una funzione normale.

    Usage:
        from conftest import call_tool
        result = call_tool(get_piano_description, "A1")
    """
    func = tool.func if hasattr(tool, 'func') else tool
    return func(*args, **kwargs)


@pytest.fixture
def tool_caller():
    """Fixture per chiamare tool LangChain nei test."""
    return call_tool


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
