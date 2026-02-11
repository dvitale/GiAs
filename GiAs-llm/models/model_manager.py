#!/usr/bin/env python3
"""
Utility per gestire la configurazione dei modelli GiAs-llm
"""

import sys
import os
from configs.config import AppConfig, ModelConfig, set_model, get_available_models_summary

def print_current_config():
    """Stampa la configurazione corrente"""
    AppConfig.print_config()

def list_models():
    """Lista i modelli disponibili"""
    print(get_available_models_summary())

def switch_model(model_key: str):
    """Cambia il modello attivo"""
    if set_model(model_key):
        print(f"✅ Modello cambiato a: {model_key}")
        print(f"   Nome: {AppConfig.get_model_name()}")
        print("   💡 Riavvia il server per applicare i cambiamenti")

        # Aggiorna variabile ambiente per la sessione corrente
        os.environ["GIAS_LLM_MODEL"] = model_key
    else:
        print(f"❌ Modello '{model_key}' non valido")
        print("Modelli disponibili:")
        list_models()

def benchmark_current_model():
    """Esegue un quick test del modello corrente"""
    print(f"🚀 Test rapido per {AppConfig.LLM_MODEL}...")

    from llm.client import LLMClient
    client = LLMClient()

    test_prompt = 'Classifica: "Ciao". Rispondi: {"intent":"greet"}'

    try:
        import time
        start = time.time()
        response = client.query(test_prompt, temperature=0.1)
        elapsed = time.time() - start

        print(f"✅ Test completato in {elapsed:.2f}s")
        print(f"📝 Risposta: {response[:100]}...")

    except Exception as e:
        print(f"❌ Errore nel test: {e}")

def main():
    """CLI per gestione modelli"""
    if len(sys.argv) < 2:
        print("🤖 GiAs-llm Model Manager")
        print("=" * 40)
        print("Comandi disponibili:")
        print("  config           - Mostra configurazione corrente")
        print("  list             - Lista modelli disponibili")
        print("  use <model>      - Cambia modello (mistral-nemo|llama3.1)")
        print("  test             - Test rapido modello corrente")
        print("")
        print("Esempi:")
        print("  python3 model_manager.py config")
        print("  python3 model_manager.py use llama3.1")
        print("  python3 model_manager.py use mistral-nemo")
        return

    command = sys.argv[1].lower()

    if command == "config":
        print_current_config()

    elif command == "list":
        list_models()

    elif command == "use":
        if len(sys.argv) < 3:
            print("❌ Specifica il modello da usare")
            list_models()
        else:
            switch_model(sys.argv[2])

    elif command == "test":
        benchmark_current_model()

    else:
        print(f"❌ Comando '{command}' non riconosciuto")
        print("Usa: config, list, use <model>, test")

if __name__ == "__main__":
    main()