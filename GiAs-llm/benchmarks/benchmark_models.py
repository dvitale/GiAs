#!/usr/bin/env python3
"""
Benchmark per confrontare prestazioni e accuratezza di intent classification
tra llama3.1:8b e mistral-nemo per il dominio veterinario GiAs-llm
"""

import json
import time
import statistics
from typing import Dict, List, Tuple
import ollama
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    model: str
    prompt: str
    response: str
    response_time: float
    intent: str
    slots: Dict
    needs_clarification: bool
    valid_json: bool
    correct_intent: bool

class ModelBenchmark:
    def __init__(self):
        self.test_cases = [
            # Saluti
            ("Ciao", "greet"),
            ("Salve", "greet"),
            ("Buongiorno", "greet"),

            # Piani specifici
            ("Descrivi il piano A1", "ask_piano_description"),
            ("Cos'è il piano B2?", "ask_piano_description"),
            ("Che attività fa il piano A32", "ask_piano_generic"),
            ("Dove si applica il piano C1", "ask_piano_stabilimenti"),

            # Priorità e ritardi
            ("Quali stabilimenti controllare per primi?", "ask_priority_establishment"),
            ("Stabilimenti più urgenti", "ask_priority_establishment"),
            ("Piani in ritardo", "ask_delayed_plans"),
            ("Controlli con più ritardo", "ask_delayed_plans"),

            # Ricerca per rischio
            ("Stabilimenti ad alto rischio", "ask_risk_based_priority"),
            ("Priorità basate su non conformità", "ask_risk_based_priority"),

            # Ricerca per topic
            ("Piani per bovini", "search_piani_by_topic"),
            ("Controlli su latte e latticini", "search_piani_by_topic"),
            ("Piani salmonella", "search_piani_by_topic"),

            # Aiuto
            ("Che domande posso fare?", "ask_help"),
            ("Cosa sai fare?", "ask_help"),

            # Addio
            ("Arrivederci", "goodbye"),
            ("Bye", "goodbye"),

            # Casi edge
            ("Piano Z999", "ask_piano_generic"),  # Piano inesistente
            ("Controlli su dinosauri", "search_piani_by_topic"),  # Topic irreale
            ("blablabla", "fallback")  # Testo casuale
        ]

        # Prompt per classificazione (copiato da router.py)
        self.classification_prompt = '''Sei un assistente AI per il monitoraggio veterinario della Regione Campania.

Il tuo compito è classificare i messaggi degli operatori ASL e identificare le intenzioni (intent) e le entità (slot).

**INTENTI VALIDI:**
1. greet - saluti iniziali
2. goodbye - saluti finali
3. ask_help - richieste di aiuto o spiegazione funzionalità
4. ask_piano_description - richieste descrizione piano specifico
5. ask_piano_stabilimenti - richieste su dove si applica un piano
6. ask_piano_generic - domande generiche o sulle attività di un piano
8. search_piani_by_topic - ricerca piani per argomento/settore
9. ask_priority_establishment - richieste priorità stabilimenti da controllare
10. ask_risk_based_priority - priorità basate su analisi rischio storico
11. ask_suggest_controls - suggerimenti per controlli
12. ask_delayed_plans - piani in ritardo nella programmazione
13. fallback - tutto il resto

**ENTITÀ DA ESTRARRE:**
- piano_code: codice piano (es. A1, B2, C12)
- topic: argomento/settore (bovini, latte, salmonella, etc.)
- asl: codice ASL se specificato

**MESSAGGIO UTENTE:** "{user_message}"

Rispondi SOLO con un JSON valido nel formato:
{{"intent": "nome_intent", "slots": {{"campo": "valore"}}, "needs_clarification": false}}'''

    def query_model(self, model: str, prompt: str) -> Tuple[str, float]:
        """Interroga un modello e misura il tempo di risposta"""
        start_time = time.time()
        try:
            response = ollama.chat(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1}  # Bassa temperature per consistenza
            )
            response_time = time.time() - start_time
            return response['message']['content'].strip(), response_time
        except Exception as e:
            response_time = time.time() - start_time
            return f"ERROR: {str(e)}", response_time

    def parse_intent_response(self, response: str) -> Tuple[str, Dict, bool, bool]:
        """Parsa la risposta JSON del modello"""
        try:
            data = json.loads(response)
            intent = data.get('intent', 'fallback')
            slots = data.get('slots', {})
            needs_clarification = data.get('needs_clarification', False)
            return intent, slots, needs_clarification, True
        except:
            return 'fallback', {}, False, False

    def run_benchmark(self, models: List[str]) -> Dict[str, List[BenchmarkResult]]:
        """Esegue il benchmark su tutti i modelli"""
        results = {model: [] for model in models}

        print("🚀 Avvio benchmark intent classification...")
        print(f"📋 Test cases: {len(self.test_cases)}")
        print(f"🤖 Modelli: {', '.join(models)}")
        print("=" * 60)

        for i, (user_message, expected_intent) in enumerate(self.test_cases, 1):
            print(f"\n[{i:2d}/{len(self.test_cases)}] Test: '{user_message}' (expect: {expected_intent})")

            for model in models:
                prompt = self.classification_prompt.format(user_message=user_message)
                response, response_time = self.query_model(model, prompt)
                intent, slots, needs_clarification, valid_json = self.parse_intent_response(response)
                correct_intent = (intent == expected_intent)

                result = BenchmarkResult(
                    model=model,
                    prompt=user_message,
                    response=response,
                    response_time=response_time,
                    intent=intent,
                    slots=slots,
                    needs_clarification=needs_clarification,
                    valid_json=valid_json,
                    correct_intent=correct_intent
                )

                results[model].append(result)

                # Feedback immediato
                status = "✅" if correct_intent else "❌"
                json_status = "📝" if valid_json else "🚫"
                print(f"  {model:15} {status} {intent:25} ({response_time:.2f}s) {json_status}")

        return results

    def analyze_results(self, results: Dict[str, List[BenchmarkResult]]) -> None:
        """Analizza e stampa i risultati del benchmark"""
        print("\n" + "=" * 80)
        print("📊 ANALISI RISULTATI")
        print("=" * 80)

        for model in results.keys():
            model_results = results[model]

            # Metriche di accuratezza
            total_tests = len(model_results)
            correct_intents = sum(1 for r in model_results if r.correct_intent)
            valid_jsons = sum(1 for r in model_results if r.valid_json)

            # Metriche di prestazioni
            response_times = [r.response_time for r in model_results]
            avg_time = statistics.mean(response_times)
            median_time = statistics.median(response_times)
            min_time = min(response_times)
            max_time = max(response_times)

            print(f"\n🤖 {model.upper()}")
            print("-" * 40)
            print(f"📈 Accuratezza intent:     {correct_intents}/{total_tests} ({correct_intents/total_tests*100:.1f}%)")
            print(f"📝 JSON validi:           {valid_jsons}/{total_tests} ({valid_jsons/total_tests*100:.1f}%)")
            print(f"⚡ Tempo medio:           {avg_time:.2f}s")
            print(f"📊 Tempo mediano:         {median_time:.2f}s")
            print(f"🏃 Tempo minimo:          {min_time:.2f}s")
            print(f"🐌 Tempo massimo:         {max_time:.2f}s")

            # Errori più comuni
            wrong_predictions = [r for r in model_results if not r.correct_intent]
            if wrong_predictions:
                print(f"❌ Errori comuni:")
                error_counts = {}
                for r in wrong_predictions:
                    key = f"{r.prompt} -> {r.intent}"
                    error_counts[key] = error_counts.get(key, 0) + 1

                for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                    print(f"   • {error}")

    def save_detailed_results(self, results: Dict[str, List[BenchmarkResult]], filename: str) -> None:
        """Salva risultati dettagliati in JSON"""
        detailed_results = {}
        for model, model_results in results.items():
            detailed_results[model] = []
            for r in model_results:
                detailed_results[model].append({
                    'prompt': r.prompt,
                    'expected_intent': next(expected for prompt, expected in self.test_cases if prompt == r.prompt),
                    'predicted_intent': r.intent,
                    'slots': r.slots,
                    'response_time': r.response_time,
                    'valid_json': r.valid_json,
                    'correct_intent': r.correct_intent,
                    'raw_response': r.response
                })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Risultati dettagliati salvati in: {filename}")

def main():
    benchmark = ModelBenchmark()
    models = ['llama3.1:8b', 'mistral-nemo:latest']

    print("🔍 Verifica modelli disponibili...")
    available_models = []
    for model in models:
        try:
            ollama.show(model)
            available_models.append(model)
            print(f"✅ {model}")
        except:
            print(f"❌ {model} - non disponibile")

    if not available_models:
        print("🚫 Nessun modello disponibile per il benchmark")
        return

    # Esegui benchmark
    results = benchmark.run_benchmark(available_models)

    # Analizza risultati
    benchmark.analyze_results(results)

    # Salva risultati dettagliati
    benchmark.save_detailed_results(results, 'benchmark_results.json')

    print("\n🎯 Benchmark completato!")

if __name__ == "__main__":
    main()