#!/usr/bin/env python3
"""
Test completo per verificare la query dell'utente:
'quali sono gli stabilimenti più a rischio per il piano A1?'
"""

def test_user_query():
    print("🔍 TEST COMPLETO: Stabilimenti a rischio per piano A1")
    print("=" * 60)

    # 1. Test classificazione intent
    print("1️⃣ CLASSIFICAZIONE INTENT")
    try:
        from orchestrator.router import Router
        router = Router()
        result = router.classify('quali sono gli stabilimenti più a rischio per il piano A1?')

        print(f"✅ Intent: {result['intent']}")
        print(f"✅ Slots: {result['slots']}")

        if result['intent'] != 'ask_risk_based_priority':
            print("❌ ERRORE: Intent sbagliato!")
            return

        if result['slots'].get('piano_code') != 'A1':
            print("❌ ERRORE: Piano code non estratto!")
            return

    except Exception as e:
        print(f"❌ ERRORE Classificazione: {e}")
        return

    print()

    # 2. Test tool risk
    print("2️⃣ ESECUZIONE TOOL RISK")
    try:
        from tools.risk_tools import risk_tool

        # Simula chiamata orchestrator
        tool_result = risk_tool(asl=None, piano_code='A1')

        print(f"✅ Piano: {tool_result.get('piano_code')}")
        print(f"✅ Errore: {tool_result.get('error', 'None')}")
        print(f"✅ Ha formatted_response: {'formatted_response' in tool_result}")

        if tool_result.get('error'):
            print(f"❌ ERRORE Tool: {tool_result['error']}")
            return

    except Exception as e:
        print(f"❌ ERRORE Tool: {e}")
        return

    print()

    # 3. Test response formatting
    print("3️⃣ FORMATTAZIONE RISPOSTA")
    formatted_response = tool_result.get('formatted_response', '')

    if not formatted_response:
        print("❌ ERRORE: Nessuna formatted_response!")
        return

    # Cerca le non conformità
    nc_found = False
    lines = formatted_response.split('\n')
    for line in lines:
        if 'non conformità storiche:' in line.lower() or 'nc gravi' in line.lower():
            nc_found = True
            print(f"✅ NC trovate: {line.strip()}")
            break

    if not nc_found:
        print("❌ ERRORE: Non conformità non trovate nella risposta!")
        print("Prime 10 righe della risposta:")
        for i, line in enumerate(lines[:10], 1):
            print(f"   {i}: {line}")
        return

    print()

    # 4. Response finale come la vedrebbe l'utente
    print("4️⃣ RISPOSTA FINALE UTENTE")
    print("=" * 60)

    # Mostra solo le parti con NC
    in_establishment = False
    for line in lines:
        if line.strip().startswith('**1.') or line.strip().startswith('**2.'):
            in_establishment = True
            print(line)
        elif in_establishment and ('non conformità' in line.lower() or 'punteggio rischio' in line.lower()):
            print(line)
        elif in_establishment and line.strip() == '':
            in_establishment = False
            print(line)
            break
        elif in_establishment:
            print(line)

    print()
    print("✅ TEST COMPLETATO: Le non conformità DOVREBBERO essere visibili!")

if __name__ == "__main__":
    test_user_query()