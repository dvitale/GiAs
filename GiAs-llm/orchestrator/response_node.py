"""
Nodo response_generator per il grafo LangGraph.

Genera la risposta finale a partire dal tool_output, usando
risposte dirette per intent semplici e LLM per dati complessi.
"""

import re
import logging
from typing import Dict, Any

from .followup_suggestions import FollowUpSuggestionEngine

_followup_engine = FollowUpSuggestionEngine()

logger = logging.getLogger(__name__)


RESPONSE_SYSTEM_PROMPT = """Sei un assistente esperto nel monitoraggio veterinario della Regione Campania.

**TASK:**
Genera una risposta chiara, professionale e utile in italiano che:

1. **Spiega i risultati** in modo comprensibile:
   - Sintetizza le informazioni principali
   - Evidenzia numeri e metriche chiave
   - Usa formattazione markdown (bold, liste) per chiarezza

2. **Motiva le priorità** (se presenti):
   - Spiega PERCHÉ certi stabilimenti/piani sono prioritari
   - Evidenzia i criteri utilizzati (rischio storico, ritardi, correlazioni)
   - Dai contesto operativo pratico

3. **Fornisci valore aggiunto**:
   - Interpreta i dati in chiave operativa
   - Suggerisci 1-2 domande di follow-up pertinenti
   - NON aggiungere informazioni sui punteggi che non sono presenti nei dati forniti

**IMPORTANTE - Formula Risk Score:**
Se menzioni punteggi di rischio, usa SOLO questa formula:
- Risk Score = P(NC) × Impatto × 100
- P(NC) = (NC totali) / (controlli totali)
- Impatto = (NC gravi) / (controlli totali)
- NON usare mai formule come "NC grave = 3 punti" che sono ERRATE

4. **Linee guida per la risposta**:
   - Interpreta i dati nel contesto veterinario regionale
   - Suggerisci azioni concrete basate sui risultati
   - Se ci sono anomalie o punti critici, evidenziali

5. **Proponi 1-2 domande successive** che l'utente potrebbe trovare utili:
   - Basate sui risultati attuali
   - Che approfondiscano l'analisi
   - Che guidino verso azioni operative

**REGOLE:**
- Tono formale ma accessibile, adatto a operatori ASL
- NON inventare dati non presenti
- Se i risultati sono vuoti o in errore, spiegalo chiaramente
- Usa terminologia tecnica corretta (ASL, UOC, OSA, NC, piani di controllo)
- Formatta usando markdown per migliore leggibilità

**OUTPUT:**
Rispondi SOLO con il testo della risposta finale, strutturato e professionale.
NO prefissi tipo "Ecco la risposta:" o "Sulla base dei dati:".
Inizia direttamente con il contenuto."""

RESPONSE_USER_TEMPLATE = """**CONTESTO:**
L'utente ha richiesto: {context_description}

**DOMANDA ORIGINALE:**
"{user_message}"

**TIPO DI ANALISI:**
{intent}

**RISULTATI OTTENUTI:**
{data}"""

INTENT_DESCRIPTIONS = {
    "ask_piano_description": "descrizione di un piano di controllo veterinario",
    "ask_piano_stabilimenti": "analisi degli stabilimenti controllati per un piano",
    "ask_piano_statistics": "statistiche aggregate sui piani di controllo eseguiti",
    "search_piani_by_topic": "ricerca di piani per argomento",
    "ask_priority_establishment": "stabilimenti prioritari da controllare secondo programmazione",
    "ask_risk_based_priority": "stabilimenti prioritari basati sul rischio storico",
    "ask_suggest_controls": "suggerimenti per controlli di stabilimenti mai ispezionati",
    "ask_delayed_plans": "analisi dei piani in ritardo",
    "check_if_plan_delayed": "verifica se un piano specifico è in ritardo",
    "ask_establishment_history": "storico controlli e NC per stabilimento",
    "ask_top_risk_activities": "top attività con risk score più elevato",
    "analyze_nc_by_category": "analisi non conformità per categoria specifica",
    "ask_help": "informazioni sulle funzionalità disponibili",
    "info_procedure": "informazioni su procedure operative da documentazione"
}

# Intent che restituiscono risposte dirette senza passaggio LLM
DIRECT_RESPONSE_INTENTS = {
    "greet", "goodbye", "fallback",
    "confirm_show_details", "decline_show_details"
}


def clean_excessive_newlines(text: str) -> str:
    """Rimuove newline eccessive dal testo."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\n\n\n+', '\n\n', text)
    return text.strip()


def extract_response_context(intent: str, slots: Dict[str, Any], tool_output: Dict[str, Any], final_response: str) -> str:
    """
    Estrae un breve contesto dalla risposta per risoluzione riferimenti anaforici.

    Il contesto viene usato nel turno successivo per capire a cosa si riferiscono
    pronomi e articoli generici (es. "le varianti" -> "varianti del piano A2").

    Returns:
        Stringa breve (~50-100 chars) che descrive il contesto della risposta.
    """
    context_parts = []

    # 1. Aggiungi info da slots
    if slots.get("piano_code"):
        context_parts.append(f"piano {slots['piano_code']}")
    if slots.get("topic"):
        context_parts.append(f"topic '{slots['topic']}'")
    if slots.get("num_registrazione"):
        context_parts.append(f"stabilimento {slots['num_registrazione']}")
    if slots.get("ragione_sociale"):
        context_parts.append(f"stabilimento '{slots['ragione_sociale']}'")
    if slots.get("categoria"):
        context_parts.append(f"categoria '{slots['categoria']}'")

    # 2. Estrai info chiave dalla risposta (varianti, count, etc.)
    data = tool_output.get("data", {}) if isinstance(tool_output, dict) else {}

    # Cerca menzioni di varianti
    if isinstance(data, dict):
        if "varianti" in data:
            varianti = data.get("varianti", [])
            if varianti:
                varianti_codes = [v.get("codice_variante", v.get("code", str(v))) for v in varianti[:5]]
                context_parts.append(f"varianti: {', '.join(str(v) for v in varianti_codes)}")
        elif "num_varianti" in data:
            context_parts.append(f"{data['num_varianti']} varianti")
        elif "total_variants" in data:
            context_parts.append(f"{data['total_variants']} varianti")
        # Cerca count di risultati
        if "count" in data:
            context_parts.append(f"{data['count']} risultati")
        elif "total" in data:
            context_parts.append(f"{data['total']} elementi")
        elif "total_controls" in data:
            context_parts.append(f"{data['total_controls']} controlli")
        elif "unique_establishments" in data:
            context_parts.append(f"{data['unique_establishments']} stabilimenti")

    # 3. Fallback: estrai numeri dalla risposta testuale
    if not context_parts and final_response:
        # Cerca pattern come "5 varianti", "10 stabilimenti"
        match = re.search(r'(\d+)\s+(varianti|stabilimenti|piani|controlli|NC|non conformità)', final_response, re.IGNORECASE)
        if match:
            context_parts.append(f"{match.group(1)} {match.group(2)}")

    # 4. Aggiungi descrizione intent
    intent_context = {
        "ask_piano_description": "descrizione piano",
        "ask_piano_stabilimenti": "stabilimenti piano",
        "ask_piano_generic": "info piano",
        "ask_piano_statistics": "statistiche piani",
        "search_piani_by_topic": "ricerca piani",
        "ask_delayed_plans": "piani in ritardo",
        "check_if_plan_delayed": "verifica ritardo piano",
        "ask_priority_establishment": "stabilimenti prioritari",
        "ask_risk_based_priority": "priorità rischio",
        "ask_suggest_controls": "suggerimenti controlli",
        "ask_establishment_history": "storico stabilimento",
        "ask_top_risk_activities": "top rischio",
        "analyze_nc_by_category": "NC per categoria",
    }
    if intent in intent_context:
        context_parts.insert(0, intent_context[intent])

    return " - ".join(context_parts) if context_parts else ""


def build_response_messages(intent: str, tool_output: Dict[str, Any], user_message: str = "") -> list:
    """Costruisce system + user messages per generazione risposta LLM."""
    data = tool_output.get("data", {})
    formatted_response = data.get("formatted_response", "") if isinstance(data, dict) else ""

    context_description = INTENT_DESCRIPTIONS.get(intent, "analisi di dati veterinari")
    data_str = formatted_response if formatted_response else str(data)

    user_content = RESPONSE_USER_TEMPLATE.format(
        context_description=context_description,
        user_message=user_message,
        intent=intent,
        data=data_str
    )

    return [
        {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]


def response_generator_node(state: Dict[str, Any], llm_client, event_callback=None) -> Dict[str, Any]:
    """
    Nodo response_generator: genera la risposta finale.

    Args:
        state: ConversationState
        llm_client: LLMClient instance
        event_callback: Callback per eventi SSE (opzionale)

    Returns:
        State aggiornato con final_response
    """
    if event_callback:
        event_callback({
            "type": "status",
            "node": "response_generator",
            "message": "Generando risposta..."
        })

    tool_output = state.get("tool_output") or {}
    intent = state.get("intent", "fallback")
    tool_type = tool_output.get("type", "") if isinstance(tool_output, dict) else ""

    # Estrai data dal tool_output
    data = tool_output.get("data", {})

    # Intent con risposte dirette (greet, goodbye, fallback, confirm/decline)
    if intent in DIRECT_RESPONSE_INTENTS or tool_type == "fallback":
        if isinstance(data, dict) and "formatted_response" in data:
            state["final_response"] = data["formatted_response"]
        else:
            state["final_response"] = str(data)
        return state

    # Se il tool ha gia' prodotto una formatted_response, usala direttamente
    # (evita chiamata LLM - risparmio ~800ms-1.5s su CPU)
    if isinstance(data, dict) and "formatted_response" in data:
        response = data["formatted_response"]
        response = clean_excessive_newlines(response)
        state["final_response"] = response
    else:
        # Fallback: genera risposta con LLM solo se non c'e' formatted_response
        logger.info(f"[ResponseNode] LLM generation for intent={intent} (no formatted_response)")
        messages = build_response_messages(intent, tool_output, state.get("message", ""))

        try:
            response = llm_client.query(messages=messages)
            response = clean_excessive_newlines(response) if response else "Errore nella generazione della risposta."
            state["final_response"] = response.strip()
        except Exception as e:
            state["final_response"] = f"Errore: {str(e)}"

    # Append suggerimenti di follow-up contestuali
    if _followup_engine.should_append(state):
        suggestions = _followup_engine.get_suggestions(
            intent=intent,
            slots=state.get("slots", {}),
            tool_output=tool_output
        )
        if suggestions:
            state["final_response"] += _followup_engine.format_suggestions(suggestions)

    # Estrai contesto per risoluzione anaforica nel turno successivo
    response_context = extract_response_context(
        intent=intent,
        slots=state.get("slots", {}),
        tool_output=tool_output,
        final_response=state.get("final_response", "")
    )
    if response_context:
        state["response_context"] = response_context

    return state
