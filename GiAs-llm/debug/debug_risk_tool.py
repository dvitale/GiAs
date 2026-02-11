#!/usr/bin/env python3
"""
Script di debug per il tool di risk analysis.
Testa tutte le funzionalità con traccia dettagliata.
"""

import traceback
import sys
import os

def test_risk_tool_debug():
    """Test completo del risk tool con debug dettagliato"""

    print("🔍 DEBUG: Test Risk Analysis Tool")
    print("=" * 50)

    try:
        # 1. Test import tools
        print("\n1. Test import tools...")
        from tools.risk_tools import get_risk_based_priority, risk_tool
        from orchestrator.router import Router
        from orchestrator.graph import ConversationGraph
        print("✅ Import tools successful")

        # 2. Test data availability
        print("\n2. Test data availability...")
        from agents.data import (
            piani_df, controlli_df, osa_mai_controllati_df,
            ocse_df, diff_prog_eseg_df, personale_df
        )

        print(f"   - piani_df: {len(piani_df)} rows")
        print(f"   - controlli_df: {len(controlli_df)} rows")
        print(f"   - osa_mai_controllati_df: {len(osa_mai_controllati_df)} rows")
        print(f"   - ocse_df: {len(ocse_df)} rows")
        print("✅ Data loading successful")

        # 3. Test DataRetriever
        print("\n3. Test DataRetriever...")
        from agents.data_agent import DataRetriever, RiskAnalyzer

        # Test controlli by piano
        controlli_test = DataRetriever.get_controlli_by_piano("A1")
        print(f"   - Controlli per A1: {len(controlli_test) if controlli_test is not None else 'None'}")

        # Test OSA mai controllati
        osa_test = DataRetriever.get_osa_mai_controllati(asl="NA1")
        print(f"   - OSA mai controllati NA1: {len(osa_test)}")
        print("✅ DataRetriever successful")

        # 4. Test RiskAnalyzer
        print("\n4. Test RiskAnalyzer...")
        risk_scores = RiskAnalyzer.calculate_risk_scores()
        print(f"   - Risk scores: {len(risk_scores)} activities")
        if not risk_scores.empty:
            print(f"   - Sample columns: {list(risk_scores.columns)}")
        print("✅ RiskAnalyzer successful")

        # 5. Test intent classification
        print("\n5. Test intent classification...")
        from llm.client import LLMClient
        llm = LLMClient()
        router = Router(llm)

        message = "Sulla base del rischio storico chi dovrei controllare per primo?"
        classification = router.classify(message)
        print(f"   - Intent: {classification.get('intent')}")
        print(f"   - Slots: {classification.get('slots')}")
        print("✅ Intent classification successful")

        # 6. Test risk tool directly
        print("\n6. Test risk tool directly...")

        # Accedi alla funzione originale sotto il decorator
        risk_func = get_risk_based_priority.func if hasattr(get_risk_based_priority, 'func') else get_risk_based_priority

        # Caso 1: Solo ASL (senza piano)
        print("   Caso 1: Solo ASL...")
        try:
            result1 = risk_func(asl="NA1")
            if "error" in result1:
                print(f"   ⚠️ Error ASL only: {result1['error']}")
            else:
                print(f"   ✅ ASL only successful: {result1.get('total_risky', 0)} risky establishments")
        except Exception as e:
            print(f"   ❌ Error ASL only: {str(e)}")

        # Caso 2: Nessun parametro
        print("   Caso 2: Nessun parametro...")
        try:
            result2 = risk_func()
            if "error" in result2:
                print(f"   ⚠️ Error no params: {result2['error']}")
            else:
                print("   ✅ No params successful")
        except Exception as e:
            print(f"   ❌ Error no params: {str(e)}")

        # Caso 3: Solo piano (nuovo comportamento)
        print("   Caso 3: Solo piano...")
        try:
            result3 = risk_func(piano_code="A1")
            if "error" in result3:
                print(f"   ⚠️ Error piano only: {result3['error']}")
            else:
                print(f"   ✅ Piano only successful: {result3.get('total_controls', 0)} total controls")
        except Exception as e:
            print(f"   ❌ Error piano only: {str(e)}")

        # 7. Test full workflow
        print("\n7. Test full workflow...")
        graph = ConversationGraph(llm)

        state = {
            "message": "Sulla base del rischio storico chi dovrei controllare per primo?",
            "metadata": {"asl": "NA1", "uoc": "SEPE", "user_id": "test_user"},
            "intent": "",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        try:
            result = graph.graph.invoke(state)
            print(f"   ✅ Full workflow successful")
            print(f"   - Intent: {result.get('intent')}")
            print(f"   - Tool output type: {result.get('tool_output', {}).get('type')}")
            if result.get('tool_output', {}).get('data', {}).get('error'):
                print(f"   ⚠️ Tool error: {result['tool_output']['data']['error']}")
        except Exception as e:
            print(f"   ❌ Full workflow failed: {str(e)}")
            traceback.print_exc()

        print("\n" + "=" * 50)
        print("🎯 DEBUG COMPLETATO")

    except Exception as e:
        print(f"\n❌ ERRORE CRITICO: {str(e)}")
        print("\nStack trace completo:")
        traceback.print_exc()

        # Informazioni diagnostiche aggiuntive
        print(f"\nInformazioni sistema:")
        print(f"   - Python: {sys.version}")
        print(f"   - Working dir: {os.getcwd()}")
        print(f"   - Python path: {sys.path[:3]}...")

if __name__ == "__main__":
    test_risk_tool_debug()