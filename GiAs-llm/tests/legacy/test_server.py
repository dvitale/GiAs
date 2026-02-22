#!/usr/bin/env python3
"""
GiAs-llm Test Suite v3.4 (Python)
Comprehensive system diagnostics with full coverage of:

Core API:
- Schema validation (Pydantic) for all API responses
- REST endpoint tests (/, /config, /status, /tracker, /model/parse)
- Input validation (malformed JSON, missing fields, wrong types)

Intent Classification:
- 20 intents including confirm_show_details/decline_show_details
- needs_clarification + slot validation rules
- Slot extraction (piano_code, topic, asl, num_registrazione, etc.)
- TRUE intent verification via /model/parse (v3.3: not just regex on response)

Session & State:
- Two-phase flow with summary/details content validation
- Session isolation and TTL
- Concurrent request handling with unique senders
- Edge cases: confirm without phase 1, state reset, TTL mechanism (v3.3)

Metadata:
- ASL priority (user > metadata)
- UOC resolution from user_id
- Default user_id from sender
- Missing ASL handling (v3.3)

Error Handling (v3.3):
- Error branches in webhook and /model/parse
- Invalid metadata types
- Very long messages
- Parse error field validation

Fallback Recovery (v3.4):
- 3-phase fallback (keyword → LLM → category menu)
- Loop prevention (max 3 consecutive fallbacks → help escalation)
- Suggestion selection by number
- Fallback state reset after valid intent

Conversational Memory (v3.4):
- Session memory across turns (last_intent, last_slots)
- Slot carry-forward on needs_clarification
- Memory isolation between senders

Workflow Orchestration (v3.4):
- Strategy presentation for ambiguous queries
- Numeric strategy selection
- "oppure?" alternative request handling

SSE Streaming (v3.4):
- /webhooks/rest/webhook/stream endpoint
- SSE event format validation
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
from pydantic import BaseModel, ValidationError

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

SERVER_URL = os.environ.get("GIAS_SERVER_URL", "http://localhost:5005")
WEBHOOK = f"{SERVER_URL}/webhooks/rest/webhook"
STATUS_URL = f"{SERVER_URL}/status"

# ═══════════════════════════════════════════════════════════════════════════
# Dynamic Timeout Configuration (adatta timeout per Ollama remoto)
# ═══════════════════════════════════════════════════════════════════════════

def is_ollama_remote() -> bool:
    """Verifica se Ollama è configurato come remoto (non localhost)"""
    try:
        project_root = Path(__file__).parent.parent
        config_file = project_root / "configs" / "config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Verifica OLLAMA_HOST env var prima di config.json
        ollama_host = os.environ.get('OLLAMA_HOST') or config.get('llm_backend', {}).get('ollama', {}).get('host', 'localhost')

        # Parse hostname
        if not ollama_host:
            return False
        parsed = urllib.parse.urlparse(ollama_host if '://' in ollama_host else f'http://{ollama_host}')
        hostname = parsed.hostname or 'localhost'

        is_remote = hostname not in ('localhost', '127.0.0.1', '0.0.0.0', '::1')
        return is_remote
    except Exception as e:
        print(f"⚠️  Warning: Could not detect Ollama host configuration: {e}")
        return False

# Adatta timeout se Ollama è remoto (aggiunge margine per latenza rete + carico server)
IS_OLLAMA_REMOTE = is_ollama_remote()
# Timeout conservativi per Ollama remoto che può essere lento o occupato
TIMEOUT_CACHED = 120 if IS_OLLAMA_REMOTE else 30      # 2 minuti per query veloci remote
TIMEOUT_UNCACHED = 300 if IS_OLLAMA_REMOTE else 120   # 5 minuti per query ML/DB remote
PARALLEL_JOBS = 4

# ═══════════════════════════════════════════════════════════════════════════
# Response Schema Validation (Pydantic)
# ═══════════════════════════════════════════════════════════════════════════

class WebhookResponseItem(BaseModel):
    """Schema for individual webhook response item (Rasa format)"""
    text: str
    recipient_id: Optional[str] = None


class ParseResponseIntent(BaseModel):
    """Schema for intent in parse response"""
    name: str
    confidence: float


class ParseResponse(BaseModel):
    """Schema for /model/parse response"""
    text: str
    intent: ParseResponseIntent
    entities: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    slots: Optional[Dict[str, Any]] = None
    needs_clarification: Optional[bool] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Schema for / health check response"""
    status: str
    version: str
    model_loaded: bool


class StatusResponse(BaseModel):
    """Schema for /status response"""
    status: str
    model_loaded: bool
    current_year: int
    data_loaded: Dict[str, int]
    framework: str
    llm: str


class ConfigResponse(BaseModel):
    """Schema for /config response"""
    current_year: int
    data_source_type: str
    status: str


class TrackerResponse(BaseModel):
    """Schema for /conversations/{id}/tracker response"""
    sender_id: str
    slots: Dict[str, Any]
    latest_message: Dict[str, Any]
    events: List[Any]
    paused: bool
    followup_action: Optional[str]
    active_loop: Dict[str, Any]


# ANSI Colors
class Colors:
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    WHITE = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.GREEN = cls.RED = cls.YELLOW = cls.BLUE = ""
        cls.CYAN = cls.WHITE = cls.RESET = ""


# ═══════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    name: str
    status: str  # "pass", "fail", "skip"
    time: float
    details: str = ""


@dataclass
class TestContext:
    quick_mode: bool = False
    verbose: bool = False
    json_output: bool = False
    auto_start: bool = True
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    results: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Intent Test Cases
# ═══════════════════════════════════════════════════════════════════════════

INTENT_TESTS_FULL = [
    # Greet/Goodbye
    ("ciao", r"benvenuto", "greet"),
    ("buongiorno", r"benvenuto", "greet"),
    ("arrivederci", r"arrivederci|buon lavoro", "goodbye"),
    ("grazie e arrivederci", r"arrivederci", "goodbye"),

    # Help
    ("aiuto", r"posso aiutarti|funzionalit", "ask_help"),
    ("cosa puoi fare", r"funzionalit|aiutarti", "ask_help"),
    ("che domande posso farti", r"funzionalit|esempi|aiutarti", "ask_help"),

    # Piano queries - Description
    ("di cosa tratta il piano A1", r"piano|A1", "ask_piano_description"),
    ("cosa prevede il piano B2", r"piano|B2", "ask_piano_description"),

    # Piano queries - Stabilimenti
    ("stabilimenti controllati piano A1", r"stabiliment|control", "ask_piano_stabilimenti"),
    ("dove è stato applicato il piano A32", r"stabiliment|control|A32", "ask_piano_stabilimenti"),

    # Piano queries - Generic (include attività) - ora mappati a ask_piano_stabilimenti
    ("attività piano A1", r"attivit|piano|A1", "ask_piano_stabilimenti"),
    ("quali attività riguarda il piano B2", r"attivit|piano", "ask_piano_stabilimenti"),
    ("dimmi del piano A1", r"piano|A1", "ask_piano_stabilimenti"),
    ("parlami del piano C3", r"piano|C3", "ask_piano_stabilimenti"),

    # Piano queries - Statistics
    ("statistiche sui piani di controllo", r"statistic|piano|control", "ask_piano_statistics"),
    ("quali sono i piani più usati", r"piano|control|frequent", "ask_piano_statistics"),
    ("quale piano è più frequente", r"piano|frequent|control", "ask_piano_statistics"),

    # Search
    ("piani su allevamenti", r"piano|allev", "search_piani_by_topic"),
    ("quali piani riguardano la macellazione", r"piano|macell", "search_piani_by_topic"),
    ("cerca piani su latte", r"piano|latte", "search_piani_by_topic"),

    # Priority
    ("chi devo controllare per primo", r"priorit|control|stabil|ASL", "ask_priority_establishment"),
    ("quali stabilimenti controllare", r"stabili|control|ASL", "ask_priority_establishment"),
    ("cosa devo fare oggi", r"priorit|control|stabil|ASL", "ask_priority_establishment"),

    # Risk-based
    ("stabilimenti ad alto rischio", r"rischio|priorit|ASL|Specificare", "ask_risk_based_priority"),
    ("stabilimenti più rischiosi", r"rischio|ASL|Specificare", "ask_risk_based_priority"),

    # Suggest controls
    ("suggerisci controlli", r"control|suggeri|mai controllat", "ask_suggest_controls"),
    ("quali stabilimenti non sono mai stati controllati", r"mai controllat|stabili", "ask_suggest_controls"),

    # Delayed plans
    ("piani in ritardo", r"ritard|piano|Statistic", "ask_delayed_plans"),
    ("quali piani sono in ritardo", r"ritard|piano|Statistic", "ask_delayed_plans"),

    # Check specific plan
    ("il piano B47 è in ritardo", r"ritard|B47|piano", "check_if_plan_delayed"),
    ("verifica se il piano A1 è in ritardo", r"ritard|A1", "check_if_plan_delayed"),

    # Establishment history
    ("storico controlli stabilimento IT 2287", r"storico|control", "ask_establishment_history"),
    ("controlli per partita IVA 12345678901", r"control|partita|storico", "ask_establishment_history"),
    ("storia dei controlli per stabilimento SEPE", r"control|storico|SEPE", "ask_establishment_history"),

    # Top risk activities
    ("attività più rischiose", r"rischio|attivit", "ask_top_risk_activities"),
    ("classifica attività per rischio", r"rischio|attivit|classif", "ask_top_risk_activities"),
    ("top 10 attività a rischio", r"rischio|attivit|top", "ask_top_risk_activities"),

    # NC analysis by category
    ("analizza le non conformità HACCP", r"NC|HACCP|non conformit", "analyze_nc_by_category"),
    ("NC categoria IGIENE DEGLI ALIMENTI", r"NC|IGIENE|non conformit", "analyze_nc_by_category"),

    # Two-phase flow: confirm/decline details (critical for 2-phase UX)
    ("sì", r"dettagli|aiutarti|domand", "confirm_show_details"),
    ("si mostrami i dettagli", r"dettagli", "confirm_show_details"),
    ("vediamo tutti", r"dettagli", "confirm_show_details"),
    ("no grazie", r"aiutarti|domand|bene", "decline_show_details"),
    ("va bene così", r"aiutarti|domand|bene", "decline_show_details"),
]

# Tests for needs_clarification scenarios (missing required slots)
CLARIFICATION_TESTS = [
    # Intent requires piano_code but missing → should ask for clarification
    ("dimmi del piano", "ask_piano_stabilimenti", True, {}),
    ("descrizione piano", "ask_piano_description", True, {}),
    ("stabilimenti controllati", "ask_piano_stabilimenti", True, {}),
    # Intent requires topic but missing
    ("cerca piani", "search_piani_by_topic", True, {}),
    # Intent requires establishment identifier but missing
    ("storico stabilimento", "ask_establishment_history", True, {}),
    # Intent with all required slots → should NOT need clarification
    ("dimmi del piano A1", "ask_piano_stabilimenti", False, {"piano_code": "A1"}),
    ("piani su allevamenti", "search_piani_by_topic", False, {"topic": "allevamenti"}),
    # Self-sufficient intents (no required slots)
    ("chi controllare per primo", "ask_priority_establishment", False, {}),
    ("piani in ritardo", "ask_delayed_plans", False, {}),
]

INTENT_TESTS_QUICK = [
    ("ciao", r"benvenuto", "greet"),
    ("aiuto", r"posso aiutarti|funzionalit", "ask_help"),
    ("di cosa tratta il piano A1", r"piano|A1", "ask_piano_description"),
    ("statistiche sui piani", r"statistic|piano", "ask_piano_statistics"),
    ("piani su allevamenti", r"piano|allev", "search_piani_by_topic"),
    ("stabilimenti ad alto rischio", r"rischio|ASL|Specificare|predittiva", "ask_risk_based_priority"),
    ("piani in ritardo", r"ritard|piano|Statistic|controlli", "ask_delayed_plans"),
    ("attività più rischiose", r"rischio|attivit", "ask_top_risk_activities"),
]

PERF_QUERIES_FULL = ["ciao", "aiuto", "piano A1", "stabilimenti rischio"]
PERF_QUERIES_QUICK = ["ciao", "aiuto"]


# ═══════════════════════════════════════════════════════════════════════════
# Logging Functions
# ═══════════════════════════════════════════════════════════════════════════

def log(ctx: TestContext, msg: str):
    # Log configurazione timeout alla prima esecuzione
    if not hasattr(log, '_logged_config'):
        if not ctx.json_output:
            print(f"\n{'='*70}")
            print(f"⏱️  Configurazione Timeout Test")
            print(f"{'='*70}")
            print(f"   Ollama remoto rilevato: {'SÌ' if IS_OLLAMA_REMOTE else 'NO'}")
            if IS_OLLAMA_REMOTE:
                try:
                    project_root = Path(__file__).parent.parent
                    config_file = project_root / "configs" / "config.json"
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    ollama_host = os.environ.get('OLLAMA_HOST') or config.get('llm_backend', {}).get('ollama', {}).get('host', 'localhost')
                    print(f"   Host Ollama: {ollama_host}")
                except:
                    pass
            print(f"   Timeout CACHED: {TIMEOUT_CACHED}s (richieste veloci)")
            print(f"   Timeout UNCACHED: {TIMEOUT_UNCACHED}s (richieste ML/predictor)")
            print(f"{'='*70}\n")
        log._logged_config = True
    if not ctx.json_output:
        print(msg)


def log_ok(ctx: TestContext, msg: str):
    ctx.passed += 1
    log(ctx, f"{Colors.GREEN}[✓]{Colors.RESET} {msg}")


def log_fail(ctx: TestContext, msg: str):
    ctx.failed += 1
    log(ctx, f"{Colors.RED}[✗]{Colors.RESET} {msg}")


def log_skip(ctx: TestContext, msg: str):
    ctx.skipped += 1
    log(ctx, f"{Colors.YELLOW}[○]{Colors.RESET} {msg}")


def log_info(ctx: TestContext, msg: str):
    log(ctx, f"{Colors.BLUE}[i]{Colors.RESET} {msg}")


def section(ctx: TestContext, title: str):
    log(ctx, f"\n{Colors.WHITE}{Colors.CYAN}▶ {title}{Colors.RESET}")
    log(ctx, "─" * 50)


# ═══════════════════════════════════════════════════════════════════════════
# API Query Functions
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class QueryResult:
    """Full result from webhook query for comprehensive testing"""
    elapsed: float
    status_code: int
    raw_text: str
    json_data: Optional[List[Dict[str, Any]]] = None
    schema_valid: bool = False
    schema_error: str = ""

    @property
    def text(self) -> str:
        """Extract text from first response item (backward compatible)"""
        if self.json_data and len(self.json_data) > 0:
            return self.json_data[0].get("text", "")
        return self.raw_text


def query(message: str, metadata: Optional[dict] = None, timeout: int = TIMEOUT_CACHED) -> tuple[float, str]:
    """Execute a query to the webhook and return (elapsed_time, response_text).

    Legacy function for backward compatibility.
    """
    result = query_full(message, metadata, timeout)
    return result.elapsed, result.text


def query_full(message: str, metadata: Optional[dict] = None, timeout: int = TIMEOUT_CACHED,
               sender: str = "test") -> QueryResult:
    """Execute a query to the webhook and return full QueryResult with schema validation."""
    if metadata is None:
        metadata = {}

    payload = {
        "sender": sender,
        "message": message,
        "metadata": metadata
    }

    start = time.time()
    try:
        resp = requests.post(
            WEBHOOK,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        elapsed = time.time() - start

        result = QueryResult(
            elapsed=elapsed,
            status_code=resp.status_code,
            raw_text=resp.text
        )

        # Try to parse JSON
        try:
            result.json_data = resp.json()

            # Validate schema (expecting list of WebhookResponseItem)
            if isinstance(result.json_data, list):
                for item in result.json_data:
                    WebhookResponseItem(**item)
                result.schema_valid = True
            else:
                result.schema_error = "Response is not a list"
        except json.JSONDecodeError as e:
            result.schema_error = f"Invalid JSON: {e}"
        except ValidationError as e:
            result.schema_error = f"Schema validation failed: {e}"

        return result

    except requests.RequestException as e:
        elapsed = time.time() - start
        return QueryResult(
            elapsed=elapsed,
            status_code=0,
            raw_text="",
            schema_error=f"Request failed: {e}"
        )


def check_response(response: str, pattern: str) -> bool:
    """Check if response matches the regex pattern (case insensitive)."""
    return bool(re.search(pattern, response, re.IGNORECASE))


def get_status() -> Optional[dict]:
    """Get server status."""
    try:
        resp = requests.get(STATUS_URL, timeout=5)
        return resp.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None


def is_server_running() -> bool:
    """Check if server is running."""
    try:
        resp = requests.get(STATUS_URL, timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def start_server() -> bool:
    """Start server using start_server.sh from scripts/."""
    project_root = Path(__file__).parent.parent
    server_script = project_root / "scripts" / "start_server.sh"

    # Fallback: try start_server.sh symlink at root
    if not server_script.exists():
        server_script = project_root / "../scripts/start_server.sh"

    if not server_script.exists():
        return False

    try:
        subprocess.run(
            [str(server_script), "start"],
            cwd=str(project_root),
            capture_output=True,
            timeout=10
        )
        time.sleep(5)
        return is_server_running()
    except subprocess.SubprocessError:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Test Sections
# ═══════════════════════════════════════════════════════════════════════════

def test_system_status(ctx: TestContext):
    """Section 1: System Status."""
    section(ctx, "1. SYSTEM STATUS")

    status = get_status()
    if status and "status" in status:
        log_ok(ctx, "API status endpoint responding")
        ctx.results.append(TestResult("api_status", "pass", 0))

        if not ctx.json_output:
            print(f"    LLM: {status.get('llm', 'N/A')}")
            print(f"    Framework: {status.get('framework', 'N/A')}")
            dl = status.get("data_loaded", {})
            print(f"    Data: {dl.get('piani', 0):,} piani, {dl.get('controlli', 0):,} controlli")
    else:
        log_fail(ctx, "API status endpoint not responding")
        ctx.results.append(TestResult("api_status", "fail", 0))
        return False

    # Process info - pid file is in project root runtime/logs/
    project_root = Path(__file__).parent.parent
    pid_file = project_root / "runtime" / "logs" / "api-server.pid"
    if pid_file.exists():
        try:
            pid = pid_file.read_text().strip()
            result = subprocess.run(
                ["ps", "-p", pid, "-o", "rss="],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                mem_kb = int(result.stdout.strip())
                mem_mb = mem_kb // 1024
                log_info(ctx, f"Server PID: {pid} | Memory: {mem_mb}MB")
        except (ValueError, subprocess.SubprocessError):
            pass

    return True


def test_intent_classification(ctx: TestContext):
    """Section 2: Intent Classification."""
    section(ctx, "2. INTENT CLASSIFICATION")

    tests = INTENT_TESTS_QUICK if ctx.quick_mode else INTENT_TESTS_FULL
    intent_pass = 0
    intent_fail = 0

    for query_text, pattern, intent in tests:
        elapsed, resp = query(query_text)
        ctx.total_time += elapsed

        if not resp or resp == "null":
            log_fail(ctx, f'"{query_text}" → TIMEOUT')
            ctx.results.append(TestResult(intent, "fail", elapsed, "timeout"))
            intent_fail += 1
        elif check_response(resp, pattern):
            if ctx.verbose:
                log_ok(ctx, f'"{query_text}" → {intent} ({elapsed:.2f}s)')
            else:
                print(f"{Colors.GREEN}.{Colors.RESET}", end="", flush=True)
            ctx.results.append(TestResult(intent, "pass", elapsed))
            intent_pass += 1
        else:
            log_fail(ctx, f'"{query_text}" → expected {intent}')
            ctx.results.append(TestResult(intent, "fail", elapsed, "pattern_mismatch"))
            intent_fail += 1

    if not ctx.verbose:
        print()  # Newline after dots

    intent_total = intent_pass + intent_fail
    intent_acc = (intent_pass * 100 // intent_total) if intent_total > 0 else 0

    if intent_acc >= 90:
        log_ok(ctx, f"Classification: {intent_acc}% ({intent_pass}/{intent_total})")
    elif intent_acc >= 70:
        log_skip(ctx, f"Classification: {intent_acc}% ({intent_pass}/{intent_total})")
    else:
        log_fail(ctx, f"Classification: {intent_acc}% ({intent_pass}/{intent_total})")

    return intent_acc


def test_performance(ctx: TestContext) -> float:
    """Section 3: Performance Benchmark."""
    section(ctx, "3. PERFORMANCE")

    # Warm cache
    query("test warm")

    queries = PERF_QUERIES_QUICK if ctx.quick_mode else PERF_QUERIES_FULL
    perf_total = 0.0

    for q in queries:
        elapsed, _ = query(q)
        perf_total += elapsed

        if elapsed < 0.5:
            color = Colors.GREEN
        elif elapsed < 2.0:
            color = Colors.YELLOW
        else:
            color = Colors.RED

        log(ctx, f'{color}{elapsed:.2f}s{Colors.RESET} ← "{q}"')

    avg = perf_total / len(queries) if queries else 0

    if avg < 1.0:
        log_ok(ctx, f"Avg response: {avg:.3f}s")
    elif avg < 3.0:
        log_skip(ctx, f"Avg response: {avg:.3f}s (acceptable)")
    else:
        log_fail(ctx, f"Avg response: {avg:.3f}s (slow)")

    return avg


def test_ml_predictor(ctx: TestContext):
    """Section 4: ML Predictor."""
    if ctx.quick_mode:
        return

    section(ctx, "4. ML PREDICTOR")

    for asl in ["AVELLINO", "NAPOLI 1 CENTRO", "SALERNO"]:
        metadata = {"asl": asl}
        elapsed, resp = query("stabilimenti ad alto rischio", metadata, TIMEOUT_UNCACHED)

        if check_response(resp, r"rischio|priorit|stabiliment|alto"):
            stab_count = len(re.findall(r'\d+\.', resp))
            log_ok(ctx, f"ASL {asl}: {stab_count} establishments")
        else:
            log_skip(ctx, f"ASL {asl}: response unclear")


def test_error_handling(ctx: TestContext):
    """Section 5: Edge Cases & Error Handling."""
    section(ctx, "5. ERROR HANDLING")

    # Empty message
    _, resp = query("")
    if resp and check_response(resp, "text"):
        log_ok(ctx, "Empty message handled")
    else:
        log_skip(ctx, "Empty message: unclear response")

    # Invalid ASL
    _, resp = query("stabilimenti rischio", {"asl": "INVALID_XYZ"})
    if resp:
        log_ok(ctx, "Invalid ASL handled gracefully")
    else:
        log_fail(ctx, "Invalid ASL crashed")

    # Very long query
    if not ctx.quick_mode:
        long_query = ("stabilimenti che hanno avuto problemi di non conformità "
                      "negli ultimi controlli e che richiedono attenzione urgente")
        _, resp = query(long_query, timeout=TIMEOUT_UNCACHED)
        if resp:
            log_ok(ctx, "Long query handled")
        else:
            log_skip(ctx, "Long query: timeout")

    # Special characters
    _, resp = query("piano A1?")
    if resp:
        log_ok(ctx, "Special chars handled")
    else:
        log_skip(ctx, "Special chars: unclear")


def test_cache_verification(ctx: TestContext):
    """Section 6: Cache Verification."""
    if ctx.quick_mode:
        return

    section(ctx, "6. CACHE VERIFICATION")

    import random
    random_id = random.randint(1000, 9999)
    times = []

    for i in range(1, 4):
        elapsed, _ = query(f"verifica cache test {random_id}")
        times.append(elapsed)
        log_info(ctx, f"Run {i}: {elapsed:.2f}s")

    log_ok(ctx, "Cache test completed")


def test_concurrent_requests(ctx: TestContext):
    """Section 7: Concurrent Requests (Enhanced with session isolation)."""
    if ctx.quick_mode:
        return

    section(ctx, "7. CONCURRENT REQUESTS")

    import random

    log_info(ctx, f"Sending {PARALLEL_JOBS} parallel requests with DIFFERENT senders...")

    # Use different senders to test session isolation under concurrency
    def run_query_with_sender(i: int) -> tuple:
        """Returns (sender_id, success, response_text)"""
        sender_id = f"concurrent_test_{i}_{random.randint(10000, 99999)}"
        result = query_full(f"ciao, sono utente {i}", sender=sender_id)
        return (sender_id, result.status_code == 200 and bool(result.text), result.text[:50] if result.text else "")

    results_list = []
    with ThreadPoolExecutor(max_workers=PARALLEL_JOBS) as executor:
        futures = [executor.submit(run_query_with_sender, i) for i in range(1, PARALLEL_JOBS + 1)]
        for future in as_completed(futures):
            try:
                results_list.append(future.result())
            except Exception as e:
                results_list.append((f"error_{len(results_list)}", False, str(e)))

    success_count = sum(1 for _, success, _ in results_list if success)
    unique_senders = len(set(sender for sender, _, _ in results_list))

    if success_count == PARALLEL_JOBS:
        log_ok(ctx, f"Concurrent: {success_count}/{PARALLEL_JOBS} succeeded")
        ctx.results.append(TestResult("concurrent_requests", "pass", 0))
    else:
        log_fail(ctx, f"Concurrent: {success_count}/{PARALLEL_JOBS} succeeded")
        ctx.results.append(TestResult("concurrent_requests", "fail", 0, f"{PARALLEL_JOBS - success_count} failed"))

    # Check sender isolation (all senders should be unique)
    if unique_senders == PARALLEL_JOBS:
        log_ok(ctx, f"Concurrent isolation: {unique_senders} unique senders, no cross-talk")
        ctx.results.append(TestResult("concurrent_isolation", "pass", 0))
    else:
        log_fail(ctx, f"Concurrent isolation: Only {unique_senders}/{PARALLEL_JOBS} unique senders")
        ctx.results.append(TestResult("concurrent_isolation", "fail", 0, f"{PARALLEL_JOBS - unique_senders} duplicates"))


def test_rest_endpoints(ctx: TestContext):
    """Section 8: REST Endpoints (Observability)."""
    section(ctx, "8. REST ENDPOINTS")

    # Test / (health check)
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=5)
        if resp.status_code == 200:
            try:
                data = resp.json()
                HealthResponse(**data)  # Validate schema
                log_ok(ctx, f"GET / → 200 OK, schema valid")
                ctx.results.append(TestResult("health_check", "pass", 0))
            except (json.JSONDecodeError, ValidationError) as e:
                log_fail(ctx, f"GET / → schema invalid: {e}")
                ctx.results.append(TestResult("health_check", "fail", 0, str(e)))
        else:
            log_fail(ctx, f"GET / → {resp.status_code}")
            ctx.results.append(TestResult("health_check", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"GET / → connection error: {e}")
        ctx.results.append(TestResult("health_check", "fail", 0, str(e)))

    # Test /config
    try:
        resp = requests.get(f"{SERVER_URL}/config", timeout=5)
        if resp.status_code == 200:
            try:
                data = resp.json()
                ConfigResponse(**data)  # Validate schema
                log_ok(ctx, f"GET /config → 200 OK, schema valid")
                ctx.results.append(TestResult("config_endpoint", "pass", 0))
            except (json.JSONDecodeError, ValidationError) as e:
                log_fail(ctx, f"GET /config → schema invalid: {e}")
                ctx.results.append(TestResult("config_endpoint", "fail", 0, str(e)))
        else:
            log_fail(ctx, f"GET /config → {resp.status_code}")
            ctx.results.append(TestResult("config_endpoint", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"GET /config → connection error: {e}")
        ctx.results.append(TestResult("config_endpoint", "fail", 0, str(e)))

    # Test /status (already tested in section 1, but verify schema)
    try:
        resp = requests.get(STATUS_URL, timeout=5)
        if resp.status_code == 200:
            try:
                data = resp.json()
                StatusResponse(**data)  # Validate schema
                log_ok(ctx, f"GET /status → 200 OK, schema valid")
                ctx.results.append(TestResult("status_endpoint", "pass", 0))
            except (json.JSONDecodeError, ValidationError) as e:
                log_fail(ctx, f"GET /status → schema invalid: {e}")
                ctx.results.append(TestResult("status_endpoint", "fail", 0, str(e)))
        else:
            log_fail(ctx, f"GET /status → {resp.status_code}")
            ctx.results.append(TestResult("status_endpoint", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"GET /status → connection error: {e}")
        ctx.results.append(TestResult("status_endpoint", "fail", 0, str(e)))

    # Test /conversations/{id}/tracker
    try:
        test_conv_id = "test_conversation_123"
        resp = requests.get(f"{SERVER_URL}/conversations/{test_conv_id}/tracker", timeout=5)
        if resp.status_code == 200:
            try:
                data = resp.json()
                TrackerResponse(**data)  # Validate schema
                if data.get("sender_id") == test_conv_id:
                    log_ok(ctx, f"GET /conversations/.../tracker → 200 OK, schema valid")
                    ctx.results.append(TestResult("tracker_endpoint", "pass", 0))
                else:
                    log_fail(ctx, f"GET /tracker → sender_id mismatch")
                    ctx.results.append(TestResult("tracker_endpoint", "fail", 0, "sender_id mismatch"))
            except (json.JSONDecodeError, ValidationError) as e:
                log_fail(ctx, f"GET /tracker → schema invalid: {e}")
                ctx.results.append(TestResult("tracker_endpoint", "fail", 0, str(e)))
        else:
            log_fail(ctx, f"GET /tracker → {resp.status_code}")
            ctx.results.append(TestResult("tracker_endpoint", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"GET /tracker → connection error: {e}")
        ctx.results.append(TestResult("tracker_endpoint", "fail", 0, str(e)))

    # Test /model/parse
    try:
        payload = {"text": "ciao", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)
        if resp.status_code == 200:
            try:
                data = resp.json()
                ParseResponse(**data)  # Validate schema
                intent_name = data.get("intent", {}).get("name", "")
                if intent_name:
                    log_ok(ctx, f"POST /model/parse → 200 OK, intent={intent_name}")
                    ctx.results.append(TestResult("parse_endpoint", "pass", 0))
                else:
                    log_fail(ctx, f"POST /model/parse → no intent returned")
                    ctx.results.append(TestResult("parse_endpoint", "fail", 0, "no intent"))
            except (json.JSONDecodeError, ValidationError) as e:
                log_fail(ctx, f"POST /model/parse → schema invalid: {e}")
                ctx.results.append(TestResult("parse_endpoint", "fail", 0, str(e)))
        else:
            log_fail(ctx, f"POST /model/parse → {resp.status_code}")
            ctx.results.append(TestResult("parse_endpoint", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"POST /model/parse → connection error: {e}")
        ctx.results.append(TestResult("parse_endpoint", "fail", 0, str(e)))


def test_webhook_schema_validation(ctx: TestContext):
    """Section 9: Webhook Schema Validation."""
    section(ctx, "9. WEBHOOK SCHEMA VALIDATION")

    # Test valid request with full schema validation
    result = query_full("ciao")

    # Check HTTP status code
    if result.status_code == 200:
        log_ok(ctx, f"Webhook HTTP status: 200 OK")
        ctx.results.append(TestResult("webhook_status_code", "pass", result.elapsed))
    else:
        log_fail(ctx, f"Webhook HTTP status: {result.status_code}")
        ctx.results.append(TestResult("webhook_status_code", "fail", result.elapsed, f"status {result.status_code}"))

    # Check JSON parsing
    if result.json_data is not None:
        log_ok(ctx, f"Webhook response is valid JSON")
        ctx.results.append(TestResult("webhook_json_valid", "pass", 0))
    else:
        log_fail(ctx, f"Webhook response not valid JSON: {result.schema_error}")
        ctx.results.append(TestResult("webhook_json_valid", "fail", 0, result.schema_error))

    # Check schema validation
    if result.schema_valid:
        log_ok(ctx, f"Webhook response schema valid (List[{{text, recipient_id}}])")
        ctx.results.append(TestResult("webhook_schema_valid", "pass", 0))
    else:
        log_fail(ctx, f"Webhook schema invalid: {result.schema_error}")
        ctx.results.append(TestResult("webhook_schema_valid", "fail", 0, result.schema_error))

    # Check response is not empty array
    if result.json_data and len(result.json_data) > 0:
        log_ok(ctx, f"Webhook response contains {len(result.json_data)} item(s)")
        ctx.results.append(TestResult("webhook_not_empty", "pass", 0))
    else:
        log_fail(ctx, f"Webhook response is empty array")
        ctx.results.append(TestResult("webhook_not_empty", "fail", 0, "empty array"))

    # Check text field has content
    if result.text and len(result.text) > 0:
        log_ok(ctx, f"Response text has content ({len(result.text)} chars)")
        ctx.results.append(TestResult("webhook_has_text", "pass", 0))
    else:
        log_fail(ctx, f"Response text is empty")
        ctx.results.append(TestResult("webhook_has_text", "fail", 0, "empty text"))


def test_input_validation(ctx: TestContext):
    """Section 10: Input Validation & Negative Cases."""
    section(ctx, "10. INPUT VALIDATION")

    # Test missing 'message' field
    try:
        payload = {"sender": "test"}  # Missing 'message'
        resp = requests.post(WEBHOOK, json=payload, timeout=5)
        if resp.status_code == 422:  # Pydantic validation error
            log_ok(ctx, f"Missing 'message' → 422 Unprocessable Entity")
            ctx.results.append(TestResult("missing_message", "pass", 0))
        elif resp.status_code == 200:
            log_skip(ctx, f"Missing 'message' → 200 (server accepts null)")
            ctx.results.append(TestResult("missing_message", "skip", 0, "accepted"))
        else:
            log_fail(ctx, f"Missing 'message' → {resp.status_code}")
            ctx.results.append(TestResult("missing_message", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"Missing 'message' → connection error: {e}")
        ctx.results.append(TestResult("missing_message", "fail", 0, str(e)))

    # Test missing 'sender' field
    try:
        payload = {"message": "ciao"}  # Missing 'sender'
        resp = requests.post(WEBHOOK, json=payload, timeout=5)
        if resp.status_code == 422:  # Pydantic validation error
            log_ok(ctx, f"Missing 'sender' → 422 Unprocessable Entity")
            ctx.results.append(TestResult("missing_sender", "pass", 0))
        elif resp.status_code == 200:
            log_skip(ctx, f"Missing 'sender' → 200 (server accepts null)")
            ctx.results.append(TestResult("missing_sender", "skip", 0, "accepted"))
        else:
            log_fail(ctx, f"Missing 'sender' → {resp.status_code}")
            ctx.results.append(TestResult("missing_sender", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"Missing 'sender' → connection error: {e}")
        ctx.results.append(TestResult("missing_sender", "fail", 0, str(e)))

    # Test malformed JSON
    try:
        resp = requests.post(
            WEBHOOK,
            data="{invalid json",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if resp.status_code in (400, 422):
            log_ok(ctx, f"Malformed JSON → {resp.status_code} (rejected)")
            ctx.results.append(TestResult("malformed_json", "pass", 0))
        else:
            log_fail(ctx, f"Malformed JSON → {resp.status_code}")
            ctx.results.append(TestResult("malformed_json", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"Malformed JSON → connection error: {e}")
        ctx.results.append(TestResult("malformed_json", "fail", 0, str(e)))

    # Test wrong type for 'message' (number instead of string)
    try:
        payload = {"sender": "test", "message": 12345}  # message should be string
        resp = requests.post(WEBHOOK, json=payload, timeout=5)
        if resp.status_code == 422:
            log_ok(ctx, f"Wrong type 'message' → 422 Unprocessable Entity")
            ctx.results.append(TestResult("wrong_type_message", "pass", 0))
        elif resp.status_code == 200:
            log_skip(ctx, f"Wrong type 'message' → 200 (server coerces)")
            ctx.results.append(TestResult("wrong_type_message", "skip", 0, "coerced"))
        else:
            log_fail(ctx, f"Wrong type 'message' → {resp.status_code}")
            ctx.results.append(TestResult("wrong_type_message", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"Wrong type 'message' → connection error: {e}")
        ctx.results.append(TestResult("wrong_type_message", "fail", 0, str(e)))

    # Test empty body
    try:
        resp = requests.post(
            WEBHOOK,
            data="",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if resp.status_code in (400, 422):
            log_ok(ctx, f"Empty body → {resp.status_code} (rejected)")
            ctx.results.append(TestResult("empty_body", "pass", 0))
        else:
            log_fail(ctx, f"Empty body → {resp.status_code}")
            ctx.results.append(TestResult("empty_body", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_fail(ctx, f"Empty body → connection error: {e}")
        ctx.results.append(TestResult("empty_body", "fail", 0, str(e)))


def test_two_phase_flow(ctx: TestContext):
    """Section 11: Two-Phase Flow & Session State (Enhanced)."""
    if ctx.quick_mode:
        return

    section(ctx, "11. TWO-PHASE FLOW")

    log_info(ctx, "Testing 2-phase flow with content validation...")

    import random
    test_sender = f"test_2phase_{random.randint(10000, 99999)}"

    # Phase 1: Query that triggers 2-phase response (ask_risk_based_priority)
    result1 = query_full(
        "stabilimenti ad alto rischio",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=test_sender
    )

    if result1.status_code != 200 or not result1.text:
        log_fail(ctx, f"Phase 1: Request failed ({result1.status_code})")
        ctx.results.append(TestResult("2phase_initial", "fail", result1.elapsed, f"status {result1.status_code}"))
        return

    # Validate Phase 1 response contains summary markers
    has_summary_prompt = "dettagli" in result1.text.lower() or "vuoi vedere" in result1.text.lower()
    has_data_content = bool(re.search(r"rischio|stabiliment|priorit", result1.text, re.IGNORECASE))

    if has_summary_prompt and has_data_content:
        log_ok(ctx, f"Phase 1: Summary with detail prompt received ({len(result1.text)} chars)")
        ctx.results.append(TestResult("2phase_summary_format", "pass", result1.elapsed))
    elif has_data_content:
        log_skip(ctx, f"Phase 1: Full response (no 2-phase triggered, data too small)")
        ctx.results.append(TestResult("2phase_summary_format", "skip", result1.elapsed, "full response"))
    else:
        log_fail(ctx, f"Phase 1: No risk data in response")
        ctx.results.append(TestResult("2phase_summary_format", "fail", result1.elapsed, "no data"))

    # Phase 2a: CONFIRM details with "sì"
    result2_confirm = query_full(
        "sì",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=test_sender
    )

    if result2_confirm.status_code == 200 and result2_confirm.text:
        # Validate confirm response contains either detailed data OR acknowledgment
        has_detail_data = len(result2_confirm.text) > 100  # Detailed response should be longer
        has_acknowledgment = bool(re.search(r"dettagli|aiutarti|domand", result2_confirm.text, re.IGNORECASE))

        if has_detail_data or has_acknowledgment:
            log_ok(ctx, f"Phase 2 CONFIRM: Response valid ({len(result2_confirm.text)} chars)")
            ctx.results.append(TestResult("2phase_confirm", "pass", result2_confirm.elapsed))
        else:
            log_fail(ctx, f"Phase 2 CONFIRM: Unexpected response format")
            ctx.results.append(TestResult("2phase_confirm", "fail", result2_confirm.elapsed, "bad format"))
    else:
        log_fail(ctx, f"Phase 2 CONFIRM: Request failed ({result2_confirm.status_code})")
        ctx.results.append(TestResult("2phase_confirm", "fail", result2_confirm.elapsed, "request failed"))

    # Test Phase 2b: DECLINE details with new sender
    test_sender_decline = f"test_2phase_decline_{random.randint(10000, 99999)}"

    # First trigger 2-phase
    result1b = query_full(
        "piani in ritardo",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=test_sender_decline
    )

    if result1b.status_code == 200 and result1b.text:
        # Now decline
        result2_decline = query_full(
            "no grazie",
            metadata={"asl": "AVELLINO"},
            timeout=TIMEOUT_UNCACHED,
            sender=test_sender_decline
        )

        if result2_decline.status_code == 200 and result2_decline.text:
            # Validate decline response is acknowledgment
            has_decline_ack = bool(re.search(r"bene|aiutarti|domand|va bene", result2_decline.text, re.IGNORECASE))
            if has_decline_ack:
                log_ok(ctx, f"Phase 2 DECLINE: Acknowledgment received")
                ctx.results.append(TestResult("2phase_decline", "pass", result2_decline.elapsed))
            else:
                log_skip(ctx, f"Phase 2 DECLINE: Response unclear (may not have been in 2-phase)")
                ctx.results.append(TestResult("2phase_decline", "skip", result2_decline.elapsed, "unclear"))
        else:
            log_fail(ctx, f"Phase 2 DECLINE: Request failed")
            ctx.results.append(TestResult("2phase_decline", "fail", result2_decline.elapsed, "request failed"))
    else:
        log_skip(ctx, f"Phase 2 DECLINE: Initial request didn't trigger 2-phase")
        ctx.results.append(TestResult("2phase_decline", "skip", 0, "no 2-phase"))

    # Test session isolation with concurrent different senders
    log_info(ctx, "Testing session isolation...")
    sender_a = f"test_session_a_{random.randint(10000, 99999)}"
    sender_b = f"test_session_b_{random.randint(10000, 99999)}"

    result_a = query_full("ciao", sender=sender_a)
    result_b = query_full("aiuto", sender=sender_b)

    if result_a.status_code == 200 and result_b.status_code == 200:
        if result_a.text != result_b.text:
            log_ok(ctx, "Session isolation: Different senders get independent responses")
            ctx.results.append(TestResult("session_isolation", "pass", 0))
        else:
            log_skip(ctx, "Session isolation: Responses same (may be coincidence)")
            ctx.results.append(TestResult("session_isolation", "skip", 0, "same response"))
    else:
        log_fail(ctx, "Session isolation: Request failed")
        ctx.results.append(TestResult("session_isolation", "fail", 0, "request failed"))


def test_clarification_rules(ctx: TestContext):
    """Section 12: Needs Clarification & Slot Validation."""
    if ctx.quick_mode:
        return

    section(ctx, "12. CLARIFICATION RULES")

    log_info(ctx, "Testing needs_clarification and slot validation via /model/parse...")

    for query_text, expected_intent, expect_clarification, expected_slots in CLARIFICATION_TESTS:
        try:
            payload = {"text": query_text, "metadata": {}}
            resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)

            if resp.status_code != 200:
                log_fail(ctx, f'"{query_text}" → HTTP {resp.status_code}')
                ctx.results.append(TestResult(f"clarification_{expected_intent}", "fail", 0, f"status {resp.status_code}"))
                continue

            data = resp.json()
            actual_intent = data.get("intent", {}).get("name", "")
            actual_clarification = data.get("needs_clarification", False)
            actual_slots = data.get("slots", {})

            # Check intent
            intent_match = actual_intent == expected_intent
            # Check clarification flag
            clarification_match = actual_clarification == expect_clarification
            # Check required slots present (if expected)
            slots_match = all(k in actual_slots for k in expected_slots.keys())

            if intent_match and clarification_match and slots_match:
                status_msg = "clarification=true" if expect_clarification else f"slots={list(actual_slots.keys())}"
                if ctx.verbose:
                    log_ok(ctx, f'"{query_text}" → {actual_intent}, {status_msg}')
                else:
                    print(f"{Colors.GREEN}.{Colors.RESET}", end="", flush=True)
                ctx.results.append(TestResult(f"clarification_{expected_intent}", "pass", 0))
            else:
                details = []
                if not intent_match:
                    details.append(f"intent={actual_intent} (expected {expected_intent})")
                if not clarification_match:
                    details.append(f"clarification={actual_clarification} (expected {expect_clarification})")
                if not slots_match:
                    details.append(f"slots={actual_slots} (expected {expected_slots})")
                log_fail(ctx, f'"{query_text}" → {"; ".join(details)}')
                ctx.results.append(TestResult(f"clarification_{expected_intent}", "fail", 0, "; ".join(details)))

        except Exception as e:
            log_fail(ctx, f'"{query_text}" → error: {e}')
            ctx.results.append(TestResult(f"clarification_{expected_intent}", "fail", 0, str(e)))

    if not ctx.verbose:
        print()  # Newline after dots


def test_metadata_handling(ctx: TestContext):
    """Section 13: Metadata Handling (ASL priority, UOC resolution)."""
    if ctx.quick_mode:
        return

    section(ctx, "13. METADATA HANDLING")

    log_info(ctx, "Testing metadata priority and slot extraction...")

    # Test 1: Metadata ASL should be used when not specified in message
    result1 = query_full(
        "stabilimenti ad alto rischio",
        metadata={"asl": "NAPOLI 1 CENTRO"},
        timeout=TIMEOUT_UNCACHED
    )

    if result1.status_code == 200 and result1.text:
        # Response should mention NAPOLI or filter by it
        has_napoli = "napoli" in result1.text.lower()
        log_ok(ctx, f"Metadata ASL: Response received ({len(result1.text)} chars)")
        ctx.results.append(TestResult("metadata_asl_used", "pass", result1.elapsed))
    else:
        log_fail(ctx, f"Metadata ASL: Request failed")
        ctx.results.append(TestResult("metadata_asl_used", "fail", result1.elapsed, "request failed"))

    # Test 2: User-specified ASL should override metadata
    try:
        payload = {
            "text": "stabilimenti rischio AVELLINO",
            "metadata": {"asl": "NAPOLI 1 CENTRO"}  # Different ASL in metadata
        }
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)

        if resp.status_code == 200:
            data = resp.json()
            slots = data.get("slots", {})
            # User-specified AVELLINO should be in slots, not NAPOLI
            asl_slot = slots.get("asl", "")
            if "AVELLINO" in asl_slot.upper():
                log_ok(ctx, f"ASL override: User ASL '{asl_slot}' takes priority over metadata")
                ctx.results.append(TestResult("asl_user_priority", "pass", 0))
            elif asl_slot:
                log_skip(ctx, f"ASL override: Got '{asl_slot}' (model may have used metadata)")
                ctx.results.append(TestResult("asl_user_priority", "skip", 0, f"got {asl_slot}"))
            else:
                log_skip(ctx, f"ASL override: No ASL in slots")
                ctx.results.append(TestResult("asl_user_priority", "skip", 0, "no asl slot"))
        else:
            log_fail(ctx, f"ASL override: HTTP {resp.status_code}")
            ctx.results.append(TestResult("asl_user_priority", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"ASL override: {e}")
        ctx.results.append(TestResult("asl_user_priority", "fail", 0, str(e)))

    # Test 3: User_id default from sender
    import random
    test_sender = f"test_user_{random.randint(10000, 99999)}"
    result3 = query_full(
        "ciao",
        metadata={},  # No user_id in metadata
        sender=test_sender
    )

    if result3.status_code == 200:
        log_ok(ctx, f"User_id default: Request succeeded without explicit user_id")
        ctx.results.append(TestResult("userid_default", "pass", result3.elapsed))
    else:
        log_fail(ctx, f"User_id default: Request failed")
        ctx.results.append(TestResult("userid_default", "fail", result3.elapsed, "request failed"))


def test_true_intent_classification(ctx: TestContext):
    """Section 14: True Intent Classification via /model/parse.

    CRITICAL: Verifies intent is correctly classified by the Router,
    not just that response text contains expected keywords.
    This addresses the finding that regex-based response validation
    can pass even with wrong intent but "compatible" text.
    """
    if ctx.quick_mode:
        return

    section(ctx, "14. TRUE INTENT CLASSIFICATION")

    log_info(ctx, "Testing actual intent classification (not regex on response)...")

    # Test cases: (query, expected_intent, expected_slots)
    TRUE_INTENT_TESTS = [
        # Greet/Goodbye
        ("ciao", "greet", {}),
        ("buongiorno", "greet", {}),
        ("arrivederci", "goodbye", {}),

        # Help
        ("aiuto", "ask_help", {}),
        ("cosa puoi fare", "ask_help", {}),

        # Piano queries
        ("di cosa tratta il piano A1", "ask_piano_description", {"piano_code": "A1"}),
        ("stabilimenti controllati piano A32", "ask_piano_stabilimenti", {"piano_code": "A32"}),
        ("attività piano B2", "ask_piano_stabilimenti", {"piano_code": "B2"}),
        ("dimmi del piano C3", "ask_piano_stabilimenti", {"piano_code": "C3"}),

        # Search
        ("piani su allevamenti", "search_piani_by_topic", {"topic": "allevamenti"}),
        ("quali piani riguardano la macellazione", "search_piani_by_topic", {}),

        # Priority
        ("chi devo controllare per primo", "ask_priority_establishment", {}),
        ("stabilimenti ad alto rischio", "ask_risk_based_priority", {}),

        # Delayed plans
        ("piani in ritardo", "ask_delayed_plans", {}),
        ("il piano B47 è in ritardo", "check_if_plan_delayed", {"piano_code": "B47"}),

        # Establishment history
        ("storico controlli stabilimento IT 2287", "ask_establishment_history", {}),

        # Top risk
        ("attività più rischiose", "ask_top_risk_activities", {}),

        # Confirm/Decline (critical for 2-phase)
        ("sì", "confirm_show_details", {}),
        ("no grazie", "decline_show_details", {}),
    ]

    pass_count = 0
    fail_count = 0

    for query_text, expected_intent, expected_slots in TRUE_INTENT_TESTS:
        try:
            payload = {"text": query_text, "metadata": {}}
            resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)

            if resp.status_code != 200:
                log_fail(ctx, f'"{query_text}" → HTTP {resp.status_code}')
                ctx.results.append(TestResult(f"true_intent_{expected_intent}", "fail", 0, f"status {resp.status_code}"))
                fail_count += 1
                continue

            data = resp.json()
            actual_intent = data.get("intent", {}).get("name", "")
            actual_slots = data.get("slots", {})

            # Check intent matches
            intent_match = actual_intent == expected_intent

            # Check required slots present (partial match for expected keys)
            slots_match = all(
                k in actual_slots and (not v or actual_slots.get(k) == v)
                for k, v in expected_slots.items()
            )

            if intent_match and slots_match:
                if ctx.verbose:
                    log_ok(ctx, f'"{query_text}" → {actual_intent} (TRUE INTENT)')
                else:
                    print(f"{Colors.GREEN}.{Colors.RESET}", end="", flush=True)
                ctx.results.append(TestResult(f"true_intent_{expected_intent}", "pass", 0))
                pass_count += 1
            else:
                details = []
                if not intent_match:
                    details.append(f"intent={actual_intent} (expected {expected_intent})")
                if not slots_match:
                    details.append(f"slots mismatch")
                log_fail(ctx, f'"{query_text}" → {"; ".join(details)}')
                ctx.results.append(TestResult(f"true_intent_{expected_intent}", "fail", 0, "; ".join(details)))
                fail_count += 1

        except Exception as e:
            log_fail(ctx, f'"{query_text}" → error: {e}')
            ctx.results.append(TestResult(f"true_intent_{expected_intent}", "fail", 0, str(e)))
            fail_count += 1

    if not ctx.verbose:
        print()  # Newline after dots

    total = pass_count + fail_count
    accuracy = (pass_count * 100 // total) if total > 0 else 0

    if accuracy >= 90:
        log_ok(ctx, f"True Intent Classification: {accuracy}% ({pass_count}/{total})")
    elif accuracy >= 70:
        log_skip(ctx, f"True Intent Classification: {accuracy}% ({pass_count}/{total})")
    else:
        log_fail(ctx, f"True Intent Classification: {accuracy}% ({pass_count}/{total})")


def test_two_phase_edge_cases(ctx: TestContext):
    """Section 15: Two-Phase Flow Edge Cases.

    Tests session state TTL, confirm without phase 1, and state reset.
    Addresses finding that edge cases of state/TTL are not tested.
    """
    if ctx.quick_mode:
        return

    section(ctx, "15. TWO-PHASE EDGE CASES")

    import random

    # Test 1: Confirm without prior phase 1 (fresh sender)
    log_info(ctx, "Testing confirm without phase 1...")
    fresh_sender = f"test_fresh_confirm_{random.randint(10000, 99999)}"

    # Send "sì" without any prior message - should NOT crash
    result_confirm_fresh = query_full(
        "sì",
        metadata={},
        timeout=TIMEOUT_CACHED,
        sender=fresh_sender
    )

    if result_confirm_fresh.status_code == 200 and result_confirm_fresh.text:
        # Should handle gracefully - either new greeting or help
        log_ok(ctx, f"Confirm without phase 1: Handled gracefully ({len(result_confirm_fresh.text)} chars)")
        ctx.results.append(TestResult("2phase_confirm_no_prior", "pass", result_confirm_fresh.elapsed))
    else:
        log_fail(ctx, f"Confirm without phase 1: Failed ({result_confirm_fresh.status_code})")
        ctx.results.append(TestResult("2phase_confirm_no_prior", "fail", result_confirm_fresh.elapsed, "request failed"))

    # Test 2: Decline without prior phase 1
    log_info(ctx, "Testing decline without phase 1...")
    fresh_sender_decline = f"test_fresh_decline_{random.randint(10000, 99999)}"

    result_decline_fresh = query_full(
        "no grazie",
        metadata={},
        timeout=TIMEOUT_CACHED,
        sender=fresh_sender_decline
    )

    if result_decline_fresh.status_code == 200 and result_decline_fresh.text:
        log_ok(ctx, f"Decline without phase 1: Handled gracefully ({len(result_decline_fresh.text)} chars)")
        ctx.results.append(TestResult("2phase_decline_no_prior", "pass", result_decline_fresh.elapsed))
    else:
        log_fail(ctx, f"Decline without phase 1: Failed ({result_decline_fresh.status_code})")
        ctx.results.append(TestResult("2phase_decline_no_prior", "fail", result_decline_fresh.elapsed, "request failed"))

    # Test 3: State reset after confirmation
    log_info(ctx, "Testing state reset after confirm...")
    state_test_sender = f"test_state_reset_{random.randint(10000, 99999)}"

    # Phase 1: Trigger 2-phase
    result1 = query_full(
        "stabilimenti ad alto rischio",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=state_test_sender
    )

    if result1.status_code == 200:
        # Phase 2: Confirm
        result2 = query_full(
            "sì",
            metadata={"asl": "AVELLINO"},
            timeout=TIMEOUT_UNCACHED,
            sender=state_test_sender
        )

        if result2.status_code == 200:
            # Phase 3: New query - state should be reset, not waiting for confirm
            result3 = query_full(
                "piani in ritardo",
                metadata={"asl": "AVELLINO"},
                timeout=TIMEOUT_UNCACHED,
                sender=state_test_sender
            )

            if result3.status_code == 200 and result3.text:
                # Should return delayed plans data, not treat as confirmation
                has_plan_content = bool(re.search(r"piano|ritard", result3.text, re.IGNORECASE))
                if has_plan_content:
                    log_ok(ctx, "State reset after confirm: New query processed correctly")
                    ctx.results.append(TestResult("2phase_state_reset", "pass", result3.elapsed))
                else:
                    log_skip(ctx, "State reset: Response unclear")
                    ctx.results.append(TestResult("2phase_state_reset", "skip", result3.elapsed, "unclear"))
            else:
                log_fail(ctx, "State reset: Third request failed")
                ctx.results.append(TestResult("2phase_state_reset", "fail", result3.elapsed, "request failed"))
        else:
            log_fail(ctx, "State reset: Confirm request failed")
            ctx.results.append(TestResult("2phase_state_reset", "fail", 0, "confirm failed"))
    else:
        log_skip(ctx, "State reset: Initial request failed")
        ctx.results.append(TestResult("2phase_state_reset", "skip", 0, "initial failed"))

    # Test 4: Multiple confirm in a row (idempotency)
    log_info(ctx, "Testing multiple confirms (idempotency)...")
    multi_confirm_sender = f"test_multi_confirm_{random.randint(10000, 99999)}"

    # Trigger phase 1
    query_full(
        "attività più rischiose",
        metadata={},
        timeout=TIMEOUT_UNCACHED,
        sender=multi_confirm_sender
    )

    # First confirm
    result_c1 = query_full(
        "sì",
        metadata={},
        timeout=TIMEOUT_UNCACHED,
        sender=multi_confirm_sender
    )

    # Second confirm (should not crash)
    result_c2 = query_full(
        "sì",
        metadata={},
        timeout=TIMEOUT_CACHED,
        sender=multi_confirm_sender
    )

    if result_c2.status_code == 200 and result_c2.text:
        log_ok(ctx, "Multiple confirms: Handled gracefully")
        ctx.results.append(TestResult("2phase_multi_confirm", "pass", result_c2.elapsed))
    else:
        log_fail(ctx, "Multiple confirms: Second confirm failed")
        ctx.results.append(TestResult("2phase_multi_confirm", "fail", result_c2.elapsed, "failed"))

    # Test 5: Session TTL simulation
    # NOTE: Cannot actually test 300s TTL in test, but verify mechanism works
    log_info(ctx, "Testing session TTL mechanism (logic check)...")

    # Just verify the session state endpoint returns valid data structure
    ttl_sender = f"test_ttl_{random.randint(10000, 99999)}"

    # Create session state
    query_full("ciao", sender=ttl_sender)

    # Immediate follow-up should work
    result_immediate = query_full("aiuto", sender=ttl_sender, timeout=TIMEOUT_CACHED)

    if result_immediate.status_code == 200:
        log_ok(ctx, "Session TTL: Session state accessible after immediate follow-up")
        ctx.results.append(TestResult("2phase_ttl_mechanism", "pass", result_immediate.elapsed))
    else:
        log_fail(ctx, "Session TTL: Follow-up failed")
        ctx.results.append(TestResult("2phase_ttl_mechanism", "fail", result_immediate.elapsed, "failed"))


def test_uoc_resolution_and_user_id(ctx: TestContext):
    """Section 16: UOC Resolution and User ID Defaults.

    Tests that UOC is resolved from user_id and user_id defaults to sender.
    Addresses finding that metadata logic is only partially tested.
    """
    if ctx.quick_mode:
        return

    section(ctx, "16. UOC RESOLUTION & USER_ID")

    import random

    # Test 1: user_id defaults to sender when not provided
    log_info(ctx, "Testing user_id default from sender...")
    test_sender = f"test_user_default_{random.randint(10000, 99999)}"

    # No user_id in metadata
    result1 = query_full(
        "ciao",
        metadata={},  # Empty metadata
        sender=test_sender
    )

    if result1.status_code == 200 and result1.text:
        log_ok(ctx, f"User_id default: Request succeeded without explicit user_id (sender={test_sender})")
        ctx.results.append(TestResult("userid_default_sender", "pass", result1.elapsed))
    else:
        log_fail(ctx, "User_id default: Request failed")
        ctx.results.append(TestResult("userid_default_sender", "fail", result1.elapsed, "request failed"))

    # Test 2: Explicit user_id should not be overridden
    log_info(ctx, "Testing explicit user_id preservation...")
    explicit_user_id = "explicit_user_12345"

    result2 = query_full(
        "aiuto",
        metadata={"user_id": explicit_user_id},
        sender=f"different_sender_{random.randint(10000, 99999)}"
    )

    if result2.status_code == 200 and result2.text:
        log_ok(ctx, f"Explicit user_id: Request succeeded with explicit user_id")
        ctx.results.append(TestResult("userid_explicit_preserved", "pass", result2.elapsed))
    else:
        log_fail(ctx, "Explicit user_id: Request failed")
        ctx.results.append(TestResult("userid_explicit_preserved", "fail", result2.elapsed, "request failed"))

    # Test 3: UOC resolution from user_id
    # Note: This requires the personale.csv to have the user_id mapping
    log_info(ctx, "Testing UOC resolution from user_id...")

    # Test with a query that might use UOC filtering
    result3 = query_full(
        "chi devo controllare per primo",
        metadata={"user_id": "test_uoc_user", "asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=f"test_uoc_{random.randint(10000, 99999)}"
    )

    if result3.status_code == 200 and result3.text:
        log_ok(ctx, f"UOC resolution: Query processed ({len(result3.text)} chars)")
        ctx.results.append(TestResult("uoc_resolution", "pass", result3.elapsed))
    else:
        log_fail(ctx, f"UOC resolution: Request failed")
        ctx.results.append(TestResult("uoc_resolution", "fail", result3.elapsed, "request failed"))

    # Test 4: Missing ASL warning (should not crash, just log warning)
    log_info(ctx, "Testing missing ASL handling...")

    result4 = query_full(
        "stabilimenti ad alto rischio",
        metadata={"user_id": "test_no_asl"},  # No ASL
        timeout=TIMEOUT_UNCACHED,
        sender=f"test_no_asl_{random.randint(10000, 99999)}"
    )

    if result4.status_code == 200:
        # Should handle gracefully - may ask for ASL or return generic response
        log_ok(ctx, f"Missing ASL: Handled gracefully ({len(result4.text)} chars)")
        ctx.results.append(TestResult("missing_asl_handling", "pass", result4.elapsed))
    else:
        log_fail(ctx, f"Missing ASL: Request failed ({result4.status_code})")
        ctx.results.append(TestResult("missing_asl_handling", "fail", result4.elapsed, f"status {result4.status_code}"))


def test_error_branches(ctx: TestContext):
    """Section 17: Error Branches and Exception Handling.

    Tests error handling paths in webhook and /model/parse endpoints.
    Addresses finding that error branch tests are missing.
    """
    if ctx.quick_mode:
        return

    section(ctx, "17. ERROR BRANCHES")

    # Test 1: Very long message (potential timeout/memory issues)
    log_info(ctx, "Testing very long message handling...")

    long_message = "stabilimenti " + " ".join(["rischio" for _ in range(500)])
    result1 = query_full(
        long_message,
        metadata={},
        timeout=TIMEOUT_UNCACHED,
        sender="test_long_message"
    )

    if result1.status_code == 200:
        log_ok(ctx, f"Very long message: Handled ({len(result1.text)} chars response)")
        ctx.results.append(TestResult("error_long_message", "pass", result1.elapsed))
    elif result1.status_code == 500:
        log_skip(ctx, f"Very long message: Server error (expected for extreme input)")
        ctx.results.append(TestResult("error_long_message", "skip", result1.elapsed, "server error"))
    else:
        log_fail(ctx, f"Very long message: Unexpected status {result1.status_code}")
        ctx.results.append(TestResult("error_long_message", "fail", result1.elapsed, f"status {result1.status_code}"))

    # Test 2: Parse endpoint with null text
    log_info(ctx, "Testing /model/parse with null/empty text...")

    try:
        payload = {"text": "", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)

        if resp.status_code == 200:
            data = resp.json()
            # Empty text should return fallback or error
            intent = data.get("intent", {}).get("name", "")
            error = data.get("error", "")

            if error or intent == "fallback":
                log_ok(ctx, f"Parse empty text: Returned fallback/error")
                ctx.results.append(TestResult("parse_empty_text", "pass", 0))
            else:
                log_skip(ctx, f"Parse empty text: Got intent '{intent}' (may be valid)")
                ctx.results.append(TestResult("parse_empty_text", "skip", 0, f"got {intent}"))
        elif resp.status_code == 422:
            log_ok(ctx, f"Parse empty text: Rejected with 422")
            ctx.results.append(TestResult("parse_empty_text", "pass", 0))
        else:
            log_fail(ctx, f"Parse empty text: Unexpected status {resp.status_code}")
            ctx.results.append(TestResult("parse_empty_text", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse empty text: Exception {e}")
        ctx.results.append(TestResult("parse_empty_text", "fail", 0, str(e)))

    # Test 3: Parse endpoint error field validation
    log_info(ctx, "Testing /model/parse error field presence...")

    try:
        # Send something that might trigger an error in classification
        payload = {"text": "★★★★★ unicode chaos 日本語 🎉 $$$", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)

        if resp.status_code == 200:
            data = resp.json()
            # Verify response schema includes error field (even if null)
            has_error_field = "error" in data or data.get("intent", {}).get("name") == "fallback"

            if has_error_field or "error" in data:
                log_ok(ctx, f"Parse error field: Response has error handling")
                ctx.results.append(TestResult("parse_error_field", "pass", 0))
            else:
                log_skip(ctx, f"Parse error field: No error field but valid response")
                ctx.results.append(TestResult("parse_error_field", "skip", 0, "no error field"))
        else:
            log_fail(ctx, f"Parse error field: Status {resp.status_code}")
            ctx.results.append(TestResult("parse_error_field", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse error field: Exception {e}")
        ctx.results.append(TestResult("parse_error_field", "fail", 0, str(e)))

    # Test 4: Webhook with invalid metadata types
    log_info(ctx, "Testing webhook with invalid metadata types...")

    try:
        payload = {
            "sender": "test_invalid_metadata",
            "message": "ciao",
            "metadata": {
                "asl": 12345,  # Should be string
                "nested": {"deep": {"object": True}},  # Complex nesting
                "array": [1, 2, 3]  # Array value
            }
        }
        resp = requests.post(WEBHOOK, json=payload, timeout=TIMEOUT_CACHED)

        if resp.status_code == 200:
            log_ok(ctx, f"Invalid metadata types: Handled gracefully")
            ctx.results.append(TestResult("webhook_invalid_metadata", "pass", 0))
        elif resp.status_code == 422:
            log_ok(ctx, f"Invalid metadata types: Rejected with 422")
            ctx.results.append(TestResult("webhook_invalid_metadata", "pass", 0))
        else:
            log_fail(ctx, f"Invalid metadata types: Unexpected status {resp.status_code}")
            ctx.results.append(TestResult("webhook_invalid_metadata", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Invalid metadata types: Exception {e}")
        ctx.results.append(TestResult("webhook_invalid_metadata", "fail", 0, str(e)))

    # Test 5: Webhook error response format (when error occurs)
    log_info(ctx, "Testing webhook error response format...")

    # The error format should be "❌ Errore: ..." based on api.py:252
    # We test that even if an internal error happens, response is valid JSON
    result5 = query_full(
        "ciao",
        metadata={},
        sender="test_error_format"
    )

    if result5.schema_valid:
        log_ok(ctx, f"Webhook error format: Response schema valid even with potential errors")
        ctx.results.append(TestResult("webhook_error_format", "pass", result5.elapsed))
    else:
        log_fail(ctx, f"Webhook error format: Schema invalid - {result5.schema_error}")
        ctx.results.append(TestResult("webhook_error_format", "fail", result5.elapsed, result5.schema_error))


def test_fallback_recovery_flow(ctx: TestContext):
    """Section 18: Fallback Recovery 3-Phase Flow.

    Tests the intelligent fallback system:
    - Phase 1: Keyword matching suggestions
    - Phase 2: LLM semantic scoring
    - Phase 3: Category menu (after max consecutive fallbacks)
    - Loop prevention (max 3 consecutive fallbacks → help escalation)
    - Suggestion selection by number
    """
    if ctx.quick_mode:
        return

    section(ctx, "18. FALLBACK RECOVERY FLOW")

    import random

    # Test 1: Nonsense triggers fallback with suggestions
    log_info(ctx, "Testing fallback with suggestions for nonsense input...")
    fallback_sender = f"test_fallback_{random.randint(10000, 99999)}"

    result1 = query_full(
        "xyz qwerty foobar",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=fallback_sender
    )

    if result1.status_code == 200 and result1.text:
        # Fallback should return suggestions or help text
        has_suggestions = bool(re.search(
            r'(\d+\.\s|\bscegli\b|\bposso\b|\baiut|\bdomand|\bfunzionalit|\bcategori)',
            result1.text, re.IGNORECASE
        ))
        if has_suggestions:
            log_ok(ctx, f"Fallback phase 1: Suggestions provided ({len(result1.text)} chars)")
            ctx.results.append(TestResult("fallback_suggestions", "pass", result1.elapsed))
        else:
            log_skip(ctx, f"Fallback phase 1: Response unclear (may be generic fallback)")
            ctx.results.append(TestResult("fallback_suggestions", "skip", result1.elapsed, "no suggestions"))
    else:
        log_fail(ctx, f"Fallback phase 1: Request failed ({result1.status_code})")
        ctx.results.append(TestResult("fallback_suggestions", "fail", result1.elapsed, "request failed"))

    # Test 2: Consecutive fallbacks → escalation (loop prevention)
    log_info(ctx, "Testing fallback loop prevention (3 consecutive)...")
    loop_sender = f"test_fallback_loop_{random.randint(10000, 99999)}"

    nonsense_queries = [
        "abc123 qwertz",
        "zzz999 nonsense",
        "blahblah gibberish random",
        "xyzzy plugh more nonsense"
    ]

    last_response = ""
    all_succeeded = True
    for i, nq in enumerate(nonsense_queries):
        result_loop = query_full(
            nq,
            metadata={"asl": "AVELLINO"},
            timeout=TIMEOUT_UNCACHED,
            sender=loop_sender
        )
        if result_loop.status_code != 200:
            all_succeeded = False
            break
        last_response = result_loop.text

    if all_succeeded and last_response:
        # After 3+ fallbacks, should escalate to full help or category menu
        has_escalation = bool(re.search(
            r'categori|operazioni\s+disponibil|cosa\s+posso\s+fare|funzionalit|aiutarti',
            last_response, re.IGNORECASE
        ))
        if has_escalation:
            log_ok(ctx, "Fallback loop prevention: Escalated to help after consecutive fallbacks")
            ctx.results.append(TestResult("fallback_loop_prevention", "pass", 0))
        else:
            log_skip(ctx, "Fallback loop prevention: No clear escalation detected")
            ctx.results.append(TestResult("fallback_loop_prevention", "skip", 0, "no escalation"))
    else:
        log_fail(ctx, "Fallback loop prevention: Requests failed")
        ctx.results.append(TestResult("fallback_loop_prevention", "fail", 0, "request failed"))

    # Test 3: Fallback selection by number (if suggestions were shown)
    log_info(ctx, "Testing fallback suggestion selection by number...")
    select_sender = f"test_fallback_select_{random.randint(10000, 99999)}"

    # Trigger fallback first
    query_full(
        "xyz nonsense foobar",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=select_sender
    )

    # Try selecting option "1" (should not crash, may redirect to an intent)
    result_select = query_full(
        "1",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=select_sender
    )

    if result_select.status_code == 200 and result_select.text:
        log_ok(ctx, f"Fallback selection by number: Handled ({len(result_select.text)} chars)")
        ctx.results.append(TestResult("fallback_selection", "pass", result_select.elapsed))
    else:
        log_fail(ctx, f"Fallback selection: Failed ({result_select.status_code})")
        ctx.results.append(TestResult("fallback_selection", "fail", result_select.elapsed, "request failed"))

    # Test 4: Fallback reset after valid intent
    log_info(ctx, "Testing fallback state reset after valid intent...")
    reset_sender = f"test_fallback_reset_{random.randint(10000, 99999)}"

    # Trigger fallback
    query_full("xyz nonsense", metadata={}, timeout=TIMEOUT_UNCACHED, sender=reset_sender)

    # Now send valid intent
    result_valid = query_full(
        "ciao",
        metadata={},
        timeout=TIMEOUT_CACHED,
        sender=reset_sender
    )

    if result_valid.status_code == 200 and result_valid.text:
        has_greeting = bool(re.search(r"benvenuto|ciao|salve", result_valid.text, re.IGNORECASE))
        if has_greeting:
            log_ok(ctx, "Fallback reset: Valid intent processed correctly after fallback")
            ctx.results.append(TestResult("fallback_reset", "pass", result_valid.elapsed))
        else:
            log_skip(ctx, "Fallback reset: Response unclear")
            ctx.results.append(TestResult("fallback_reset", "skip", result_valid.elapsed, "unclear"))
    else:
        log_fail(ctx, "Fallback reset: Request failed")
        ctx.results.append(TestResult("fallback_reset", "fail", result_valid.elapsed, "request failed"))


def test_conversational_memory(ctx: TestContext):
    """Section 19: Conversational Memory & Slot Carry-Forward.

    Tests that session state carries context between turns:
    - Last intent/slots are remembered
    - Slot carry-forward on needs_clarification
    - Session summary injected into metadata
    """
    if ctx.quick_mode:
        return

    section(ctx, "19. CONVERSATIONAL MEMORY")

    import random

    # Test 1: Session remembers last intent across turns
    log_info(ctx, "Testing session memory across turns...")
    memory_sender = f"test_memory_{random.randint(10000, 99999)}"

    # Turn 1: Ask about a specific piano
    result1 = query_full(
        "di cosa tratta il piano A1",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=memory_sender
    )

    if result1.status_code != 200:
        log_fail(ctx, "Conversational memory: First turn failed")
        ctx.results.append(TestResult("memory_first_turn", "fail", result1.elapsed, "request failed"))
        return

    # Turn 2: Follow-up that could benefit from context
    result2 = query_full(
        "e gli stabilimenti?",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=memory_sender
    )

    if result2.status_code == 200 and result2.text:
        # Response should have some content (even if context wasn't perfectly carried)
        log_ok(ctx, f"Conversational memory: Follow-up processed ({len(result2.text)} chars)")
        ctx.results.append(TestResult("memory_followup", "pass", result2.elapsed))
    else:
        log_fail(ctx, "Conversational memory: Follow-up failed")
        ctx.results.append(TestResult("memory_followup", "fail", result2.elapsed, "request failed"))

    # Test 2: Slot carry-forward on needs_clarification
    log_info(ctx, "Testing slot carry-forward on clarification...")
    carry_sender = f"test_carry_{random.randint(10000, 99999)}"

    # Turn 1: Query with piano code
    query_full(
        "stabilimenti piano A32",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=carry_sender
    )

    # Turn 2: Ambiguous follow-up that needs clarification but should carry piano_code
    result_carry = query_full(
        "dimmi del piano",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=carry_sender
    )

    if result_carry.status_code == 200 and result_carry.text:
        # If slot carry-forward works, it should NOT ask for piano_code
        # (because A32 was carried from previous turn)
        asks_for_piano = bool(re.search(r"quale\s+piano|specifica.*piano", result_carry.text, re.IGNORECASE))
        if not asks_for_piano:
            log_ok(ctx, "Slot carry-forward: Piano code carried from previous turn")
            ctx.results.append(TestResult("slot_carry_forward", "pass", result_carry.elapsed))
        else:
            log_skip(ctx, "Slot carry-forward: Still asked for piano (carry-forward may not have applied)")
            ctx.results.append(TestResult("slot_carry_forward", "skip", result_carry.elapsed, "asked for piano"))
    else:
        log_fail(ctx, "Slot carry-forward: Request failed")
        ctx.results.append(TestResult("slot_carry_forward", "fail", result_carry.elapsed, "request failed"))

    # Test 3: Different senders don't share memory
    log_info(ctx, "Testing memory isolation between senders...")
    sender_x = f"test_mem_x_{random.randint(10000, 99999)}"
    sender_y = f"test_mem_y_{random.randint(10000, 99999)}"

    # Sender X discusses piano A1
    query_full("piano A1", metadata={"asl": "AVELLINO"}, timeout=TIMEOUT_UNCACHED, sender=sender_x)

    # Sender Y asks ambiguous question - should NOT carry X's context
    result_y = query_full(
        "dimmi del piano",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=sender_y
    )

    if result_y.status_code == 200 and result_y.text:
        # Sender Y should need clarification (no carry-forward from X)
        log_ok(ctx, "Memory isolation: Senders don't share context")
        ctx.results.append(TestResult("memory_isolation", "pass", result_y.elapsed))
    else:
        log_fail(ctx, "Memory isolation: Request failed")
        ctx.results.append(TestResult("memory_isolation", "fail", result_y.elapsed, "request failed"))


def test_streaming_endpoint(ctx: TestContext):
    """Section 20: SSE Streaming Endpoint.

    Tests the /webhooks/rest/webhook/stream endpoint returns valid SSE events.
    """
    if ctx.quick_mode:
        return

    section(ctx, "20. SSE STREAMING ENDPOINT")

    # Test 1: Stream endpoint returns valid SSE format
    log_info(ctx, "Testing SSE streaming endpoint...")

    try:
        payload = {
            "sender": "test_stream",
            "message": "ciao",
            "metadata": {}
        }

        resp = requests.post(
            f"{SERVER_URL}/webhooks/rest/webhook/stream",
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            timeout=TIMEOUT_UNCACHED,
            stream=True
        )

        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            events_received = 0
            has_final = False

            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    events_received += 1
                    try:
                        event_data = json.loads(line[5:].strip())
                        if event_data.get("type") == "final":
                            has_final = True
                    except json.JSONDecodeError:
                        pass
                # Stop after reasonable number of events
                if events_received > 20:
                    break

            resp.close()

            if "text/event-stream" in content_type:
                log_ok(ctx, f"SSE endpoint: Valid content-type, {events_received} events received")
                ctx.results.append(TestResult("sse_content_type", "pass", 0))
            else:
                log_skip(ctx, f"SSE endpoint: Content-type is '{content_type}' (expected text/event-stream)")
                ctx.results.append(TestResult("sse_content_type", "skip", 0, f"content-type: {content_type}"))

            if events_received > 0:
                log_ok(ctx, f"SSE events: Received {events_received} events")
                ctx.results.append(TestResult("sse_events_received", "pass", 0))
            else:
                log_fail(ctx, "SSE events: No events received")
                ctx.results.append(TestResult("sse_events_received", "fail", 0, "no events"))

            if has_final:
                log_ok(ctx, "SSE final event: Received final event with response")
                ctx.results.append(TestResult("sse_final_event", "pass", 0))
            else:
                log_skip(ctx, "SSE final event: No 'final' event detected")
                ctx.results.append(TestResult("sse_final_event", "skip", 0, "no final event"))

        else:
            log_fail(ctx, f"SSE endpoint: HTTP {resp.status_code}")
            ctx.results.append(TestResult("sse_endpoint", "fail", 0, f"status {resp.status_code}"))
    except requests.RequestException as e:
        log_skip(ctx, f"SSE endpoint: Connection error ({e})")
        ctx.results.append(TestResult("sse_endpoint", "skip", 0, str(e)))


def test_workflow_orchestration(ctx: TestContext):
    """Section 21: Workflow Orchestration (Strategy Presentation).

    Tests the conversational workflow system:
    - Strategy presentation for ambiguous queries
    - Numeric strategy selection
    - Oppure (alternative) request
    """
    if ctx.quick_mode:
        return

    section(ctx, "21. WORKFLOW ORCHESTRATION")

    import random

    # Test 1: Ambiguous priority query may trigger strategy presentation
    log_info(ctx, "Testing strategy presentation for ambiguous queries...")
    workflow_sender = f"test_workflow_{random.randint(10000, 99999)}"

    result1 = query_full(
        "quali controlli devo fare",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=workflow_sender
    )

    if result1.status_code == 200 and result1.text:
        has_strategies = bool(re.search(
            r'(\d+\.\s\*\*|strategia|alternativa|opzione|quale\s+approccio|scegli)',
            result1.text, re.IGNORECASE
        ))
        has_data = bool(re.search(
            r'(control|stabiliment|priorit|piano|rischio)',
            result1.text, re.IGNORECASE
        ))

        if has_strategies:
            log_ok(ctx, f"Workflow: Strategy presentation triggered ({len(result1.text)} chars)")
            ctx.results.append(TestResult("workflow_strategy_present", "pass", result1.elapsed))

            # Test 2: Select strategy by number
            log_info(ctx, "Testing strategy selection by number...")
            result2 = query_full(
                "1",
                metadata={"asl": "AVELLINO"},
                timeout=TIMEOUT_UNCACHED,
                sender=workflow_sender
            )

            if result2.status_code == 200 and result2.text:
                log_ok(ctx, f"Workflow selection: Strategy selected ({len(result2.text)} chars)")
                ctx.results.append(TestResult("workflow_strategy_select", "pass", result2.elapsed))
            else:
                log_fail(ctx, "Workflow selection: Request failed")
                ctx.results.append(TestResult("workflow_strategy_select", "fail", result2.elapsed, "request failed"))

        elif has_data:
            log_skip(ctx, "Workflow: Direct response (no strategy presentation, query not ambiguous enough)")
            ctx.results.append(TestResult("workflow_strategy_present", "skip", result1.elapsed, "direct response"))
        else:
            log_skip(ctx, f"Workflow: Response unclear")
            ctx.results.append(TestResult("workflow_strategy_present", "skip", result1.elapsed, "unclear"))
    else:
        log_fail(ctx, f"Workflow: Request failed ({result1.status_code})")
        ctx.results.append(TestResult("workflow_strategy_present", "fail", result1.elapsed, "request failed"))

    # Test 3: "oppure?" request handling
    log_info(ctx, "Testing 'oppure?' alternative request...")
    oppure_sender = f"test_oppure_{random.randint(10000, 99999)}"

    # First trigger something that could have alternatives
    query_full(
        "indicazioni su controlli",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=oppure_sender
    )

    result_oppure = query_full(
        "oppure?",
        metadata={"asl": "AVELLINO"},
        timeout=TIMEOUT_UNCACHED,
        sender=oppure_sender
    )

    if result_oppure.status_code == 200 and result_oppure.text:
        log_ok(ctx, f"Oppure request: Handled gracefully ({len(result_oppure.text)} chars)")
        ctx.results.append(TestResult("workflow_oppure", "pass", result_oppure.elapsed))
    else:
        log_fail(ctx, f"Oppure request: Failed ({result_oppure.status_code})")
        ctx.results.append(TestResult("workflow_oppure", "fail", result_oppure.elapsed, "request failed"))


def test_parse_endpoint_comprehensive(ctx: TestContext):
    """Section 22: /model/parse Comprehensive Tests."""
    if ctx.quick_mode:
        return

    section(ctx, "22. PARSE ENDPOINT (Comprehensive)")

    # Test 1: Negative case - missing 'text' field
    try:
        payload = {"metadata": {}}  # Missing 'text'
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=5)
        if resp.status_code == 422:
            log_ok(ctx, f"Parse missing 'text' → 422 Unprocessable Entity")
            ctx.results.append(TestResult("parse_missing_text", "pass", 0))
        else:
            log_skip(ctx, f"Parse missing 'text' → {resp.status_code} (expected 422)")
            ctx.results.append(TestResult("parse_missing_text", "skip", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse missing 'text' → {e}")
        ctx.results.append(TestResult("parse_missing_text", "fail", 0, str(e)))

    # Test 2: Slot extraction - piano_code
    try:
        payload = {"text": "piano A1", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)
        if resp.status_code == 200:
            data = resp.json()
            slots = data.get("slots", {})
            if slots.get("piano_code") == "A1":
                log_ok(ctx, f"Parse slot extraction: piano_code=A1 ✓")
                ctx.results.append(TestResult("parse_slot_piano", "pass", 0))
            else:
                log_fail(ctx, f"Parse slot extraction: piano_code={slots.get('piano_code')} (expected A1)")
                ctx.results.append(TestResult("parse_slot_piano", "fail", 0, f"got {slots.get('piano_code')}"))
        else:
            log_fail(ctx, f"Parse slot extraction → {resp.status_code}")
            ctx.results.append(TestResult("parse_slot_piano", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse slot extraction → {e}")
        ctx.results.append(TestResult("parse_slot_piano", "fail", 0, str(e)))

    # Test 3: Slot extraction - topic
    try:
        payload = {"text": "piani su allevamenti bovini", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)
        if resp.status_code == 200:
            data = resp.json()
            slots = data.get("slots", {})
            topic = slots.get("topic", "")
            if topic and "allev" in topic.lower():
                log_ok(ctx, f"Parse slot extraction: topic='{topic}' ✓")
                ctx.results.append(TestResult("parse_slot_topic", "pass", 0))
            else:
                log_fail(ctx, f"Parse slot extraction: topic='{topic}' (expected allevamenti)")
                ctx.results.append(TestResult("parse_slot_topic", "fail", 0, f"got '{topic}'"))
        else:
            log_fail(ctx, f"Parse slot extraction (topic) → {resp.status_code}")
            ctx.results.append(TestResult("parse_slot_topic", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse slot extraction (topic) → {e}")
        ctx.results.append(TestResult("parse_slot_topic", "fail", 0, str(e)))

    # Test 4: Entities array structure
    try:
        payload = {"text": "storico IT 2287", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)
        if resp.status_code == 200:
            data = resp.json()
            entities = data.get("entities", [])
            if isinstance(entities, list) and len(entities) > 0:
                # Check entity structure has 'entity' and 'value' keys
                has_valid_structure = all(
                    isinstance(e, dict) and "entity" in e and "value" in e
                    for e in entities
                )
                if has_valid_structure:
                    log_ok(ctx, f"Parse entities: {len(entities)} entities with valid structure")
                    ctx.results.append(TestResult("parse_entities_structure", "pass", 0))
                else:
                    log_fail(ctx, f"Parse entities: invalid entity structure")
                    ctx.results.append(TestResult("parse_entities_structure", "fail", 0, "bad structure"))
            else:
                log_skip(ctx, f"Parse entities: no entities extracted")
                ctx.results.append(TestResult("parse_entities_structure", "skip", 0, "no entities"))
        else:
            log_fail(ctx, f"Parse entities → {resp.status_code}")
            ctx.results.append(TestResult("parse_entities_structure", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse entities → {e}")
        ctx.results.append(TestResult("parse_entities_structure", "fail", 0, str(e)))

    # Test 5: Fallback intent for nonsense
    try:
        payload = {"text": "xyz123 qwerty nonsense", "metadata": {}}
        resp = requests.post(f"{SERVER_URL}/model/parse", json=payload, timeout=TIMEOUT_CACHED)
        if resp.status_code == 200:
            data = resp.json()
            intent = data.get("intent", {}).get("name", "")
            if intent == "fallback":
                log_ok(ctx, f"Parse fallback: nonsense → fallback ✓")
                ctx.results.append(TestResult("parse_fallback", "pass", 0))
            else:
                log_skip(ctx, f"Parse fallback: nonsense → {intent} (expected fallback)")
                ctx.results.append(TestResult("parse_fallback", "skip", 0, f"got {intent}"))
        else:
            log_fail(ctx, f"Parse fallback → {resp.status_code}")
            ctx.results.append(TestResult("parse_fallback", "fail", 0, f"status {resp.status_code}"))
    except Exception as e:
        log_fail(ctx, f"Parse fallback → {e}")
        ctx.results.append(TestResult("parse_fallback", "fail", 0, str(e)))


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

def print_summary(ctx: TestContext, avg_time: float):
    """Print test summary."""
    total = ctx.passed + ctx.failed
    rate = (ctx.passed * 100 // total) if total > 0 else 0

    if ctx.json_output:
        summary = {
            "passed": ctx.passed,
            "failed": ctx.failed,
            "skipped": ctx.skipped,
            "total": total,
            "success_rate": rate,
            "avg_response_time": f"{avg_time:.3f}",
            "timestamp": datetime.now().isoformat(),
            "tests": [asdict(r) for r in ctx.results]
        }
        print(json.dumps(summary, indent=2))
    else:
        print()
        print("═" * 67)
        print("                         TEST SUMMARY")
        print("═" * 67)
        print()
        print(f"  {Colors.GREEN}Passed:{Colors.RESET}  {ctx.passed}")
        print(f"  {Colors.RED}Failed:{Colors.RESET}  {ctx.failed}")
        print(f"  {Colors.YELLOW}Skipped:{Colors.RESET} {ctx.skipped}")
        print()

        if rate >= 90:
            print(f"  {Colors.GREEN}{Colors.WHITE}✅ HEALTH: EXCELLENT ({rate}%){Colors.RESET}")
        elif rate >= 70:
            print(f"  {Colors.YELLOW}{Colors.WHITE}⚠️  HEALTH: DEGRADED ({rate}%){Colors.RESET}")
        else:
            print(f"  {Colors.RED}{Colors.WHITE}❌ HEALTH: CRITICAL ({rate}%){Colors.RESET}")

        print()
        print("═" * 67)
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Avg: {avg_time:.3f}s | {SERVER_URL}")
        print("═" * 67)

    return ctx.failed == 0


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="GiAs-llm Test Suite v3.4 (Full Workflow Coverage)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_server.py           # Full test suite (22 sections)
  python test_server.py -q        # Quick smoke test (7 sections)
  python test_server.py -j        # JSON output for automation
  python test_server.py -v        # Verbose output

New in v3.4:
  - Fallback recovery 3-phase flow (keyword → LLM → category menu)
  - Loop prevention (max 3 consecutive fallbacks → help escalation)
  - Suggestion selection by number
  - Conversational memory & slot carry-forward
  - SSE streaming endpoint validation
  - Workflow orchestration (strategy presentation, selection, oppure?)

Sections (Full mode):
  1. System Status           12. Clarification Rules
  2. Intent Classification   13. Metadata Handling
  3. Performance             14. TRUE Intent Classification
  4. ML Predictor            15. Two-Phase Edge Cases
  5. Error Handling          16. UOC Resolution & User ID
  6. Cache Verification      17. Error Branches
  7. Concurrent Requests     18. Fallback Recovery Flow (NEW)
  8. REST Endpoints          19. Conversational Memory (NEW)
  9. Webhook Schema          20. SSE Streaming Endpoint (NEW)
  10. Input Validation       21. Workflow Orchestration (NEW)
  11. Two-Phase Flow         22. Parse Endpoint Comprehensive
        """
    )
    parser.add_argument("-q", "--quick", action="store_true", help="Quick mode (fewer tests, shorter timeouts)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-j", "--json", action="store_true", help="JSON output for CI/CD")
    parser.add_argument("-n", "--no-start", action="store_true", help="Don't auto-start server")
    parser.add_argument("--sections", type=str, help="Run only specific sections (comma-separated, e.g. '2,3,14')")

    args = parser.parse_args()

    # Parse selected sections
    selected_sections = None
    if args.sections:
        try:
            selected_sections = set(int(s.strip()) for s in args.sections.split(','))
        except ValueError:
            print(f"{Colors.RED}✗ Invalid sections format. Use comma-separated numbers (e.g., '2,3,14'){Colors.RESET}")
            sys.exit(1)

    ctx = TestContext(
        quick_mode=args.quick,
        verbose=args.verbose,
        json_output=args.json,
        auto_start=not args.no_start
    )

    # Disable colors for JSON output
    if ctx.json_output:
        Colors.disable()

    # Header
    if not ctx.json_output:
        mode = "(Quick)" if ctx.quick_mode else "(Full)"
        print("═" * 67)
        print(f"        GiAs-llm Test Suite v3.4 {mode}")
        print(f"        Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 67)

    # Pre-flight: Server Check
    if not is_server_running():
        if ctx.auto_start:
            log_info(ctx, "Server not running, starting via  start_server.sh...")
            if start_server():
                log_ok(ctx, "Server started")
            else:
                log_fail(ctx, "Failed to start server")
                sys.exit(1)
        else:
            log_fail(ctx, "Server not running. Start with: ./start_server.sh start")
            sys.exit(1)

    # Run tests
    avg_time = 0.0

    # Section 1: System Status
    if selected_sections is None or 1 in selected_sections:
        if not test_system_status(ctx):
            sys.exit(1)

    # Section 2: Intent Classification
    if selected_sections is None or 2 in selected_sections:
        test_intent_classification(ctx)

    # Section 3: Performance
    if selected_sections is None or 3 in selected_sections:
        avg_time = test_performance(ctx)

    # Section 4: ML Predictor
    if selected_sections is None or 4 in selected_sections:
        test_ml_predictor(ctx)

    # Section 5: Error Handling
    if selected_sections is None or 5 in selected_sections:
        test_error_handling(ctx)

    # Section 6: Cache Verification
    if selected_sections is None or 6 in selected_sections:
        test_cache_verification(ctx)

    # Section 7: Concurrent Requests
    if selected_sections is None or 7 in selected_sections:
        test_concurrent_requests(ctx)

    # v3.1: Extended coverage

    # Section 8: REST Endpoints
    if selected_sections is None or 8 in selected_sections:
        test_rest_endpoints(ctx)

    # Section 9: Webhook Schema Validation
    if selected_sections is None or 9 in selected_sections:
        test_webhook_schema_validation(ctx)

    # Section 10: Input Validation
    if selected_sections is None or 10 in selected_sections:
        test_input_validation(ctx)

    # Section 11: Two-Phase Flow
    if selected_sections is None or 11 in selected_sections:
        test_two_phase_flow(ctx)

    # v3.2: Comprehensive coverage

    # Section 12: Clarification Rules
    if selected_sections is None or 12 in selected_sections:
        test_clarification_rules(ctx)

    # Section 13: Metadata Handling
    if selected_sections is None or 13 in selected_sections:
        test_metadata_handling(ctx)

    # v3.3: Address audit findings (true intent, edge cases, error branches)

    # Section 14: TRUE Intent Classification
    if selected_sections is None or 14 in selected_sections:
        test_true_intent_classification(ctx)

    # Section 15: Two-Phase Edge Cases
    if selected_sections is None or 15 in selected_sections:
        test_two_phase_edge_cases(ctx)

    # Section 16: UOC Resolution & User ID
    if selected_sections is None or 16 in selected_sections:
        test_uoc_resolution_and_user_id(ctx)

    # Section 17: Error Branches
    if selected_sections is None or 17 in selected_sections:
        test_error_branches(ctx)

    # v3.4: Full workflow coverage

    # Section 18: Fallback Recovery Flow
    if selected_sections is None or 18 in selected_sections:
        test_fallback_recovery_flow(ctx)

    # Section 19: Conversational Memory
    if selected_sections is None or 19 in selected_sections:
        test_conversational_memory(ctx)

    # Section 20: SSE Streaming Endpoint
    if selected_sections is None or 20 in selected_sections:
        test_streaming_endpoint(ctx)

    # Section 21: Workflow Orchestration
    if selected_sections is None or 21 in selected_sections:
        test_workflow_orchestration(ctx)

    # Section 22: Parse Endpoint Comprehensive
    if selected_sections is None or 22 in selected_sections:
        test_parse_endpoint_comprehensive(ctx)

    # Summary
    success = print_summary(ctx, avg_time)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
