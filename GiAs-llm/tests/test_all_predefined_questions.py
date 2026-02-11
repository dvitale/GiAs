#!/usr/bin/env python3
"""
Test tutte le 10 domande predefinite di GChat con semantic search.
"""

import requests
import json
import time

API_URL = "http://localhost:5005/webhooks/rest/webhook"
METADATA = {"asl": "AVELLINO", "user_id": "42145"}

PREDEFINED_QUESTIONS = [
    ("d1", "Cosa posso chiederti?"),
    ("d2", "stabilimenti del piano A22"),
    ("d3", "Sulla base del rischio storico chi dovrei controllare per primo?"),
    ("d4", "quale stabilimento dovrei controllare per primo secondo la programmazione?"),
    ("d5", "di cosa tratta il piano A11_F?"),
    ("d6", "quali sono i piani che riguardano allevamenti?"),
    ("d7", "quali sono gli stabilimenti più a rischio per il piano A1?"),
    ("d8", "Quali sono i miei piani in ritardo?"),
    ("d9", "quali sono i piani che riguardano il benessere animale?"),
    ("d10", "suggeriscimi stabilimenti mai controllati ad alto rischio"),
]

def test_question(question_id, question_text):
    """Test singola domanda"""
    print(f"\n{'='*70}")
    print(f"TEST {question_id}: {question_text}")
    print('='*70)

    payload = {
        "sender": f"test_{question_id}",
        "message": question_text,
        "metadata": METADATA
    }

    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload, timeout=30)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                answer = data[0].get('text', '')

                print(f"✅ SUCCESS ({elapsed:.2f}s)")
                print(f"📊 Response length: {len(answer)} chars")

                if len(answer) < 100:
                    print(f"📝 Full response:\n{answer}")
                else:
                    print(f"📝 First 300 chars:\n{answer[:300]}...")

                if "error" in answer.lower() or "non ho capito" in answer.lower():
                    print("⚠️  WARNING: Possibile errore nella risposta")
                    return False

                return True
            else:
                print(f"❌ FAILED: Empty response")
                return False
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False


def main():
    print("\n" + "="*70)
    print("TEST SUITE: Tutte le domande predefinite GChat")
    print("Con semantic search Qdrant + LLM")
    print("="*70)

    results = []

    for question_id, question_text in PREDEFINED_QUESTIONS:
        success = test_question(question_id, question_text)
        results.append((question_id, success))
        time.sleep(1)  # Rate limiting

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nRisultati: {passed}/{total} domande completate con successo\n")

    for question_id, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {question_id}")

    if passed == total:
        print(f"\n🎉 Tutti i test superati ({passed}/{total})!")
    else:
        print(f"\n⚠️  {total - passed} test falliti")

    print("="*70)


if __name__ == "__main__":
    main()
