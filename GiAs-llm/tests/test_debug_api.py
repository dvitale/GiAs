#!/usr/bin/env python3
"""
Test per verificare la compatibilità con la pagina di debug di GChat
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5005"


def test_parse_endpoint():
    """Test /model/parse endpoint (usato dalla pagina debug)"""
    print("\n" + "=" * 60)
    print("TEST 1: /model/parse - Parse NLU")
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
        print(f"\n📝 Messaggio: '{message}'")

        payload = {
            "text": message,
            "metadata": {"asl": "NA1", "uoc": "Veterinaria"}
        }

        try:
            response = requests.post(
                f"{BASE_URL}/model/parse",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                print(f"   ❌ Status code: {response.status_code}")
                all_passed = False
                continue

            result = response.json()

            # Verifica campi obbligatori per GChat
            required_fields = ["text", "intent", "entities"]
            missing_fields = [f for f in required_fields if f not in result]

            if missing_fields:
                print(f"   ❌ Campi mancanti: {missing_fields}")
                all_passed = False
                continue

            # Verifica struttura intent
            if "intent" in result:
                intent_name = result["intent"].get("name", "")
                confidence = result["intent"].get("confidence", 0)
                print(f"   ✅ Intent: {intent_name} (confidence: {confidence:.2f})")

                if intent_name != expected_intent:
                    print(f"      ⚠️  Atteso: {expected_intent}")
            else:
                print(f"   ❌ Campo 'intent' mancante")
                all_passed = False

            # Verifica entities
            if "entities" in result:
                entities = result["entities"]
                print(f"   ✅ Entities: {len(entities)} trovate")

                if expected_entity:
                    entity_values = [e.get("value") for e in entities if e.get("entity") == "piano_code"]
                    if expected_entity in entity_values:
                        print(f"      ✓ Piano code '{expected_entity}' estratto correttamente")
                    else:
                        print(f"      ⚠️  Piano code '{expected_entity}' non trovato")
            else:
                print(f"   ❌ Campo 'entities' mancante")
                all_passed = False

        except Exception as e:
            print(f"   ❌ Errore: {e}")
            all_passed = False

    return all_passed


def test_tracker_endpoint():
    """Test /conversations/{sender_id}/tracker endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: /conversations/{id}/tracker - Conversation Tracker")
    print("=" * 60)

    sender_id = "test_debug_user"

    try:
        response = requests.get(f"{BASE_URL}/conversations/{sender_id}/tracker")

        print(f"Status Code: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Status code non valido")
            return False

        result = response.json()

        # Verifica campi richiesti da GChat
        required_fields = ["sender_id", "slots", "latest_message", "events"]
        missing_fields = [f for f in required_fields if f not in result]

        if missing_fields:
            print(f"❌ Campi mancanti: {missing_fields}")
            return False

        print(f"✅ Sender ID: {result.get('sender_id')}")
        print(f"✅ Slots: {len(result.get('slots', {}))} slot(s)")
        print(f"✅ Events: {len(result.get('events', []))} event(s)")
        print(f"✅ Latest Message: {result.get('latest_message', {})}")

        return True

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_debug_workflow():
    """Simula il workflow completo della pagina debug di GChat"""
    print("\n" + "=" * 60)
    print("TEST 3: Workflow Completo Debug Page")
    print("=" * 60)

    message = "quali attività ha il piano A32?"
    sender = "debug_test_user"

    print(f"\n📝 Simulazione richiesta debug:")
    print(f"   Message: {message}")
    print(f"   Sender: {sender}")

    # Step 1: Parse message (per mostrare intent/entities nella UI)
    print(f"\n[Step 1] Parse NLU...")
    try:
        parse_resp = requests.post(
            f"{BASE_URL}/model/parse",
            json={"text": message, "metadata": {"asl": "NA1"}}
        )

        if parse_resp.status_code != 200:
            print(f"   ❌ Parse failed with status {parse_resp.status_code}")
            return False

        parse_data = parse_resp.json()
        intent = parse_data.get("intent", {}).get("name", "unknown")
        entities = parse_data.get("entities", [])

        print(f"   ✅ Intent detected: {intent}")
        print(f"   ✅ Entities: {len(entities)}")

    except Exception as e:
        print(f"   ❌ Parse error: {e}")
        return False

    # Step 2: Send to webhook (per ottenere la risposta)
    print(f"\n[Step 2] Invio a webhook...")
    try:
        webhook_resp = requests.post(
            f"{BASE_URL}/webhooks/rest/webhook",
            json={
                "sender": sender,
                "message": message,
                "metadata": {"asl": "NA1", "uoc": "Veterinaria"}
            }
        )

        if webhook_resp.status_code != 200:
            print(f"   ❌ Webhook failed with status {webhook_resp.status_code}")
            return False

        responses = webhook_resp.json()
        if not responses or len(responses) == 0:
            print(f"   ❌ Nessuna risposta dal webhook")
            return False

        response_text = responses[0].get("text", "")
        print(f"   ✅ Risposta ricevuta ({len(response_text)} caratteri)")

    except Exception as e:
        print(f"   ❌ Webhook error: {e}")
        return False

    # Step 3: Get tracker (per mostrare slots nella UI)
    print(f"\n[Step 3] Recupero tracker...")
    try:
        tracker_resp = requests.get(
            f"{BASE_URL}/conversations/{sender}/tracker"
        )

        if tracker_resp.status_code != 200:
            print(f"   ❌ Tracker failed with status {tracker_resp.status_code}")
            return False

        tracker_data = tracker_resp.json()
        slots = tracker_data.get("slots", {})

        print(f"   ✅ Tracker recuperato")
        print(f"   ✅ Slots disponibili: {len(slots)}")

    except Exception as e:
        print(f"   ❌ Tracker error: {e}")
        return False

    # Riepilogo come sarebbe mostrato nella debug page
    print(f"\n📊 DEBUG PAGE OUTPUT:")
    print(f"   Intent: {intent}")
    print(f"   Entities: {json.dumps(entities, indent=2)}")
    print(f"   Slots: {json.dumps(slots, indent=2)}")
    print(f"   Response: {response_text[:200]}...")

    return True


def test_debug_response_format():
    """Verifica che il formato sia identico a quello atteso da GChat"""
    print("\n" + "=" * 60)
    print("TEST 4: Formato Response Debug")
    print("=" * 60)

    # Formato atteso da GChat per DebugChatResponse
    expected_format = {
        "message": "risposta del sistema",
        "status": "success",
        "intent": {"name": "intent_name", "confidence": 0.95},
        "entities": [{"entity": "entity_type", "value": "entity_value"}],
        "slots": {"slot_name": "slot_value"},
        "metadata": {"asl": "NA1"},
        "confidence": 0.95,
        "executed_actions": ["action_name"]
    }

    print(f"Formato atteso da GChat:")
    print(json.dumps(expected_format, indent=2))

    # Test parse response
    try:
        response = requests.post(
            f"{BASE_URL}/model/parse",
            json={"text": "test", "metadata": {}}
        )

        result = response.json()

        print(f"\nFormato corrente parse endpoint:")
        print(json.dumps(result, indent=2))

        # Verifica compatibilità
        has_intent = "intent" in result and isinstance(result["intent"], dict)
        has_entities = "entities" in result and isinstance(result["entities"], list)

        if has_intent and has_entities:
            print(f"\n✅ Formato compatibile con GChat")
            return True
        else:
            print(f"\n❌ Formato non compatibile")
            return False

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("   TEST COMPATIBILITÀ DEBUG PAGE GChat")
    print("=" * 60)

    # Verifica connessione
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        print(f"✅ Server raggiungibile")
    except:
        print(f"❌ Server non raggiungibile su {BASE_URL}")
        print(f"   Avvia il server con: ./start_server.sh")
        sys.exit(1)

    results = []
    results.append(("Parse Endpoint", test_parse_endpoint()))
    results.append(("Tracker Endpoint", test_tracker_endpoint()))
    results.append(("Workflow Completo", test_debug_workflow()))
    results.append(("Formato Response", test_debug_response_format()))

    print("\n" + "=" * 60)
    print("RIEPILOGO TEST DEBUG PAGE")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotale: {passed}/{total} test passati ({passed*100//total}%)")

    if passed == total:
        print("\n✅ TUTTI I TEST PASSATI - Debug page completamente supportata")
    else:
        print(f"\n⚠️  {total - passed} test falliti - Verificare implementazione")

    print("=" * 60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
