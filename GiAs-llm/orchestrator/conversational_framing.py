"""
Conversational framing layer: aggiunge intro naturali alle risposte template.
Zero chiamate LLM — solo string operations con frasi randomizzate per varieta'.
Intro caricati da DB (intents.intro_phrases) con fallback Python.
"""
import secrets
from datetime import datetime
from typing import Dict, List, Optional

# Intent le cui risposte si basano sulla valutazione "ad oggi" (confronto con
# datetime.now() in BusinessLogic.calculate_delayed_plans). Per questi, il frame
# layer antepone esplicitamente la data corrente all'intestazione, così che la
# risposta resti interpretabile anche se riletta o condivisa in seguito.
_CHRONOLOGICAL_INTENTS = frozenset({
    "ask_delayed_plans",
    "check_if_plan_delayed",
    "ask_priority_establishment",
})

_MONTHS_IT = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre",
}


def _format_today_italian() -> str:
    """Restituisce la data odierna in italiano, es. "8 aprile 2026"."""
    t = datetime.now()
    return f"{t.day} {_MONTHS_IT[t.month]} {t.year}"

# Fallback hardcoded (usato se DB non disponibile)
_FALLBACK_INTROS: Dict[str, List[str]] = {
    "ask_piano_description": [
        "Ecco le informazioni sul piano che cerchi.",
        "Ho recuperato i dettagli del piano.",
    ],
    "ask_piano_stabilimenti": [
        "Ecco gli stabilimenti coinvolti.",
        "Ho trovato gli stabilimenti corrispondenti.",
    ],
    "ask_piano_statistics": [
        "Ecco le statistiche che hai richiesto.",
        "Ho elaborato i dati statistici.",
    ],
    "search_piani_by_topic": [
        "Ecco i piani che ho trovato.",
        "Ho cercato nei piani di monitoraggio.",
    ],
    "ask_delayed_plans": [
        "Ho analizzato la situazione dei ritardi.",
        "Ecco il quadro dei piani in ritardo.",
    ],
    "check_if_plan_delayed": [
        "Ho verificato lo stato del piano.",
        "Ecco cosa risulta per questo piano.",
    ],
    "ask_priority_establishment": [
        "Ho calcolato le priorita' di controllo.",
        "Ecco gli stabilimenti su cui concentrare l'attenzione.",
    ],
    "ask_risk_based_priority": [
        "Ho analizzato il rischio storico.",
        "Ecco la classifica basata sul rischio.",
    ],
    "ask_suggest_controls": [
        "Ecco i controlli che ti suggerisco.",
        "Ho elaborato dei suggerimenti per te.",
    ],
    "ask_nearby_priority": [
        "Ho cercato gli stabilimenti nelle vicinanze.",
        "Ecco cosa c'e' nella tua zona.",
    ],
    "ask_establishment_history": [
        "Ho recuperato lo storico dello stabilimento.",
        "Ecco il quadro dei controlli per questo stabilimento.",
    ],
    "ask_top_risk_activities": [
        "Ho analizzato le attivita' a rischio.",
        "Ecco le linee di attivita' piu' critiche.",
    ],
    "info_procedure": [
        "Ho trovato le informazioni sulla procedura.",
        "Ecco cosa prevede la procedura.",
    ],
    "query_data": [
        "Ecco il risultato della tua ricerca.",
        "Ho interrogato i dati.",
    ],
}

_DEFAULT_INTROS = [
    "Ecco quello che ho trovato.",
    "Ho elaborato la tua richiesta.",
]

# Buddy mode: intro amichevoli e informali
_BUDDY_INTROS: Dict[str, List[str]] = {
    "ask_piano_description": [
        "Ecco cosa ho trovato sul piano! 📋",
        "Guarda, ho recuperato i dettagli del piano.",
    ],
    "ask_piano_stabilimenti": [
        "Ecco gli stabilimenti che cercavi! 🏭",
        "Dai un'occhiata agli stabilimenti coinvolti.",
    ],
    "ask_piano_statistics": [
        "Ecco le statistiche — numeri alla mano! 📊",
        "Ho tirato fuori i dati, guarda un po'.",
    ],
    "search_piani_by_topic": [
        "Ho cercato per te, ecco cosa salta fuori! 🔍",
        "Guarda cosa ho trovato nei piani.",
    ],
    "ask_delayed_plans": [
        "Ho dato un'occhiata ai ritardi — ecco la situazione. ⏰",
        "Senti, ecco il quadro sui piani in ritardo.",
    ],
    "check_if_plan_delayed": [
        "Ho controllato lo stato del piano per te! ✅",
        "Ecco cosa risulta, dai un'occhiata.",
    ],
    "ask_priority_establishment": [
        "Ho calcolato le priorita' — occhio a questi! 🎯",
        "Ecco gli stabilimenti su cui puntare l'attenzione.",
    ],
    "ask_risk_based_priority": [
        "Ho analizzato il rischio storico — guarda qui! ⚠️",
        "Senti, ecco la classifica rischio.",
    ],
    "ask_suggest_controls": [
        "Ecco qualche suggerimento per i prossimi controlli! 💡",
        "Ho elaborato dei suggerimenti, dai un'occhiata.",
    ],
    "ask_nearby_priority": [
        "Ho cercato nelle vicinanze — ecco cosa c'e'! 📍",
        "Guarda cosa ho trovato nella tua zona.",
    ],
    "ask_establishment_history": [
        "Ho recuperato lo storico — ecco il quadro! 📜",
        "Dai un'occhiata allo storico di questo stabilimento.",
    ],
    "ask_top_risk_activities": [
        "Ho analizzato le attivita' a rischio — occhio a queste! 🔴",
        "Ecco le linee di attivita' piu' critiche, guarda.",
    ],
    "info_procedure": [
        "Ho trovato le info sulla procedura! 📖",
        "Ecco cosa prevede la procedura, dai un'occhiata.",
    ],
    "query_data": [
        "Ecco il risultato della tua ricerca! 🔎",
        "Ho interrogato i dati, guarda cosa salta fuori.",
    ],
}

_BUDDY_DEFAULT_INTROS = [
    "Ecco cosa ho trovato per te! 👀",
    "Guarda un po' qui!",
    "Ho elaborato la tua richiesta, dai un'occhiata!",
]

# Prefissi che indicano una risposta gia' conversazionale (no double-framing).
# Include sia prefissi derivati dagli intro sia quelli usati nei messaggi vuoti dei tool.
_CONVERSATIONAL_PREFIXES = tuple(sorted({
    phrase.split()[0] for phrases in _FALLBACK_INTROS.values() for phrase in phrases
} | {
    phrase.split()[0] for phrase in _DEFAULT_INTROS
} | {
    "Non", "Ottima", "Certo", "Nessun", "Per",
}))

# Cache lazy-loaded dal DB
_intros_cache: Optional[Dict[str, List[str]]] = None


def _get_intros() -> Dict[str, List[str]]:
    """Carica intro da IntentMetadataService (DB-first), fallback a _FALLBACK_INTROS."""
    global _intros_cache
    if _intros_cache is not None:
        return _intros_cache
    try:
        from .intent_metadata_service import get_intent_metadata_service
        svc = get_intent_metadata_service()
        db_intros = svc.get_intro_phrases()
        if db_intros:
            _intros_cache = db_intros
            return _intros_cache
    except Exception:
        pass
    _intros_cache = _FALLBACK_INTROS
    return _intros_cache


def frame_response(intent: str, formatted_response: str, buddy_mode: bool = False) -> str:
    """Aggiunge un intro conversazionale a una risposta template, se appropriato."""
    if not formatted_response or not formatted_response.strip():
        return formatted_response

    stripped = formatted_response.lstrip()
    is_chronological = intent in _CHRONOLOGICAL_INTENTS

    # Idempotenza: se la risposta (o il tool) contiene già un header "Ad oggi …"
    # non raddoppiare.
    if is_chronological and stripped.lower().startswith("ad oggi"):
        return formatted_response

    already_conversational = stripped.startswith(_CONVERSATIONAL_PREFIXES)

    # Intent non cronologici: preserva comportamento originale.
    if not is_chronological:
        if already_conversational:
            return formatted_response
        if len(stripped) < 80:
            return formatted_response
        if buddy_mode:
            intros = _BUDDY_INTROS.get(intent, _BUDDY_DEFAULT_INTROS)
        else:
            intros = _get_intros().get(intent, _DEFAULT_INTROS)
        return f"{secrets.choice(intros)}\n\n{formatted_response}"

    # Intent cronologici: risposte brevi (es. "Nessun piano in ritardo.")
    # non vengono decorate per non appesantire output minimali.
    if len(stripped) < 80:
        return formatted_response

    today = _format_today_italian()

    # Se la risposta inizia già con un prefisso conversazionale (es. "Ho …"),
    # anteponi l'header della data abbassando la prima lettera del template
    # esistente per ottenere una frase unica naturale.
    if already_conversational:
        head, _, rest = formatted_response.partition("\n")
        head_stripped = head.lstrip()
        if head_stripped:
            reframed_head = head_stripped[0].lower() + head_stripped[1:]
            leading_ws = head[: len(head) - len(head_stripped)]
            new_head = f"{leading_ws}Ad oggi {today}, {reframed_head}"
            return f"{new_head}\n{rest}" if rest or "\n" in formatted_response else new_head
        return f"Ad oggi {today}, {formatted_response}"

    # Caso standard: scegli un intro dal set (normale o buddy), abbassa la
    # prima lettera e prefissa con la data odierna.
    if buddy_mode:
        intros = _BUDDY_INTROS.get(intent, _BUDDY_DEFAULT_INTROS)
    else:
        intros = _get_intros().get(intent, _DEFAULT_INTROS)
    intro = secrets.choice(intros)
    intro_lowered = intro[0].lower() + intro[1:] if intro else intro
    return f"Ad oggi {today}, {intro_lowered}\n\n{formatted_response}"
