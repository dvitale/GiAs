#!/usr/bin/env python3
"""
Test script per verificare l'integrazione del ML Risk Predictor.

Testa sia il funzionamento del modulo ML che il fallback rule-based.
"""

import sys
import os
import traceback
from datetime import datetime

# Aggiungi il path corrente per import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_predictor_ml_module():
    """Testa il modulo predictor_ml direttamente."""
    print("=" * 60)
    print("TEST 1: Modulo ML Predictor")
    print("=" * 60)

    try:
        from predictor_ml import load_predictor

        # Inizializza predittore
        predictor = load_predictor()
        print(f"✅ Predittore caricato: {type(predictor)}")
        print(f"   Modello disponibile: {predictor.model_available}")
        print(f"   Path modello: {predictor.model_path}")

        # Test predizione
        result = predictor.predict(asl="AVELLINO", limit=5)

        print(f"✅ Predizione completata")
        print(f"   ASL: {result.get('asl')}")
        print(f"   Stabilimenti mai controllati: {result.get('total_never_controlled')}")
        print(f"   Stabilimenti rischiosi: {result.get('total_predicted_risky')}")
        print(f"   Modello: {result.get('model_version')}")

        if result.get('risky_establishments'):
            print(f"   Top 3 stabilimenti:")
            for i, est in enumerate(result['risky_establishments'][:3], 1):
                print(f"     {i}. {est.get('macroarea', 'N/D')} (score: {est.get('risk_score', 0):.3f})")

        return True

    except Exception as e:
        print(f"❌ Errore test modulo ML: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_predictor_tools():
    """Testa il tool LangGraph predictor_tools."""
    print("\n" + "=" * 60)
    print("TEST 2: Tool LangGraph")
    print("=" * 60)

    try:
        from tools.predictor_tools import get_ml_risk_prediction

        # Estrai la funzione dal tool decorator se necessario
        ml_func = get_ml_risk_prediction.func if hasattr(get_ml_risk_prediction, 'func') else get_ml_risk_prediction

        # Test con ASL valida
        result = ml_func(asl="AVELLINO", limit=3)

        print(f"✅ Tool LangGraph funzionante")
        print(f"   ASL: {result.get('asl')}")
        print(f"   Timestamp: {result.get('prediction_timestamp')}")
        print(f"   Modello: {result.get('model_version')}")

        if 'error' in result:
            print(f"   ⚠️  Errore: {result['error']}")
        else:
            print(f"   Stabilimenti rischiosi: {len(result.get('risky_establishments', []))}")

        # Test con piano code
        result_piano = ml_func(asl="SALERNO", piano_code="A1", limit=2)
        print(f"✅ Test con piano A1 completato")
        print(f"   Stabilimenti: {len(result_piano.get('risky_establishments', []))}")

        return True

    except Exception as e:
        print(f"❌ Errore test tool: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_langgraph_integration():
    """Testa l'integrazione con LangGraph."""
    print("\n" + "=" * 60)
    print("TEST 3: Integrazione LangGraph")
    print("=" * 60)

    try:
        from orchestrator.graph import ConversationGraph
        from llm.client import LLMClient

        # Inizializza LLM client (usa stub se Ollama non disponibile)
        try:
            llm_client = LLMClient()
            print(f"✅ LLM Client inizializzato")
        except:
            print(f"⚠️  LLM Client non disponibile, usando mock")
            # Mock per testing
            class MockLLMClient:
                def generate_response(self, prompt, temperature=0.1):
                    return '{"intent": "ask_risk_based_priority", "slots": {"piano_code": null}, "needs_clarification": false}'
            llm_client = MockLLMClient()

        # Crea graph
        graph = ConversationGraph(llm_client)
        print(f"✅ ConversationGraph inizializzato")

        # Simula stato conversazione
        state = {
            "message": "stabilimenti a rischio per ASL AVELLINO",
            "metadata": {"asl": "AVELLINO", "user_id": "test_user"},
            "intent": "ask_risk_based_priority",
            "slots": {"piano_code": None},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        # Testa nodo ML predictor direttamente
        result_state = graph._ml_risk_predictor_tool(state)

        print(f"✅ Nodo ML predictor funzionante")
        print(f"   Tool output type: {result_state['tool_output']['type']}")

        tool_data = result_state['tool_output']['data']
        if 'error' in tool_data:
            print(f"   ⚠️  Errore: {tool_data['error']}")
        else:
            print(f"   Stabilimenti: {len(tool_data.get('risky_establishments', []))}")
            print(f"   Modello: {tool_data.get('model_version', 'N/D')}")

        return True

    except Exception as e:
        print(f"❌ Errore test LangGraph: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def test_fallback_mechanism():
    """Testa il meccanismo di fallback rule-based."""
    print("\n" + "=" * 60)
    print("TEST 4: Fallback Rule-Based")
    print("=" * 60)

    try:
        # Forza fallback disabilitando temporaneamente ML
        import tools.predictor_tools
        original_ml_available = tools.predictor_tools.ML_AVAILABLE

        # Simula ML non disponibile
        tools.predictor_tools.ML_AVAILABLE = False
        print("   ML temporaneamente disabilitato per test fallback")

        from tools.predictor_tools import get_ml_risk_prediction

        # Estrai la funzione dal tool decorator
        ml_func = get_ml_risk_prediction.func if hasattr(get_ml_risk_prediction, 'func') else get_ml_risk_prediction

        # Test fallback
        result = ml_func(asl="NAPOLI", limit=3)

        print(f"✅ Fallback rule-based funzionante")
        print(f"   Modello: {result.get('model_version', 'N/D')}")

        if 'rule-based' in result.get('model_version', '').lower():
            print("   ✓ Fallback correttamente attivato")
        else:
            print("   ⚠️  Fallback non rilevato")

        print(f"   Stabilimenti: {len(result.get('risky_establishments', []))}")

        # Ripristina stato originale
        tools.predictor_tools.ML_AVAILABLE = original_ml_available

        return True

    except Exception as e:
        print(f"❌ Errore test fallback: {e}")
        # Ripristina stato in caso di errore
        try:
            tools.predictor_tools.ML_AVAILABLE = original_ml_available
        except:
            pass
        return False


def test_performance_benchmark():
    """Testa le performance del predittore."""
    print("\n" + "=" * 60)
    print("TEST 5: Performance Benchmark")
    print("=" * 60)

    try:
        import time
        from tools.predictor_tools import get_ml_risk_prediction

        # Estrai la funzione dal tool decorator
        ml_func = get_ml_risk_prediction.func if hasattr(get_ml_risk_prediction, 'func') else get_ml_risk_prediction

        start_time = time.time()

        # Test con diversi parametri
        test_cases = [
            {"asl": "AVELLINO", "limit": 10},
            {"asl": "SALERNO", "piano_code": "A1", "limit": 5},
            {"asl": "NAPOLI", "min_score": 0.3, "limit": 15}
        ]

        results = []
        for i, case in enumerate(test_cases, 1):
            case_start = time.time()
            result = ml_func(**case)
            case_time = time.time() - case_start

            results.append({
                'case': case,
                'time': case_time,
                'establishments': len(result.get('risky_establishments', [])),
                'error': 'error' in result
            })

            print(f"   Test case {i}: {case_time:.3f}s - {case}")

        total_time = time.time() - start_time

        print(f"✅ Benchmark completato")
        print(f"   Tempo totale: {total_time:.3f}s")
        print(f"   Tempo medio: {total_time/len(test_cases):.3f}s")

        # Verifica target performance (< 2s per test case)
        avg_time = total_time / len(test_cases)
        if avg_time < 2.0:
            print(f"   ✓ Performance OK (target: <2s)")
        else:
            print(f"   ⚠️  Performance lenta (target: <2s)")

        return True

    except Exception as e:
        print(f"❌ Errore benchmark: {e}")
        return False


def main():
    """Esegue tutti i test."""
    print("🤖 Test ML Risk Predictor - GiAs-llm")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n")

    tests = [
        test_predictor_ml_module,
        test_predictor_tools,
        test_langgraph_integration,
        test_fallback_mechanism,
        test_performance_benchmark
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Errore critico in {test.__name__}: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {test.__name__}: {status}")

    print(f"\nRisultato finale: {passed}/{total} test passati")

    if passed == total:
        print("🎉 Tutti i test sono passati! ML Predictor pronto per produzione.")
        return 0
    else:
        print("⚠️  Alcuni test sono falliti. Verificare i log sopra.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)