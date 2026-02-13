#!/usr/bin/env python3
"""
GiAs-llm Backend Comparison Tool
=================================

Confronta performance e accuratezza tra Ollama e Llama.cpp
su tutti gli intent principali del sistema.

Usage:
    python3 compare_llm_backends.py
    python3 compare_llm_backends.py --iterations 5 --output report.json
"""

import sys
import os
import time
import json
import argparse
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import statistics

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.router import Router
from llm.client import LLMClient
from configs.config import LLMBackendConfig, AppConfig


@dataclass
class TestCase:
    """Caso di test per un intent specifico"""
    intent: str
    message: str
    expected_slots: Dict[str, Any]
    category: str  # "simple", "medium", "complex"


@dataclass
class TestResult:
    """Risultato di un singolo test"""
    backend: str
    intent: str
    message: str
    expected_intent: str
    predicted_intent: str
    correct: bool
    response_time_ms: float
    slots_extracted: Dict[str, Any]
    needs_clarification: bool
    error: str = None


@dataclass
class BackendStats:
    """Statistiche aggregate per un backend"""
    backend: str
    total_tests: int
    correct: int
    incorrect: int
    accuracy: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    std_response_time_ms: float
    errors: int


# Test cases organizzati per categoria
TEST_CASES = [
    # ========== SALUTI E AIUTO ==========
    TestCase("greet", "ciao", {}, "simple"),
    TestCase("greet", "buongiorno", {}, "simple"),
    TestCase("greet", "salve", {}, "simple"),
    TestCase("goodbye", "arrivederci", {}, "simple"),
    TestCase("goodbye", "bye", {}, "simple"),
    TestCase("ask_help", "aiuto", {}, "simple"),
    TestCase("ask_help", "cosa puoi fare?", {}, "simple"),
    TestCase("ask_help", "quali domande posso fare?", {}, "simple"),

    # ========== PIANI - DESCRIZIONE ==========
    TestCase("ask_piano_description", "di cosa tratta il piano A1?", {"piano_code": "A1"}, "medium"),
    TestCase("ask_piano_description", "descrizione piano B2", {"piano_code": "B2"}, "medium"),
    TestCase("ask_piano_description", "cosa prevede il piano C3?", {"piano_code": "C3"}, "medium"),

    # ========== PIANI - STABILIMENTI ==========
    TestCase("ask_piano_stabilimenti", "stabilimenti controllati dal piano A1", {"piano_code": "A1"}, "medium"),
    TestCase("ask_piano_stabilimenti", "quali OSA per il piano B2?", {"piano_code": "B2"}, "medium"),
    TestCase("ask_piano_stabilimenti", "dove è stato applicato il piano A1?", {"piano_code": "A1"}, "complex"),

    # ========== PIANI - GENERIC (mappati a ask_piano_stabilimenti) ==========
    TestCase("ask_piano_stabilimenti", "piano A1", {"piano_code": "A1"}, "medium"),
    TestCase("ask_piano_stabilimenti", "dimmi del piano B2", {"piano_code": "B2"}, "medium"),
    TestCase("ask_piano_stabilimenti", "attività del piano C3", {"piano_code": "C3"}, "medium"),

    # ========== PIANI - STATISTICHE ==========
    TestCase("ask_piano_statistics", "quale piano è più frequente?", {}, "medium"),
    TestCase("ask_piano_statistics", "statistiche piani", {}, "medium"),
    TestCase("ask_piano_statistics", "piani più usati", {}, "medium"),

    # ========== RICERCA PIANI ==========
    TestCase("search_piani_by_topic", "piani su latte", {"topic": "latte"}, "medium"),
    TestCase("search_piani_by_topic", "cerca piani riguardanti bovini", {"topic": "bovini"}, "complex"),
    TestCase("search_piani_by_topic", "piani per mangimi", {"topic": "mangimi"}, "medium"),

    # ========== PRIORITÀ ==========
    TestCase("ask_priority_establishment", "chi devo controllare per primo?", {}, "medium"),
    TestCase("ask_priority_establishment", "quali stabilimenti controllare?", {}, "medium"),
    TestCase("ask_priority_establishment", "priorità controlli", {}, "medium"),

    # ========== RISCHIO ==========
    TestCase("ask_risk_based_priority", "stabilimenti a rischio", {}, "medium"),
    TestCase("ask_risk_based_priority", "stabilimenti più rischiosi", {}, "medium"),
    TestCase("ask_risk_based_priority", "OSA ad alto rischio", {}, "complex"),
    TestCase("ask_top_risk_activities", "attività più rischiose", {}, "medium"),
    TestCase("ask_top_risk_activities", "classifica attività per rischio", {}, "complex"),
    TestCase("ask_top_risk_activities", "top 10 attività a rischio", {}, "complex"),

    # ========== STABILIMENTI MAI CONTROLLATI ==========
    TestCase("ask_suggest_controls", "stabilimenti mai controllati", {}, "medium"),
    TestCase("ask_suggest_controls", "mai stati controllati", {}, "medium"),
    TestCase("ask_suggest_controls", "OSA non controllati", {}, "medium"),

    # ========== PIANI IN RITARDO ==========
    TestCase("ask_delayed_plans", "piani in ritardo", {}, "medium"),
    TestCase("ask_delayed_plans", "quali piani sono in ritardo?", {}, "medium"),
    TestCase("check_if_plan_delayed", "ritardo del piano A1", {"piano_code": "A1"}, "complex"),
    TestCase("check_if_plan_delayed", "il piano B2 è in ritardo?", {"piano_code": "B2"}, "complex"),

    # ========== STORICO STABILIMENTI ==========
    TestCase("ask_establishment_history", "storico controlli IT 2287", {"num_registrazione": "IT 2287"}, "complex"),
    TestCase("ask_establishment_history", "storia controlli stabilimento IT 123", {"num_registrazione": "IT 123"}, "complex"),

    # ========== NON CONFORMITÀ ==========
    TestCase("analyze_nc_by_category", "non conformità HACCP", {"categoria": "HACCP"}, "complex"),
    TestCase("analyze_nc_by_category", "problemi igiene degli alimenti", {"categoria": "IGIENE"}, "complex"),
]


class BackendBenchmark:
    """Classe per eseguire benchmark sui backend LLM"""

    def __init__(self, test_cases: List[TestCase], iterations: int = 3, verbose: bool = True):
        self.test_cases = test_cases
        self.iterations = iterations
        self.verbose = verbose
        self.results: List[TestResult] = []

    def _log(self, message: str, level: str = "INFO"):
        """Log con livelli"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
            symbol = symbols.get(level, "•")
            print(f"[{timestamp}] {symbol}  {message}")

    def _switch_backend(self, backend: str):
        """Cambia backend LLM modificando temporaneamente la variabile ambiente"""
        os.environ["GIAS_LLM_BACKEND"] = backend
        # Force reload config
        import importlib
        from configs import config
        importlib.reload(config)
        self._log(f"Switched to backend: {backend.upper()}", "INFO")

    def _run_single_test(self, test_case: TestCase, backend: str) -> TestResult:
        """Esegue un singolo test su un backend"""
        try:
            # Crea nuovo router per ogni test (per evitare cache cross-backend)
            router = Router(enable_cache=False)

            # Misura tempo di classificazione
            start_time = time.time()
            classification = router.classify(test_case.message, {})
            elapsed_ms = (time.time() - start_time) * 1000

            predicted_intent = classification.get("intent", "fallback")
            slots = classification.get("slots", {})
            needs_clarification = classification.get("needs_clarification", False)

            # Verifica correttezza
            correct = (predicted_intent == test_case.intent)

            return TestResult(
                backend=backend,
                intent=test_case.intent,
                message=test_case.message,
                expected_intent=test_case.intent,
                predicted_intent=predicted_intent,
                correct=correct,
                response_time_ms=round(elapsed_ms, 2),
                slots_extracted=slots,
                needs_clarification=needs_clarification,
                error=None
            )

        except Exception as e:
            return TestResult(
                backend=backend,
                intent=test_case.intent,
                message=test_case.message,
                expected_intent=test_case.intent,
                predicted_intent="error",
                correct=False,
                response_time_ms=0.0,
                slots_extracted={},
                needs_clarification=False,
                error=str(e)
            )

    def run_tests(self, backends: List[str]) -> Dict[str, List[TestResult]]:
        """Esegue tutti i test su tutti i backend"""
        all_results = {backend: [] for backend in backends}

        total_tests = len(self.test_cases) * self.iterations * len(backends)
        self._log(f"Starting benchmark: {len(self.test_cases)} test cases × {self.iterations} iterations × {len(backends)} backends = {total_tests} tests", "INFO")
        print("=" * 80)

        test_num = 0
        for backend in backends:
            self._log(f"Testing backend: {backend.upper()}", "INFO")
            self._switch_backend(backend)

            # Warmup
            self._log("Warmup...", "INFO")
            try:
                warmup_router = Router(enable_cache=False)
                warmup_router.classify("ciao", {})
            except:
                pass

            time.sleep(1)

            for iteration in range(self.iterations):
                self._log(f"Iteration {iteration + 1}/{self.iterations}", "INFO")

                for test_case in self.test_cases:
                    test_num += 1

                    if self.verbose and test_num % 10 == 0:
                        progress = (test_num / total_tests) * 100
                        self._log(f"Progress: {test_num}/{total_tests} ({progress:.1f}%)", "INFO")

                    result = self._run_single_test(test_case, backend)
                    all_results[backend].append(result)

                    if result.error:
                        self._log(f"Error on '{test_case.message[:50]}...': {result.error}", "ERROR")
                    elif not result.correct:
                        self._log(f"Mismatch on '{test_case.message[:50]}...': expected {test_case.intent}, got {result.predicted_intent}", "WARN")

                # Small delay between iterations
                time.sleep(0.5)

            print()

        self._log("Benchmark completed!", "SUCCESS")
        return all_results

    def calculate_stats(self, results: List[TestResult]) -> BackendStats:
        """Calcola statistiche aggregate per un backend"""
        if not results:
            return BackendStats(
                backend="unknown",
                total_tests=0,
                correct=0,
                incorrect=0,
                accuracy=0.0,
                avg_response_time_ms=0.0,
                min_response_time_ms=0.0,
                max_response_time_ms=0.0,
                std_response_time_ms=0.0,
                errors=0
            )

        correct = sum(1 for r in results if r.correct)
        errors = sum(1 for r in results if r.error)
        response_times = [r.response_time_ms for r in results if r.response_time_ms > 0]

        return BackendStats(
            backend=results[0].backend,
            total_tests=len(results),
            correct=correct,
            incorrect=len(results) - correct,
            accuracy=round((correct / len(results)) * 100, 2),
            avg_response_time_ms=round(statistics.mean(response_times), 2) if response_times else 0.0,
            min_response_time_ms=round(min(response_times), 2) if response_times else 0.0,
            max_response_time_ms=round(max(response_times), 2) if response_times else 0.0,
            std_response_time_ms=round(statistics.stdev(response_times), 2) if len(response_times) > 1 else 0.0,
            errors=errors
        )

    def print_comparison_report(self, all_results: Dict[str, List[TestResult]]):
        """Stampa report comparativo dettagliato"""
        print("\n" + "=" * 80)
        print(" " * 25 + "BENCHMARK COMPARISON REPORT")
        print("=" * 80)

        # Calcola statistiche per ogni backend
        stats = {backend: self.calculate_stats(results) for backend, results in all_results.items()}

        # Tabella statistiche generali
        print("\n📊 OVERALL STATISTICS")
        print("-" * 80)
        print(f"{'Backend':<15} {'Tests':<8} {'Correct':<10} {'Accuracy':<12} {'Avg Time (ms)':<15} {'Std Dev':<10}")
        print("-" * 80)

        for backend, stat in stats.items():
            print(f"{backend.upper():<15} {stat.total_tests:<8} {stat.correct:<10} {stat.accuracy:>6.2f}%     {stat.avg_response_time_ms:>10.2f}      {stat.std_response_time_ms:>7.2f}")

        print("-" * 80)

        # Confronto diretto
        if len(stats) == 2:
            backends_list = list(stats.keys())
            b1, b2 = backends_list[0], backends_list[1]
            s1, s2 = stats[b1], stats[b2]

            print(f"\n🔍 DIRECT COMPARISON: {b1.upper()} vs {b2.upper()}")
            print("-" * 80)

            # Accuracy
            acc_diff = s1.accuracy - s2.accuracy
            acc_winner = b1 if acc_diff > 0 else b2
            print(f"Accuracy:        {acc_winner.upper()} wins by {abs(acc_diff):.2f}%")

            # Speed
            speed_diff = s2.avg_response_time_ms - s1.avg_response_time_ms
            speed_winner = b1 if speed_diff > 0 else b2
            speed_improvement = (abs(speed_diff) / max(s1.avg_response_time_ms, s2.avg_response_time_ms)) * 100
            print(f"Speed:           {speed_winner.upper()} is {abs(speed_diff):.2f}ms faster ({speed_improvement:.1f}% improvement)")

            # Errori
            if s1.errors > 0 or s2.errors > 0:
                print(f"Errors:          {b1.upper()}: {s1.errors}, {b2.upper()}: {s2.errors}")

        # Dettagli per intent
        print(f"\n📋 ACCURACY BY INTENT")
        print("-" * 80)

        # Raggruppa risultati per intent
        intent_results = {}
        for backend, results in all_results.items():
            for result in results:
                if result.intent not in intent_results:
                    intent_results[result.intent] = {}
                if backend not in intent_results[result.intent]:
                    intent_results[result.intent][backend] = []
                intent_results[result.intent][backend].append(result)

        # Stampa per intent
        for intent in sorted(intent_results.keys()):
            print(f"\n{intent}:")
            for backend, results in intent_results[intent].items():
                correct = sum(1 for r in results if r.correct)
                total = len(results)
                accuracy = (correct / total * 100) if total > 0 else 0
                avg_time = statistics.mean([r.response_time_ms for r in results if r.response_time_ms > 0])
                print(f"  {backend.upper():<15} Accuracy: {accuracy:>6.2f}% ({correct}/{total})  Avg Time: {avg_time:>7.2f}ms")

        # Tempo di risposta - dettagli
        print(f"\n⏱️  RESPONSE TIME DETAILS")
        print("-" * 80)
        print(f"{'Backend':<15} {'Min (ms)':<12} {'Max (ms)':<12} {'Avg (ms)':<12} {'Std Dev (ms)':<15}")
        print("-" * 80)

        for backend, stat in stats.items():
            print(f"{backend.upper():<15} {stat.min_response_time_ms:<12.2f} {stat.max_response_time_ms:<12.2f} {stat.avg_response_time_ms:<12.2f} {stat.std_response_time_ms:<15.2f}")

        print("-" * 80)

        # Errori dettagliati
        errors_found = False
        for backend, results in all_results.items():
            errors = [r for r in results if r.error]
            if errors:
                errors_found = True
                print(f"\n❌ ERRORS - {backend.upper()}")
                print("-" * 80)
                for err in errors[:10]:  # Max 10 errori
                    print(f"  Message: {err.message[:60]}...")
                    print(f"  Error: {err.error}")
                if len(errors) > 10:
                    print(f"  ... and {len(errors) - 10} more errors")

        if not errors_found:
            print(f"\n✅ NO ERRORS FOUND")

        print("\n" + "=" * 80)

    def export_json(self, all_results: Dict[str, List[TestResult]], output_file: str):
        """Esporta risultati in formato JSON"""
        stats = {backend: asdict(self.calculate_stats(results)) for backend, results in all_results.items()}

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "test_config": {
                "test_cases": len(self.test_cases),
                "iterations": self.iterations,
                "backends": list(all_results.keys())
            },
            "statistics": stats,
            "detailed_results": {
                backend: [asdict(r) for r in results]
                for backend, results in all_results.items()
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        self._log(f"Results exported to: {output_file}", "SUCCESS")


def main():
    parser = argparse.ArgumentParser(
        description="GiAs-llm Backend Comparison Tool - Compare Ollama vs Llama.cpp"
    )
    parser.add_argument(
        "--backends",
        nargs="+",
        default=["ollama", "llamacpp"],
        choices=["ollama", "llamacpp"],
        help="Backends to test (default: both)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations per test case (default: 3)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="Output JSON file (default: benchmark_results.json)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test with subset of test cases (10 cases, 1 iteration)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (only final report)"
    )

    args = parser.parse_args()

    # Quick mode
    test_cases = TEST_CASES
    iterations = args.iterations

    if args.quick:
        # Select representative test cases
        quick_cases = [
            TEST_CASES[0],   # greet
            TEST_CASES[8],   # ask_piano_description
            TEST_CASES[11],  # ask_piano_stabilimenti
            TEST_CASES[17],  # search_piani_by_topic
            TEST_CASES[20],  # ask_priority_establishment
            TEST_CASES[23],  # ask_risk_based_priority
            TEST_CASES[29],  # ask_suggest_controls
            TEST_CASES[32],  # ask_delayed_plans
            TEST_CASES[38],  # ask_establishment_history
            TEST_CASES[40],  # analyze_nc_by_category
        ]
        test_cases = quick_cases
        iterations = 1
        print("🚀 QUICK MODE: Testing 10 representative cases with 1 iteration")

    # Run benchmark
    benchmark = BackendBenchmark(
        test_cases=test_cases,
        iterations=iterations,
        verbose=not args.quiet
    )

    all_results = benchmark.run_tests(args.backends)

    # Print report
    benchmark.print_comparison_report(all_results)

    # Export JSON
    benchmark.export_json(all_results, args.output)

    print(f"\n✅ Benchmark completed! Results saved to: {args.output}")


if __name__ == "__main__":
    main()
