#!/usr/bin/env python3
"""
Test rapido per verificare l'integrazione ML.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_quick():
    """Test rapido dell'integrazione ML."""
    print("🚀 Quick Test ML Risk Predictor")

    try:
        # Test tool
        from tools.predictor_tools import get_ml_risk_prediction
        ml_func = get_ml_risk_prediction.func if hasattr(get_ml_risk_prediction, 'func') else get_ml_risk_prediction

        print("✅ Tool importato correttamente")

        # Test predizione
        result = ml_func(asl="AVELLINO", limit=5)

        print(f"✅ Predizione completata")
        print(f"   ASL: {result.get('asl')}")
        print(f"   Modello: {result.get('model_version')}")
        print(f"   Stabilimenti rischiosi: {len(result.get('risky_establishments', []))}")

        if result.get('risky_establishments'):
            print(f"   Primo stabilimento: {result['risky_establishments'][0].get('macroarea', 'N/D')}")

        # Test with LangGraph node
        from orchestrator.graph import ConversationGraph
        from llm.client import LLMClient

        # Usa client reale o skip se non disponibile
        try:
            graph = ConversationGraph(LLMClient())
        except:
            print("⚠️  Skipping LangGraph test (LLM not available)")
            return True
        state = {
            "message": "test",
            "metadata": {"asl": "NAPOLI"},
            "intent": "ask_risk_based_priority",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result_state = graph._ml_risk_predictor_tool(state)
        print(f"✅ LangGraph node funzionante")
        print(f"   Tool output: {result_state['tool_output']['type']}")

        return True

    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_quick()
    print(f"\nTest {'PASSATO' if success else 'FALLITO'}")
    sys.exit(0 if success else 1)