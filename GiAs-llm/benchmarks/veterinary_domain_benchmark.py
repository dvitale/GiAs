#!/usr/bin/env python3
"""
Benchmark specifico per il dominio veterinario ASL
Confronta Almawave/Velvet, Mistral-Nemo e LLaMA 3.1
"""

import json
import time
import statistics
import ollama

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠️ psutil non installato, utilizzo metrica memoria limitata")
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class VeterinaryBenchmarkResult:
    model: str
    test_case: str
    expected_intent: str
    predicted_intent: str
    response_time: float
    memory_usage_mb: float
    correct_intent: bool
    valid_json: bool
    confidence_score: float
    italian_quality: int  # 1-5 score per qualità italiano
    domain_accuracy: int  # 1-5 score per accuratezza dominio

class VeterinaryDomainBenchmark:
    def __init__(self):
        """Test cases specifici per il dominio veterinario ASL Campania"""
        self.veterinary_test_cases = [
            # Saluti in italiano
            ("Buongiorno dottore", "greet"),
            ("Salve, come posso iniziare?", "greet"),

            # Piani veterinari specifici
            ("Descrivi il piano A1 per la TBC bovina", "ask_piano_description"),
            ("Cos'è il piano B2 sulla biosicurezza?", "ask_piano_description"),
            ("Piano A14 farmacosorveglianza", "ask_piano_description"),

            # Stabilimenti e controlli
            ("Stabilimenti controllati per il piano A3 salmonella", "ask_piano_stabilimenti"),
            ("Dove si applica il piano A8 anagrafe zootecnica?", "ask_piano_stabilimenti"),

            # Priorità e rischio - terminologia italiana specifica
            ("Quali stabilimenti più a rischio per il piano A1?", "ask_risk_based_priority"),
            ("Priorità controlli basate su non conformità", "ask_risk_based_priority"),
            ("Stabilimenti con maggiori NC storiche", "ask_risk_based_priority"),

            # Ricerca per settore zootecnico
            ("Piani per allevamenti bovini", "search_piani_by_topic"),
            ("Controlli su latte e latticini", "search_piani_by_topic"),
            ("Piani di monitoraggio salmonella", "search_piani_by_topic"),
            ("Biosicurezza negli allevamenti suini", "search_piani_by_topic"),

            # Ritardi programmazione
            ("Piani in ritardo nella mia ASL", "ask_delayed_plans"),
            ("Il piano A1 è in ritardo?", "check_if_plan_delayed"),

            # Terminologia veterinaria specifica
            ("Non conformità gravi vs non gravi", "ask_help"),
            ("OSA mai controllati", "ask_priority_establishment"),
            ("Controlli ufficiali programmati", "ask_delayed_plans"),

            # Casi edge con terminologia mista
            ("Piano per controllo residui farmacologici", "search_piani_by_topic"),
            ("Benessere animale negli allevamenti", "search_piani_by_topic"),
            ("Audit negli stabilimenti 853/04", "search_piani_by_topic"),

            # Addii italiani
            ("Grazie dottore, arrivederci", "goodbye"),
            ("Buona giornata", "goodbye")
        ]

        # Prompt ottimizzato per il dominio veterinario
        self.classification_prompt = '''Sei un assistente AI specializzato nel monitoraggio veterinario per la Regione Campania.

Il tuo compito è classificare messaggi degli operatori ASL (Aziende Sanitarie Locali) che si occupano di:
- Controlli veterinari ufficiali
- Piani di monitoraggio sanitario
- Gestione stabilimenti alimentari (OSA - Operatori Settore Alimentare)
- Anagrafe zootecnica e benessere animale
- Biosicurezza negli allevamenti
- Non conformità (NC) e farmacosorveglianza

**CONTESTO TECNICO:**
- Piano: codice alfanumerico (A1, B2, C3, ecc.) per piani di controllo specifici
- OSA: Operatori del Settore Alimentare (stabilimenti da controllare)
- NC: Non Conformità (gravi o non gravi)
- ASL: Azienda Sanitaria Locale
- UOC/UOS: Unità Operative di controllo

**INTENTI DISPONIBILI:**
1. greet - saluti
2. goodbye - saluti finali
3. ask_help - richieste aiuto
4. ask_piano_description - descrizione piano specifico
5. ask_piano_stabilimenti - stabilimenti controllati per piano
6. ask_piano_generic - domande generiche o sulle attività di un piano
8. search_piani_by_topic - ricerca piani per settore (bovini, suini, latte, etc.)
9. ask_priority_establishment - priorità controlli per programmazione
10. ask_risk_based_priority - priorità basate su rischio/NC storiche
11. ask_suggest_controls - suggerimenti controlli
12. ask_delayed_plans - piani in ritardo
13. check_if_plan_delayed - verifica ritardo piano specifico
14. ask_establishment_history - storico controlli stabilimento
15. fallback - altro

**MESSAGGIO:** "{user_message}"

Rispondi SOLO con JSON valido:
{{"intent": "nome_intent", "slots": {{"piano_code": "A1"}}, "confidence": 0.95}}'''

    def query_model_with_memory_monitoring(self, model: str, prompt: str) -> Tuple[str, float, float]:
        """Query modello monitorando memoria"""
        if HAS_PSUTIL:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        else:
            initial_memory = 0

        start_time = time.time()
        try:
            response = ollama.chat(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.1}
            )
            response_time = time.time() - start_time

            if HAS_PSUTIL:
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_used = final_memory - initial_memory
            else:
                memory_used = 0.0

            return response['message']['content'].strip(), response_time, memory_used

        except Exception as e:
            response_time = time.time() - start_time
            return f"ERROR: {str(e)}", response_time, 0.0

    def evaluate_italian_quality(self, response: str, test_case: str) -> int:
        """Valuta qualità dell'italiano (1-5)"""
        # Criteri di valutazione per l'italiano
        italian_indicators = {
            'good': ['veterinario', 'stabilimento', 'controllo', 'monitoraggio', 'conformità', 'allevamento'],
            'technical': ['ASL', 'OSA', 'UOC', 'piano', 'NC', 'farmacosorveglianza'],
            'formal': ['dottore', 'salve', 'buongiorno', 'arrivederci', 'grazie']
        }

        response_lower = response.lower()
        score = 3  # Base

        # Bonus per terminologia tecnica italiana
        for term in italian_indicators['technical']:
            if term.lower() in response_lower:
                score += 0.2

        # Bonus per cortesia italiana
        for term in italian_indicators['formal']:
            if term.lower() in response_lower:
                score += 0.1

        # Penalty per anglicismi
        anglicisms = ['monitoring', 'control', 'establishment', 'compliance']
        for term in anglicisms:
            if term in response_lower:
                score -= 0.3

        return max(1, min(5, int(score)))

    def evaluate_domain_accuracy(self, predicted_intent: str, expected_intent: str,
                                response: str, test_case: str) -> int:
        """Valuta accuratezza del dominio veterinario (1-5)"""
        score = 3  # Base

        # Accuratezza intent
        if predicted_intent == expected_intent:
            score += 2
        elif predicted_intent in ['fallback', 'ask_help'] and expected_intent != 'fallback':
            score -= 1

        # Riconoscimento terminologia veterinaria
        vet_terms = ['piano', 'stabilimento', 'controllo', 'ASL', 'OSA', 'monitoraggio',
                    'veterinario', 'allevamento', 'biosicurezza', 'conformità']

        response_lower = response.lower()
        test_lower = test_case.lower()

        recognized_terms = sum(1 for term in vet_terms if term in test_lower and term in response_lower)
        score += min(1, recognized_terms * 0.2)

        return max(1, min(5, int(score)))

    def parse_response(self, response: str) -> Tuple[str, float, bool]:
        """Parsa risposta JSON del modello"""
        try:
            data = json.loads(response)
            intent = data.get('intent', 'fallback')
            confidence = data.get('confidence', 0.5)
            return intent, confidence, True
        except:
            return 'fallback', 0.0, False

    def run_comprehensive_benchmark(self, models: List[str]) -> Dict[str, List[VeterinaryBenchmarkResult]]:
        """Esegue benchmark completo per il dominio veterinario"""
        results = {model: [] for model in models}

        print("🩺 BENCHMARK DOMINIO VETERINARIO ASL")
        print("=" * 60)
        print(f"📋 Test cases: {len(self.veterinary_test_cases)}")
        print(f"🤖 Modelli: {', '.join(models)}")
        print("=" * 60)

        for i, (test_case, expected_intent) in enumerate(self.veterinary_test_cases, 1):
            print(f"\n[{i:2d}/{len(self.veterinary_test_cases)}] 🧪 {test_case}")
            print(f"   Atteso: {expected_intent}")

            for model in models:
                prompt = self.classification_prompt.format(user_message=test_case)
                response, response_time, memory_used = self.query_model_with_memory_monitoring(model, prompt)

                predicted_intent, confidence, valid_json = self.parse_response(response)
                correct_intent = (predicted_intent == expected_intent)

                italian_quality = self.evaluate_italian_quality(response, test_case)
                domain_accuracy = self.evaluate_domain_accuracy(predicted_intent, expected_intent, response, test_case)

                result = VeterinaryBenchmarkResult(
                    model=model,
                    test_case=test_case,
                    expected_intent=expected_intent,
                    predicted_intent=predicted_intent,
                    response_time=response_time,
                    memory_usage_mb=memory_used,
                    correct_intent=correct_intent,
                    valid_json=valid_json,
                    confidence_score=confidence,
                    italian_quality=italian_quality,
                    domain_accuracy=domain_accuracy
                )

                results[model].append(result)

                # Feedback immediato
                status = "✅" if correct_intent else "❌"
                json_status = "📝" if valid_json else "🚫"
                print(f"   {model:20} {status} {predicted_intent:25} ({response_time:.2f}s, {memory_used:+.1f}MB) {json_status}")

        return results

    def analyze_veterinary_results(self, results: Dict[str, List[VeterinaryBenchmarkResult]]) -> None:
        """Analisi dettagliata risultati per dominio veterinario"""
        print("\n" + "=" * 80)
        print("🩺 ANALISI RISULTATI DOMINIO VETERINARIO")
        print("=" * 80)

        for model in results.keys():
            model_results = results[model]

            print(f"\n🤖 {model.upper()}")
            print("-" * 50)

            # Metriche di accuratezza
            total_tests = len(model_results)
            correct_intents = sum(1 for r in model_results if r.correct_intent)
            valid_jsons = sum(1 for r in model_results if r.valid_json)

            # Metriche performance
            response_times = [r.response_time for r in model_results]
            memory_usages = [r.memory_usage_mb for r in model_results if r.memory_usage_mb > 0]

            # Metriche dominio specifico
            italian_scores = [r.italian_quality for r in model_results]
            domain_scores = [r.domain_accuracy for r in model_results]
            confidence_scores = [r.confidence_score for r in model_results if r.confidence_score > 0]

            print(f"📊 **ACCURATEZZA INTENT VETERINARI**")
            print(f"   Corretti: {correct_intents}/{total_tests} ({correct_intents/total_tests*100:.1f}%)")
            print(f"   JSON validi: {valid_jsons}/{total_tests} ({valid_jsons/total_tests*100:.1f}%)")

            print(f"⚡ **PRESTAZIONI**")
            if response_times:
                print(f"   Tempo medio: {statistics.mean(response_times):.2f}s")
                print(f"   Tempo mediano: {statistics.median(response_times):.2f}s")
                print(f"   Range: {min(response_times):.2f}s - {max(response_times):.2f}s")

            print(f"💾 **MEMORIA**")
            if memory_usages:
                avg_memory = statistics.mean(memory_usages)
                print(f"   Uso medio: {avg_memory:.1f}MB per query")
                print(f"   Picco massimo: {max(memory_usages):.1f}MB")

            print(f"🇮🇹 **QUALITÀ ITALIANO**")
            avg_italian = statistics.mean(italian_scores)
            print(f"   Score medio: {avg_italian:.1f}/5.0")
            print(f"   Distribuzione: {[italian_scores.count(i) for i in range(1,6)]}")

            print(f"🩺 **ACCURATEZZA DOMINIO VETERINARIO**")
            avg_domain = statistics.mean(domain_scores)
            print(f"   Score medio: {avg_domain:.1f}/5.0")
            print(f"   Distribuzione: {[domain_scores.count(i) for i in range(1,6)]}")

            if confidence_scores:
                print(f"🎯 **CONFIDENZA**")
                print(f"   Media: {statistics.mean(confidence_scores):.2f}")

            # Analisi errori per categoria
            errors_by_category = {}
            for r in model_results:
                if not r.correct_intent:
                    category = r.expected_intent
                    if category not in errors_by_category:
                        errors_by_category[category] = []
                    errors_by_category[category].append(r.test_case)

            if errors_by_category:
                print(f"❌ **ERRORI PER CATEGORIA**")
                for category, tests in errors_by_category.items():
                    print(f"   {category}: {len(tests)} errori")

    def generate_comprehensive_report(self, results: Dict[str, List[VeterinaryBenchmarkResult]]) -> None:
        """Genera report comparativo finale"""
        print("\n" + "=" * 80)
        print("📊 REPORT COMPARATIVO FINALE - DOMINIO VETERINARIO ASL")
        print("=" * 80)

        summary_data = []
        for model, model_results in results.items():
            correct_intents = sum(1 for r in model_results if r.correct_intent)
            total = len(model_results)
            response_times = [r.response_time for r in model_results]
            memory_usages = [r.memory_usage_mb for r in model_results if r.memory_usage_mb > 0]
            italian_scores = [r.italian_quality for r in model_results]
            domain_scores = [r.domain_accuracy for r in model_results]

            summary_data.append({
                'model': model,
                'accuracy': correct_intents/total*100,
                'avg_time': statistics.mean(response_times),
                'avg_memory': statistics.mean(memory_usages) if memory_usages else 0,
                'italian_quality': statistics.mean(italian_scores),
                'domain_accuracy': statistics.mean(domain_scores)
            })

        # Ordina per accuratezza intent
        summary_data.sort(key=lambda x: x['accuracy'], reverse=True)

        print(f"{'MODELLO':<20} {'INTENT%':<8} {'TEMPO':<8} {'MEMORIA':<10} {'ITALIANO':<9} {'DOMINIO':<8}")
        print("-" * 80)
        for data in summary_data:
            print(f"{data['model']:<20} {data['accuracy']:<7.1f}% {data['avg_time']:<7.2f}s {data['avg_memory']:<9.1f}MB {data['italian_quality']:<8.1f}/5 {data['domain_accuracy']:<7.1f}/5")

        print(f"\n🏆 **RACCOMANDAZIONI PER DOMINIO VETERINARIO ASL:**")

        # Determina il migliore per categoria
        best_accuracy = max(summary_data, key=lambda x: x['accuracy'])
        best_speed = min(summary_data, key=lambda x: x['avg_time'])
        best_italian = max(summary_data, key=lambda x: x['italian_quality'])
        best_domain = max(summary_data, key=lambda x: x['domain_accuracy'])

        print(f"   🎯 Migliore accuratezza intent: **{best_accuracy['model']}** ({best_accuracy['accuracy']:.1f}%)")
        print(f"   ⚡ Più veloce: **{best_speed['model']}** ({best_speed['avg_time']:.2f}s)")
        print(f"   🇮🇹 Migliore italiano: **{best_italian['model']}** ({best_italian['italian_quality']:.1f}/5)")
        print(f"   🩺 Migliore dominio veterinario: **{best_domain['model']}** ({best_domain['domain_accuracy']:.1f}/5)")

    def save_detailed_results(self, results: Dict[str, List[VeterinaryBenchmarkResult]], filename: str) -> None:
        """Salva risultati dettagliati"""
        detailed_results = {}
        for model, model_results in results.items():
            detailed_results[model] = []
            for r in model_results:
                detailed_results[model].append({
                    'test_case': r.test_case,
                    'expected_intent': r.expected_intent,
                    'predicted_intent': r.predicted_intent,
                    'response_time': r.response_time,
                    'memory_usage_mb': r.memory_usage_mb,
                    'correct_intent': r.correct_intent,
                    'valid_json': r.valid_json,
                    'confidence_score': r.confidence_score,
                    'italian_quality': r.italian_quality,
                    'domain_accuracy': r.domain_accuracy
                })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Risultati dettagliati salvati in: {filename}")

def main():
    benchmark = VeterinaryDomainBenchmark()
    models = ['Almawave/Velvet:latest', 'mistral-nemo:latest', 'llama3.1:8b']

    print("🔍 Verifica modelli disponibili...")
    available_models = []
    for model in models:
        try:
            ollama.show(model)
            available_models.append(model)
            print(f"✅ {model}")
        except:
            print(f"❌ {model} - non disponibile")

    if len(available_models) < 2:
        print("🚫 Servono almeno 2 modelli per il confronto")
        return

    # Esegui benchmark veterinario
    results = benchmark.run_comprehensive_benchmark(available_models)

    # Analizza risultati
    benchmark.analyze_veterinary_results(results)
    benchmark.generate_comprehensive_report(results)

    # Salva risultati
    benchmark.save_detailed_results(results, 'veterinary_domain_benchmark.json')

    print(f"\n🎯 Benchmark dominio veterinario completato!")
    print(f"   Testati: {len(available_models)} modelli")
    print(f"   Test cases: {len(benchmark.veterinary_test_cases)}")
    print(f"   Focus: ASL Campania, terminologia italiana, accuratezza dominio")

if __name__ == "__main__":
    main()