#!/usr/bin/env python3
"""
GiAs-llm Model Comparison Tool
Compares performance of two LLM models using the existing test suite.

Usage:
    python compare_models.py --baseline llama3.2 --candidate falcon
    python compare_models.py --config compare_models_quick.json
    python compare_models.py --skip-tests --results-dir runtime/comparison/2026-01-31_18-30
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import shutil


# ═══════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ModelMetrics:
    """Metriche aggregate per un modello"""
    model_name: str
    intent_accuracy: float  # % (0-100)
    avg_response_time: float  # seconds
    slot_extraction_f1: float  # 0-1
    test_pass_rate: float  # % (0-100)
    total_tests: int
    passed: int
    failed: int
    skipped: int
    section_details: Dict[int, Dict[str, Any]]  # {section_num: {passed, failed, ...}}


@dataclass
class ComparisonResult:
    """Risultato della comparazione tra due modelli"""
    baseline: ModelMetrics
    candidate: ModelMetrics
    accuracy_delta: float  # % (candidate - baseline)
    speed_delta: float  # seconds (candidate - baseline, negative = faster)
    f1_delta: float  # (candidate - baseline)
    pass_rate_delta: float  # % (candidate - baseline)
    verdict: str  # "baseline_better" | "candidate_better" | "equivalent"
    recommendation: str
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════
# Model Test Runner
# ═══════════════════════════════════════════════════════════════════════════

class ModelTestRunner:
    """Esegue test suite per un modello specifico"""

    def __init__(self, model_name: str, config: Dict, project_root: Path):
        self.model_name = model_name
        self.config = config
        self.project_root = project_root
        self.server_script = project_root / config['test_config']['server_script']
        self.test_script = project_root / config['test_config']['test_script']

        # Server URL: env var > config > default
        self.server_url = os.environ.get(
            "GIAS_SERVER_URL",
            config['server'].get('gias_server_url', 'http://localhost:5005')
        )

        # Ollama host: env var > config > default
        self.ollama_host = os.environ.get(
            "OLLAMA_HOST",
            config['server'].get('ollama_host', 'localhost')
        )

    def start_server(self) -> bool:
        """Avvia server con modello specifico"""
        print(f"🚀 Avvio server con modello: {self.model_name}")
        print(f"   Ollama host: {self.ollama_host}")
        print(f"   GiAs server: {self.server_url}")

        env = os.environ.copy()
        env['GIAS_LLM_MODEL'] = self.model_name
        env['OLLAMA_HOST'] = self.ollama_host

        # Stop any existing server first
        self._stop_server()
        time.sleep(self.config['server']['shutdown_grace_period'])

        # Start server
        cmd = [str(self.server_script), 'start']
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Errore avvio server: {result.stderr}")
            return False

        # Wait for health check
        return self._wait_for_health()

    def _stop_server(self):
        """Ferma server"""
        cmd = [str(self.server_script), 'stop']
        subprocess.run(cmd, capture_output=True, text=True)

    def _wait_for_health(self) -> bool:
        """Polling health endpoint"""
        max_retries = self.config['server']['health_check_retries']
        interval = self.config['server']['health_check_interval']

        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.server_url}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'ready' and data.get('model_loaded'):
                        print(f"✅ Server pronto (modello: {data.get('llm', 'unknown')})")
                        return True
            except requests.exceptions.RequestException:
                pass

            print(f"⏳ Attendo server... ({attempt + 1}/{max_retries})")
            time.sleep(interval)

        print(f"❌ Timeout: server non disponibile dopo {max_retries * interval}s")
        return False

    def run_tests(self, sections: List[int]) -> Optional[Dict]:
        """Esegue test suite e ritorna risultati JSON"""
        print(f"🧪 Esecuzione test suite (sezioni: {sections})")

        sections_arg = ','.join(str(s) for s in sections)
        cmd = [
            'python3',
            str(self.test_script),
            '--json',
            '--sections', sections_arg
        ]

        if self.config['test_config'].get('verbose'):
            cmd.append('-v')

        # Propaga env vars ai test
        env = os.environ.copy()
        env['GIAS_SERVER_URL'] = self.server_url
        env['OLLAMA_HOST'] = self.ollama_host

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.project_root), env=env)

        if result.returncode != 0:
            print(f"❌ Test falliti (exit code: {result.returncode})")
            print(f"STDERR: {result.stderr}")
            return None

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"❌ Errore parsing JSON: {e}")
            print(f"STDOUT: {result.stdout[:500]}")
            return None

    def stop_server(self):
        """Ferma server"""
        print(f"🛑 Arresto server ({self.model_name})")
        self._stop_server()
        time.sleep(self.config['server']['shutdown_grace_period'])


# ═══════════════════════════════════════════════════════════════════════════
# Model Comparator
# ═══════════════════════════════════════════════════════════════════════════

class ModelComparator:
    """Compara risultati di due modelli"""

    def __init__(self, baseline_name: str, candidate_name: str, config: Dict, project_root: Path):
        self.baseline_name = baseline_name
        self.candidate_name = candidate_name
        self.config = config
        self.project_root = project_root

    def run_comparison(self, skip_tests: bool = False, results_dir: Optional[Path] = None) -> Optional[ComparisonResult]:
        """Esegue test comparativo completo"""

        if skip_tests and results_dir:
            # Carica risultati esistenti
            baseline_results = self._load_results(results_dir / f"{self.baseline_name}_results.json")
            candidate_results = self._load_results(results_dir / f"{self.candidate_name}_results.json")
        else:
            # Esegui test per baseline
            print("\n" + "="*70)
            print(f"BASELINE MODEL: {self.baseline_name}")
            print("="*70 + "\n")

            baseline_runner = ModelTestRunner(self.baseline_name, self.config, self.project_root)
            if not baseline_runner.start_server():
                print("❌ Impossibile avviare server per baseline")
                return None

            baseline_results = baseline_runner.run_tests(self.config['test_sections'])
            baseline_runner.stop_server()

            if not baseline_results:
                print("❌ Nessun risultato per baseline")
                return None

            # Esegui test per candidate
            print("\n" + "="*70)
            print(f"CANDIDATE MODEL: {self.candidate_name}")
            print("="*70 + "\n")

            candidate_runner = ModelTestRunner(self.candidate_name, self.config, self.project_root)
            if not candidate_runner.start_server():
                print("❌ Impossibile avviare server per candidate")
                return None

            candidate_results = candidate_runner.run_tests(self.config['test_sections'])
            candidate_runner.stop_server()

            if not candidate_results:
                print("❌ Nessun risultato per candidate")
                return None

        # Calcola metriche
        baseline_metrics = self._compute_metrics(baseline_results, self.baseline_name)
        candidate_metrics = self._compute_metrics(candidate_results, self.candidate_name)

        # Genera verdetto
        return self._generate_verdict(baseline_metrics, candidate_metrics, baseline_results, candidate_results)

    def _load_results(self, file_path: Path) -> Dict:
        """Carica risultati da file JSON"""
        print(f"📂 Caricamento risultati: {file_path}")
        with open(file_path, 'r') as f:
            return json.load(f)

    def _compute_metrics(self, test_results: Dict, model_name: str) -> ModelMetrics:
        """Estrae metriche da risultati JSON"""

        summary = test_results.get('summary', {})
        sections = test_results.get('sections', {})

        # Intent accuracy (da sezioni 2 e 14)
        intent_accuracy = 0.0
        intent_tests = 0
        intent_passed = 0

        for section_num in [2, 14]:
            section_key = f"section_{section_num}"
            if section_key in sections:
                sec_data = sections[section_key]
                passed = sec_data.get('passed', 0)
                total = sec_data.get('total', 0)
                if total > 0:
                    intent_tests += total
                    intent_passed += passed

        if intent_tests > 0:
            intent_accuracy = (intent_passed / intent_tests) * 100

        # Avg response time (da sezione 3)
        avg_response_time = 0.0
        section_3_key = "section_3"
        if section_3_key in sections:
            avg_response_time = sections[section_3_key].get('avg_time', 0.0)

        # Slot extraction F1 (da sezioni 12 e 22)
        slot_f1 = 0.0
        slot_tests = 0
        slot_passed = 0

        for section_num in [12, 22]:
            section_key = f"section_{section_num}"
            if section_key in sections:
                sec_data = sections[section_key]
                passed = sec_data.get('passed', 0)
                total = sec_data.get('total', 0)
                if total > 0:
                    slot_tests += total
                    slot_passed += passed

        if slot_tests > 0:
            slot_f1 = slot_passed / slot_tests

        # Test pass rate (aggregate)
        passed = summary.get('passed', 0)
        total = summary.get('total', 0)
        test_pass_rate = (passed / total * 100) if total > 0 else 0

        # Section details
        section_details = {}
        for section_key, sec_data in sections.items():
            section_num = int(section_key.split('_')[1])
            section_details[section_num] = {
                'passed': sec_data.get('passed', 0),
                'failed': sec_data.get('failed', 0),
                'skipped': sec_data.get('skipped', 0),
                'total': sec_data.get('total', 0)
            }

        return ModelMetrics(
            model_name=model_name,
            intent_accuracy=intent_accuracy,
            avg_response_time=avg_response_time,
            slot_extraction_f1=slot_f1,
            test_pass_rate=test_pass_rate,
            total_tests=summary.get('total', 0),
            passed=summary.get('passed', 0),
            failed=summary.get('failed', 0),
            skipped=summary.get('skipped', 0),
            section_details=section_details
        )

    def _generate_verdict(self, baseline: ModelMetrics, candidate: ModelMetrics,
                         baseline_results: Dict, candidate_results: Dict) -> ComparisonResult:
        """Determina vincitore e genera raccomandazione"""

        accuracy_delta = candidate.intent_accuracy - baseline.intent_accuracy
        speed_delta = candidate.avg_response_time - baseline.avg_response_time
        f1_delta = candidate.slot_extraction_f1 - baseline.slot_extraction_f1
        pass_rate_delta = candidate.test_pass_rate - baseline.test_pass_rate

        thresholds = self.config['thresholds']

        # Decision tree
        verdict = "equivalent"
        recommendation = ""

        # Caso 1: Candidate significativamente migliore in accuracy
        if accuracy_delta >= thresholds['significant_accuracy_improvement']:
            if speed_delta <= thresholds['acceptable_speed_degradation']:
                verdict = "candidate_better"
                recommendation = (
                    f"✅ Raccomandato {candidate.model_name}: "
                    f"+{accuracy_delta:.1f}% accuracy, "
                    f"speed degradation accettabile (+{speed_delta:.1f}s)"
                )
            else:
                verdict = "candidate_better"
                recommendation = (
                    f"⚠️ {candidate.model_name} ha migliore accuracy (+{accuracy_delta:.1f}%) "
                    f"ma è più lento (+{speed_delta:.1f}s). "
                    f"Valutare trade-off accuracy vs latenza."
                )

        # Caso 2: Candidate peggiore in accuracy
        elif accuracy_delta < thresholds['acceptable_accuracy_delta']:
            verdict = "baseline_better"
            recommendation = (
                f"❌ {baseline.model_name} raccomandato: "
                f"{candidate.model_name} ha accuracy inferiore ({accuracy_delta:.1f}%)"
            )

        # Caso 3: Accuracy simile, baseline più veloce
        elif abs(accuracy_delta) < abs(thresholds['acceptable_accuracy_delta']):
            if speed_delta > thresholds['acceptable_speed_degradation']:
                verdict = "baseline_better"
                recommendation = (
                    f"✅ {baseline.model_name} raccomandato: "
                    f"accuracy simile ma più veloce (-{abs(speed_delta):.1f}s)"
                )
            elif speed_delta < -thresholds['acceptable_speed_degradation']:
                verdict = "candidate_better"
                recommendation = (
                    f"✅ {candidate.model_name} raccomandato: "
                    f"accuracy simile ma più veloce ({abs(speed_delta):.1f}s)"
                )
            else:
                verdict = "equivalent"
                recommendation = (
                    f"⚖️ Modelli equivalenti: "
                    f"accuracy delta {accuracy_delta:.1f}%, "
                    f"speed delta {speed_delta:.1f}s"
                )

        # Caso 4: Considera anche F1 e pass rate
        if verdict == "equivalent":
            if pass_rate_delta >= 2.0:
                verdict = "candidate_better"
                recommendation = (
                    f"✅ {candidate.model_name} raccomandato: "
                    f"+{pass_rate_delta:.1f}% robustness"
                )
            elif pass_rate_delta <= -2.0:
                verdict = "baseline_better"
                recommendation = (
                    f"✅ {baseline.model_name} raccomandato: "
                    f"più robusto (+{abs(pass_rate_delta):.1f}%)"
                )

        return ComparisonResult(
            baseline=baseline,
            candidate=candidate,
            accuracy_delta=accuracy_delta,
            speed_delta=speed_delta,
            f1_delta=f1_delta,
            pass_rate_delta=pass_rate_delta,
            verdict=verdict,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat()
        )

    def generate_markdown_report(self, result: ComparisonResult) -> str:
        """Genera report Markdown leggibile"""

        sections = self.config['test_sections']
        section_desc = self.config.get('description', {})

        # Header
        report = [
            f"# Comparazione Modelli LLM: {result.baseline.model_name} vs {result.candidate.model_name}",
            f"**Data:** {datetime.fromisoformat(result.timestamp).strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Sezioni testate:** {', '.join(str(s) for s in sections)}",
            "",
            "## Riepilogo Esecutivo",
            "",
        ]

        # Verdetto
        winner_emoji = "🏆"
        if result.verdict == "baseline_better":
            winner = result.baseline.model_name
        elif result.verdict == "candidate_better":
            winner = result.candidate.model_name
        else:
            winner = "Nessuno (equivalenti)"
            winner_emoji = "⚖️"

        report.extend([
            f"{winner_emoji} **Vincitore:** {winner}",
            f"📊 **Raccomandazione:** {result.recommendation}",
            "",
            "## Metriche Comparative",
            "",
            "| Metrica | " + result.baseline.model_name + " | " + result.candidate.model_name + " | Delta | Vincitore |",
            "|---------|" + "-" * len(result.baseline.model_name) + "|" + "-" * len(result.candidate.model_name) + "|-------|-----------|",
            f"| **Intent Accuracy** | {result.baseline.intent_accuracy:.1f}% | {result.candidate.intent_accuracy:.1f}% | {result.accuracy_delta:+.1f}% | {self._winner_emoji(result.accuracy_delta, True)} |",
            f"| **Avg Response Time** | {result.baseline.avg_response_time:.2f}s | {result.candidate.avg_response_time:.2f}s | {result.speed_delta:+.2f}s | {self._winner_emoji(result.speed_delta, False)} |",
            f"| **Slot Extraction F1** | {result.baseline.slot_extraction_f1:.3f} | {result.candidate.slot_extraction_f1:.3f} | {result.f1_delta:+.3f} | {self._winner_emoji(result.f1_delta, True)} |",
            f"| **Test Pass Rate** | {result.baseline.test_pass_rate:.1f}% | {result.candidate.test_pass_rate:.1f}% | {result.pass_rate_delta:+.1f}% | {self._winner_emoji(result.pass_rate_delta, True)} |",
            "",
            "## Dettagli per Sezione",
            ""
        ])

        # Per ogni sezione
        for section_num in sections:
            desc = section_desc.get(str(section_num), f"Section {section_num}")

            baseline_sec = result.baseline.section_details.get(section_num, {})
            candidate_sec = result.candidate.section_details.get(section_num, {})

            baseline_total = baseline_sec.get('total', 0)
            baseline_passed = baseline_sec.get('passed', 0)
            candidate_total = candidate_sec.get('total', 0)
            candidate_passed = candidate_sec.get('passed', 0)

            baseline_rate = (baseline_passed / baseline_total * 100) if baseline_total > 0 else 0
            candidate_rate = (candidate_passed / candidate_total * 100) if candidate_total > 0 else 0
            delta = candidate_rate - baseline_rate

            winner_emoji = self._winner_emoji(delta, True)

            report.extend([
                f"### Sezione {section_num}: {desc}",
                f"- {result.baseline.model_name}: {baseline_passed}/{baseline_total} pass ({baseline_rate:.1f}%)",
                f"- {result.candidate.model_name}: {candidate_passed}/{candidate_total} pass ({candidate_rate:.1f}%)",
                f"- **Vincitore:** {winner_emoji} ({delta:+.1f}%)",
                ""
            ])

        # Verdetto finale
        report.extend([
            "## Verdetto Finale",
            "",
            result.recommendation,
            "",
            "---",
            f"Report generato da: `scripts/compare_models.py`"
        ])

        return "\n".join(report)

    def _winner_emoji(self, delta: float, higher_is_better: bool) -> str:
        """Ritorna emoji vincitore basato su delta"""
        threshold = 0.5  # Soglia minima per considerare significativo

        if abs(delta) < threshold:
            return "⚖️ Pari"

        if higher_is_better:
            return "🥇 Candidate" if delta > 0 else "🥇 Baseline"
        else:
            # Per metriche dove lower is better (es. response time)
            return "🥇 Baseline" if delta > 0 else "🥇 Candidate"

    def save_results(self, result: ComparisonResult, baseline_results: Dict,
                    candidate_results: Dict, output_dir: Path):
        """Salva risultati in JSON + Markdown"""

        # Crea directory con timestamp
        timestamp_str = datetime.fromisoformat(result.timestamp).strftime('%Y-%m-%d_%H-%M-%S')
        results_dir = output_dir / timestamp_str
        results_dir.mkdir(parents=True, exist_ok=True)

        # Salva config
        config_file = results_dir / 'config.json'
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

        # Salva risultati raw
        baseline_file = results_dir / f"{result.baseline.model_name}_results.json"
        with open(baseline_file, 'w') as f:
            json.dump(baseline_results, f, indent=2)

        candidate_file = results_dir / f"{result.candidate.model_name}_results.json"
        with open(candidate_file, 'w') as f:
            json.dump(candidate_results, f, indent=2)

        # Salva comparison
        comparison_file = results_dir / 'comparison.json'
        comparison_data = {
            'timestamp': result.timestamp,
            'baseline': asdict(result.baseline),
            'candidate': asdict(result.candidate),
            'deltas': {
                'accuracy': result.accuracy_delta,
                'response_time': result.speed_delta,
                'slot_f1': result.f1_delta,
                'pass_rate': result.pass_rate_delta
            },
            'verdict': result.verdict,
            'recommendation': result.recommendation
        }
        with open(comparison_file, 'w') as f:
            json.dump(comparison_data, f, indent=2)

        # Salva report Markdown
        if self.config['output'].get('save_markdown', True):
            report_file = results_dir / 'report.md'
            with open(report_file, 'w') as f:
                f.write(self.generate_markdown_report(result))

        # Crea symlink 'latest'
        latest_link = output_dir / 'latest'
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(results_dir.name)

        print(f"\n✅ Risultati salvati in: {results_dir}")
        print(f"📄 Report: {report_file}")
        print(f"📊 JSON: {comparison_file}")

        return results_dir


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='GiAs-llm Model Comparison Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test completo con config default
  python compare_models.py --baseline llama3.2 --candidate falcon

  # Quick test (solo sezioni critiche)
  python compare_models.py --config compare_models_quick.json

  # Test con Ollama remoto
  python compare_models.py --ollama-host 192.168.1.100 --baseline llama3.2 --candidate falcon

  # Test con env var
  OLLAMA_HOST=192.168.1.100 python compare_models.py --baseline llama3.2 --candidate falcon

  # Genera report da risultati esistenti
  python compare_models.py --skip-tests --results-dir runtime/comparison/2026-01-31_18-30
        """
    )

    parser.add_argument('--baseline', default='llama3.2', help='Nome modello baseline')
    parser.add_argument('--candidate', default='falcon', help='Nome modello candidate')
    parser.add_argument('--config', type=Path,
                       default=Path(__file__).parent / 'compare_models_config.json',
                       help='File di configurazione JSON')
    parser.add_argument('--output-dir', type=Path,
                       default=None,
                       help='Directory output (default: da config)')
    parser.add_argument('--skip-tests', action='store_true',
                       help='Salta esecuzione test, usa risultati esistenti')
    parser.add_argument('--results-dir', type=Path,
                       help='Directory con risultati esistenti (richiede --skip-tests)')
    parser.add_argument('--ollama-host', type=str,
                       default=None,
                       help='Host Ollama (default: da config o localhost)')
    parser.add_argument('--gias-server-url', type=str,
                       default=None,
                       help='URL server GiAs (default: da config o http://localhost:5005)')

    args = parser.parse_args()

    # Determina project root
    project_root = Path(__file__).parent.parent

    # Carica config
    if not args.config.exists():
        print(f"❌ File config non trovato: {args.config}")
        sys.exit(1)

    with open(args.config, 'r') as f:
        config = json.load(f)

    # Override modelli da args
    config['models']['baseline'] = args.baseline
    config['models']['candidate'] = args.candidate

    # Override server config da args
    if args.ollama_host:
        config['server']['ollama_host'] = args.ollama_host
    if args.gias_server_url:
        config['server']['gias_server_url'] = args.gias_server_url

    # Determina output dir
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = project_root / config['output']['results_dir']

    output_dir.mkdir(parents=True, exist_ok=True)

    # Validazione skip-tests
    if args.skip_tests and not args.results_dir:
        print("❌ --skip-tests richiede --results-dir")
        sys.exit(1)

    # Run comparison
    print("\n" + "="*70)
    print(f"COMPARAZIONE MODELLI LLM")
    print(f"Baseline: {args.baseline}")
    print(f"Candidate: {args.candidate}")
    print(f"Sezioni: {config['test_sections']}")
    print(f"Ollama host: {config['server'].get('ollama_host', 'localhost')}")
    print(f"GiAs server: {config['server'].get('gias_server_url', 'http://localhost:5005')}")
    print("="*70 + "\n")

    comparator = ModelComparator(args.baseline, args.candidate, config, project_root)

    if args.skip_tests:
        # Carica risultati esistenti
        result = comparator.run_comparison(skip_tests=True, results_dir=args.results_dir)
        if not result:
            print("❌ Impossibile caricare risultati esistenti")
            sys.exit(1)

        # Salva report
        baseline_results = comparator._load_results(args.results_dir / f"{args.baseline}_results.json")
        candidate_results = comparator._load_results(args.results_dir / f"{args.candidate}_results.json")
        results_dir = comparator.save_results(result, baseline_results, candidate_results, output_dir)
    else:
        # Esegui test completi
        # Dobbiamo salvare anche i risultati raw, quindi modifichiamo run_comparison
        # per ritornare anche i risultati raw
        print("\n⚠️ NOTA: Assicurarsi che il server Ollama sia attivo con i modelli richiesti!")
        print("Avvio comparazione...")

        # Esegui baseline
        print("\n" + "="*70)
        print(f"BASELINE MODEL: {args.baseline}")
        print("="*70 + "\n")

        baseline_runner = ModelTestRunner(args.baseline, config, project_root)
        if not baseline_runner.start_server():
            print("❌ Impossibile avviare server per baseline")
            sys.exit(1)

        baseline_results = baseline_runner.run_tests(config['test_sections'])
        baseline_runner.stop_server()

        if not baseline_results:
            print("❌ Nessun risultato per baseline")
            sys.exit(1)

        # Esegui candidate
        print("\n" + "="*70)
        print(f"CANDIDATE MODEL: {args.candidate}")
        print("="*70 + "\n")

        candidate_runner = ModelTestRunner(args.candidate, config, project_root)
        if not candidate_runner.start_server():
            print("❌ Impossibile avviare server per candidate")
            sys.exit(1)

        candidate_results = candidate_runner.run_tests(config['test_sections'])
        candidate_runner.stop_server()

        if not candidate_results:
            print("❌ Nessun risultato per candidate")
            sys.exit(1)

        # Calcola metriche
        baseline_metrics = comparator._compute_metrics(baseline_results, args.baseline)
        candidate_metrics = comparator._compute_metrics(candidate_results, args.candidate)

        # Genera verdetto
        result = comparator._generate_verdict(baseline_metrics, candidate_metrics, baseline_results, candidate_results)

        # Salva risultati
        results_dir = comparator.save_results(result, baseline_results, candidate_results, output_dir)

    # Print summary
    print("\n" + "="*70)
    print("RIEPILOGO COMPARAZIONE")
    print("="*70)
    print(f"\n{comparator.generate_markdown_report(result)}\n")

    sys.exit(0)


if __name__ == '__main__':
    main()
