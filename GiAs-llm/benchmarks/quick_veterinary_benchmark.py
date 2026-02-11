#!/usr/bin/env python3
"""
Quick benchmark per confrontare i 3 modelli LLM del dominio veterinario
"""
import json
import time
import ollama
from datetime import datetime

def query_model(model: str, prompt: str) -> tuple:
    """Query singolo modello con timing"""
    start_time = time.time()
    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}
        )
        response_time = time.time() - start_time
        return response['message']['content'].strip(), response_time, True
    except Exception as e:
        response_time = time.time() - start_time
        return f"ERROR: {str(e)}", response_time, False

def extract_intent(response: str) -> str:
    """Estrae intent da risposta JSON"""
    try:
        # Cerca JSON nella risposta
        if '{' in response:
            start = response.find('{')
            end = response.rfind('}') + 1
            json_str = response[start:end]
            data = json.loads(json_str)
            return data.get('intent', 'parse_error')
        return 'no_json'
    except:
        return 'json_error'

def main():
    print("🩺 QUICK BENCHMARK VETERINARIO - 3 MODELLI LLM")
    print("=" * 60)

    # Test cases ridotti ma rappresentativi
    test_cases = [
        ("Buongiorno dottore", "greet"),
        ("Stabilimenti più a rischio per il piano A1?", "ask_risk_based_priority"),
        ("Di cosa tratta il piano A3?", "ask_piano_description"),
        ("Piani per allevamenti bovini", "search_piani_by_topic"),
        ("Chi controllare oggi?", "ask_priority_establishment")
    ]

    models = [
        "Almawave/Velvet:latest",
        "mistral-nemo:latest",
        "llama3.1:8b"
    ]

    # Prompt di classificazione semplificato
    classification_prompt = """Sei un assistente veterinario ASL. Classifica questo messaggio:

INTENT VALIDI:
- greet: saluti
- ask_piano_description: descrizione piano specifico
- ask_risk_based_priority: stabilimenti più a rischio
- search_piani_by_topic: cerca piani per argomento
- ask_priority_establishment: priorità controlli
- fallback: altro

MESSAGGIO: "{message}"

Rispondi SOLO con JSON: {{"intent": "nome_intent"}}"""

    results = {}

    # Test ogni modello
    for model in models:
        print(f"\n🤖 Testando: {model}")
        model_results = []

        try:
            # Verifica che il modello sia disponibile
            ollama.show(model)
        except:
            print(f"❌ Modello {model} non disponibile")
            continue

        for test_case, expected in test_cases:
            print(f"   📝 '{test_case[:40]}...'")

            prompt = classification_prompt.format(message=test_case)
            response, response_time, success = query_model(model, prompt)

            if success:
                predicted = extract_intent(response)
                correct = (predicted == expected)
                model_results.append({
                    'test': test_case,
                    'expected': expected,
                    'predicted': predicted,
                    'correct': correct,
                    'time': response_time
                })
                status = "✅" if correct else "❌"
                print(f"      {status} {predicted} ({response_time:.1f}s)")
            else:
                print(f"      ❌ Errore: {response}")

        results[model] = model_results

    # Report finale
    print("\n" + "=" * 60)
    print("📊 RISULTATI FINALI")
    print("=" * 60)

    for model, model_results in results.items():
        if not model_results:
            continue

        correct_count = sum(1 for r in model_results if r['correct'])
        total = len(model_results)
        avg_time = sum(r['time'] for r in model_results) / total
        accuracy = (correct_count / total) * 100

        print(f"\n🤖 {model}")
        print(f"   📊 Accuratezza: {accuracy:.1f}% ({correct_count}/{total})")
        print(f"   ⚡ Tempo medio: {avg_time:.1f}s")

        # Mostra errori
        errors = [r for r in model_results if not r['correct']]
        if errors:
            print(f"   ❌ Errori:")
            for err in errors:
                print(f"      '{err['test'][:30]}...' → {err['predicted']} (atteso: {err['expected']})")

    print(f"\n🕒 Benchmark completato: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()