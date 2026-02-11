#!/usr/bin/env python3
"""
Benchmark specifico per l'utilizzo di memoria dei 3 modelli LLM
"""
import subprocess
import time
import ollama
from datetime import datetime

def get_memory_usage():
    """Ottiene utilizzo memoria di sistema in MB"""
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        mem_line = lines[1].split()
        used = int(mem_line[2])
        available = int(mem_line[6])
        return used, available
    except:
        return 0, 0

def get_ollama_process_memory():
    """Ottiene memoria utilizzata dai processi Ollama"""
    try:
        result = subprocess.run(['pgrep', '-f', 'ollama'], capture_output=True, text=True)
        if not result.stdout.strip():
            return 0

        pids = result.stdout.strip().split('\n')
        total_memory = 0

        for pid in pids:
            try:
                mem_result = subprocess.run(['ps', '-p', pid, '-o', 'rss='], capture_output=True, text=True)
                if mem_result.stdout.strip():
                    memory_kb = int(mem_result.stdout.strip())
                    total_memory += memory_kb / 1024  # Convert to MB
            except:
                continue

        return total_memory
    except:
        return 0

def test_model_memory_usage(model_name: str):
    """Testa utilizzo memoria per un modello specifico"""
    print(f"\n🧠 Test memoria per: {model_name}")

    # Memoria prima del caricamento
    used_before, available_before = get_memory_usage()
    ollama_before = get_ollama_process_memory()

    print(f"   📊 Memoria sistema prima: {used_before}MB usata, {available_before}MB disponibile")
    print(f"   🤖 Memoria Ollama prima: {ollama_before:.1f}MB")

    # Carica il modello con una query semplice
    try:
        print(f"   ⏳ Caricamento modello...")
        start_time = time.time()

        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': 'Test'}],
            options={'temperature': 0.1}
        )

        load_time = time.time() - start_time

        # Memoria dopo il caricamento
        time.sleep(2)  # Attendi stabilizzazione
        used_after, available_after = get_memory_usage()
        ollama_after = get_ollama_process_memory()

        # Calcola differenze
        system_memory_increase = used_after - used_before
        ollama_memory_increase = ollama_after - ollama_before
        available_decrease = available_before - available_after

        print(f"   ✅ Modello caricato in {load_time:.1f}s")
        print(f"   📊 Memoria sistema dopo: {used_after}MB usata, {available_after}MB disponibile")
        print(f"   🤖 Memoria Ollama dopo: {ollama_after:.1f}MB")
        print(f"   📈 Incremento memoria sistema: {system_memory_increase}MB")
        print(f"   📈 Incremento memoria Ollama: {ollama_memory_increase:.1f}MB")
        print(f"   📉 Memoria disponibile ridotta di: {available_decrease}MB")

        return {
            'model': model_name,
            'load_time': load_time,
            'system_memory_increase': system_memory_increase,
            'ollama_memory_increase': ollama_memory_increase,
            'available_memory_decrease': available_decrease,
            'success': True
        }

    except Exception as e:
        print(f"   ❌ Errore caricamento: {e}")
        return {
            'model': model_name,
            'error': str(e),
            'success': False
        }

def main():
    print("🧠 BENCHMARK MEMORIA - MODELLI LLM VETERINARIO")
    print("=" * 60)
    print(f"🕒 Inizio test: {datetime.now().strftime('%H:%M:%S')}")

    models = [
        "llama3.1:8b",         # Più piccolo
        "mistral-nemo:latest", # Medio
        "Almawave/Velvet:latest"  # Più grande
    ]

    results = []

    # Prima ferma tutti i modelli
    print(f"\n🛑 Fermando tutti i modelli attivi...")
    try:
        subprocess.run(['killall', 'ollama'], capture_output=True)
        time.sleep(3)
    except:
        pass

    # Riavvia ollama serve
    print(f"🚀 Riavviando Ollama serve...")
    ollama_process = subprocess.Popen(['ollama', 'serve'],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
    time.sleep(5)

    # Test memoria iniziale
    initial_used, initial_available = get_memory_usage()
    print(f"📊 Memoria iniziale sistema: {initial_used}MB usata, {initial_available}MB disponibile")

    # Test ogni modello
    for model in models:
        try:
            result = test_model_memory_usage(model)
            results.append(result)

            # Breve pausa tra test
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Test interrotto dall'utente")
            break

    # Report finale
    print("\n" + "=" * 60)
    print("📊 REPORT MEMORIA FINALE")
    print("=" * 60)

    successful_results = [r for r in results if r.get('success', False)]

    if successful_results:
        print(f"\n{'Modello':<25} {'Caricamento':<12} {'RAM Ollama':<12} {'RAM Sistema':<12}")
        print("-" * 65)

        for result in successful_results:
            model_short = result['model'].split(':')[0].replace('Almawave/', '')
            print(f"{model_short:<25} {result['load_time']:<11.1f}s {result['ollama_memory_increase']:<11.1f}MB {result['system_memory_increase']:<11}MB")

        # Statistiche comparative
        print(f"\n📈 CONFRONTO PRESTAZIONI:")

        fastest = min(successful_results, key=lambda x: x['load_time'])
        least_memory = min(successful_results, key=lambda x: x['ollama_memory_increase'])
        most_available = min(successful_results, key=lambda x: x['available_memory_decrease'])

        print(f"⚡ Più veloce: {fastest['model']} ({fastest['load_time']:.1f}s)")
        print(f"💾 Meno memoria Ollama: {least_memory['model']} ({least_memory['ollama_memory_increase']:.1f}MB)")
        print(f"🆓 Impatto minore su memoria disponibile: {most_available['model']} ({most_available['available_memory_decrease']}MB)")

    else:
        print("❌ Nessun test completato con successo")

    # Cleanup
    try:
        ollama_process.terminate()
    except:
        pass

    print(f"\n🕒 Test completato: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()