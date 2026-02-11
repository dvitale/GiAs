"""
Configurazione workflow conversazionali multi-turno.

Questo modulo definisce:
- Strategie workflow per i 6 intent conversazionali
- Pattern regex per estrazione filtri
- Whitelist domini (comuni, ASL) per validazione
- Mapping strategia -> intent per tool execution
"""

import re
from typing import Dict, Any, List

# =============================================================================
# WORKFLOW STRATEGIES CONFIGURATION
# =============================================================================

WORKFLOW_STRATEGIES = {
    "ask_suggest_controls": {
        "strategies": [
            {
                "id": "strategy_planning",
                "label": "dalla pianificazione",
                "description": "Analizza piani in ritardo della tua UOC",
                "intent_mapping": "ask_delayed_plans",
                "requires_params": ["limit"],
                "question": "vuoi che ti mostri i top 10 piani in maggior ritardo della tua struttura organizzativa?"
            },
            {
                "id": "strategy_risk_nc",
                "label": "dall'analisi del rischio - non conformità",
                "description": "Identifica attività statisticamente più rischiose basandosi su NC storiche",
                "intent_mapping": "ask_top_risk_activities",
                "requires_params": ["limit"]
            },
            {
                "id": "strategy_risk_mai_controllati",
                "label": "dall'analisi del rischio - mai controllati",
                "description": "Estrae stabilimenti mai controllati che esercitano attività a maggior rischio",
                "intent_mapping": "ask_risk_based_priority",
                "requires_params": ["limit"]
            }
        ],
        "initial_question": "preferisci partire dalla pianificazione o dall'analisi del rischio?",
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit"]
    },

    "ask_priority_establishment": {
        "strategies": [
            {
                "id": "priority_delayed",
                "label": "piani in ritardo",
                "description": "Priorità basata su ritardi nella programmazione",
                "intent_mapping": "ask_delayed_plans",
                "requires_params": []
            },
            {
                "id": "priority_risk",
                "label": "rischio storico",
                "description": "Priorità basata su analisi rischio NC",
                "intent_mapping": "ask_risk_based_priority",
                "requires_params": []
            }
        ],
        "initial_question": "vuoi basare la priorità sui ritardi o sul rischio storico?",
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit"]
    },

    "ask_risk_based_priority": {
        "strategies": [],  # Intent diretto, solo raffinamento
        "supported_filters": ["comune", "asl", "tipo_attivita", "limit", "piano_code"]
    },

    "ask_delayed_plans": {
        "strategies": [],
        "supported_filters": ["asl", "uoc", "limit", "piano_code"]
    },

    "ask_establishment_history": {
        "strategies": [],
        "supported_filters": ["asl", "limit", "data_inizio", "data_fine"]
    },

    "search_piani_by_topic": {
        "strategies": [],
        "supported_filters": ["limit", "categoria"]
    }
}

# =============================================================================
# FILTER EXTRACTION PATTERNS
# =============================================================================

FILTER_PATTERNS = {
    "comune": r"(?:nel\s+comune\s+(?:di\s+)?|a\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    "asl": r"(?:ASL\s+|asl\s+)([A-Z]{2}[0-9])",
    "limit": r"(?:primi?\s+|top\s+)?(\d+)",
    "tipo_attivita": {
        "macroarea": r"macroarea\s+([^\s,]+)",
        "aggregazione": r"aggregazione\s+([^\s,]+)",
        "attivita": r"attivit[àa]\s+([^\s,]+)"
    }
}

# =============================================================================
# DOMAIN VALIDATION WHITELISTS
# =============================================================================

# Whitelist comuni Campania (sample - da completare con tutti i ~550 comuni)
# IMPORTANTE: Completare questa lista prima del deployment
VALID_COMUNI = {
    # Provincia di Napoli
    "Napoli", "Pozzuoli", "Giugliano in Campania", "Torre del Greco",
    "Castellammare di Stabia", "Afragola", "Marano di Napoli", "Casoria",
    "Acerra", "Portici", "Ercolano", "Bacoli", "Monte di Procida",
    "Quarto", "Qualiano", "Villaricca", "Calvizzano", "Mugnano di Napoli",
    "Frattamaggiore", "Frattaminore", "Cardito", "Crispano", "Caivano",
    "Arzano", "Casandrino", "Casavatore", "Cercola", "Volla",
    "San Giorgio a Cremano", "San Sebastiano al Vesuvio", "Massa di Somma",
    "Pollena Trocchia", "Sant'Anastasia", "Somma Vesuviana", "Marigliano",
    "Brusciano", "Castello di Cisterna", "Roccarainola", "Tufino",
    "Cicciano", "Comiziano", "Liveri", "Nola", "Camposano",
    "Carbonara di Nola", "Saviano", "Scisciano", "Visciano",
    "Ottaviano", "San Giuseppe Vesuviano", "Palma Campania", "Poggiomarino",
    "Striano", "Terzigno", "Boscoreale", "Boscotrecase", "Trecase",
    "Pompei", "Scafati", "Angri", "Sant'Antonio Abate", "Santa Maria la Carità",
    "Gragnano", "Lettere", "Casola di Napoli", "Pimonte", "Agerola",
    "Vico Equense", "Meta", "Piano di Sorrento", "Sant'Agnello", "Sorrento",
    "Massa Lubrense", "Anacapri", "Capri", "Ischia", "Casamicciola Terme",
    "Lacco Ameno", "Forio", "Serrara Fontana", "Barano d'Ischia",
    "Procida",

    # Provincia di Salerno
    "Salerno", "Battipaglia", "Cava de' Tirreni", "Eboli", "Nocera Inferiore",
    "Nocera Superiore", "Scafati", "Pagani", "Angri", "Sarno",
    "Mercato San Severino", "Baronissi", "Pontecagnano Faiano", "Bellizzi",
    "Giffoni Valle Piana", "Montecorvino Rovella", "Fisciano", "Agropoli",
    "Capaccio Paestum", "Sapri", "Vallo della Lucania", "Sala Consilina",
    "Campagna", "Altavilla Silentina", "Castel San Giorgio", "Roccadaspide",
    "Palomonte", "Bracigliano", "Montecorvino Pugliano", "Olevano sul Tusciano",
    "Pellezzano", "Siano", "Castel San Lorenzo", "Ogliastro Cilento",
    "Positano", "Amalfi", "Ravello", "Maiori", "Minori", "Cetara",
    "Vietri sul Mare", "Tramonti", "Furore", "Conca dei Marini",
    "Praiano", "Scala", "Atrani",

    # Provincia di Caserta
    "Caserta", "Aversa", "Marcianise", "Santa Maria Capua Vetere",
    "Maddaloni", "Orta di Atella", "Mondragone", "Capua", "Casal di Principe",
    "Sessa Aurunca", "Teano", "Piedimonte Matese", "Casagiove", "Recale",
    "San Nicola la Strada", "Macerata Campania", "Casapulla", "Curti",
    "San Prisco", "Portico di Caserta", "Valle di Maddaloni", "Cervino",
    "Casaluce", "San Marcellino", "Gricignano di Aversa", "Lusciano",
    "Parete", "Trentola Ducenta", "Villa Literno", "Carinaro", "Teverola",
    "Succivo", "Frignano", "Cesa", "Sant'Arpino", "San Cipriano d'Aversa",
    "Villa di Briano", "Lusciano", "Casapesenna", "San Tammaro",
    "Grazzanise", "Cancello ed Arnone", "Francolise", "Pignataro Maggiore",
    "Sparanise", "Bellona", "Vitulazio", "Camigliano", "Capodrise",
    "Marzano Appio", "Cellole", "Falciano del Massico", "Carinola",

    # Provincia di Avellino
    "Avellino", "Ariano Irpino", "Montoro", "Solofra", "Mercogliano",
    "Atripalda", "Monteforte Irpino", "Cervinara", "Grottaminarda",
    "Mirabella Eclano", "Baiano", "Mugnano del Cardinale", "Montella",
    "Sperone", "Lauro", "Pago del Vallo di Lauro", "Quindici",
    "Forino", "Contrada", "Sant'Angelo dei Lombardi", "Lioni",
    "Nusco", "Vallata", "Bisaccia", "Calitri", "Lacedonia",
    "Andretta", "Guardia Lombardi", "Frigento", "Gesualdo", "Fontanarosa",
    "Flumeri", "Villamaina", "Bonito", "Apice", "Melito Irpino",
    "Pietradefusi", "Prata di Principato Ultra", "Pratola Serra",
    "Candida", "Manocalzati", "San Michele di Serino", "Santo Stefano del Sole",
    "Sorbo Serpico", "Summonte", "Torrioni", "Tufo", "Chianche",

    # Provincia di Benevento
    "Benevento", "Montesarchio", "Sant'Agata de' Goti", "Telese Terme",
    "San Giorgio del Sannio", "Airola", "San Bartolomeo in Galdo",
    "Apice", "Apollosa", "Arpaia", "Bonea", "Bucciano", "Cautano",
    "Dugenta", "Durazzano", "Forchia", "Frasso Telesino", "Melizzano",
    "Moiano", "Paolisi", "Solopaca", "Torrecuso", "Vitulano",
    "Guardia Sanframondi", "San Lupo", "San Salvatore Telesino",
    "Cerreto Sannita", "Cusano Mutri", "Pietraroja", "San Lorenzello",
    "Morcone", "Ponte", "Pontelandolfo", "Reino", "San Marco dei Cavoti",
    "Sassinoro", "Molinara", "Casalduni", "Castelpoto", "Ceppaloni",
    "Foglianise", "Pago Veiano", "Paduli", "Reino", "Fragneto l'Abate",
    "Fragneto Monforte", "Pesco Sannita", "Pietrelcina", "San Giorgio La Molara",
    "San Nazzaro", "Tocco Caudio",
}

# Whitelist ASL Campania
VALID_ASL = {
    "NA1", "NA2", "NA3",  # Napoli
    "SA1", "SA2", "SA3", "SA",  # Salerno
    "AV1", "AV",  # Avellino
    "CE1", "CE2", "CE",  # Caserta
    "BN1", "BN"  # Benevento
}

# =============================================================================
# STRATEGY TO INTENT MAPPING (Security Allowlist)
# =============================================================================

# Mapping esplicito strategy_id → intent per validazione tool execution
STRATEGY_TO_INTENT_MAP = {
    "strategy_planning": "ask_delayed_plans",
    "strategy_risk_nc": "ask_top_risk_activities",
    "strategy_risk_mai_controllati": "ask_risk_based_priority",
    "priority_delayed": "ask_delayed_plans",
    "priority_risk": "ask_risk_based_priority",
}

# =============================================================================
# CONVERSATIONAL INTENTS SET
# =============================================================================

# Set di intent che supportano workflow multi-turno
CONVERSATIONAL_INTENTS = {
    "ask_suggest_controls",
    "ask_priority_establishment",
    "ask_risk_based_priority",
    "ask_delayed_plans",
    "ask_establishment_history",
    "search_piani_by_topic"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_strategy_config(intent: str) -> Dict[str, Any]:
    """
    Recupera configurazione workflow per intent.

    Args:
        intent: Nome intent

    Returns:
        Configurazione workflow o dict vuoto se non configurato
    """
    return WORKFLOW_STRATEGIES.get(intent, {})


def get_supported_filters(intent: str) -> List[str]:
    """
    Recupera filtri supportati per intent.

    Args:
        intent: Nome intent

    Returns:
        Lista nomi filtri supportati
    """
    config = get_strategy_config(intent)
    return config.get("supported_filters", [])


def has_strategies(intent: str) -> bool:
    """
    Controlla se intent ha strategie multiple configurate.

    Args:
        intent: Nome intent

    Returns:
        True se ha strategie, False altrimenti
    """
    config = get_strategy_config(intent)
    strategies = config.get("strategies", [])
    return len(strategies) > 0


def validate_strategy_id(strategy_id: str) -> bool:
    """
    Valida se strategy_id è nella allowlist.

    Args:
        strategy_id: ID strategia da validare

    Returns:
        True se valido, False altrimenti
    """
    return strategy_id in STRATEGY_TO_INTENT_MAP


def get_intent_for_strategy(strategy_id: str) -> str:
    """
    Recupera intent mappato a strategy_id.

    Args:
        strategy_id: ID strategia

    Returns:
        Intent corrispondente o stringa vuota
    """
    return STRATEGY_TO_INTENT_MAP.get(strategy_id, "")


def is_conversational_intent(intent: str) -> bool:
    """
    Controlla se intent supporta workflow conversazionale.

    Args:
        intent: Nome intent

    Returns:
        True se conversazionale, False altrimenti
    """
    return intent in CONVERSATIONAL_INTENTS
