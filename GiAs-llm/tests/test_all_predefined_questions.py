#!/usr/bin/env python3
"""
Test tutte le 10 domande predefinite di GChat con semantic search.

Eseguire come script:
    python tests/test_all_predefined_questions.py

O con pytest:
    python -m pytest tests/test_all_predefined_questions.py -v
"""

import pytest
import requests
import json
import time

API_URL = "http://localhost:5005/api/v1/chat"
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


def _run_question(question_id, question_text):
    """Esegue una domanda e ritorna (success, answer, elapsed)."""
    payload = {
        "sender": f"test_{question_id}",
        "message": question_text,
        "metadata": METADATA
    }

    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload, timeout=60)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data and "result" in data:
                answer = data["result"].get('text', '')
                has_error = "error" in answer.lower() or "non ho capito" in answer.lower()
                return (not has_error, answer, elapsed)
            return (False, "", elapsed)
        return (False, f"HTTP {response.status_code}", elapsed)

    except requests.exceptions.ConnectionError:
        return (None, "Server non disponibile", 0)  # None = skip
    except Exception as e:
        return (False, str(e), 0)


# ==================================================
# Pytest test parametrizzato
# ==================================================

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize("question_id,question_text", PREDEFINED_QUESTIONS)
def test_predefined_question(question_id, question_text):
    """Test parametrizzato per ogni domanda predefinita."""
    success, answer, elapsed = _run_question(question_id, question_text)

    # Skip se server non disponibile
    if success is None:
        pytest.skip("Server non disponibile - avviare con: scripts/server.sh start")

    print(f"\n[{question_id}] {question_text}")
    print(f"Response ({elapsed:.2f}s, {len(answer)} chars): {answer[:200]}...")

    assert success, f"Risposta non valida o errore: {answer[:500]}"


# ==================================================
# Standalone script mode
# ==================================================

def main():
    """Esecuzione standalone (senza pytest)."""
    print("\n" + "="*70)
    print("TEST SUITE: Tutte le domande predefinite GChat")
    print("Con semantic search Qdrant + LLM")
    print("="*70)

    results = []

    for question_id, question_text in PREDEFINED_QUESTIONS:
        print(f"\n[{question_id}] {question_text}")
        success, answer, elapsed = _run_question(question_id, question_text)

        if success is None:
            print("SKIP: Server non disponibile")
            continue

        if success:
            print(f"PASS ({elapsed:.2f}s, {len(answer)} chars)")
        else:
            print(f"FAIL: {answer[:200]}")

        results.append((question_id, success))
        time.sleep(1)  # Rate limiting

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for _, s in results if s)
    total = len(results)

    print(f"\nRisultati: {passed}/{total} domande completate con successo")

    if passed == total:
        print(f"\nTutti i test superati!")
    else:
        print(f"\n{total - passed} test falliti")

    print("="*70)


if __name__ == "__main__":
    main()
