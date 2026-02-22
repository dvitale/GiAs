#!/usr/bin/env python3
"""
Test client per API GiAs-llm
Simula le chiamate che GChat farebbe al server
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5005"


def test_health():
    """Test health check endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_status():
    """Test status endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Status Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/status")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_webhook_greet():
    """Test webhook con saluto"""
    print("\n" + "=" * 60)
    print("TEST 3: Webhook - Saluto")
    print("=" * 60)

    payload = {
        "sender": "test_user_001",
        "message": "ciao",
        "metadata": {
            "asl": "NA1",
            "uoc": "Veterinaria",
            "user_id": "123",
            "username": "test"
        }
    }

    try:
        print(f"Request: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200 and "result" in response.json()
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_webhook_piano_description():
    """Test chat con richiesta descrizione piano"""
    print("\n" + "=" * 60)
    print("TEST 4: Chat V1 - Descrizione Piano A1")
    print("=" * 60)

    payload = {
        "sender": "test_user_002",
        "message": "quali attività ha il piano A1?",
        "metadata": {
            "asl": "NA1",
            "uoc": "Veterinaria"
        }
    }

    try:
        print(f"Request: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"\nStatus Code: {response.status_code}")
        result = response.json()

        if "result" in result:
            text = result["result"].get("text", "")
            print(f"Response Text (primi 300 caratteri):\n{text[:300]}...")
            return "A1" in text or "piano" in text.lower()
        return False
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_webhook_search():
    """Test chat con ricerca semantica"""
    print("\n" + "=" * 60)
    print("TEST 5: Chat V1 - Ricerca Piani (bovini)")
    print("=" * 60)

    payload = {
        "sender": "test_user_003",
        "message": "cerca piani che riguardano i bovini",
        "metadata": {
            "asl": "NA1"
        }
    }

    try:
        print(f"Request: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"\nStatus Code: {response.status_code}")
        result = response.json()

        if "result" in result:
            text = result["result"].get("text", "")
            print(f"Response Text (primi 300 caratteri):\n{text[:300]}...")
            return True
        return False
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_parse():
    """Test endpoint parse NLU"""
    print("\n" + "=" * 60)
    print("TEST 6: Parse NLU")
    print("=" * 60)

    payload = {
        "sender": "test_user_004",
        "message": "descrivi il piano A32",
        "metadata": {}
    }

    try:
        print(f"Request: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{BASE_URL}/api/v1/parse",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_v1_format():
    """Test formato V1 nativo"""
    print("\n" + "=" * 60)
    print("TEST 7: Formato API V1")
    print("=" * 60)

    payload = {
        "sender": "v1_test",
        "message": "help"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json=payload
        )

        result = response.json()

        is_dict = isinstance(result, dict)
        print(f"✓ Response è dict: {is_dict}")

        if is_dict and "result" in result:
            has_text = "text" in result["result"]
            print(f"✓ result ha campo 'text': {has_text}")

            has_intent = "intent" in result["result"]
            print(f"✓ result ha campo 'intent': {has_intent}")

            has_sender = "sender" in result
            print(f"✓ Response ha campo 'sender': {has_sender}")

            return has_text and has_intent
        return False

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("   TEST CLIENT API GiAs-llm")
    print("   API V1 Nativa")
    print("=" * 60)

    results = []

    print("\n🔍 Verifica connessione al server...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        print(f"✅ Server raggiungibile (porta 5005)")
    except requests.exceptions.ConnectionError:
        print(f"❌ Server non raggiungibile su {BASE_URL}")
        print(f"   Avvia il server con: ./start_server.sh")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Errore connessione: {e}")
        sys.exit(1)

    results.append(("Health Check", test_health()))
    results.append(("Status Endpoint", test_status()))
    results.append(("Chat V1 - Saluto", test_webhook_greet()))
    results.append(("Chat V1 - Piano A1", test_webhook_piano_description()))
    results.append(("Chat V1 - Ricerca", test_webhook_search()))
    results.append(("Parse V1 NLU", test_parse()))
    results.append(("Formato V1", test_v1_format()))

    print("\n" + "=" * 60)
    print("RIEPILOGO TEST")
    print("=" * 60)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1

    total = len(results)
    print(f"\nTotale: {passed}/{total} test passati ({passed*100//total}%)")
    print("=" * 60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
