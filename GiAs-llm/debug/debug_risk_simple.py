#!/usr/bin/env python3
"""
Debug semplice del risk tool senza LLM
"""

import traceback

def test_risk_simple():
    print("🔍 DEBUG SEMPLICE: Risk Tool")
    print("=" * 40)

    try:
        # 1. Test data
        print("1. Test data availability...")
        from agents.data import piani_df, controlli_df, osa_mai_controllati_df
        print(f"   ✅ Data loaded: piani={len(piani_df)}, controlli={len(controlli_df)}")

        # 2. Test tools import
        print("\n2. Test tools import...")
        from tools.risk_tools import get_risk_based_priority
        from agents.data_agent import DataRetriever, RiskAnalyzer
        print("   ✅ Tools imported")

        # 3. Test function directly
        print("\n3. Test risk function...")

        # Accedi alla funzione vera sotto il decorator
        risk_func = get_risk_based_priority.func if hasattr(get_risk_based_priority, 'func') else get_risk_based_priority

        print("   Tipo funzione:", type(risk_func))

        # Test caso senza parametri (dovrebbe dare errore controllato)
        print("   Caso: Nessun parametro...")
        result_none = risk_func()
        print(f"   Result: {result_none}")

        # Test caso solo piano
        print("   Caso: Solo piano A1...")
        result_piano = risk_func(piano_code="A1")
        print(f"   Result keys: {list(result_piano.keys())}")
        if "error" in result_piano:
            print(f"   ❌ Error: {result_piano['error']}")
        else:
            print("   ✅ Success")

        # Test caso ASL
        print("   Caso: ASL NA1...")
        result_asl = risk_func(asl="NA1")
        print(f"   Result keys: {list(result_asl.keys())}")
        if "error" in result_asl:
            print(f"   ❌ Error: {result_asl['error']}")
        else:
            print("   ✅ Success")

    except Exception as e:
        print(f"\n❌ ERRORE: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_risk_simple()