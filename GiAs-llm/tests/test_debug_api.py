#!/usr/bin/env python3
"""
Test per verificare la compatibilita' con la pagina di debug di GChat
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5005"


def test_parse_endpoint():
    """Test /api/v1/parse endpoint (usato dalla pagina debug)"""
    print("\n" + "=" * 60)
    print("TEST 1: /api/v1/parse - Parse NLU")
    print("=" * 60)

    test_messages = [
        ("quali attività ha il piano A1?", "ask_piano_description", "A1"),
        ("descrivi il piano B2", "ask_piano_description", "B2"),
        ("cerca piani sui bovini", "search_piani_by_topic", None),
        ("stabilimenti ad alto rischio", "ask_risk_based_priority", None),
        ("ciao", "greet", None),
    ]

    all_passed = True

    for message, expected_intent, expected_entity in test_messages:
        print(f"\n  Messaggio: '{message}'")

        payload = {
            "text": message,
            "metadata": {"asl": "NA1", "uoc": "Veterinaria"}
        }

        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/parse",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                print(f"   X Status code: {response.status_code}")
                all_passed = False
                continue

            result = response.json()

            # Verifica campi obbligatori V1
            required_fields = ["text", "intent", "confidence"]
            missing_fields = [f for f in required_fields if f not in result]

            if missing_fields:
                print(f"   X Campi mancanti: {missing_fields}")
                all_passed = False
                continue

            intent_name = result.get("intent", "")
            confidence = result.get("confidence", 0)
            print(f"   OK Intent: {intent_name} (confidence: {confidence:.2f})")

            if intent_name != expected_intent:
                print(f"      Atteso: {expected_intent}")

            # Verifica slots
            if expected_entity:
                slots = result.get("slots", {})
                if slots.get("piano_code") == expected_entity:
                    print(f"      Piano code '{expected_entity}' estratto correttamente")
                else:
                    print(f"      Piano code '{expected_entity}' non trovato in slots")

        except Exception as e:
            print(f"   X Errore: {e}")
            all_passed = False

    return all_passed


def test_debug_workflow():
    """Simula il workflow completo della pagina debug di GChat"""
    print("\n" + "=" * 60)
    print("TEST 2: Workflow Completo Debug Page")
    print("=" * 60)

    message = "quali attività ha il piano A32?"
    sender = "debug_test_user"

    print(f"\n  Simulazione richiesta debug:")
    print(f"   Message: {message}")
    print(f"   Sender: {sender}")

    # Step 1: Parse message (per mostrare intent nella UI)
    print(f"\n[Step 1] Parse NLU...")
    try:
        parse_resp = requests.post(
            f"{BASE_URL}/api/v1/parse",
            json={"text": message, "metadata": {"asl": "NA1"}}
        )

        if parse_resp.status_code != 200:
            print(f"   X Parse failed with status {parse_resp.status_code}")
            return False

        parse_data = parse_resp.json()
        intent = parse_data.get("intent", "unknown")
        confidence = parse_data.get("confidence", 0)

        print(f"   OK Intent detected: {intent} (confidence: {confidence:.2f})")

    except Exception as e:
        print(f"   X Parse error: {e}")
        return False

    # Step 2: Send to V1 chat (per ottenere la risposta)
    print(f"\n[Step 2] Invio a /api/v1/chat...")
    try:
        chat_resp = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={
                "sender": sender,
                "message": message,
                "metadata": {"asl": "NA1", "uoc": "Veterinaria"}
            }
        )

        if chat_resp.status_code != 200:
            print(f"   X Chat failed with status {chat_resp.status_code}")
            return False

        chat_data = chat_resp.json()
        if "result" not in chat_data:
            print(f"   X Nessun result nella risposta")
            return False

        result = chat_data["result"]
        response_text = result.get("text", "")
        slots = result.get("slots", {})
        print(f"   OK Risposta ricevuta ({len(response_text)} caratteri)")
        print(f"   OK Intent: {result.get('intent', 'N/A')}")
        print(f"   OK Slots: {len(slots)}")

    except Exception as e:
        print(f"   X Chat error: {e}")
        return False

    # Riepilogo come sarebbe mostrato nella debug page
    print(f"\n  DEBUG PAGE OUTPUT:")
    print(f"   Intent: {intent}")
    print(f"   Slots: {json.dumps(slots, indent=2)}")
    print(f"   Response: {response_text[:200]}...")

    return True


def test_debug_response_format():
    """Verifica che il formato V1 sia corretto"""
    print("\n" + "=" * 60)
    print("TEST 3: Formato Response V1")
    print("=" * 60)

    # Test parse response V1
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/parse",
            json={"text": "test", "metadata": {}}
        )

        result = response.json()

        print(f"Formato corrente /api/v1/parse:")
        print(json.dumps(result, indent=2))

        # Verifica formato V1
        has_intent = "intent" in result and isinstance(result["intent"], str)
        has_confidence = "confidence" in result and isinstance(result["confidence"], (int, float))

        if has_intent and has_confidence:
            print(f"\n  OK Formato V1 corretto")
            return True
        else:
            print(f"\n  X Formato non corretto")
            return False

    except Exception as e:
        print(f"X Errore: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("   TEST DEBUG PAGE GChat (API V1)")
    print("=" * 60)

    # Verifica connessione
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        print(f"OK Server raggiungibile")
    except:
        print(f"X Server non raggiungibile su {BASE_URL}")
        print(f"   Avvia il server con: scripts/server.sh start")
        sys.exit(1)

    results = []
    results.append(("Parse V1 Endpoint", test_parse_endpoint()))
    results.append(("Workflow Completo V1", test_debug_workflow()))
    results.append(("Formato Response V1", test_debug_response_format()))

    print("\n" + "=" * 60)
    print("RIEPILOGO TEST DEBUG PAGE")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "OK PASS" if result else "X FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotale: {passed}/{total} test passati ({passed*100//total}%)")

    if passed == total:
        print("\nOK TUTTI I TEST PASSATI - Debug page V1 supportata")
    else:
        print(f"\n{total - passed} test falliti - Verificare implementazione")

    print("=" * 60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
