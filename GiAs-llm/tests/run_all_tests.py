#!/usr/bin/env python3
"""
GiAs-llm Test Suite Runner v4.0

Esegue tutti i test E2E e integrazione, genera report completo.

Usage:
    python run_all_tests.py                    # Esegue tutti i test
    python run_all_tests.py --quick            # Solo test veloci
    python run_all_tests.py --report json      # Salva report JSON
    python run_all_tests.py --report html      # Salva report HTML
    python run_all_tests.py --parallel 4       # 4 worker paralleli
    python run_all_tests.py --verbose          # Output dettagliato
    python run_all_tests.py --suite e2e        # Solo test E2E
    python run_all_tests.py --suite integration # Solo test integrazione
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
# Data Classes
# ===================================================================

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
    path: str
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
    server_version: str
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
# Test Execution
# ===================================================================

def run_pytest_suite(suite_path: str, extra_args: List[str] = None,
                     verbose: bool = False) -> TestSuite:
    """Esegue pytest su un path e ritorna risultati."""
    suite_name = Path(suite_path).name
    suite = TestSuite(name=suite_name, path=suite_path)

    # Verifica che il path esista
    full_path = TEST_DIR / suite_path
    if not full_path.exists():
        suite.errors = 1
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=0,
            message=f"Path non trovato: {full_path}"
        ))
        return suite

    # Costruisci comando pytest
    args = [
        sys.executable, "-m", "pytest",
        str(full_path),
        "-v",
        "--tb=short",
        "-q",
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

        # Parse output pytest
        output = result.stdout + result.stderr

        if verbose:
            print(output)

        # Rimuovi codici ANSI per parsing affidabile
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output)

        # Conta risultati dall'output pulito
        for line in clean_output.split('\n'):
            line_lower = line.lower()

            # Match linee di risultato test
            if '::test_' in line or '::Test' in line:
                if 'PASSED' in line:
                    suite.passed += 1
                    suite.tests.append(TestResult(
                        name=line.split(' ')[0].split('::')[-1],
                        status="passed",
                        duration=0
                    ))
                elif 'FAILED' in line:
                    suite.failed += 1
                    suite.tests.append(TestResult(
                        name=line.split(' ')[0].split('::')[-1],
                        status="failed",
                        duration=0,
                        message=line
                    ))
                elif 'SKIPPED' in line or 'SKIP' in line:
                    suite.skipped += 1
                    suite.tests.append(TestResult(
                        name=line.split(' ')[0].split('::')[-1],
                        status="skipped",
                        duration=0
                    ))
                elif 'ERROR' in line:
                    suite.errors += 1
                    suite.tests.append(TestResult(
                        name=line.split(' ')[0].split('::')[-1],
                        status="error",
                        duration=0,
                        message=line
                    ))

            # Sommario finale (es: "5 passed, 2 failed")
            if 'passed' in line_lower and ('failed' in line_lower or 'error' in line_lower or 'skipped' in line_lower):
                # Estrai numeri
                import re
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
                message=f"Pytest exit code: {result.returncode}",
                traceback=output[:2000]  # Primi 2000 caratteri
            ))

    except subprocess.TimeoutExpired:
        suite.duration = time.time() - start
        suite.errors = 1
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=suite.duration,
            message="Timeout (>5 minuti)"
        ))
    except Exception as e:
        suite.duration = time.time() - start
        suite.errors = 1
        suite.tests.append(TestResult(
            name=suite_path,
            status="error",
            duration=suite.duration,
            message=str(e)
        ))

    return suite


def run_all_tests(quick: bool = False, parallel: int = 1,
                  suite_filter: str = None, verbose: bool = False,
                  auto_start: bool = True) -> TestReport:
    """Esegue tutti i test e genera report."""

    # Check server
    server_ok, server_status, server_version = check_server()

    report = TestReport(
        timestamp=datetime.now().isoformat(),
        server_url=SERVER_URL,
        server_status=server_status,
        server_version=server_version
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
    else:
        test_suites = e2e_suites + integration_suites
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
    print(f"{Colors.CYAN}GiAs-llm Test Suite v4.0{Colors.RESET}")
    print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")
    print(f"Server:   {SERVER_URL} ({Colors.GREEN}{server_status}{Colors.RESET})")
    print(f"Version:  {server_version}")
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


def save_report(report: TestReport, format: str = "json") -> Path:
    """Salva report su file."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        path = REPORT_DIR / f"test_report_{timestamp}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    elif format == "html":
        path = REPORT_DIR / f"test_report_{timestamp}.html"
        html = generate_html_report(report)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

    print(f"\nReport salvato: {Colors.CYAN}{path}{Colors.RESET}")
    return path


def generate_html_report(report: TestReport) -> str:
    """Genera report HTML."""
    total = report.total_passed + report.total_failed + report.total_skipped + report.total_errors
    pass_rate = (report.total_passed / total * 100) if total > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>GiAs-llm Test Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat {{ background: #f9f9f9; padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; }}
        .passed {{ color: #4CAF50; }}
        .failed {{ color: #f44336; }}
        .skipped {{ color: #ff9800; }}
        .suite {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 8px; }}
        .suite-header {{ background: #f5f5f5; padding: 10px 15px; font-weight: bold; border-radius: 8px 8px 0 0; }}
        .suite-body {{ padding: 15px; }}
        .test {{ padding: 5px 0; border-bottom: 1px solid #eee; }}
        .test:last-child {{ border-bottom: none; }}
        .test-passed {{ color: #4CAF50; }}
        .test-failed {{ color: #f44336; }}
        .test-skipped {{ color: #ff9800; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GiAs-llm Test Report</h1>
        <div class="meta">
            <p>Timestamp: {report.timestamp}</p>
            <p>Server: {report.server_url} ({report.server_status})</p>
            <p>Version: {report.server_version}</p>
        </div>

        <div class="summary">
            <div class="stat">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value passed">{report.total_passed}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value failed">{report.total_failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value skipped">{report.total_skipped}</div>
                <div class="stat-label">Skipped</div>
            </div>
            <div class="stat">
                <div class="stat-value">{pass_rate:.1f}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
            <div class="stat">
                <div class="stat-value">{report.total_duration:.1f}s</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>
"""

    for suite in report.suites:
        suite_status = "passed" if suite.failed == 0 and suite.errors == 0 else "failed"
        html += f"""
        <div class="suite">
            <div class="suite-header {suite_status}">
                {suite.name} - {suite.passed} passed, {suite.failed} failed ({suite.duration:.1f}s)
            </div>
            <div class="suite-body">
"""
        for test in suite.tests:
            html += f'<div class="test test-{test.status}">{test.name}</div>\n'

        html += """
            </div>
        </div>
"""

    html += """
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
        description="GiAs-llm Test Suite Runner v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_all_tests.py                     # Tutti i test
    python run_all_tests.py --quick             # Solo test veloci
    python run_all_tests.py --suite e2e         # Solo test E2E
    python run_all_tests.py --report json       # Con report JSON
    python run_all_tests.py --verbose           # Output dettagliato
        """
    )
    parser.add_argument("--quick", action="store_true",
                       help="Solo test veloci (esclude @slow)")
    parser.add_argument("--report", choices=["json", "html"],
                       help="Salva report nel formato specificato")
    parser.add_argument("--parallel", type=int, default=1,
                       help="Numero di worker paralleli")
    parser.add_argument("--suite", choices=["e2e", "integration"],
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
