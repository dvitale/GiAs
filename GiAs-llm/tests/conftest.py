"""
Configurazione pytest e fixtures per test suite GiAs-llm v4.0

PRINCIPI:
- NESSUN mock globale
- Test E2E replicano esattamente chiamate frontend
- Sender ID dinamici come frontend JS
- Metadata completi come passati da gchat
- Timeout allineati al frontend (75s)
"""

import os
import sys
import time
import random
import string
from pathlib import Path
from typing import Dict, Callable

import pytest
import requests

# ============================================================
# Path setup
# ============================================================

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# Configuration
# ============================================================

SERVER_URL = os.environ.get("GIAS_SERVER_URL", "http://localhost:5005")
FRONTEND_URL = os.environ.get("GIAS_FRONTEND_URL", "http://localhost:8080")
WEBHOOK_URL = f"{SERVER_URL}/api/v1/chat"
STREAM_URL = f"{SERVER_URL}/api/v1/chat/stream"
PARSE_URL = f"{SERVER_URL}/api/v1/parse"
STATUS_URL = f"{SERVER_URL}/status"

# Timeout allineati al frontend (JS: 75s, Go: 60s)
TIMEOUT_DEFAULT = 75
TIMEOUT_QUICK = 30
TIMEOUT_STREAMING = 120

# ============================================================
# Markers pytest
# ============================================================

def pytest_configure(config):
    """Registra markers custom."""
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (require running server)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests with real components"
    )
    config.addinivalue_line(
        "markers", "slow: Tests taking more than 30 seconds"
    )
    config.addinivalue_line(
        "markers", "streaming: SSE streaming tests"
    )
    config.addinivalue_line(
        "markers", "rag: Tests requiring RAG/vector search"
    )


# ============================================================
# Server fixtures
# ============================================================

@pytest.fixture(scope="session")
def server_url() -> str:
    """URL base del server."""
    return SERVER_URL


@pytest.fixture(scope="session")
def webhook_url() -> str:
    """URL endpoint webhook."""
    return WEBHOOK_URL


@pytest.fixture(scope="session")
def stream_url() -> str:
    """URL endpoint streaming SSE."""
    return STREAM_URL


@pytest.fixture(scope="session")
def parse_url() -> str:
    """URL endpoint parse NLU."""
    return PARSE_URL


# ============================================================
# Health check fixtures
# ============================================================

@pytest.fixture(scope="session")
def server_available() -> bool:
    """
    Verifica se il server GiAs-llm e' disponibile.
    Fixture di sessione - verifica una sola volta.
    """
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def server_status(server_available) -> Dict:
    """Ritorna status completo del server."""
    if not server_available:
        return {"status": "offline", "error": "Server non raggiungibile"}

    try:
        resp = requests.get(STATUS_URL, timeout=10)
        return resp.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


@pytest.fixture(autouse=True)
def skip_if_server_down(request, server_available):
    """Skip automatico per test E2E/integration se server non disponibile."""
    # Skip solo per test marcati e2e o integration
    markers = [m.name for m in request.node.iter_markers()]
    if ("e2e" in markers or "integration" in markers) and not server_available:
        pytest.skip("Server GiAs-llm non disponibile - avvia con: scripts/server.sh start")


# ============================================================
# Sender e Metadata fixtures (replica frontend)
# ============================================================

@pytest.fixture
def unique_sender() -> str:
    """
    Genera sender ID identico al frontend JS.
    Formato: user_<timestamp_ms>_<random9chars>

    Da chat.js linea 34:
    this.senderId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    """
    timestamp = int(time.time() * 1000)
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"user_{timestamp}_{suffix}"


@pytest.fixture
def complete_metadata() -> Dict:
    """
    Metadata completi come passati dal frontend gchat.

    Da gchat/statics/js/chat.js e gchat/app/llm_client.go:
    - asl: nome ASL (prioritario)
    - asl_id: ID numerico ASL
    - user_id: ID utente
    - codice_fiscale: CF utente
    - username: nome utente
    """
    return {
        "asl": "BENEVENTO",
        "asl_id": "202",
        "user_id": "6448",
        "codice_fiscale": "ZZIBRD65R11A783K",
        "username": "test_automation"
    }


@pytest.fixture
def frontend_payload(unique_sender, complete_metadata) -> Dict:
    """
    Payload esattamente come costruito dal frontend gchat.

    Formato identico a quello inviato da chat.js -> Go -> Python.
    """
    return {
        "sender": unique_sender,
        "message": "",  # Da sovrascrivere nel test
        "metadata": complete_metadata.copy()
    }


@pytest.fixture
def metadata_avellino() -> Dict:
    """Metadata per ASL Avellino (usata in molti test esistenti)."""
    return {
        "asl": "AVELLINO",
        "asl_id": "201",
        "user_id": "test_av_001",
        "codice_fiscale": "TESTAV00A00A000A",
        "username": "test_avellino"
    }


@pytest.fixture
def metadata_napoli() -> Dict:
    """Metadata per ASL Napoli."""
    return {
        "asl": "NAPOLI 1 CENTRO",
        "asl_id": "203",
        "user_id": "test_na_001",
        "codice_fiscale": "TESTNA00A00A000A",
        "username": "test_napoli"
    }


# ============================================================
# API Client fixtures
# ============================================================

def _v1_to_compat(data: Dict) -> Dict:
    """
    Mappa risposta V1 {result: {text, intent, slots, ...}, sender}
    al formato compatibile con i test esistenti {text, custom: {intent, slots, ...}}.
    """
    result = data.get("result", {})
    # Costruisci "custom" compatibile con i test che leggono response["custom"]["intent"]
    custom = {
        "intent": result.get("intent", ""),
        "slots": result.get("slots", {}),
        "suggestions": result.get("suggestions", []),
        "execution_path": (result.get("execution", {}) or {}).get("execution_path", []),
        "node_timings": (result.get("execution", {}) or {}).get("node_timings", {}),
        "total_execution_ms": (result.get("execution", {}) or {}).get("total_execution_ms"),
    }
    return {
        "text": result.get("text", ""),
        "custom": custom,
        # Campi V1 diretti (per test nuovi)
        "intent": result.get("intent", ""),
        "slots": result.get("slots", {}),
        "suggestions": result.get("suggestions", []),
    }


@pytest.fixture
def api_client(webhook_url, diagnostic_ctx) -> Callable:
    """
    Client per chiamate API V1 chat con timeout frontend-aligned.
    Ritorna una funzione che accetta (message, sender, metadata).

    Include automaticamente tracciamento diagnostico per arricchire
    i report di fallimento con request/response context.
    """
    def call(message: str, sender: str, metadata: Dict = None) -> Dict:
        """Chiama /api/v1/chat e ritorna risposta compatibile."""
        # Traccia request per diagnostica
        diagnostic_ctx.set_request(message, sender, metadata)

        payload = {
            "sender": sender,
            "message": message
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=TIMEOUT_DEFAULT,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()

        data = resp.json()
        result = _v1_to_compat(data)

        # Traccia response per diagnostica
        diagnostic_ctx.set_response(result)

        return result

    return call


@pytest.fixture
def api_client_raw(webhook_url) -> Callable:
    """
    Client che ritorna response V1 completa.
    """
    def call(message: str, sender: str, metadata: Dict = None) -> Dict:
        payload = {
            "sender": sender,
            "message": message
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=TIMEOUT_DEFAULT,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        return resp.json()

    return call


@pytest.fixture
def parse_client(parse_url) -> Callable:
    """Client per endpoint /api/v1/parse (NLU)."""
    def call(text: str, metadata: Dict = None) -> Dict:
        payload = {"text": text}
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(
            parse_url,
            json=payload,
            timeout=TIMEOUT_QUICK,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        return resp.json()

    return call


# ============================================================
# Helper fixtures
# ============================================================

@pytest.fixture
def tool_caller() -> Callable:
    """
    Helper per chiamare tool LangChain decorati con @tool.
    Gestisce sia tool decorati che funzioni normali.
    """
    def call_tool(tool, *args, **kwargs):
        func = tool.func if hasattr(tool, 'func') else tool
        return func(*args, **kwargs)
    return call_tool


@pytest.fixture
def keyword_checker() -> Callable:
    """
    Helper per verificare keywords in un testo.
    Ritorna dict con found, missing, coverage.
    """
    def check(text: str, keywords: list) -> Dict:
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


# ============================================================
# Session management fixtures
# ============================================================

@pytest.fixture
def session_sender_factory() -> Callable:
    """
    Factory per creare sender unici per test di sessione.
    Utile per test che richiedono multiple sessioni isolate.
    """
    def create_sender(prefix: str = "user") -> str:
        timestamp = int(time.time() * 1000)
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
        return f"{prefix}_{timestamp}_{suffix}"

    return create_sender


# ============================================================
# Fixtures per compatibilita' con test esistenti
# ============================================================

@pytest.fixture(scope="session")
def rag_api_url():
    """URL dell'API RAG (alias per webhook_url)."""
    return WEBHOOK_URL


@pytest.fixture(scope="session")
def rag_status_url():
    """URL per health check (alias)."""
    return STATUS_URL


@pytest.fixture(scope="session")
def rag_timeout():
    """Timeout per chiamate API RAG."""
    return TIMEOUT_DEFAULT


@pytest.fixture
def rag_test_sender(unique_sender):
    """Sender ID per test RAG (usa unique_sender)."""
    return unique_sender


@pytest.fixture
def rag_api_client(api_client):
    """Client RAG (alias per api_client)."""
    return api_client


# ============================================================
# Fixtures per test_server.py compatibility
# ============================================================

@pytest.fixture
def ctx():
    """
    Fixture per test_server.py che richiede TestContext.
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
        pytest.skip("TestContext non disponibile")


# ============================================================
# Diagnostic helpers per report fallimenti
# ============================================================

class DiagnosticContext:
    """
    Contesto diagnostico per tracciare request/response durante i test.
    Usato per arricchire i report di fallimento.
    """

    def __init__(self):
        self.last_request = None
        self.last_response = None
        self.metadata = {}

    def set_request(self, query: str, sender: str, metadata: Dict = None):
        """Registra l'ultima request effettuata."""
        self.last_request = {
            "query": query,
            "sender": sender,
            "metadata": metadata or {}
        }

    def set_response(self, response: Dict):
        """Registra l'ultima response ricevuta."""
        self.last_response = response

    def add_metadata(self, key: str, value):
        """Aggiunge metadata diagnostici."""
        self.metadata[key] = value

    def format_failure_message(self, test_name: str, error_msg: str) -> str:
        """Formatta messaggio di errore con contesto diagnostico completo."""
        lines = [
            "",
            "=" * 70,
            f"TEST FAILURE: {test_name}",
            "=" * 70,
        ]

        if self.last_request:
            lines.extend([
                "",
                "REQUEST:",
                f"  Query: {self.last_request['query']}",
                f"  Sender: {self.last_request['sender']}",
            ])
            if self.last_request['metadata']:
                lines.append(f"  Metadata: {self.last_request['metadata']}")

        if self.last_response:
            lines.extend([
                "",
                "RESPONSE:",
                f"  Text: {self.last_response.get('text', 'N/A')[:500]}",
            ])
            if 'custom' in self.last_response:
                custom = self.last_response['custom']
                lines.append(f"  Intent: {custom.get('intent', 'N/A')}")
                lines.append(f"  Confidence: {custom.get('confidence', 'N/A')}")
                if 'session_id' in custom:
                    lines.append(f"  Session: {custom['session_id']}")

        if self.metadata:
            lines.extend([
                "",
                "DIAGNOSTIC METADATA:",
            ])
            for k, v in self.metadata.items():
                lines.append(f"  {k}: {v}")

        lines.extend([
            "",
            "ERROR:",
            f"  {error_msg}",
            "=" * 70,
        ])

        return "\n".join(lines)

    def clear(self):
        """Resetta il contesto."""
        self.last_request = None
        self.last_response = None
        self.metadata = {}


# Contesto diagnostico globale per la sessione
_diagnostic_context = DiagnosticContext()


@pytest.fixture
def diagnostic_ctx():
    """Fixture per accedere al contesto diagnostico."""
    return _diagnostic_context


@pytest.fixture
def api_client_diagnostic(webhook_url, diagnostic_ctx) -> Callable:
    """
    Client API che traccia automaticamente request/response per diagnosi.
    Usa questo invece di api_client per avere report dettagliati in caso di fallimento.
    """
    def call(message: str, sender: str, metadata: Dict = None) -> Dict:
        # Traccia request
        diagnostic_ctx.set_request(message, sender, metadata)

        payload = {
            "sender": sender,
            "message": message
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=TIMEOUT_DEFAULT,
            headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()

        data = resp.json()
        result = _v1_to_compat(data)

        # Traccia response
        diagnostic_ctx.set_response(result)

        return result

    return call


@pytest.fixture(autouse=True)
def clear_diagnostic_context(diagnostic_ctx):
    """Pulisce il contesto diagnostico prima di ogni test."""
    diagnostic_ctx.clear()
    yield
    # Non pulire dopo per permettere accesso nel report


# ============================================================
# Pytest hooks per report fallimenti
# ============================================================

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook per arricchire report di fallimento con contesto diagnostico.
    Cattura automaticamente info su request/response in caso di errore.
    """
    outcome = yield
    report = outcome.get_result()

    # Solo per fallimenti in fase di call (non setup/teardown)
    if report.when == "call" and report.failed:
        # Aggiungi contesto diagnostico se disponibile
        if _diagnostic_context.last_request or _diagnostic_context.last_response:
            extra_info = []

            if _diagnostic_context.last_request:
                req = _diagnostic_context.last_request
                extra_info.append(f"\n--- Last Request ---")
                extra_info.append(f"Query: {req['query']}")
                extra_info.append(f"Sender: {req['sender']}")
                if req['metadata']:
                    extra_info.append(f"Metadata: {req['metadata']}")

            if _diagnostic_context.last_response:
                resp = _diagnostic_context.last_response
                extra_info.append(f"\n--- Last Response ---")
                extra_info.append(f"Text: {resp.get('text', 'N/A')[:300]}...")
                if 'custom' in resp:
                    extra_info.append(f"Intent: {resp['custom'].get('intent', 'N/A')}")
                    extra_info.append(f"Confidence: {resp['custom'].get('confidence', 'N/A')}")

            if extra_info:
                report.longrepr = str(report.longrepr) + "\n" + "\n".join(extra_info)


# ============================================================
# Assert helpers per messaggi diagnostici
# ============================================================

def assert_intent(response: Dict, expected_intent: str, query: str = None):
    """
    Assert su intent con messaggio diagnostico completo.

    Usage:
        assert_intent(response, "ask_delayed_plans", query="piani in ritardo")
    """
    actual_intent = response.get("custom", {}).get("intent", "N/A")
    confidence = response.get("custom", {}).get("confidence", "N/A")
    text = response.get("text", "")[:300]

    assert actual_intent == expected_intent, (
        f"\nIntent classification failed:"
        f"\n  Query: {query or 'N/A'}"
        f"\n  Expected: {expected_intent}"
        f"\n  Actual: {actual_intent}"
        f"\n  Confidence: {confidence}"
        f"\n  Response: {text}..."
    )


def assert_patterns(response: Dict, patterns: list, min_matches: int = 1, query: str = None):
    """
    Assert su pattern presenti nella risposta con contesto diagnostico.

    Usage:
        assert_patterns(response, ["ritard", "piano"], min_matches=1, query="piani in ritardo")
    """
    text = response.get("text", "").lower()
    found = [p for p in patterns if p.lower() in text]
    missing = [p for p in patterns if p.lower() not in text]

    assert len(found) >= min_matches, (
        f"\nPattern matching failed:"
        f"\n  Query: {query or 'N/A'}"
        f"\n  Expected patterns: {patterns}"
        f"\n  Found: {found} ({len(found)}/{len(patterns)})"
        f"\n  Missing: {missing}"
        f"\n  Min required: {min_matches}"
        f"\n  Response: {text[:300]}..."
    )


def assert_response_valid(response: Dict, query: str = None):
    """
    Assert che la response sia valida e non vuota.

    Usage:
        assert_response_valid(response, query="piani in ritardo")
    """
    assert response is not None, f"Response is None for query: {query or 'N/A'}"
    assert "text" in response, f"Response missing 'text' for query: {query or 'N/A'}"

    text = response.get("text", "")
    assert len(text) > 0, (
        f"\nEmpty response:"
        f"\n  Query: {query or 'N/A'}"
        f"\n  Intent: {response.get('custom', {}).get('intent', 'N/A')}"
    )
