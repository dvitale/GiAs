#!/usr/bin/env python3
"""
Test script for real LLM integration with Ollama.
Tests both intent classification and response generation.
"""

from llm.client import LLMClient
import json

def test_intent_classification():
    """Test intent classification with real LLM"""
    print("="*60)
    print("TEST 1: Intent Classification with Real LLM")
    print("="*60)

    client = LLMClient(use_real_llm=True)

    test_messages = [
        "ciao",
        "di cosa tratta il piano A1?",
        "quali sono i piani in ritardo?",
        "stabilimenti ad alto rischio",
        "piani sul benessere animale"
    ]

    for msg in test_messages:
        print(f"\n📨 Message: '{msg}'")

        prompt = f"""
**TASK**: Classifica il messaggio utente in uno degli intent disponibili.

**MESSAGGIO UTENTE**: "{msg}"

**INTENT DISPONIBILI**:
1. greet: Saluti (es. "ciao", "buongiorno")
2. goodbye: Saluti finali
3. ask_help: Richieste aiuto
4. ask_piano_description: Descrizione piano (es. "di cosa tratta A1?")
5. ask_piano_stabilimenti: Stabilimenti per piano (include query generiche o attività per piano)
6. search_piani_by_topic: Ricerca per argomento (es. "piani su allevamenti")
7. ask_priority_establishment: Priorità programmazione
8. ask_risk_based_priority: Priorità rischio storico
9. ask_suggest_controls: Suggerimenti controlli
10. ask_delayed_plans: Piani in ritardo
11. fallback: Non classificabile

**EXTRACTION RULES**:
- Se presente codice piano (A1, B2, C3_F, etc.): estrarre come piano_code
- Se ricerca per topic: estrarre keywords come topic
- Formato output: JSON con chiavi: intent, slots, needs_clarification

**OUTPUT** (solo JSON, nessun testo aggiuntivo):
"""

        response = client.query(prompt, temperature=0.1)
        print(f"🤖 LLM Response:\n{response}")

        try:
            parsed = json.loads(response)
            print(f"✅ Valid JSON: intent={parsed.get('intent')}, slots={parsed.get('slots')}")
        except:
            print(f"⚠️  Not valid JSON, but LLM responded")


def test_response_generation():
    """Test response generation with real LLM"""
    print("\n" + "="*60)
    print("TEST 2: Response Generation with Real LLM")
    print("="*60)

    client = LLMClient(use_real_llm=True)

    prompt = """
Sei un assistente esperto nel monitoraggio veterinario della Regione Campania.

**CONTESTO:**
L'utente ha richiesto: piani in ritardo per la sua struttura

**DOMANDA ORIGINALE:**
"Quali sono i miei piani in ritardo?"

**RISULTATI OTTENUTI:**
{
    "piani_in_ritardo": [
        {"piano": "A1", "programmati": 50, "eseguiti": 30, "ritardo_percentuale": 40},
        {"piano": "B2", "programmati": 20, "eseguiti": 10, "ritardo_percentuale": 50},
        {"piano": "C3", "programmati": 15, "eseguiti": 12, "ritardo_percentuale": 20}
    ],
    "totale_piani_ritardo": 3,
    "asl": "AVELLINO"
}

**TASK:**
Genera una risposta chiara, professionale e utile in italiano che:

1. Spiega i risultati in modo comprensibile
2. Evidenzia i piani più critici (B2 con 50% ritardo)
3. Fornisce raccomandazioni operative
4. Proponi 1-2 domande successive utili

**REGOLE:**
- Tono formale ma accessibile
- NON inventare dati non presenti
- Usa terminologia tecnica corretta (ASL, UOC, piani di controllo)
- Formatta usando markdown per leggibilità

**OUTPUT:**
Rispondi SOLO con il testo della risposta finale.
NO prefissi tipo "Ecco la risposta:" o "Sulla base dei dati:".
Inizia direttamente con il contenuto.
"""

    print("\n🤖 Generating response...")
    response = client.query(prompt, temperature=0.5, max_tokens=500)
    print(f"\n{response}")
    print(f"\n✅ Response generated ({len(response)} chars)")


def test_llm_availability():
    """Test if LLM is available"""
    print("\n" + "="*60)
    print("TEST 0: LLM Availability Check")
    print("="*60)

    client = LLMClient(use_real_llm=True)

    is_available = client.ping()
    print(f"LLM Available: {'✅ YES' if is_available else '❌ NO (using stub)'}")
    print(f"Using real LLM: {'✅ YES' if client.use_real_llm else '❌ NO (stub mode)'}")
    print(f"Model: {client.model}")


if __name__ == "__main__":
    test_llm_availability()
    test_intent_classification()
    test_response_generation()

    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
