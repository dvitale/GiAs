#!/usr/bin/env python3
"""
Quick benchmark con test ridotti per confronto rapido llama3.1 vs mistral-nemo
"""

import json
import time
import ollama

def quick_test():
    models = ['llama3.1:8b', 'mistral-nemo:latest']

    # Test cases ridotti
    test_cases = [
        ("Ciao", "greet"),
        ("Descrivi il piano A1", "ask_piano_description"),
        ("Stabilimenti prioritari", "ask_priority_establishment"),
        ("Piani per bovini", "search_piani_by_topic"),
        ("Arrivederci", "goodbye")
    ]

    prompt_template = '''Classifica questo messaggio veterinario:
MESSAGGIO: "{user_message}"

Rispondi SOLO con JSON:
{{"intent": "greet|ask_piano_description|ask_priority_establishment|search_piani_by_topic|goodbye|fallback", "confidence": 0.95}}'''

    print("🚀 Quick benchmark: llama3.1 vs mistral-nemo")
    print("=" * 50)

    results = {}

    for model in models:
        print(f"\n🤖 Testing {model}...")
        results[model] = {'times': [], 'correct': 0, 'total': 0}

        for user_msg, expected in test_cases:
            prompt = prompt_template.format(user_message=user_msg)

            start = time.time()
            try:
                response = ollama.chat(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'temperature': 0.1, 'num_predict': 50}
                )
                elapsed = time.time() - start

                # Parse response
                try:
                    data = json.loads(response['message']['content'])
                    predicted = data.get('intent', 'fallback')
                    correct = (predicted == expected)

                    results[model]['times'].append(elapsed)
                    results[model]['total'] += 1
                    if correct:
                        results[model]['correct'] += 1

                    status = "✅" if correct else "❌"
                    print(f"  {user_msg:20} -> {predicted:20} ({elapsed:.2f}s) {status}")

                except json.JSONDecodeError:
                    print(f"  {user_msg:20} -> INVALID_JSON       ({elapsed:.2f}s) ❌")
                    results[model]['times'].append(elapsed)
                    results[model]['total'] += 1

            except Exception as e:
                print(f"  {user_msg:20} -> ERROR: {str(e)[:20]}... ❌")

    # Summary
    print("\n" + "=" * 50)
    print("📊 RISULTATI FINALI")
    print("=" * 50)

    for model in models:
        r = results[model]
        if r['times']:
            accuracy = r['correct'] / r['total'] * 100
            avg_time = sum(r['times']) / len(r['times'])
            print(f"\n{model}:")
            print(f"  Accuratezza: {r['correct']}/{r['total']} ({accuracy:.1f}%)")
            print(f"  Tempo medio: {avg_time:.2f}s")
            print(f"  Tempo totale: {sum(r['times']):.1f}s")

if __name__ == "__main__":
    quick_test()