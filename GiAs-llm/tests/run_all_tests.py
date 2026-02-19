#!/usr/bin/env python3
"""
GiAs-llm Test Suite Runner v5.0

Esegue tutti i test E2E e integrazione, genera report completo.

Usage:
    python run_all_tests.py                    # Esegue tutti i test
    python run_all_tests.py --quick            # Solo test veloci
    python run_all_tests.py --report json      # Salva report JSON
    python run_all_tests.py --report html      # Salva report HTML
    python run_all_tests.py --report both      # Salva entrambi i report
    python run_all_tests.py --parallel 4       # 4 worker paralleli
    python run_all_tests.py --verbose          # Output dettagliato
    python run_all_tests.py --suite e2e        # Solo test E2E
    python run_all_tests.py --suite integration # Solo test integrazione
    python run_all_tests.py --suite unit       # Solo test unitari
"""

import argparse
import ast
import json
import subprocess
import sys
import time
import socket
import platform
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os

try:
    import requests
except ImportError:
    print("ERROR: requests non installato. Esegui: pip install requests")
    sys.exit(1)

# ===================================================================
# Configuration
# ===================================================================

PROJECT_ROOT = Path(__file__).parent.parent
TEST_DIR = PROJECT_ROOT / "tests"
REPORT_DIR = PROJECT_ROOT / "runtime" / "test_reports"

SERVER_URL = os.environ.get("GIAS_SERVER_URL", "http://localhost:5005")

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


# ===================================================================
# Environment Info
# ===================================================================

def get_environment_info() -> Dict:
    """Raccoglie informazioni sull'ambiente di esecuzione."""
    env_info = {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "working_directory": str(PROJECT_ROOT),
        "test_directory": str(TEST_DIR),
        "execution_time": datetime.now().isoformat(),
        "timezone": time.strftime("%Z"),
    }

    # Ottieni IP locale
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        env_info["ip_address"] = s.getsockname()[0]
        s.close()
    except Exception:
        env_info["ip_address"] = "127.0.0.1"

    # Ottieni info LLM dalla configurazione
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from configs.config import AppConfig, ModelConfig, LLMBackendConfig
        env_info["llm_model"] = AppConfig.get_model_name()
        env_info["llm_model_key"] = AppConfig.LLM_MODEL
        env_info["llm_backend"] = LLMBackendConfig.get_backend_type()
        model_info = AppConfig.get_model_info()
        env_info["llm_description"] = model_info.get("description", "N/A")
    except Exception as e:
        env_info["llm_model"] = f"Error: {e}"
        env_info["llm_backend"] = "unknown"

    # User info
    env_info["user"] = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    return env_info


# ===================================================================
# Data Classes
# ===================================================================

@dataclass
class TestResult:
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    timestamp: str = ""
    query: str = ""           # Domanda/input del test
    expected_intent: str = "" # Intent atteso
    message: str = ""
    traceback: str = ""


@dataclass
class TestSuite:
    name: str
    path: str
    tests: List[TestResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    start_time: str = ""
    end_time: str = ""


@dataclass
class TestReport:
    timestamp: str
    server_url: str
    server_status: str
    server_version: str
    environment: Dict = field(default_factory=dict)
    suites: List[TestSuite] = field(default_factory=list)
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    total_duration: float = 0.0

    def to_dict(self):
        return asdict(self)


# ===================================================================
# Server Check
# ===================================================================

def check_server() -> tuple:
    """Verifica stato server. Ritorna (ok, status, version)."""
    try:
        resp = requests.get(f"{SERVER_URL}/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            version = data.get('version', 'unknown')
            status = data.get('status', 'ok')
            return True, status, version
        return False, f"HTTP {resp.status_code}", "unknown"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused", "unknown"
    except Exception as e:
        return False, str(e), "unknown"


def detect_server_llm_config() -> Dict:
    """
    Rileva modello e backend LLM dal server in esecuzione via /status.
    Propaga le env var GIAS_LLM_MODEL e GIAS_LLM_BACKEND cosi' che
    i test integration che istanziano LLMClient() direttamente usino
    lo stesso modello del server.

    Returns:
        Dict con llm_model, llm_model_key, llm_backend, llm_mode
    """
    result = {
        "llm_model": "unknown",
        "llm_model_key": "",
        "llm_backend": "",
        "llm_mode": "unknown"
    }

    try:
        resp = requests.get(f"{SERVER_URL}/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["llm_model"] = data.get("llm", "unknown")
            result["llm_model_key"] = data.get("llm_model_key", "")
            result["llm_backend"] = data.get("llm_backend", "")

            # Estrai mode (real/stub) dal campo llm: "model_name (real)"
            llm_str = data.get("llm", "")
            if "(real)" in llm_str:
                result["llm_mode"] = "real"
            elif "(stub)" in llm_str:
                result["llm_mode"] = "stub"

            # Propaga env var per allineare i test integration al server
            if result["llm_model_key"]:
                os.environ["GIAS_LLM_MODEL"] = result["llm_model_key"]
            if result["llm_backend"]:
                os.environ["GIAS_LLM_BACKEND"] = result["llm_backend"]

    except Exception as e:
        print(f"{Colors.YELLOW}Warning: impossibile rilevare config LLM dal server: {e}{Colors.RESET}")

    return result


def start_server() -> bool:
    """Tenta di avviare il server."""
    print(f"{Colors.YELLOW}Avvio server...{Colors.RESET}")
    script = PROJECT_ROOT / "scripts" / "server.sh"
    if not script.exists():
        print(f"{Colors.RED}Script server.sh non trovato{Colors.RESET}")
        return False

    try:
        subprocess.run([str(script), "start"], cwd=str(PROJECT_ROOT), check=True,
                      capture_output=True, timeout=30)
        # Attendi che il server sia pronto
        for _ in range(10):
            time.sleep(1)
            ok, _, _ = check_server()
            if ok:
                return True
        return False
    except Exception as e:
        print(f"{Colors.RED}Errore avvio server: {e}{Colors.RESET}")
        return False


# ===================================================================
# Test Metadata Extraction (from source files)
# ===================================================================

class TestMetadataExtractor:
    """Estrae query e intent atteso dai file di test Python usando AST."""

    _cache: Dict[str, Dict[str, Tuple[str, str]]] = {}

    @classmethod
    def extract_from_file(cls, file_path: Path) -> Dict[str, Tuple[str, str]]:
        """
        Estrae metadata da un file di test.

        Returns:
            Dict[test_name, (query, expected_intent)]
        """
        cache_key = str(file_path)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        result = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_name = node.name
                    query, expected_intent = cls._extract_from_function(node, source)
                    if query or expected_intent:
                        result[test_name] = (query, expected_intent)

        except Exception as e:
            pass  # Silently fail, will use fallback

        cls._cache[cache_key] = result
        return result

    @classmethod
    def _extract_from_function(cls, func_node: ast.FunctionDef, source: str) -> Tuple[str, str]:
        """Estrae query e intent da una funzione di test."""
        query = ""
        expected_intent = ""

        for node in ast.walk(func_node):
            # Cerca chiamate a router.classify("..."), api_client("..."), etc.
            if isinstance(node, ast.Call):
                # Estrai primo argomento stringa (query)
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    func_name = cls._get_call_name(node)
                    if func_name in ('classify', 'api_client', 'call'):
                        query = node.args[0].value

            # Cerca assert result["intent"] == "..."
            if isinstance(node, ast.Compare):
                left = node.left
                if isinstance(left, ast.Subscript):
                    if isinstance(left.slice, ast.Constant) and left.slice.value == "intent":
                        if node.comparators and isinstance(node.comparators[0], ast.Constant):
                            expected_intent = node.comparators[0].value
                        # Gestisci assert in ["intent1", "intent2"]
                        elif node.comparators and isinstance(node.comparators[0], ast.List):
                            intents = [e.value for e in node.comparators[0].elts if isinstance(e, ast.Constant)]
                            expected_intent = "|".join(intents)

        return query, expected_intent

    @classmethod
    def _get_call_name(cls, call_node: ast.Call) -> str:
        """Estrae nome funzione da un nodo Call."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return ""

    @classmethod
    def get_test_metadata(cls, file_path: Path, test_name: str) -> Tuple[str, str]:
        """
        Ottiene metadata per un test specifico.

        Returns:
            (query, expected_intent) o ("", "") se non trovato
        """
        # Rimuovi parametri dal nome test: test_foo[param] -> test_foo
        base_name = re.sub(r'\[.*\]', '', test_name)

        metadata = cls.extract_from_file(file_path)
        return metadata.get(base_name, ("", ""))


# ===================================================================
# Test Parsing Helpers
# ===================================================================

def parse_test_params(test_name: str) -> Tuple[str, str]:
    """
    Estrae query e intent atteso dal nome del test parametrizzato.

    Esempio:
        test_intent_response[ciao-greet-patterns0] -> ("ciao", "greet")
        test_classify_piano_with_slot -> ("", "")
    """
    # Pattern per test parametrizzati: test_name[query-intent-...]
    match = re.search(r'\[([^\]]+)\]', test_name)
    if match:
        params = match.group(1)
        parts = params.split('-')
        if len(parts) >= 2:
            # Prima parte è la query, seconda è l'intent
            query = parts[0]
            intent = parts[1]
            # Decodifica caratteri escaped
            query = query.encode().decode('unicode_escape') if '\\x' in query else query
            return query, intent
    return "", ""


# ===================================================================
# Test Execution
# ===================================================================

def run_pytest_suite(suite_path: str, extra_args: List[str] = None,
                     verbose: bool = False) -> TestSuite:
    """Esegue pytest su un path e ritorna risultati."""
    suite_name = Path(suite_path).name
    suite = TestSuite(name=suite_name, path=suite_path)
    suite.start_time = datetime.now().isoformat()

    # Verifica che il path esista
    full_path = TEST_DIR / suite_path
    if not full_path.exists():
        suite.errors = 1
        suite.end_time = datetime.now().isoformat()
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=0,
            timestamp=datetime.now().isoformat(),
            message=f"Path non trovato: {full_path}"
        ))
        return suite

    # Costruisci comando pytest
    # NOTA: Non usare -q insieme a -v, si annullano a vicenda
    args = [
        sys.executable, "-m", "pytest",
        str(full_path),
        "-v",
        "--tb=short",
        "--no-header"
    ]

    if extra_args:
        args.extend(extra_args)

    start = time.time()

    try:
        result = subprocess.run(
            args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300  # 5 minuti max per suite
        )
        suite.duration = time.time() - start
        suite.end_time = datetime.now().isoformat()

        # Parse output pytest
        output = result.stdout + result.stderr

        if verbose:
            print(output)

        # Rimuovi codici ANSI per parsing affidabile
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output)

        # Conta risultati dall'output pulito
        for line in clean_output.split('\n'):
            line_lower = line.lower()

            # Match linee di risultato test
            if '::test_' in line or '::Test' in line:
                test_full_name = line.split(' ')[0].split('::')[-1]
                query, expected_intent = parse_test_params(test_full_name)

                # Fallback: estrai da file sorgente se non trovato nei parametri
                if not query and not expected_intent:
                    query, expected_intent = TestMetadataExtractor.get_test_metadata(
                        full_path, test_full_name
                    )

                test_timestamp = datetime.now().isoformat()

                if 'PASSED' in line:
                    suite.passed += 1
                    suite.tests.append(TestResult(
                        name=test_full_name,
                        status="passed",
                        duration=0,
                        timestamp=test_timestamp,
                        query=query,
                        expected_intent=expected_intent
                    ))
                elif 'FAILED' in line:
                    suite.failed += 1
                    suite.tests.append(TestResult(
                        name=test_full_name,
                        status="failed",
                        duration=0,
                        timestamp=test_timestamp,
                        query=query,
                        expected_intent=expected_intent,
                        message=line
                    ))
                elif 'SKIPPED' in line or 'SKIP' in line:
                    suite.skipped += 1
                    suite.tests.append(TestResult(
                        name=test_full_name,
                        status="skipped",
                        duration=0,
                        timestamp=test_timestamp,
                        query=query,
                        expected_intent=expected_intent
                    ))
                elif 'ERROR' in line:
                    suite.errors += 1
                    suite.tests.append(TestResult(
                        name=test_full_name,
                        status="error",
                        duration=0,
                        timestamp=test_timestamp,
                        query=query,
                        expected_intent=expected_intent,
                        message=line
                    ))

            # Sommario finale (es: "5 passed, 2 failed" oppure "12 passed in 1.47s")
            # Cerca pattern tipo "N passed", "N failed", etc.
            if re.search(r'\d+\s+(passed|failed|skipped|error)', line_lower):
                # Estrai numeri
                matches = re.findall(r'(\d+)\s+(passed|failed|skipped|error)', line_lower)
                for count, status in matches:
                    count = int(count)
                    if status == 'passed':
                        suite.passed = max(suite.passed, count)
                    elif status == 'failed':
                        suite.failed = max(suite.failed, count)
                    elif status == 'skipped':
                        suite.skipped = max(suite.skipped, count)
                    elif status == 'error':
                        suite.errors = max(suite.errors, count)

        # Se nessun test trovato ma pytest è uscito con errore
        if suite.passed == 0 and suite.failed == 0 and result.returncode != 0:
            suite.errors = 1
            suite.tests.append(TestResult(
                name=suite_path,
                status="error",
                duration=suite.duration,
                timestamp=datetime.now().isoformat(),
                message=f"Pytest exit code: {result.returncode}",
                traceback=output[:2000]  # Primi 2000 caratteri
            ))

    except subprocess.TimeoutExpired:
        suite.duration = time.time() - start
        suite.end_time = datetime.now().isoformat()
        suite.errors = 1
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=suite.duration,
            timestamp=datetime.now().isoformat(),
            message="Timeout (>5 minuti)"
        ))
    except Exception as e:
        suite.duration = time.time() - start
        suite.end_time = datetime.now().isoformat()
        suite.errors = 1
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=suite.duration,
            timestamp=datetime.now().isoformat(),
            message=str(e)
        ))

    return suite


def run_all_tests(quick: bool = False, parallel: int = 1,
                  suite_filter: str = None, verbose: bool = False,
                  auto_start: bool = True) -> TestReport:
    """Esegue tutti i test e genera report."""

    # Raccogli info ambiente
    env_info = get_environment_info()

    # Check server
    server_ok, server_status, server_version = check_server()

    report = TestReport(
        timestamp=datetime.now().isoformat(),
        server_url=SERVER_URL,
        server_status=server_status,
        server_version=server_version,
        environment=env_info
    )

    if not server_ok:
        print(f"{Colors.RED}Server non disponibile: {server_status}{Colors.RESET}")

        if auto_start:
            if start_server():
                print(f"{Colors.GREEN}Server avviato con successo{Colors.RESET}")
                server_ok, server_status, server_version = check_server()
                report.server_status = server_status
                report.server_version = server_version
            else:
                print(f"{Colors.RED}Impossibile avviare server{Colors.RESET}")
                print(f"Avvia manualmente con: {Colors.CYAN}scripts/server.sh start{Colors.RESET}")
                return report
        else:
            print(f"Avvia con: {Colors.CYAN}scripts/server.sh start{Colors.RESET}")
            return report

    # Rileva config LLM dal server e allinea env var per test integration
    server_llm = detect_server_llm_config()
    if server_llm["llm_model_key"]:
        env_info["llm_model"] = server_llm["llm_model"]
        env_info["llm_model_key"] = server_llm["llm_model_key"]
        env_info["llm_backend"] = server_llm["llm_backend"]
        env_info["llm_mode"] = server_llm["llm_mode"]

    # Definisci suite di test
    e2e_suites = [
        "e2e/test_api_endpoints.py",
        "e2e/test_api_webhook.py",
        "e2e/test_intents.py",
        "e2e/test_metadata.py",
        "e2e/test_sessions.py",
        "e2e/test_two_phase.py",
        "e2e/test_fallback.py",
    ]

    integration_suites = [
        "integration/test_router_real.py",
        "integration/test_tools_real.py",
        "integration/test_search_real.py",
        "integration/test_rag_consistency.py",
    ]

    unit_suites = [
        "unit/test_llm_providers.py",
    ]

    slow_suites = [
        "e2e/test_streaming.py",
        "integration/test_ml_predictor_real.py",
    ]

    # Filtra suite
    if suite_filter == "e2e":
        test_suites = e2e_suites
    elif suite_filter == "integration":
        test_suites = integration_suites
    elif suite_filter == "unit":
        test_suites = unit_suites
    else:
        test_suites = unit_suites + e2e_suites + integration_suites
        if not quick:
            test_suites.extend(slow_suites)

    # Extra args per pytest
    extra_args = []
    if parallel > 1:
        extra_args.extend(["-n", str(parallel)])
    if quick:
        extra_args.extend(["-m", "not slow"])

    # Print header
    print(f"\n{Colors.WHITE}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}GiAs-llm Test Suite v5.0{Colors.RESET}")
    print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")
    print(f"Server:   {SERVER_URL} ({Colors.GREEN}{server_status}{Colors.RESET})")
    print(f"Version:  {server_version}")
    print(f"Host:     {env_info['hostname']} ({env_info['ip_address']})")
    print(f"LLM:      {env_info.get('llm_model', 'N/A')} (backend: {env_info.get('llm_backend', 'N/A')})")
    print(f"Mode:     {'Quick' if quick else 'Full'}")
    print(f"Parallel: {parallel} workers")
    print(f"Suites:   {len(test_suites)}")
    print(f"{Colors.WHITE}{'='*60}{Colors.RESET}\n")

    # Esegui test
    for suite_path in test_suites:
        full_path = TEST_DIR / suite_path

        if not full_path.exists():
            print(f"{Colors.YELLOW}Skip: {suite_path} (non esiste){Colors.RESET}")
            continue

        print(f"Running: {Colors.CYAN}{suite_path}{Colors.RESET}")
        suite = run_pytest_suite(suite_path, extra_args, verbose)
        report.suites.append(suite)

        # Update totals
        report.total_passed += suite.passed
        report.total_failed += suite.failed
        report.total_skipped += suite.skipped
        report.total_errors += suite.errors
        report.total_duration += suite.duration

        # Print suite summary
        if suite.failed > 0 or suite.errors > 0:
            status = f"{Colors.RED}FAIL{Colors.RESET}"
        elif suite.passed > 0:
            status = f"{Colors.GREEN}PASS{Colors.RESET}"
        else:
            status = f"{Colors.YELLOW}SKIP{Colors.RESET}"

        print(f"  {status} {suite.passed} passed, {suite.failed} failed, "
              f"{suite.skipped} skipped ({suite.duration:.1f}s)")

    return report


# ===================================================================
# Report Generation
# ===================================================================

def print_summary(report: TestReport) -> int:
    """Stampa sommario finale. Ritorna exit code."""
    print(f"\n{Colors.WHITE}{'='*60}{Colors.RESET}")
    print(f"{Colors.WHITE}SUMMARY{Colors.RESET}")
    print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")

    total = report.total_passed + report.total_failed + report.total_skipped + report.total_errors

    print(f"Total:    {total} tests")
    print(f"Passed:   {Colors.GREEN}{report.total_passed}{Colors.RESET}")
    print(f"Failed:   {Colors.RED}{report.total_failed}{Colors.RESET}")
    print(f"Skipped:  {Colors.YELLOW}{report.total_skipped}{Colors.RESET}")
    print(f"Errors:   {Colors.RED}{report.total_errors}{Colors.RESET}")
    print(f"Duration: {report.total_duration:.1f}s")
    print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")

    # Mostra dettagli fallimenti
    if report.total_failed > 0 or report.total_errors > 0:
        print(f"\n{Colors.RED}FAILURES:{Colors.RESET}")
        for suite in report.suites:
            for test in suite.tests:
                if test.status in ("failed", "error"):
                    print(f"  - {test.name}")
                    if test.message:
                        print(f"    {test.message[:200]}")

        print(f"\n{Colors.RED}TEST SUITE FAILED{Colors.RESET}")
        return 1
    else:
        print(f"\n{Colors.GREEN}ALL TESTS PASSED{Colors.RESET}")
        return 0


def save_report(report: TestReport, format: str = "json") -> List[Path]:
    """Salva report su file. Ritorna lista dei path salvati."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_paths = []

    if format in ("json", "both"):
        path = REPORT_DIR / f"test_report_{timestamp}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nReport JSON: {Colors.CYAN}{path}{Colors.RESET}")
        saved_paths.append(path)

    if format in ("html", "both"):
        path = REPORT_DIR / f"test_report_{timestamp}.html"
        html = generate_html_report(report)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Report HTML: {Colors.CYAN}{path}{Colors.RESET}")
        saved_paths.append(path)

    return saved_paths


def generate_html_report(report: TestReport) -> str:
    """Genera report HTML self-contained con dettagli completi."""
    total = report.total_passed + report.total_failed + report.total_skipped + report.total_errors
    pass_rate = (report.total_passed / total * 100) if total > 0 else 0
    env = report.environment

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GiAs-llm Test Report - {report.timestamp[:10]}</title>
    <style>
        :root {{
            --color-pass: #4CAF50;
            --color-fail: #f44336;
            --color-skip: #ff9800;
            --color-bg: #f5f5f5;
            --color-card: #ffffff;
            --color-border: #e0e0e0;
            --color-text: #333333;
            --color-text-secondary: #666666;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        .header-meta {{
            opacity: 0.9;
            font-size: 0.95em;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: var(--color-card);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .card h2 {{
            margin: 0 0 15px 0;
            font-size: 1.1em;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid var(--color-border);
            padding-bottom: 10px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }}
        .stat {{
            text-align: center;
            padding: 15px;
            background: var(--color-bg);
            border-radius: 8px;
        }}
        .stat-value {{
            font-size: 2.2em;
            font-weight: 700;
            line-height: 1;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: var(--color-text-secondary);
            margin-top: 5px;
        }}
        .stat-passed .stat-value {{ color: var(--color-pass); }}
        .stat-failed .stat-value {{ color: var(--color-fail); }}
        .stat-skipped .stat-value {{ color: var(--color-skip); }}
        .env-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}
        .env-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background: var(--color-bg);
            border-radius: 6px;
            font-size: 0.9em;
        }}
        .env-label {{
            color: var(--color-text-secondary);
        }}
        .env-value {{
            font-weight: 500;
            font-family: 'SF Mono', Monaco, monospace;
        }}
        .suite {{
            background: var(--color-card);
            border-radius: 10px;
            margin-bottom: 15px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .suite-header {{
            padding: 15px 20px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }}
        .suite-header:hover {{
            background: var(--color-bg);
        }}
        .suite-passed {{ border-left: 4px solid var(--color-pass); }}
        .suite-failed {{ border-left: 4px solid var(--color-fail); }}
        .suite-stats {{
            display: flex;
            gap: 15px;
            font-size: 0.9em;
        }}
        .suite-body {{
            border-top: 1px solid var(--color-border);
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        .suite.expanded .suite-body {{
            max-height: 5000px;
        }}
        .test-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .test-table th {{
            background: var(--color-bg);
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            color: var(--color-text-secondary);
            position: sticky;
            top: 0;
        }}
        .test-table td {{
            padding: 10px 15px;
            border-bottom: 1px solid var(--color-border);
            vertical-align: top;
        }}
        .test-table tr:last-child td {{
            border-bottom: none;
        }}
        .test-table tr:hover {{
            background: var(--color-bg);
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-passed {{ background: #e8f5e9; color: var(--color-pass); }}
        .status-failed {{ background: #ffebee; color: var(--color-fail); }}
        .status-skipped {{ background: #fff3e0; color: var(--color-skip); }}
        .status-error {{ background: #ffebee; color: var(--color-fail); }}
        .query-text {{
            font-family: 'SF Mono', Monaco, monospace;
            background: var(--color-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .intent-badge {{
            display: inline-block;
            padding: 2px 8px;
            background: #e3f2fd;
            color: #1565c0;
            border-radius: 4px;
            font-size: 0.85em;
            font-family: 'SF Mono', Monaco, monospace;
        }}
        .timestamp {{
            font-size: 0.8em;
            color: var(--color-text-secondary);
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--color-text-secondary);
            font-size: 0.9em;
        }}
        .expand-icon {{
            transition: transform 0.3s;
        }}
        .suite.expanded .expand-icon {{
            transform: rotate(180deg);
        }}
        .progress-bar {{
            height: 8px;
            background: var(--color-border);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 15px;
        }}
        .progress-fill {{
            height: 100%;
            background: var(--color-pass);
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        @media (max-width: 768px) {{
            .cards-grid {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .env-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>GiAs-llm Test Report</h1>
            <div class="header-meta">
                <strong>Timestamp:</strong> {report.timestamp} |
                <strong>Server:</strong> {report.server_url} ({report.server_status}) |
                <strong>Version:</strong> {report.server_version}
            </div>
        </div>

        <div class="cards-grid">
            <div class="card">
                <h2>Test Results</h2>
                <div class="stats-grid">
                    <div class="stat">
                        <div class="stat-value">{total}</div>
                        <div class="stat-label">Total</div>
                    </div>
                    <div class="stat stat-passed">
                        <div class="stat-value">{report.total_passed}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat stat-failed">
                        <div class="stat-value">{report.total_failed}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat stat-skipped">
                        <div class="stat-value">{report.total_skipped}</div>
                        <div class="stat-label">Skipped</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{pass_rate:.1f}%</div>
                        <div class="stat-label">Pass Rate</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{report.total_duration:.0f}s</div>
                        <div class="stat-label">Duration</div>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {pass_rate}%"></div>
                </div>
            </div>

            <div class="card">
                <h2>Environment</h2>
                <div class="env-grid">
                    <div class="env-item">
                        <span class="env-label">Host</span>
                        <span class="env-value">{env.get('hostname', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">IP Address</span>
                        <span class="env-value">{env.get('ip_address', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">Platform</span>
                        <span class="env-value">{env.get('platform', 'N/A')} {env.get('platform_release', '')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">Python</span>
                        <span class="env-value">{env.get('python_version', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">LLM Model</span>
                        <span class="env-value">{env.get('llm_model', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">LLM Backend</span>
                        <span class="env-value">{env.get('llm_backend', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">User</span>
                        <span class="env-value">{env.get('user', 'N/A')}</span>
                    </div>
                    <div class="env-item">
                        <span class="env-label">Timezone</span>
                        <span class="env-value">{env.get('timezone', 'N/A')}</span>
                    </div>
                </div>
            </div>
        </div>

        <h2 style="margin: 30px 0 15px; color: var(--color-text-secondary);">Test Suites ({len(report.suites)})</h2>
"""

    for suite in report.suites:
        suite_class = "suite-passed" if suite.failed == 0 and suite.errors == 0 else "suite-failed"
        html += f"""
        <div class="suite {suite_class}" onclick="this.classList.toggle('expanded')">
            <div class="suite-header">
                <span>{suite.name}</span>
                <div class="suite-stats">
                    <span style="color: var(--color-pass)">{suite.passed} passed</span>
                    <span style="color: var(--color-fail)">{suite.failed} failed</span>
                    <span>{suite.duration:.1f}s</span>
                    <span class="expand-icon">▼</span>
                </div>
            </div>
            <div class="suite-body">
                <table class="test-table">
                    <thead>
                        <tr>
                            <th style="width: 80px">Status</th>
                            <th>Test Name</th>
                            <th>Query</th>
                            <th>Expected Intent</th>
                            <th style="width: 180px">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for test in suite.tests:
            status_class = f"status-{test.status}"
            query_display = f'<span class="query-text">{test.query}</span>' if test.query else '<span style="color: #999">-</span>'
            intent_display = f'<span class="intent-badge">{test.expected_intent}</span>' if test.expected_intent else '<span style="color: #999">-</span>'

            # Pulisci il nome del test (rimuovi parametri per visualizzazione)
            test_name_clean = re.sub(r'\[.*\]', '', test.name)

            html += f"""
                        <tr>
                            <td><span class="status-badge {status_class}">{test.status}</span></td>
                            <td>{test_name_clean}</td>
                            <td>{query_display}</td>
                            <td>{intent_display}</td>
                            <td class="timestamp">{test.timestamp[11:19] if test.timestamp else '-'}</td>
                        </tr>
"""

        html += """
                    </tbody>
                </table>
            </div>
        </div>
"""

    html += f"""
        <div class="footer">
            <p>Generated by GiAs-llm Test Suite v5.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
    return html


# ===================================================================
# Main
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GiAs-llm Test Suite Runner v5.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_all_tests.py                     # Tutti i test
    python run_all_tests.py --quick             # Solo test veloci
    python run_all_tests.py --suite e2e         # Solo test E2E
    python run_all_tests.py --suite unit        # Solo test unitari
    python run_all_tests.py --report json       # Con report JSON
    python run_all_tests.py --report html       # Con report HTML
    python run_all_tests.py --report both       # Entrambi i report
    python run_all_tests.py --verbose           # Output dettagliato
        """
    )
    parser.add_argument("--quick", action="store_true",
                       help="Solo test veloci (esclude @slow)")
    parser.add_argument("--report", choices=["json", "html", "both"],
                       help="Salva report nel formato specificato")
    parser.add_argument("--parallel", type=int, default=1,
                       help="Numero di worker paralleli")
    parser.add_argument("--suite", choices=["e2e", "integration", "unit"],
                       help="Esegui solo suite specifica")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Output dettagliato pytest")
    parser.add_argument("--no-auto-start", action="store_true",
                       help="Non avviare automaticamente il server")
    parser.add_argument("--no-color", action="store_true",
                       help="Disabilita colori output")

    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    report = run_all_tests(
        quick=args.quick,
        parallel=args.parallel,
        suite_filter=args.suite,
        verbose=args.verbose,
        auto_start=not args.no_auto_start
    )

    if args.report:
        save_report(report, args.report)

    exit_code = print_summary(report)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
