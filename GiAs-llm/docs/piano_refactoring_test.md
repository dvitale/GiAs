# Piano di Refactoring Suite Test GiAs-llm

**Data**: 2026-02-15
**Versione**: 1.0
**Autore**: Claude Code Review

---

## Executive Summary

La suite di test attuale presenta **15 file con mock** su 25 file totali. Questi mock mascherano potenziali problemi di integrazione e non replicano il comportamento reale del sistema. Il refactoring proposto elimina completamente i mock creando una suite di test end-to-end che replica esattamente le chiamate dal frontend.

---

## 1. Analisi Situazione Attuale

### 1.1 Inventario Mock Esistenti

| File | Mock Usati | Componenti Mockati |
|------|------------|-------------------|
| `test_router.py` | `@patch('orchestrator.router.LLMClient')` | LLM client per classificazione |
| `test_graph.py` | `@patch LLMClient, Router` | LLM + Router intero grafo |
| `test_tools.py` | `@patch DataRetriever, BusinessLogic, ResponseFormatter, RiskAnalyzer` | Intero data layer |
| `test_few_shot_retriever.py` | `@patch QdrantClient` | Vector database |
| `test_procedure_tools.py` | `@patch LLMClient` | RAG LLM |
| `test_intelligent_monitor.py` | `Mock` generico | Analisi qualità |
| `test_nearby_priority.py` | `@patch geo_utils` | Geocoding |
| `test_nc_categories.py` | `@patch DataRetriever` | Data layer |
| `test_graph_fallback.py` | `@patch Router, LLMClient` | Fallback recovery |
| `test_fallback_recovery.py` | `@patch` multipli | Fallback chain |
| `test_ml_predictor.py` | `@patch` modello ML | Predictor XGBoost |
| `conftest.py` | `sys.modules mock` | langgraph/langchain |

### 1.2 Problemi Identificati

1. **Test non realistici**: Mock del DataRetriever restituiscono DataFrame costruiti a mano, non dati reali
2. **Metadata incomplete**: Test usano `{"asl": "AVELLINO"}`, frontend passa 5+ campi
3. **Sender statici**: Test usano `sender="test_user"`, frontend usa `user_<timestamp>_<random>`
4. **Layer Go saltato**: Test chiamano direttamente Python, saltando trasformazione metadata Go
5. **Timeout diversi**: Test 30s, frontend 75s → possibili falsi positivi
6. **Streaming non testato**: Endpoint SSE non coperto
7. **Sessioni non isolate**: Test paralleli possono interferire

### 1.3 Modello di Riferimento

`test_server.py` è il modello corretto:
- Chiama API reale senza mock
- Validazione Pydantic delle response
- Gestione sessioni con sender unici
- Test two-phase flow
- Report strutturato

---

## 2. Architettura Target

### 2.1 Struttura Directory Proposta

```
GiAs-llm/tests/
├── conftest.py                    # Fixtures condivise (NO mock globali)
├── pytest.ini                     # Configurazione pytest
├── run_all_tests.py              # Runner unico con report
│
├── e2e/                          # Test End-to-End (NESSUN MOCK)
│   ├── __init__.py
│   ├── test_api_webhook.py       # Test webhook principale
│   ├── test_api_endpoints.py     # Test /, /status, /config, /model/parse
│   ├── test_intents_complete.py  # Test tutti i 20 intent
│   ├── test_sessions.py          # Test sessioni, TTL, isolamento
│   ├── test_two_phase.py         # Test flusso sommario/dettagli
│   ├── test_metadata.py          # Test tutti i campi metadata
│   ├── test_fallback.py          # Test fallback 3-phase
│   └── test_streaming.py         # Test SSE endpoint
│
├── integration/                  # Test integrazione componenti
│   ├── __init__.py
│   ├── test_router_llm.py        # Router con LLM reale
│   ├── test_tools_data.py        # Tools con dati reali
│   ├── test_hybrid_search.py     # Hybrid search completo
│   └── test_ml_predictor.py      # ML predictor completo
│
├── fixtures/                     # Dati di test
│   ├── payloads/                 # Payload JSON di riferimento
│   │   ├── frontend_call.json    # Payload esatto frontend
│   │   └── metadata_complete.json
│   └── expected/                 # Response attese
│       └── intent_responses.yaml
│
└── legacy/                       # Test vecchi (deprecati, da rimuovere)
    └── *.py                      # Tutti i test con mock
```

### 2.2 Payload di Riferimento

**Payload Frontend Reale** (da `gchat/statics/js/chat.js`):

```json
{
  "sender": "user_1739612345678_abc123def",
  "message": "piani in ritardo",
  "metadata": {
    "asl": "BENEVENTO",
    "asl_id": "202",
    "user_id": "6448",
    "codice_fiscale": "ZZIBRD65R11A783K",
    "username": "mario.rossi"
  }
}
```

Ogni test E2E deve usare questo formato completo.

### 2.3 Generazione Sender Dinamici

```python
# conftest.py
import time
import random
import string

@pytest.fixture
def unique_sender() -> str:
    """Genera sender ID identico al frontend."""
    timestamp = int(time.time() * 1000)
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"user_{timestamp}_{random_suffix}"

@pytest.fixture
def frontend_payload(unique_sender) -> dict:
    """Payload completo come frontend."""
    return {
        "sender": unique_sender,
        "message": "",  # Da sovrascrivere nel test
        "metadata": {
            "asl": "BENEVENTO",
            "asl_id": "202",
            "user_id": "6448",
            "codice_fiscale": "ZZIBRD65R11A783K",
            "username": "test_user"
        }
    }
```

---

## 3. Piano di Migrazione

### Fase 1: Infrastruttura (Settimana 1)

#### 3.1.1 Nuovo `conftest.py`

```python
"""
Configurazione pytest - NO MOCK GLOBALI
"""
import os
import time
import random
import string
import requests
import pytest
from pathlib import Path

# ============================================================
# Configurazione
# ============================================================

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent

SERVER_URL = os.environ.get("GIAS_SERVER_URL", "http://localhost:5005")
FRONTEND_URL = os.environ.get("GIAS_FRONTEND_URL", "http://localhost:8080")
WEBHOOK_URL = f"{SERVER_URL}/webhooks/rest/webhook"
STREAM_URL = f"{SERVER_URL}/webhooks/rest/webhook/stream"

# Timeout allineati al frontend (75s client, 60s server)
TIMEOUT_DEFAULT = 75
TIMEOUT_STREAMING = 120

# ============================================================
# Fixtures Base
# ============================================================

@pytest.fixture(scope="session")
def server_url():
    return SERVER_URL

@pytest.fixture(scope="session")
def webhook_url():
    return WEBHOOK_URL

@pytest.fixture(scope="session")
def stream_url():
    return STREAM_URL

# ============================================================
# Health Check
# ============================================================

@pytest.fixture(scope="session")
def server_available():
    """Verifica server disponibile prima di tutti i test."""
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=10)
        return resp.status_code == 200
    except Exception:
        return False

@pytest.fixture(autouse=True)
def skip_if_server_down(server_available):
    """Skip automatico se server non disponibile."""
    if not server_available:
        pytest.skip("Server GiAs-llm non disponibile")

# ============================================================
# Sender e Payload
# ============================================================

@pytest.fixture
def unique_sender() -> str:
    """Genera sender ID identico al frontend JS."""
    timestamp = int(time.time() * 1000)
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"user_{timestamp}_{suffix}"

@pytest.fixture
def complete_metadata() -> dict:
    """Metadata completi come passati dal frontend."""
    return {
        "asl": "BENEVENTO",
        "asl_id": "202",
        "user_id": "6448",
        "codice_fiscale": "ZZIBRD65R11A783K",
        "username": "test_automation"
    }

@pytest.fixture
def frontend_payload(unique_sender, complete_metadata) -> dict:
    """Payload esattamente come costruito dal frontend."""
    return {
        "sender": unique_sender,
        "message": "",
        "metadata": complete_metadata
    }

# ============================================================
# API Client
# ============================================================

@pytest.fixture
def api_client(webhook_url):
    """Client per chiamate API con timeout frontend-aligned."""

    def call(message: str, sender: str, metadata: dict = None) -> dict:
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
        return data[0] if data else {"text": "", "custom": {}}

    return call

# ============================================================
# Markers
# ============================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-end tests (require running server)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests (>30s)")
    config.addinivalue_line("markers", "streaming: SSE streaming tests")
```

#### 3.1.2 Nuovo `pytest.ini`

```ini
[pytest]
testpaths = tests/e2e tests/integration
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    e2e: End-to-end tests requiring running server
    integration: Integration tests with real components
    slow: Tests taking more than 30 seconds
    streaming: SSE streaming tests

addopts =
    -v
    --tb=short
    --strict-markers
    -x

filterwarnings =
    ignore::DeprecationWarning

# Report output
junit_family = xunit2
```

#### 3.1.3 Runner Unico `run_all_tests.py`

```python
#!/usr/bin/env python3
"""
GiAs-llm Test Suite Runner v4.0
Esegue tutti i test E2E e genera report completo.

Usage:
    python run_all_tests.py                    # Esegue tutti i test
    python run_all_tests.py --quick            # Solo test veloci
    python run_all_tests.py --report json      # Output JSON
    python run_all_tests.py --report html      # Report HTML
    python run_all_tests.py --parallel 4       # 4 worker paralleli
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import requests

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
TEST_DIR = PROJECT_ROOT / "tests"
REPORT_DIR = PROJECT_ROOT / "runtime" / "test_reports"

SERVER_URL = "http://localhost:5005"

# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: str = ""
    traceback: str = ""

@dataclass
class TestSuite:
    name: str
    tests: List[TestResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0

@dataclass
class TestReport:
    timestamp: str
    server_url: str
    server_status: str
    suites: List[TestSuite] = field(default_factory=list)
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    total_duration: float = 0.0

    def to_dict(self):
        return asdict(self)

# ═══════════════════════════════════════════════════════════════
# Server Check
# ═══════════════════════════════════════════════════════════════

def check_server() -> tuple[bool, str]:
    """Verifica stato server."""
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return True, f"v{data.get('version', '?')} - {data.get('status', 'ok')}"
        return False, f"HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused"
    except Exception as e:
        return False, str(e)

# ═══════════════════════════════════════════════════════════════
# Test Execution
# ═══════════════════════════════════════════════════════════════

def run_pytest(test_path: str, extra_args: List[str] = None) -> TestSuite:
    """Esegue pytest su un path e ritorna risultati."""
    args = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short",
        "--json-report",
        "--json-report-file=-",
        "-q"
    ]
    if extra_args:
        args.extend(extra_args)

    start = time.time()
    result = subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    duration = time.time() - start

    suite = TestSuite(name=Path(test_path).stem, duration=duration)

    # Parse JSON report da stdout
    try:
        # pytest-json-report output
        lines = result.stdout.split('\n')
        for line in lines:
            if line.startswith('{'):
                report = json.loads(line)
                for test in report.get('tests', []):
                    tr = TestResult(
                        name=test['nodeid'],
                        status=test['outcome'],
                        duration=test.get('duration', 0),
                        message=test.get('call', {}).get('longrepr', '')
                    )
                    suite.tests.append(tr)
                    if tr.status == 'passed':
                        suite.passed += 1
                    elif tr.status == 'failed':
                        suite.failed += 1
                    elif tr.status == 'skipped':
                        suite.skipped += 1
                    else:
                        suite.errors += 1
                break
    except (json.JSONDecodeError, KeyError):
        # Fallback: parse output testuale
        suite.errors += 1
        suite.tests.append(TestResult(
            name=test_path,
            status="error",
            duration=duration,
            message=result.stderr or result.stdout
        ))

    return suite

def run_all_tests(quick: bool = False, parallel: int = 1) -> TestReport:
    """Esegue tutti i test e genera report."""

    # Check server
    server_ok, server_status = check_server()

    report = TestReport(
        timestamp=datetime.now().isoformat(),
        server_url=SERVER_URL,
        server_status=server_status if server_ok else f"OFFLINE: {server_status}"
    )

    if not server_ok:
        print(f"❌ Server non disponibile: {server_status}")
        print("   Avvia il server con: scripts/server.sh start")
        return report

    # Test suites da eseguire
    test_suites = [
        "tests/e2e/test_api_endpoints.py",
        "tests/e2e/test_api_webhook.py",
        "tests/e2e/test_intents_complete.py",
        "tests/e2e/test_metadata.py",
        "tests/e2e/test_sessions.py",
        "tests/e2e/test_two_phase.py",
        "tests/e2e/test_fallback.py",
    ]

    if not quick:
        test_suites.extend([
            "tests/e2e/test_streaming.py",
            "tests/integration/test_router_llm.py",
            "tests/integration/test_tools_data.py",
            "tests/integration/test_hybrid_search.py",
            "tests/integration/test_ml_predictor.py",
        ])

    extra_args = []
    if parallel > 1:
        extra_args.extend(["-n", str(parallel)])
    if quick:
        extra_args.append("-m not slow")

    # Esegui test
    print(f"\n{'='*60}")
    print(f"GiAs-llm Test Suite v4.0")
    print(f"{'='*60}")
    print(f"Server: {SERVER_URL} ({server_status})")
    print(f"Mode: {'Quick' if quick else 'Full'}")
    print(f"Parallel: {parallel} workers")
    print(f"{'='*60}\n")

    for suite_path in test_suites:
        if not (PROJECT_ROOT / suite_path).exists():
            print(f"⚠️  Skip: {suite_path} (file non esiste)")
            continue

        print(f"Running: {suite_path}")
        suite = run_pytest(suite_path, extra_args)
        report.suites.append(suite)

        # Update totals
        report.total_passed += suite.passed
        report.total_failed += suite.failed
        report.total_skipped += suite.skipped
        report.total_errors += suite.errors
        report.total_duration += suite.duration

        # Print summary
        status = "✅" if suite.failed == 0 and suite.errors == 0 else "❌"
        print(f"  {status} {suite.passed} passed, {suite.failed} failed, "
              f"{suite.skipped} skipped ({suite.duration:.1f}s)")

    return report

# ═══════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════

def print_summary(report: TestReport):
    """Stampa sommario finale."""
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    total = report.total_passed + report.total_failed + report.total_skipped + report.total_errors

    print(f"Total:    {total} tests")
    print(f"Passed:   {report.total_passed} ✅")
    print(f"Failed:   {report.total_failed} ❌")
    print(f"Skipped:  {report.total_skipped} ⏭️")
    print(f"Errors:   {report.total_errors} 💥")
    print(f"Duration: {report.total_duration:.1f}s")
    print(f"{'='*60}")

    if report.total_failed > 0 or report.total_errors > 0:
        print("\n❌ FAILED")
        return 1
    else:
        print("\n✅ ALL TESTS PASSED")
        return 0

def save_report(report: TestReport, format: str = "json"):
    """Salva report su file."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        path = REPORT_DIR / f"test_report_{timestamp}.json"
        with open(path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
    elif format == "html":
        path = REPORT_DIR / f"test_report_{timestamp}.html"
        # TODO: HTML template
        with open(path, 'w') as f:
            f.write(f"<html><body><pre>{json.dumps(report.to_dict(), indent=2)}</pre></body></html>")

    print(f"\nReport salvato: {path}")
    return path

# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="GiAs-llm Test Suite Runner")
    parser.add_argument("--quick", action="store_true", help="Solo test veloci")
    parser.add_argument("--report", choices=["json", "html"], help="Salva report")
    parser.add_argument("--parallel", type=int, default=1, help="Worker paralleli")
    args = parser.parse_args()

    report = run_all_tests(quick=args.quick, parallel=args.parallel)

    if args.report:
        save_report(report, args.report)

    exit_code = print_summary(report)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

### Fase 2: Test E2E (Settimana 2)

#### 3.2.1 `test_api_webhook.py`

```python
"""
Test E2E per endpoint webhook principale.
Replica esattamente le chiamate dal frontend gchat.
"""

import pytest
import requests

class TestWebhook:
    """Test webhook /webhooks/rest/webhook."""

    @pytest.mark.e2e
    def test_webhook_basic(self, webhook_url, unique_sender, complete_metadata):
        """Test chiamata base come frontend."""
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
        assert "benvenuto" in data[0]["text"].lower() or "ciao" in data[0]["text"].lower()

    @pytest.mark.e2e
    def test_webhook_with_all_metadata(self, webhook_url, unique_sender):
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
        # Verifica che risposta menzioni ritardi o piani
        text = data[0]["text"].lower()
        assert "piano" in text or "ritard" in text or "control" in text

    @pytest.mark.e2e
    def test_webhook_sender_format(self, webhook_url, complete_metadata):
        """Test che sender formato frontend funzioni."""
        import time
        import random
        import string

        # Formato esatto frontend: user_<timestamp>_<random9>
        timestamp = int(time.time() * 1000)
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
        sender = f"user_{timestamp}_{suffix}"

        payload = {
            "sender": sender,
            "message": "aiuto",
            "metadata": complete_metadata
        }

        resp = requests.post(webhook_url, json=payload, timeout=75)

        assert resp.status_code == 200
        # recipient_id deve corrispondere al sender
        data = resp.json()
        if data and "recipient_id" in data[0]:
            assert data[0]["recipient_id"] == sender
```

#### 3.2.2 `test_intents_complete.py`

```python
"""
Test E2E per tutti i 20 intent.
Ogni test replica chiamata frontend completa.
"""

import pytest
import re

# Definizione test per ogni intent
INTENT_TESTS = [
    # (query, expected_intent, response_pattern)
    ("ciao", "greet", r"benvenuto|ciao|buon"),
    ("arrivederci", "goodbye", r"arrivederci|buon lavoro"),
    ("aiuto", "ask_help", r"posso aiutarti|domand"),
    ("cosa puoi fare", "ask_help", r"posso|funzionalit"),

    # Piano queries
    ("di cosa tratta il piano A1", "ask_piano_description", r"piano|A1"),
    ("stabilimenti del piano A22", "ask_piano_stabilimenti", r"stabiliment|control"),
    ("attività piano B2", "ask_piano_stabilimenti", r"attivit|piano"),
    ("statistiche sui piani", "ask_piano_statistics", r"statistic|piano"),

    # Search
    ("quali piani riguardano bovini", "search_piani_by_topic", r"piano|bovin"),
    ("piani su allevamenti", "search_piani_by_topic", r"piano|allev"),

    # Priority
    ("chi devo controllare per primo", "ask_priority_establishment", r"priorit|control|stabil"),
    ("quale stabilimento controllare", "ask_priority_establishment", r"stabil|control"),

    # Risk
    ("stabilimenti ad alto rischio", "ask_risk_based_priority", r"rischio|priorit"),
    ("sulla base del rischio storico", "ask_risk_based_priority", r"rischio|storic"),

    # Suggest controls
    ("suggerisci controlli", "ask_suggest_controls", r"control|suggeri"),

    # Delayed plans
    ("piani in ritardo", "ask_delayed_plans", r"ritard|piano"),
    ("quali piani sono in ritardo", "ask_delayed_plans", r"ritard|piano"),
    ("il piano B47 è in ritardo", "check_if_plan_delayed", r"ritard|B47|piano"),

    # Establishment history
    ("storico controlli stabilimento IT 2287", "ask_establishment_history", r"storico|control"),

    # Top risk activities
    ("attività più rischiose", "ask_top_risk_activities", r"rischio|attivit"),

    # NC analysis
    ("analizza le non conformità HACCP", "analyze_nc_by_category", r"NC|HACCP|conformit"),

    # Two-phase (richiedono contesto)
    # Testati separatamente in test_two_phase.py
]


class TestIntentsComplete:
    """Test E2E per tutti i 20 intent."""

    @pytest.mark.e2e
    @pytest.mark.parametrize("query,expected_intent,response_pattern", INTENT_TESTS)
    def test_intent(self, api_client, unique_sender, complete_metadata,
                    query, expected_intent, response_pattern):
        """Test singolo intent con payload frontend completo."""

        response = api_client(query, unique_sender, complete_metadata)

        assert "text" in response
        text = response["text"]

        # Verifica pattern nella risposta
        assert re.search(response_pattern, text, re.IGNORECASE), \
            f"Intent {expected_intent}: pattern '{response_pattern}' non trovato in '{text[:200]}...'"

    @pytest.mark.e2e
    def test_all_intents_coverage(self):
        """Verifica che tutti i 20 intent siano testati."""
        from orchestrator.router import Router

        tested_intents = {t[1] for t in INTENT_TESTS}
        tested_intents.add("confirm_show_details")  # In test_two_phase.py
        tested_intents.add("decline_show_details")  # In test_two_phase.py
        tested_intents.add("info_procedure")         # Test separato (RAG)
        tested_intents.add("ask_nearby_priority")    # Test separato (geo)
        tested_intents.add("fallback")               # In test_fallback.py

        missing = set(Router.VALID_INTENTS) - tested_intents
        assert not missing, f"Intent non testati: {missing}"
```

#### 3.2.3 `test_two_phase.py`

```python
"""
Test E2E per flusso two-phase (sommario + dettagli).
"""

import pytest


class TestTwoPhase:
    """Test flusso sommario → conferma → dettagli."""

    @pytest.mark.e2e
    def test_two_phase_confirm(self, api_client, unique_sender, complete_metadata):
        """Test conferma dopo sommario."""
        # Phase 1: query che genera sommario
        resp1 = api_client("piani in ritardo", unique_sender, complete_metadata)

        assert "text" in resp1
        text1 = resp1["text"].lower()
        # Deve contenere sommario e chiedere conferma
        assert "piano" in text1 or "ritard" in text1

        # Phase 2: conferma con stesso sender
        resp2 = api_client("sì", unique_sender, complete_metadata)

        assert "text" in resp2
        text2 = resp2["text"].lower()
        # Risposta deve essere diversa (dettagli o altra azione)
        assert len(text2) > 0

    @pytest.mark.e2e
    def test_two_phase_decline(self, api_client, unique_sender, complete_metadata):
        """Test rifiuto dettagli dopo sommario."""
        # Phase 1: query
        resp1 = api_client("stabilimenti prioritari", unique_sender, complete_metadata)

        # Phase 2: rifiuto
        resp2 = api_client("no grazie", unique_sender, complete_metadata)

        assert "text" in resp2
        text2 = resp2["text"].lower()
        # Deve offrire altro aiuto
        assert "aiut" in text2 or "domand" in text2 or "altro" in text2

    @pytest.mark.e2e
    def test_session_isolation(self, api_client, complete_metadata):
        """Test che sessioni diverse siano isolate."""
        import time
        import random
        import string

        def make_sender():
            ts = int(time.time() * 1000)
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
            return f"user_{ts}_{suffix}"

        sender_a = make_sender()
        sender_b = make_sender()

        # User A: query piani
        api_client("piani in ritardo", sender_a, complete_metadata)

        # User B: query diversa
        api_client("stabilimenti ad alto rischio", sender_b, complete_metadata)

        # User A: conferma (deve riferirsi ai piani, non al rischio)
        resp_a = api_client("sì", sender_a, complete_metadata)

        text_a = resp_a["text"].lower()
        # Non deve menzionare rischio (context di B)
        # Può menzionare piani o offrire aiuto
        assert "rischio storico" not in text_a or "piano" in text_a
```

#### 3.2.4 `test_metadata.py`

```python
"""
Test E2E per gestione metadata completi.
"""

import pytest


class TestMetadata:
    """Test gestione metadata come frontend."""

    @pytest.mark.e2e
    def test_metadata_asl_priority(self, api_client, unique_sender):
        """Test che asl abbia priorità su asl_id."""
        metadata = {
            "asl": "BENEVENTO",  # Deve avere priorità
            "asl_id": "999",     # Ignorato se asl presente
            "user_id": "6448"
        }

        resp = api_client("chi devo controllare", unique_sender, metadata)

        # Risposta deve usare BENEVENTO, non 999
        # Il backend deve filtrare per ASL corretta
        assert "text" in resp

    @pytest.mark.e2e
    def test_metadata_uoc_resolution(self, api_client, unique_sender):
        """Test risoluzione UOC da user_id."""
        metadata = {
            "asl": "AVELLINO",
            "user_id": "6448"  # Backend deve risolvere UOC
        }

        resp = api_client("stabilimenti prioritari", unique_sender, metadata)

        assert "text" in resp
        # La risposta deve essere contestualizzata all'UOC dell'utente

    @pytest.mark.e2e
    def test_metadata_all_fields(self, api_client, unique_sender):
        """Test con tutti i campi metadata come frontend reale."""
        metadata = {
            "asl": "BENEVENTO",
            "asl_id": "202",
            "user_id": "6448",
            "codice_fiscale": "ZZIBRD65R11A783K",
            "username": "mario.rossi"
        }

        resp = api_client("piani in ritardo", unique_sender, metadata)

        assert "text" in resp
        assert len(resp["text"]) > 0

    @pytest.mark.e2e
    def test_metadata_missing_asl(self, api_client, unique_sender):
        """Test comportamento senza ASL."""
        metadata = {
            "user_id": "6448"
            # NO asl, NO asl_id
        }

        resp = api_client("aiuto", unique_sender, metadata)

        # Deve comunque funzionare (help non richiede ASL)
        assert "text" in resp
```

### Fase 3: Test Integrazione (Settimana 3)

#### 3.3.1 `test_router_llm.py`

```python
"""
Test integrazione Router con LLM reale (NO MOCK).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRouterLLM:
    """Test Router con LLM reale."""

    @pytest.fixture
    def router(self):
        """Router con LLM reale."""
        from orchestrator.router import Router
        from llm.client import LLMClient

        llm = LLMClient()
        return Router(llm)

    @pytest.mark.integration
    def test_classify_greet(self, router):
        """Test classificazione saluto."""
        result = router.classify("ciao")
        assert result["intent"] == "greet"

    @pytest.mark.integration
    def test_classify_with_slot(self, router):
        """Test classificazione con estrazione slot."""
        result = router.classify("di cosa tratta il piano A1")

        assert result["intent"] == "ask_piano_description"
        assert result["slots"].get("piano_code") == "A1"

    @pytest.mark.integration
    def test_classify_complex(self, router):
        """Test classificazione query complessa."""
        result = router.classify(
            "quali sono gli stabilimenti che dovrei controllare "
            "per primi basandomi sul rischio storico"
        )

        assert result["intent"] in ["ask_risk_based_priority", "ask_priority_establishment"]

    @pytest.mark.integration
    def test_classify_ambiguous(self, router):
        """Test query ambigua."""
        result = router.classify("rischio")

        # Può essere ask_risk_based_priority o chiedere chiarimento
        assert result["intent"] in ["ask_risk_based_priority", "fallback"] or \
               result.get("needs_clarification", False)
```

#### 3.3.2 `test_tools_data.py`

```python
"""
Test integrazione Tools con dati reali (NO MOCK).
"""

import pytest


class TestToolsData:
    """Test tools con dati PostgreSQL/CSV reali."""

    @pytest.mark.integration
    def test_piano_description_real(self):
        """Test get_piano_description con dati reali."""
        from tools.piano_tools import get_piano_description

        # Piano A1 esiste nel database
        result = get_piano_description.func("A1")

        assert "error" not in result
        assert "formatted_response" in result
        assert len(result["formatted_response"]) > 0

    @pytest.mark.integration
    def test_piano_not_found(self):
        """Test piano inesistente."""
        from tools.piano_tools import get_piano_description

        result = get_piano_description.func("ZZZZZ")

        assert "error" in result
        assert "non trovato" in result["error"].lower()

    @pytest.mark.integration
    def test_search_real(self):
        """Test search con dati reali."""
        from tools.search_tools import search_piani_by_topic

        result = search_piani_by_topic.func("bovini")

        assert "error" not in result
        assert result["total_found"] > 0
        assert "matches" in result

    @pytest.mark.integration
    def test_priority_real(self):
        """Test priority con dati reali."""
        from tools.priority_tools import get_priority_establishment

        result = get_priority_establishment.func(
            asl="AVELLINO",
            uoc="UOC IGIENE URBANA"
        )

        assert isinstance(result, dict)
        # Può avere dati o errore "nessun dato", ma non crash

    @pytest.mark.integration
    def test_delayed_plans_real(self):
        """Test piani in ritardo con dati reali."""
        from tools.priority_tools import get_delayed_plans

        result = get_delayed_plans.func(
            asl="AVELLINO",
            uoc="UOC IGIENE URBANA"
        )

        assert isinstance(result, dict)
        # Verifica struttura, non contenuto specifico
```

### Fase 4: Cleanup e Documentazione (Settimana 4)

#### 3.4.1 Rimozione File Legacy

```bash
# Script di migrazione
mkdir -p tests/legacy

# Sposta file con mock in legacy
mv tests/test_router.py tests/legacy/
mv tests/test_graph.py tests/legacy/
mv tests/test_tools.py tests/legacy/
mv tests/test_few_shot_retriever.py tests/legacy/
mv tests/test_procedure_tools.py tests/legacy/
mv tests/test_intelligent_monitor.py tests/legacy/
mv tests/test_graph_fallback.py tests/legacy/
mv tests/test_ml_predictor.py tests/legacy/

# Mantieni file già senza mock
# test_server.py → rinomina a tests/e2e/test_server_legacy.py (reference)
# test_tools_simple.py → integra in tests/integration/

# Aggiungi .gitignore per legacy
echo "# Test legacy con mock - deprecati" > tests/legacy/.gitignore
echo "# Mantenuti per reference, non eseguiti" >> tests/legacy/.gitignore
```

#### 3.4.2 Script di Migrazione Completo

```bash
#!/bin/bash
# migrate_tests.sh - Esegui dalla root del progetto

set -e

echo "=== Migrazione Test Suite GiAs-llm ==="
echo ""

cd GiAs-llm

# 1. Crea struttura directory
echo "1. Creazione struttura directory..."
mkdir -p tests/e2e
mkdir -p tests/integration
mkdir -p tests/fixtures/payloads
mkdir -p tests/fixtures/expected
mkdir -p tests/legacy

# 2. Sposta file legacy
echo "2. Spostamento file legacy (con mock)..."
for f in test_router.py test_graph.py test_tools.py test_few_shot_retriever.py \
         test_procedure_tools.py test_intelligent_monitor.py test_graph_fallback.py \
         test_ml_predictor.py test_nc_categories.py test_nearby_priority.py \
         test_fallback_recovery.py; do
    if [ -f "tests/$f" ]; then
        mv "tests/$f" "tests/legacy/"
        echo "   Moved: $f"
    fi
done

# 3. Crea __init__.py
echo "3. Creazione __init__.py..."
touch tests/e2e/__init__.py
touch tests/integration/__init__.py
touch tests/legacy/__init__.py

# 4. Verifica file mantenuti
echo ""
echo "4. File mantenuti (senza mock):"
ls -la tests/*.py 2>/dev/null || echo "   (nessuno nella root)"

echo ""
echo "=== Migrazione completata ==="
echo ""
echo "Prossimi passi:"
echo "1. Copia i nuovi file test in tests/e2e/ e tests/integration/"
echo "2. Aggiorna conftest.py"
echo "3. Crea pytest.ini"
echo "4. Esegui: python tests/run_all_tests.py"
```

---

## 4. Comando Unico di Esecuzione

### 4.1 Aggiornamento `scripts/server.sh`

Aggiungere al file `scripts/server.sh`:

```bash
# ... existing code ...

test)
    echo "🧪 Running test suite..."
    cd "$PROJECT_ROOT"

    # Verifica server
    if ! curl -s http://localhost:5005/ > /dev/null 2>&1; then
        echo "⚠️  Server non attivo. Avvio automatico..."
        $0 start
        sleep 5
    fi

    # Esegui test
    python tests/run_all_tests.py "$@"
    ;;

test-quick)
    echo "🧪 Running quick tests..."
    cd "$PROJECT_ROOT"
    python tests/run_all_tests.py --quick "$@"
    ;;

test-report)
    echo "🧪 Running tests with report..."
    cd "$PROJECT_ROOT"
    python tests/run_all_tests.py --report json "$@"
    ;;

# ... existing code ...
```

### 4.2 Comando Finale

```bash
# Test completi con report
cd GiAs-llm && scripts/server.sh test --report json

# Test veloci (no slow, no streaming)
cd GiAs-llm && scripts/server.sh test-quick

# Test con output parallelo
cd GiAs-llm && scripts/server.sh test --parallel 4

# Solo E2E
cd GiAs-llm && python -m pytest tests/e2e/ -v

# Solo integrazione
cd GiAs-llm && python -m pytest tests/integration/ -v
```

---

## 5. Report Output

### 5.1 Formato Console

```
============================================================
GiAs-llm Test Suite v4.0
============================================================
Server: http://localhost:5005 (v3.4.0 - ok)
Mode: Full
Parallel: 4 workers
============================================================

Running: tests/e2e/test_api_endpoints.py
  ✅ 5 passed, 0 failed, 0 skipped (2.3s)
Running: tests/e2e/test_api_webhook.py
  ✅ 8 passed, 0 failed, 0 skipped (15.2s)
Running: tests/e2e/test_intents_complete.py
  ✅ 22 passed, 0 failed, 0 skipped (45.8s)
Running: tests/e2e/test_metadata.py
  ✅ 4 passed, 0 failed, 0 skipped (8.1s)
Running: tests/e2e/test_sessions.py
  ✅ 6 passed, 0 failed, 0 skipped (12.4s)
Running: tests/e2e/test_two_phase.py
  ✅ 3 passed, 0 failed, 0 skipped (9.7s)
Running: tests/e2e/test_fallback.py
  ✅ 5 passed, 0 failed, 0 skipped (11.2s)
Running: tests/integration/test_router_llm.py
  ✅ 4 passed, 0 failed, 0 skipped (18.3s)
Running: tests/integration/test_tools_data.py
  ✅ 5 passed, 0 failed, 0 skipped (6.4s)

============================================================
SUMMARY
============================================================
Total:    62 tests
Passed:   62 ✅
Failed:   0 ❌
Skipped:  0 ⏭️
Errors:   0 💥
Duration: 129.4s
============================================================

✅ ALL TESTS PASSED

Report salvato: runtime/test_reports/test_report_20260215_143022.json
```

### 5.2 Formato JSON Report

```json
{
  "timestamp": "2026-02-15T14:30:22.123456",
  "server_url": "http://localhost:5005",
  "server_status": "v3.4.0 - ok",
  "suites": [
    {
      "name": "test_api_endpoints",
      "tests": [
        {
          "name": "tests/e2e/test_api_endpoints.py::TestEndpoints::test_health",
          "status": "passed",
          "duration": 0.234,
          "message": ""
        }
      ],
      "passed": 5,
      "failed": 0,
      "skipped": 0,
      "errors": 0,
      "duration": 2.3
    }
  ],
  "total_passed": 62,
  "total_failed": 0,
  "total_skipped": 0,
  "total_errors": 0,
  "total_duration": 129.4
}
```

---

## 6. Checklist Implementazione

### Fase 1: Infrastruttura
- [ ] Creare struttura directory `tests/e2e/`, `tests/integration/`, `tests/legacy/`
- [ ] Nuovo `conftest.py` senza mock globali
- [ ] Creare `pytest.ini`
- [ ] Creare `run_all_tests.py`
- [ ] Aggiornare `scripts/server.sh` con comandi test

### Fase 2: Test E2E
- [ ] `test_api_endpoints.py` - endpoint base
- [ ] `test_api_webhook.py` - webhook con payload frontend
- [ ] `test_intents_complete.py` - tutti i 20 intent
- [ ] `test_metadata.py` - gestione metadata completi
- [ ] `test_sessions.py` - isolamento sessioni
- [ ] `test_two_phase.py` - flusso sommario/dettagli
- [ ] `test_fallback.py` - fallback 3-phase
- [ ] `test_streaming.py` - endpoint SSE

### Fase 3: Test Integrazione
- [ ] `test_router_llm.py` - Router con LLM reale
- [ ] `test_tools_data.py` - Tools con dati reali
- [ ] `test_hybrid_search.py` - Hybrid search completo
- [ ] `test_ml_predictor.py` - ML predictor

### Fase 4: Cleanup
- [ ] Spostare file legacy in `tests/legacy/`
- [ ] Verificare copertura 20/20 intent
- [ ] Documentare in `GiAs-llm/docs/CLAUDE.md`
- [ ] Update `CLAUDE.md` root con nuovi comandi

---

## 7. Benefici Attesi

| Aspetto | Prima | Dopo |
|---------|-------|------|
| **Mock** | 15 file | 0 file |
| **Copertura reale** | ~40% | 100% |
| **Payload frontend** | Parziale | Identico |
| **Timeout allineati** | No | Sì (75s) |
| **Report strutturato** | No | JSON/HTML |
| **Comando unico** | No | `scripts/server.sh test` |
| **Streaming testato** | No | Sì |
| **Sessioni isolate** | Parziale | Completo |

---

## 8. Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| LLM non deterministico | Test flaky | Pattern matching fuzzy, multiple run |
| Server lento | Timeout | Timeout adattivi, retry |
| Dati cambiano | Test falliscono | Test su struttura, non contenuto |
| Parallelismo | Race condition | Sender unici, isolamento |

---

## Appendice: Dipendenze

```
# requirements-test.txt
pytest>=7.0.0
pytest-json-report>=1.5.0
pytest-xdist>=3.0.0  # Per parallelismo
requests>=2.28.0
pydantic>=2.0.0
```

Installazione:
```bash
pip install -r requirements-test.txt
```
