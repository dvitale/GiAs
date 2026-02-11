"""
Intent Metadata Registry per Fallback Recovery System

Questo modulo definisce i metadati per tutti gli intent supportati dal sistema,
inclusi keyword mapping, descrizioni user-friendly, e gerarchia categoriale.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class IntentMetadata:
    """Metadati completi per un intent"""
    intent_id: str
    label: str  # Nome user-friendly
    description: str  # Descrizione breve per l'utente
    category: str  # Categoria di appartenenza
    keywords: List[str]  # Keyword primarie (+10 punti)
    context_keywords: List[str] = field(default_factory=list)  # Keyword di contesto (+5 punti)
    negative_keywords: List[str] = field(default_factory=list)  # Keyword che escludono (-50 punti)
    examples: List[str] = field(default_factory=list)  # Esempi domande utente
    requires_slots: List[str] = field(default_factory=list)  # Slot obbligatori
    emoji: str = "📋"  # Emoji rappresentativo


# Registry completo degli intent con metadati
INTENT_REGISTRY: Dict[str, IntentMetadata] = {
    # ===== CATEGORIA: Basilari =====
    "greet": IntentMetadata(
        intent_id="greet",
        label="Saluto",
        description="Saluta il sistema",
        category="Altro",
        keywords=["ciao", "buongiorno", "salve", "hey", "buonasera"],
        context_keywords=["hello", "hi"],
        negative_keywords=[],
        examples=["Ciao", "Buongiorno", "Salve"],
        requires_slots=[],
        emoji="👋"
    ),

    "goodbye": IntentMetadata(
        intent_id="goodbye",
        label="Arrivederci",
        description="Termina la conversazione",
        category="Altro",
        keywords=["arrivederci", "ciao", "addio", "grazie", "basta"],
        context_keywords=["fine", "stop"],
        negative_keywords=[],
        examples=["Arrivederci", "Grazie, ciao", "Basta così"],
        requires_slots=[],
        emoji="👋"
    ),

    "ask_help": IntentMetadata(
        intent_id="ask_help",
        label="Aiuto",
        description="Mostra le funzionalità disponibili",
        category="Altro",
        keywords=["aiuto", "help", "cosa puoi fare", "funzionalità", "comandi"],
        context_keywords=["cosa", "puoi", "fare"],
        negative_keywords=[],
        examples=["Aiuto", "Cosa puoi fare?", "Quali sono le funzionalità?"],
        requires_slots=[],
        emoji="❓"
    ),

    # ===== CATEGORIA: Piano di Controllo =====
    "ask_piano_description": IntentMetadata(
        intent_id="ask_piano_description",
        label="Descrizione Piano",
        description="Ottieni descrizione dettagliata di un piano di controllo",
        category="Piano di Controllo",
        keywords=["descrizione", "di cosa tratta", "cosa prevede", "dettagli", "cos'è"],
        context_keywords=["piano"],
        negative_keywords=["stabilimenti", "statistiche", "dove", "quanti"],
        examples=["Di cosa tratta il piano A1?", "Descrizione piano B2", "Dettagli sul piano C3"],
        requires_slots=["piano_code"],
        emoji="📄"
    ),

    "ask_piano_stabilimenti": IntentMetadata(
        intent_id="ask_piano_stabilimenti",
        label="Stabilimenti per Piano",
        description="Elenca stabilimenti coinvolti in un piano specifico",
        category="Piano di Controllo",
        keywords=["stabilimenti", "dove", "applicato", "controllati", "osa"],
        context_keywords=["piano"],
        negative_keywords=["statistiche", "descrizione", "dettagli"],
        examples=["Quali stabilimenti per piano A1?", "Dove si applica piano B2?", "OSA del piano C3"],
        requires_slots=["piano_code"],
        emoji="🏭"
    ),

    "ask_piano_generic": IntentMetadata(
        intent_id="ask_piano_generic",
        label="Info Generiche Piano",
        description="Informazioni generiche su un piano (periodo, stato, ecc.)",
        category="Piano di Controllo",
        keywords=["quando", "periodo", "scadenza", "stato", "informazioni"],
        context_keywords=["piano"],
        negative_keywords=["stabilimenti", "descrizione", "statistiche"],
        examples=["Quando inizia piano A1?", "Periodo piano B2", "Stato del piano C3"],
        requires_slots=["piano_code"],
        emoji="ℹ️"
    ),

    "ask_piano_statistics": IntentMetadata(
        intent_id="ask_piano_statistics",
        label="Statistiche Piano",
        description="Statistiche e numeri relativi a un piano (controlli eseguiti, NC, ecc.)",
        category="Piano di Controllo",
        keywords=["statistiche", "numeri", "quanti", "percentuale", "controlli eseguiti"],
        context_keywords=["piano"],
        negative_keywords=["stabilimenti", "descrizione"],
        examples=["Statistiche piano A1", "Quanti controlli nel piano B2?", "Percentuali piano C3"],
        requires_slots=["piano_code"],
        emoji="📊"
    ),

    # ===== CATEGORIA: Ricerca =====
    "search_piani_by_topic": IntentMetadata(
        intent_id="search_piani_by_topic",
        label="Cerca Piani per Argomento",
        description="Cerca piani che trattano un argomento o settore specifico",
        category="Ricerca",
        keywords=["cerca", "ricerca", "trova", "piani", "argomento", "settore"],
        context_keywords=["topic", "tema", "riguardano"],
        negative_keywords=["piano A", "piano B", "piano C"],  # Esclude ricerca piano specifico
        examples=["Cerca piani sulla sicurezza alimentare", "Piani sul settore carne", "Trova piani igiene"],
        requires_slots=["topic"],
        emoji="🔍"
    ),

    # ===== CATEGORIA: Priorità e Rischio =====
    "ask_priority_establishment": IntentMetadata(
        intent_id="ask_priority_establishment",
        label="Priorità da Programmazione",
        description="Stabilimenti prioritari derivati da piani in ritardo",
        category="Priorità e Rischio",
        keywords=["priorità", "prioritari", "urgenti", "da programmare", "da controllare"],
        context_keywords=["stabilimenti", "osa", "controlli"],
        negative_keywords=["rischio", "mai controllati", "nc", "pericolosi"],
        examples=["Stabilimenti prioritari", "Quali OSA sono urgenti?", "Priorità controlli"],
        requires_slots=[],
        emoji="⚠️"
    ),

    "ask_risk_based_priority": IntentMetadata(
        intent_id="ask_risk_based_priority",
        label="Stabilimenti a Rischio NC",
        description="Stabilimenti con alto rischio storico di non conformità",
        category="Priorità e Rischio",
        keywords=["rischio", "pericolosi", "rischiosi", "non conformità", "nc", "alto rischio"],
        context_keywords=["stabilimenti", "osa"],
        negative_keywords=["attività", "mai controllati", "pianificazione", "priorità da programmare"],
        examples=["Stabilimenti a rischio", "OSA pericolosi", "Quali stabilimenti hanno più NC?"],
        requires_slots=[],
        emoji="⚠️"
    ),

    "ask_suggest_controls": IntentMetadata(
        intent_id="ask_suggest_controls",
        label="Stabilimenti Mai Controllati",
        description="Stabilimenti mai ispezionati che necessitano controllo",
        category="Priorità e Rischio",
        keywords=["mai controllati", "non controllati", "da controllare", "suggerimenti", "suggerisci"],
        context_keywords=["stabilimenti", "osa", "ispezionare"],
        negative_keywords=["rischio", "ritardo", "priorità"],
        examples=["Stabilimenti mai controllati", "OSA da ispezionare", "Suggerisci controlli"],
        requires_slots=[],
        emoji="🔍"
    ),

    "ask_top_risk_activities": IntentMetadata(
        intent_id="ask_top_risk_activities",
        label="Attività più Rischiose",
        description="Classifica delle tipologie di attività con più rischio NC",
        category="Priorità e Rischio",
        keywords=["attività", "rischiose", "pericolose", "top", "classifica", "tipologie"],
        context_keywords=["rischio", "più", "maggior"],
        negative_keywords=["stabilimenti", "osa"],
        examples=["Attività più rischiose", "Top tipologie a rischio", "Classifica attività pericolose"],
        requires_slots=[],
        emoji="📊"
    ),

    # ===== CATEGORIA: Ritardi =====
    "ask_delayed_plans": IntentMetadata(
        intent_id="ask_delayed_plans",
        label="Piani in Ritardo",
        description="Elenco dei piani di controllo in ritardo",
        category="Ritardi e Monitoraggio",
        keywords=["ritardo", "ritardi", "in ritardo", "scaduti", "piani"],
        context_keywords=["quali", "elenco"],
        negative_keywords=["piano A", "piano B", "piano C"],  # Piano singolo
        examples=["Piani in ritardo", "Quali piani sono scaduti?", "Elenco ritardi"],
        requires_slots=[],
        emoji="⏰"
    ),

    "check_if_plan_delayed": IntentMetadata(
        intent_id="check_if_plan_delayed",
        label="Verifica Ritardo Piano",
        description="Verifica se un piano specifico è in ritardo",
        category="Ritardi e Monitoraggio",
        keywords=["ritardo", "è in ritardo", "scaduto", "controllare"],
        context_keywords=["piano A", "piano B", "piano C"],  # Piano specifico
        negative_keywords=["piani", "quali", "elenco"],
        examples=["Il piano A1 è in ritardo?", "Controlla ritardo piano B2", "Piano C3 scaduto?"],
        requires_slots=["piano_code"],
        emoji="⏰"
    ),

    # ===== CATEGORIA: Storico e Analisi =====
    "ask_establishment_history": IntentMetadata(
        intent_id="ask_establishment_history",
        label="Storico Stabilimento",
        description="Storico controlli e NC per uno stabilimento specifico",
        category="Storico e Analisi",
        keywords=["storico", "storia", "precedenti", "passati"],
        context_keywords=["stabilimento", "osa", "controlli", "nc"],
        negative_keywords=["piani", "categoria"],
        examples=["Storico stabilimento X", "Controlli passati OSA Y", "Storia NC stabilimento Z"],
        requires_slots=["num_registrazione"],  # o partita_iva o ragione_sociale
        emoji="📜"
    ),

    "analyze_nc_by_category": IntentMetadata(
        intent_id="analyze_nc_by_category",
        label="Analisi NC per Categoria",
        description="Analisi non conformità aggregate per categoria",
        category="Storico e Analisi",
        keywords=["analisi", "nc", "categoria", "tipologia", "distribuzione"],
        context_keywords=["non conformità", "aggregate"],
        negative_keywords=["stabilimento", "piano"],
        examples=["Analisi NC per categoria", "Distribuzione non conformità", "NC aggregate"],
        requires_slots=[],
        emoji="📈"
    ),

    # ===== CATEGORIA: Two-Phase (Interni) =====
    "confirm_show_details": IntentMetadata(
        intent_id="confirm_show_details",
        label="Mostra Dettagli",
        description="Conferma visualizzazione dettagli completi",
        category="Altro",
        keywords=["sì", "si", "yes", "ok", "mostra", "dettagli"],
        context_keywords=["tutti", "completi"],
        negative_keywords=["no", "non"],
        examples=["Sì", "Ok mostra tutto", "Sì, dettagli"],
        requires_slots=[],
        emoji="✅"
    ),

    "decline_show_details": IntentMetadata(
        intent_id="decline_show_details",
        label="Non Mostrare Dettagli",
        description="Rifiuta visualizzazione dettagli completi",
        category="Altro",
        keywords=["no", "non", "basta", "così"],
        context_keywords=["va bene", "ok"],
        negative_keywords=["sì", "mostra"],
        examples=["No", "Basta così", "No grazie"],
        requires_slots=[],
        emoji="❌"
    ),

    # ===== CATEGORIA: Procedure Operative =====
    "info_procedure": IntentMetadata(
        intent_id="info_procedure",
        label="Informazioni Procedura",
        description="Informazioni su procedure operative da documentazione",
        category="Procedure Operative",
        keywords=["procedura", "procedimento", "passi", "step", "guida", "istruzioni",
                  "come si fa", "come procedere", "come funziona"],
        context_keywords=["ispezione", "controllo", "verifica", "audit", "registrazione"],
        negative_keywords=["piano", "stabilimento", "ritardo", "rischio"],
        examples=[
            "Qual e' la procedura per ispezione semplice?",
            "Come si esegue un controllo ufficiale?",
            "Quali sono i passi per registrare una NC?",
        ],
        requires_slots=[],
        emoji="📋"
    ),

    # ===== FALLBACK =====
    "fallback": IntentMetadata(
        intent_id="fallback",
        label="Non Compreso",
        description="Intent non riconosciuto - attiva fallback recovery",
        category="Altro",
        keywords=[],
        context_keywords=[],
        negative_keywords=[],
        examples=[],
        requires_slots=[],
        emoji="❓"
    ),
}


# Gerarchia categoriale a 2 livelli
CATEGORY_HIERARCHY: Dict[str, List[str]] = {
    "Piano di Controllo": [
        "ask_piano_description",
        "ask_piano_stabilimenti",
        "ask_piano_generic",
        "ask_piano_statistics"
    ],
    "Priorità e Rischio": [
        "ask_priority_establishment",
        "ask_risk_based_priority",
        "ask_suggest_controls",
        "ask_top_risk_activities"
    ],
    "Ricerca": [
        "search_piani_by_topic"
    ],
    "Ritardi e Monitoraggio": [
        "ask_delayed_plans",
        "check_if_plan_delayed"
    ],
    "Storico e Analisi": [
        "ask_establishment_history",
        "analyze_nc_by_category"
    ],
    "Procedure Operative": [
        "info_procedure"
    ],
    "Altro": [
        "greet",
        "goodbye",
        "ask_help"
    ]
}


# Emoji per categorie
CATEGORY_EMOJI: Dict[str, str] = {
    "Piano di Controllo": "📋",
    "Priorità e Rischio": "🎯",
    "Ricerca": "🔍",
    "Ritardi e Monitoraggio": "⏰",
    "Storico e Analisi": "📈",
    "Procedure Operative": "📋",
    "Altro": "ℹ️"
}


def get_intent_metadata(intent_id: str) -> Optional[IntentMetadata]:
    """Recupera metadati per un intent"""
    return INTENT_REGISTRY.get(intent_id)


def get_category_intents(category: str) -> List[str]:
    """Recupera lista intent per categoria"""
    return CATEGORY_HIERARCHY.get(category, [])


def get_all_categories() -> List[str]:
    """Recupera lista di tutte le categorie"""
    # Escludi "Altro" dal menu principale
    return [cat for cat in CATEGORY_HIERARCHY.keys() if cat != "Altro"]


def get_intent_by_label(label: str) -> Optional[str]:
    """Trova intent_id da label user-friendly"""
    for intent_id, metadata in INTENT_REGISTRY.items():
        if metadata.label.lower() == label.lower():
            return intent_id
    return None


# Validazione registry
def validate_registry():
    """Valida consistenza del registry"""
    errors = []

    # Verifica che tutti gli intent in CATEGORY_HIERARCHY esistano in INTENT_REGISTRY
    for category, intents in CATEGORY_HIERARCHY.items():
        for intent_id in intents:
            if intent_id not in INTENT_REGISTRY:
                errors.append(f"Intent '{intent_id}' in categoria '{category}' non trovato in INTENT_REGISTRY")

    # Verifica che tutti gli intent in INTENT_REGISTRY siano in CATEGORY_HIERARCHY
    for intent_id in INTENT_REGISTRY:
        found = False
        for category, intents in CATEGORY_HIERARCHY.items():
            if intent_id in intents:
                found = True
                break
        if not found and intent_id != "fallback":
            errors.append(f"Intent '{intent_id}' non assegnato a nessuna categoria")

    return errors


# Esegui validazione al caricamento
_validation_errors = validate_registry()
if _validation_errors:
    import warnings
    warnings.warn(f"Errori validazione intent registry: {_validation_errors}")
