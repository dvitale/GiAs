"""
Fallback classifier e response generator per quando l'LLM non e' disponibile.

Approccio data-driven: pattern → intent mappings in dizionari.
Usato da LLMClient._fallback_stub() quando il provider reale fallisce.
"""

import json
import re


# Pattern di classificazione: lista di (regex_o_keywords, intent, slot_extractor)
# Processati in ordine - il primo match vince.
GREETING_PATTERN = re.compile(
    r'^\s*(ciao|salve|buongiorno|buonasera|buonanotte|buondì|buon\s*pomeriggio|'
    r'hello|hey|hi|ehilà|ehi|eccomi|ben\s*trovato|ben\s*tornato|come\s*(stai|va))\s*[!.?]?\s*$'
)
GOODBYE_PATTERN = re.compile(
    r'^\s*(arrivederci|addio|bye|ciao\s*ciao|tanti\s*saluti|'
    r'alla\s*prossima|ci\s*vediamo|a\s*domani|stammi?\s*bene)\s*[!.?]?\s*$'
)
CONFIRM_PATTERN = re.compile(r'^\s*(s[ìi]|yes|ok|va bene|mostra|dettagli|tutti)\s*[!.?]?\s*$')
DECLINE_PATTERN = re.compile(r'^\s*(no|non|niente|basta|va bene cos[ìi])\s*[!.?]?\s*$')
PIANO_CODE_PATTERN = re.compile(r'\b([A-F]\d{1,2}(?:_[A-Z0-9]+)?)\b', re.IGNORECASE)

# Keyword → intent mappings (ordine conta per disambiguazione)
KEYWORD_INTENTS = [
    (["aiuto", "help", "che domande", "cosa sai", "cosa posso", "come posso", "come puoi", "cosa puoi"],
     "ask_help"),
    (["attività rischiose", "attività più rischiose", "top attività", "classifica attività",
      "linee di attività", "linea di attività"],
     "ask_top_risk_activities"),
    (["rischio", "non conformità", "nc", "pericolosi", "alto rischio"],
     "ask_risk_based_priority"),
    (["priorità", "per primo", "prima", "urgenti", "controllare subito"],
     "ask_priority_establishment"),
    (["mai controllati", "non controllati", "suggerisci controll", "da controllare"],
     "ask_suggest_controls"),
    (["controlli eseguiti", "controlli fatti", "controlli totali", "quanti controlli",
      "numero controlli", "controlli programmati", "lista controlli", "elenco controlli",
      "lista dei controlli", "elenco dei controlli", "mostrami i controlli"],
     "ask_cu_statistics"),
    (["ritardo", "ritardi", "in ritardo"],
     "ask_delayed_plans"),
    (["vicino", "dintorni", "pressi", "entro km", "vicinanze"],
     "ask_nearby_priority"),
    (["storico", "storia dei controlli", "storia controlli"],
     "ask_establishment_history"),
    (["procedura", "come si fa", "come si esegue", "passi per", "istruzioni per"],
     "info_procedure"),
    (["statistiche", "frequenza piani", "quanti piani"],
     "ask_piano_statistics"),
]

# Keywords per topic search
TOPIC_KEYWORDS = [
    "bovini", "bovino", "vacche", "vitelli", "bufalini", "bufale", "bufala",
    "suini", "suino", "maiali", "porci", "scrofe", "scrofa", "verri", "verro", "suinetti",
    "ovini", "ovino", "pecore", "agnelli", "arieti",
    "caprini", "caprino", "capre", "capretti",
    "avicoli", "avicolo", "polli", "pollame", "galline", "tacchini", "oche", "anatre",
    "equini", "equino", "cavalli", "asini", "muli",
    "latte", "lattiero", "caseario", "latticini",
    "carne", "macellazione", "macello", "carni",
    "mangimi", "mangime", "alimentazione",
    "allevamenti", "allevamento", "zootecniche", "zootecnia", "zootecnico",
    "benessere", "biosicurezza",
    "salmonella", "residui", "farmaco", "farmaci",
    "api", "apicoltura", "miele",
    "acquacoltura", "ittico", "pesca", "pesci",
    "cani", "gatti", "randagismo", "canile",
    "selvaggina", "selvatici", "cinghiali",
]

SEARCH_TRIGGERS = [
    "cerca", "ricerca", "trova piani", "piani che", "quali piani",
    "quali sono i piani", "piani di", "piani per", "piani sul",
    "piani riguardanti", "piani relativi",
]


def _result(intent: str, slots: dict = None, needs_clarification: bool = False) -> str:
    return json.dumps({
        "intent": intent,
        "slots": slots or {},
        "needs_clarification": needs_clarification,
    })


def _extract_user_message(prompt: str) -> str:
    """Estrae il messaggio utente dal prompt di classificazione."""
    prompt_lower = prompt.lower()
    match = re.search(r'\*\*messaggio utente:\*\*\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
    if not match:
        match = re.search(r'messaggio:\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
    return match.group(1).strip() if match else prompt_lower


def classify(prompt: str) -> str:
    """
    Classificazione mock basata su pattern.
    Usata quando l'LLM non e' disponibile.
    """
    if not prompt:
        return _result("fallback", needs_clarification=True)

    msg = _extract_user_message(prompt)

    # Regex-based intents
    if GREETING_PATTERN.match(msg):
        return _result("greet")
    if GOODBYE_PATTERN.match(msg):
        return _result("goodbye")
    if CONFIRM_PATTERN.match(msg):
        return _result("confirm_show_details")
    if DECLINE_PATTERN.match(msg):
        return _result("decline_show_details")

    # Piano code extraction
    piano_match = PIANO_CODE_PATTERN.search(msg)
    piano_code = piano_match.group(1).upper() if piano_match else None

    if piano_code:
        # Ritardo con piano specifico
        if any(w in msg for w in ["ritardo", "ritardi", "in ritardo", "è in ritardo", "scadut"]):
            return _result("check_if_plan_delayed", {"piano_code": piano_code})
        if any(w in msg for w in ["descrizione", "descrivi", "cos'è", "cosa è", "di cosa tratta", "cosa tratta"]):
            return _result("ask_piano_description", {"piano_code": piano_code})
        if any(w in msg for w in ["stabilimenti", "dove", "applicazione", "applica"]):
            return _result("ask_piano_stabilimenti", {"piano_code": piano_code})
        return _result("ask_piano_stabilimenti", {"piano_code": piano_code})

    # Keyword-based intents
    for keywords, intent in KEYWORD_INTENTS:
        if any(w in msg for w in keywords):
            return _result(intent)

    # NC per categoria
    if ("nc" in msg or "non conformità" in msg) and any(w in msg for w in ["categoria", "haccp", "igiene", "struttur", "analizza"]):
        return _result("analyze_nc_by_category")

    # Ricerca piani per topic
    if any(w in msg for w in SEARCH_TRIGGERS):
        topic_words = [w for w in TOPIC_KEYWORDS if w in msg]
        slots = {"topic": " ".join(topic_words)} if topic_words else {}
        return _result("search_piani_by_topic", slots)

    return _result("fallback", needs_clarification=True)


def generate_response(prompt: str) -> str:
    """
    Generazione risposta mock.
    Estrae formatted_response dal prompt o genera risposta generica.
    """
    if not prompt:
        return "Ciao! Come posso aiutarti con i piani di monitoraggio veterinario?"

    formatted_match = re.search(
        r'\*\*RISULTATI OTTENUTI:\*\*\s*\{[^}]*["\']formatted_response["\']:\s*["\']([^"\']+)["\']',
        prompt, re.DOTALL
    )
    if formatted_match:
        return formatted_match.group(1)[:2000]

    data_section = re.search(r'\*\*RISULTATI OTTENUTI:\*\*\s*(.+?)(?:\*\*|$)', prompt, re.DOTALL)
    if data_section:
        data_text = data_section.group(1).strip()[:500]
        return f"Ecco i risultati della tua richiesta:\n\n{data_text}\n\nPosso aiutarti con ulteriori dettagli?"

    return "Ciao! Come posso aiutarti con i piani di monitoraggio veterinario?"
