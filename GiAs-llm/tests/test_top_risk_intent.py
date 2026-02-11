#!/usr/bin/env python3
"""
Test per il nuovo intent ask_top_risk_activities
"""

import sys
import os

# Aggiungi path per imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from orchestrator.router import Router
    from tools.risk_analysis_tools import get_top_risk_activities
    from llm.client import LLMClient
except ImportError as e:
    print(f"❌ Errore import: {e}")
    sys.exit(1)

def test_intent_classification():
    """Test classificazione intent per top risk activities"""
    print("🧪 TEST CLASSIFICAZIONE INTENT")
    print("=" * 50)

    # Test cases specifici per il nuovo intent
    test_cases = [
        "attività più rischiose",
        "top 10 attività a rischio",
        "classifica attività per rischio",
        "quali sono le attività con maggior risk score",
        "attività ad alto rischio",
        "mostrami le attività più pericolose"
    ]

    # Inizializza router
    router = Router(LLMClient())

    for test_case in test_cases:
        print(f"\n📝 Test: '{test_case}'")
        try:
            result = router.classify(test_case)
            intent = result.get('intent', 'unknown')
            success = intent == 'ask_top_risk_activities'
            status = "✅" if success else "❌"

            print(f"   {status} Intent: {intent}")
            if not success:
                print(f"   ⚠️  Atteso: ask_top_risk_activities")

        except Exception as e:
            print(f"   ❌ Errore: {e}")

def test_tool_functionality():
    """Test funzionalità del tool"""
    print(f"\n🔧 TEST FUNZIONALITÀ TOOL")
    print("=" * 50)

    try:
        # Test del tool direttamente
        tool_func = get_top_risk_activities.func if hasattr(get_top_risk_activities, 'func') else get_top_risk_activities
        result = tool_func(limit=5)

        if 'error' in result:
            print(f"❌ Errore tool: {result['error']}")
            return

        print(f"✅ Tool eseguito con successo")
        print(f"   📊 Attività analizzate: {result.get('total_activities_analyzed', 0)}")
        print(f"   🔴 Alto rischio: {result.get('high_risk_count', 0)}")
        print(f"   📋 Attività restituite: {len(result.get('activities', []))}")

        if result.get('formatted_response'):
            print(f"\n📄 ANTEPRIMA RISPOSTA:")
            preview = result['formatted_response'][:300]
            print(f"   {preview}{'...' if len(result['formatted_response']) > 300 else ''}")

    except Exception as e:
        print(f"❌ Errore test tool: {e}")

def test_integration():
    """Test integrazione completa intent -> tool -> response"""
    print(f"\n🔄 TEST INTEGRAZIONE COMPLETA")
    print("=" * 50)

    try:
        # Simula flusso completo
        test_message = "attività più rischiose"

        # 1. Classificazione intent
        router = Router(LLMClient())
        classification = router.classify(test_message)

        intent = classification.get('intent')
        print(f"1️⃣ Classificazione: {intent}")

        if intent != 'ask_top_risk_activities':
            print(f"❌ Intent errato: {intent}")
            return

        # 2. Esecuzione tool
        tool_func = get_top_risk_activities.func if hasattr(get_top_risk_activities, 'func') else get_top_risk_activities
        tool_result = tool_func(limit=3)
        print(f"2️⃣ Tool eseguito: {len(tool_result.get('activities', []))} risultati")

        # 3. Check risposta formattata
        if tool_result.get('formatted_response'):
            print(f"3️⃣ Risposta formattata: ✅")
            print(f"\n📊 SAMPLE OUTPUT:")
            lines = tool_result['formatted_response'].split('\n')
            for line in lines[:10]:  # Prime 10 righe
                print(f"   {line}")
            if len(lines) > 10:
                print(f"   ... (altre {len(lines)-10} righe)")
        else:
            print(f"3️⃣ Risposta formattata: ❌")

    except Exception as e:
        print(f"❌ Errore integrazione: {e}")

if __name__ == "__main__":
    print("🎯 TEST NUOVO INTENT: ask_top_risk_activities")
    print("=" * 60)

    test_intent_classification()
    test_tool_functionality()
    test_integration()

    print(f"\n✅ Test completato!")