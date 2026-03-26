"""
Dialogue Manager: nodo centrale del nuovo workflow LangGraph.

Decide, sulla base del DialogueState accumulato e della classificazione
corrente, se:
- Eseguire un tool (info sufficiente)
- Chiedere disambiguazione all'utente (info insufficiente)
- Presentare strategie alternative
- Gestire raffinamento di query precedenti

Regole rule-based per velocità (nessuna chiamata LLM aggiuntiva).
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple

try:
    from .dialogue_state import (
        DialogueState, IntentCandidate, merge_slots, add_clarification,
    )
    from .workflow_strategies import (
        WORKFLOW_STRATEGIES, CONVERSATIONAL_INTENTS,
        get_strategy_config, has_strategies, FILTER_PATTERNS,
    )
    from .intent_metadata import get_intent_metadata
except ImportError:
    from orchestrator.dialogue_state import (
        DialogueState, IntentCandidate, merge_slots, add_clarification,
    )
    from orchestrator.workflow_strategies import (
        WORKFLOW_STRATEGIES, CONVERSATIONAL_INTENTS,
        get_strategy_config, has_strategies, FILTER_PATTERNS,
    )
    from orchestrator.intent_metadata import get_intent_metadata

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Soglie confidence adattive per modello
# Modelli piccoli (<=7B) producono confidence meno calibrata,
# quindi abbassare le soglie per evitare fallback inutili.
# ------------------------------------------------------------------
_MODEL_CONFIDENCE_THRESHOLDS = {
    "velvet":       {"high": 0.80, "min": 0.50, "delta": 0.20},
    "llama3.1":     {"high": 0.75, "min": 0.45, "delta": 0.20},
    "mistral-nemo": {"high": 0.80, "min": 0.50, "delta": 0.20},
    "llama3.2":     {"high": 0.60, "min": 0.35, "delta": 0.15},
    "ministral":    {"high": 0.65, "min": 0.40, "delta": 0.18},
    "falcon":       {"high": 0.65, "min": 0.40, "delta": 0.18},
    "google/gemini-2.5-flash": {"high": 0.80, "min": 0.50, "delta": 0.20},
}
_DEFAULT_THRESHOLDS = {"high": 0.80, "min": 0.50, "delta": 0.20}

def _get_thresholds():
    """Restituisce soglie confidence basate sul modello configurato."""
    try:
        from configs.config import AppConfig, LLMBackendConfig
        model_key = AppConfig.LLM_MODEL
        # Per provider esterni il modello reale e' nel backend config
        backend_type = LLMBackendConfig.get_backend_type()
        if backend_type in ("openai", "anthropic", "openai_compat", "openrouter"):
            backend_cfg = LLMBackendConfig.get_backend_config()
            model_key = backend_cfg.get("model", model_key)
        return _MODEL_CONFIDENCE_THRESHOLDS.get(model_key, _DEFAULT_THRESHOLDS)
    except Exception:
        return _DEFAULT_THRESHOLDS

_thresholds = _get_thresholds()
CONFIDENCE_HIGH = _thresholds["high"]
CONFIDENCE_AMBIGUITY_DELTA = _thresholds["delta"]
CONFIDENCE_MIN = _thresholds["min"]

# Intent auto-sufficienti che non richiedono slot obbligatori
SELF_SUFFICIENT_INTENTS = {
    "greet", "goodbye", "ask_help",
    "ask_priority_establishment", "ask_risk_based_priority",
    "ask_suggest_controls", "ask_delayed_plans",
    "ask_piano_statistics", "ask_top_risk_activities",
    "confirm_show_details", "decline_show_details",
}

# Required slots per intent (mirror di Router.REQUIRED_SLOTS)
REQUIRED_SLOTS = {
    "ask_piano_description": ["piano_code"],
    "ask_piano_stabilimenti": ["piano_code"],
    "check_if_plan_delayed": ["piano_code"],
    "search_piani_by_topic": ["topic"],
    "ask_establishment_history": ["num_registrazione", "numero_riconoscimento", "partita_iva", "ragione_sociale"],
    "ask_nearby_priority": ["location"],
}

from .constants import SLOT_PROMPTS

# Pattern per rilevare richieste vaghe
VAGUE_PATTERNS = [
    r"come\s+(?:mi\s+)?organizz",
    r"cosa\s+(?:devo|posso)\s+fare",
    r"da\s+dove\s+(?:inizio|parto|comincio)",
    r"aiut(?:ami|o)\s+(?:a\s+)?capire",
    r"indicazioni",
    r"consigli",
]

# Pattern per rilevare "oppure?" / richiesta alternative
OPPURE_PATTERNS = [
    r"^oppure\??$",
    r"^alternative\??$",
    r"^altro\s+modo\??$",
    r"^(?:e\s+)?(?:se\s+)?(?:invece|altrimenti)\??$",
    r"^(?:c['\u2019]è\s+)?(?:un['\u2019]?\s*)?altr[oa]\s+(?:opzione|possibilit[àa])\??$",
]

# Pattern per rilevare raffinamenti
REFINEMENT_PATTERNS = [
    r"(?:nel|del|al)\s+comune\s+(?:di\s+)?",
    r"(?:solo|filtra|cerca)\s+(?:nel|per|a)\s+",
    r"rifa[i']?\s+(?:la\s+)?(?:ricerca|analisi)",
    r"(?:stess[oa]\s+)?(?:ricerca|analisi)\s+(?:ma|però|solo)\s+",
    r"(?:mostra|vedi|fammi\s+vedere)\s+(?:solo|i\s+primi)\s+",
    r"(?:primi?|top)\s+\d+",
]

# Pattern per conferme / risposte affermative
CONFIRM_PATTERNS = [
    r"^s[ìi]$",
    r"^ok$",
    r"^va\s+bene$",
    r"^(?:certo|certamente|assolutamente)$",
    r"^(?:procedi|fallo|mostra|vai)$",
    r"^d['\u2019]?accordo$",
]


class DialogueManagerResult:
    """Risultato del dialogue manager."""

    def __init__(
        self,
        action: str,  # "execute", "ask_user", "fallback"
        target_tool: Optional[str] = None,
        question: Optional[str] = None,
        updated_state: Optional[DialogueState] = None,
        intent: Optional[str] = None,
        slots: Optional[Dict[str, Any]] = None,
    ):
        self.action = action
        self.target_tool = target_tool
        self.question = question
        self.updated_state = updated_state
        self.intent = intent
        self.slots = slots


def _get_missing_slots(intent: str, slots: Dict[str, Any]) -> List[str]:
    """Restituisce la lista di slot obbligatori mancanti per l'intent."""
    required = REQUIRED_SLOTS.get(intent, [])
    if intent == "ask_establishment_history":
        # Almeno un identificatore necessario
        if any(slots.get(k) for k in required):
            return []
        return required
    return [r for r in required if not slots.get(r)]


def is_oppure(message: str) -> bool:
    """Rileva se il messaggio è una variante di 'oppure?'"""
    msg = message.strip().lower()
    return any(re.match(p, msg) for p in OPPURE_PATTERNS)


def is_refinement(message: str) -> bool:
    """Rileva se il messaggio è un raffinamento di query precedente."""
    msg = message.strip().lower()
    return any(re.search(p, msg) for p in REFINEMENT_PATTERNS)


def _is_confirmation(message: str) -> bool:
    """Rileva se il messaggio è una conferma."""
    msg = message.strip().lower()
    return any(re.match(p, msg) for p in CONFIRM_PATTERNS)


def is_vague(message: str) -> bool:
    """Rileva se il messaggio è una richiesta vaga."""
    msg = message.strip().lower()
    return any(re.search(p, msg) for p in VAGUE_PATTERNS)


def _extract_filters(message: str) -> Dict[str, Any]:
    """Estrae filtri dal messaggio (comune, limit, ecc.)."""
    filters = {}
    msg = message.strip()

    # Comune
    comune_match = re.search(FILTER_PATTERNS["comune"], msg, re.IGNORECASE)
    if comune_match:
        filters["comune"] = comune_match.group(1)

    # Limit
    limit_match = re.search(FILTER_PATTERNS["limit"], msg.lower())
    if limit_match:
        limit_val = int(limit_match.group(1))
        if 1 <= limit_val <= 500:
            filters["limit"] = limit_val

    return filters


def _build_slot_question(intent: str, missing: List[str]) -> str:
    """Costruisce domanda per slot mancanti."""
    metadata = get_intent_metadata(intent)
    label = metadata.label if metadata else "questa richiesta"

    # Caso speciale: ask_establishment_history richiede ALMENO UNO degli identificatori
    if intent == "ask_establishment_history":
        return (
            f"Per trovare lo storico dello stabilimento, fornisci **uno** dei seguenti identificatori:\n\n"
            f"- Numero di registrazione (es. IT 123456, UE IT 2287 M)\n"
            f"- Partita IVA (es. 01234567890)\n"
            f"- Ragione sociale (anche parziale, es. \"Rossi SRL\")"
        )

    prompts = [f"- {SLOT_PROMPTS.get(s, f'Specifica: {s}')}" for s in missing]

    return f"Per completare la richiesta su *{label}*, ho bisogno di:\n\n" + "\n".join(prompts)


def _build_disambiguation_question(candidates: List[IntentCandidate]) -> str:
    """Costruisce domanda di disambiguazione tra intent candidati."""
    top = candidates[:3]
    options = []
    for i, c in enumerate(top, 1):
        metadata = get_intent_metadata(c["intent"])
        if metadata:
            options.append(f"{i}. **{metadata.label}**: {metadata.description}")
        else:
            options.append(f"{i}. {c['intent']}")

    return (
        "Non sono sicuro di aver capito. Intendi:\n\n"
        + "\n".join(options)
        + "\n\n*Rispondi con il numero o riformula la domanda.*"
    )


def _build_strategy_question(intent: str) -> Optional[str]:
    """Costruisce domanda per scelta strategia."""
    config = get_strategy_config(intent)
    strategies = config.get("strategies", [])
    if not strategies:
        return None

    initial_q = config.get("initial_question", "Come vuoi procedere?")
    options = []
    for i, s in enumerate(strategies, 1):
        options.append(f"{i}. **{s['label']}**: {s.get('description', '')}")

    return initial_q + "\n\n" + "\n".join(options)


def _resolve_tool(intent: str) -> str:
    """Risolve il nome del tool per un intent."""
    from .tool_nodes import INTENT_TO_TOOL
    return INTENT_TO_TOOL.get(intent, "fallback_tool")


def _rule_slot_continuation(
    ds: DialogueState, current_slots: Dict[str, Any], extracted_slots: Dict[str, Any]
) -> Optional[DialogueManagerResult]:
    """REGOLA 0: continuazione dopo richiesta slot mancanti."""
    if not (ds.get("confirmed_intent") and ds.get("missing_slots") and extracted_slots):
        return None

    pending_intent = ds["confirmed_intent"]
    pending_missing = ds["missing_slots"]
    filled = [s for s in pending_missing if current_slots.get(s)]

    if not filled:
        return None

    still_missing = _get_missing_slots(pending_intent, current_slots)
    if still_missing:
        return None

    tool_name = _resolve_tool(pending_intent)
    ds["last_tool_intent"] = pending_intent
    ds["last_tool_slots"] = current_slots
    ds["missing_slots"] = None

    logger.info(f"[DM] Slot continuation: {pending_intent} con slot {filled}")
    return DialogueManagerResult(
        action="execute", target_tool=tool_name,
        updated_state=ds, intent=pending_intent, slots=current_slots,
    )


def _rule_oppure(message: str, ds: DialogueState) -> Optional[DialogueManagerResult]:
    """REGOLA 7: gestione 'oppure?' per alternative."""
    if not (is_oppure(message) and ds.get("confirmed_intent")):
        return None

    intent = ds["confirmed_intent"]
    if not has_strategies(intent):
        return DialogueManagerResult(
            action="ask_user",
            question="Non ci sono alternative disponibili per questa richiesta.",
            updated_state=ds,
        )

    config = get_strategy_config(intent)
    strategies = config.get("strategies", [])
    current_id = ds.get("confirmed_strategy_id")

    current_idx = 0
    for i, s in enumerate(strategies):
        if s["id"] == current_id:
            current_idx = i
            break

    next_idx = (current_idx + 1) % len(strategies)
    next_strategy = strategies[next_idx]

    ds["confirmed_strategy"] = next_strategy["label"]
    ds["confirmed_strategy_id"] = next_strategy["id"]

    question = (
        f"**Alternativa**: {next_strategy['label']}\n\n"
        f"{next_strategy.get('description', '')}\n\n"
        f"Vuoi procedere con questa opzione?"
    )
    return DialogueManagerResult(action="ask_user", question=question, updated_state=ds)


def _rule_refinement(
    message: str, ds: DialogueState, current_slots: Dict[str, Any]
) -> Optional[DialogueManagerResult]:
    """REGOLA 5: raffinamento di query precedente."""
    if not (is_refinement(message) and ds.get("last_tool_intent")):
        return None

    intent = ds["last_tool_intent"]
    refined_slots = merge_slots(ds.get("last_tool_slots", {}), current_slots)
    refined_slots = merge_slots(refined_slots, ds.get("filters", {}))
    ds["slots"] = refined_slots

    tool_name = _resolve_tool(intent)
    if not tool_name or tool_name == "fallback_tool":
        return None

    logger.info(f"[DM] Refinement: re-execute {intent} con filtri {ds.get('filters', {})}")
    return DialogueManagerResult(
        action="execute", target_tool=tool_name,
        updated_state=ds, intent=intent, slots=refined_slots,
    )


def _rule_strategy_confirmation(
    message: str, ds: DialogueState, current_slots: Dict[str, Any]
) -> Optional[DialogueManagerResult]:
    """REGOLA 6: conferma strategia pendente."""
    if not (_is_confirmation(message) and ds.get("confirmed_intent") and ds.get("confirmed_strategy_id")):
        return None

    intent = ds["confirmed_intent"]
    strategy_id = ds["confirmed_strategy_id"]
    config = get_strategy_config(intent)

    for s in config.get("strategies", []):
        if s["id"] == strategy_id:
            mapped_intent = s["intent_mapping"]
            tool_name = _resolve_tool(mapped_intent)
            if tool_name and tool_name != "fallback_tool":
                ds["last_tool_intent"] = mapped_intent
                ds["last_tool_slots"] = current_slots
                return DialogueManagerResult(
                    action="execute", target_tool=tool_name,
                    updated_state=ds, intent=mapped_intent, slots=current_slots,
                )
    return None


def _rule_high_confidence_execute(
    message: str, ds: DialogueState, current_slots: Dict[str, Any],
    top_intent: str, top_confidence: float
) -> Optional[DialogueManagerResult]:
    """REGOLA 1+2: intent chiaro — esegui o chiedi slot mancanti."""
    if top_confidence < CONFIDENCE_HIGH:
        return None

    missing = _get_missing_slots(top_intent, current_slots)

    if not missing or top_intent in SELF_SUFFICIENT_INTENTS:
        ds["confirmed_intent"] = top_intent

        # Scelta strategia per richieste vaghe
        if (
            top_intent in CONVERSATIONAL_INTENTS
            and has_strategies(top_intent)
            and not ds.get("confirmed_strategy_id")
            and is_vague(message)
        ):
            question = _build_strategy_question(top_intent)
            if question:
                return DialogueManagerResult(action="ask_user", question=question, updated_state=ds)

        tool_name = _resolve_tool(top_intent)
        ds["last_tool_intent"] = top_intent
        ds["last_tool_slots"] = current_slots
        return DialogueManagerResult(
            action="execute", target_tool=tool_name,
            updated_state=ds, intent=top_intent, slots=current_slots,
        )

    # REGOLA 2: slot mancanti
    ds["confirmed_intent"] = top_intent
    ds["missing_slots"] = missing
    question = _build_slot_question(top_intent, missing)
    return DialogueManagerResult(action="ask_user", question=question, updated_state=ds)


def _rule_ambiguous(
    ds: DialogueState, candidates: List[IntentCandidate],
    top_confidence: float
) -> Optional[DialogueManagerResult]:
    """REGOLA 3: intent ambiguo (2+ candidati con confidence simile)."""
    if not (
        len(candidates) >= 2
        and top_confidence >= CONFIDENCE_MIN
        and top_confidence - candidates[1]["confidence"] < CONFIDENCE_AMBIGUITY_DELTA
    ):
        return None

    ds["intent_candidates"] = candidates[:3]
    question = _build_disambiguation_question(candidates)
    return DialogueManagerResult(action="ask_user", question=question, updated_state=ds)


def evaluate(
    message: str,
    candidates: List[IntentCandidate],
    extracted_slots: Dict[str, Any],
    dialogue_state: DialogueState,
    raw_message_type: str = "unknown",
) -> DialogueManagerResult:
    """
    Funzione principale del Dialogue Manager.

    Valuta lo stato del dialogo e decide l'azione successiva applicando
    le regole in ordine di priorita'.
    """
    ds = dialogue_state
    ds["turn_count"] = ds.get("turn_count", 0) + 1
    ds["timestamp"] = __import__("time").time()

    # Merge slot correnti con accumulati
    current_slots = merge_slots(ds.get("slots", {}), extracted_slots)
    ds["slots"] = current_slots

    # Merge filtri estratti dal messaggio
    new_filters = _extract_filters(message)
    if new_filters:
        ds["filters"] = merge_slots(ds.get("filters", {}), new_filters)

    # --- Regole context-based (prima dei candidati) ---

    result = _rule_slot_continuation(ds, current_slots, extracted_slots)
    if result:
        return result

    result = _rule_oppure(message, ds)
    if result:
        return result

    result = _rule_refinement(message, ds, current_slots)
    if result:
        return result

    result = _rule_strategy_confirmation(message, ds, current_slots)
    if result:
        return result

    # --- Analisi candidati dal Router ---

    if not candidates:
        return DialogueManagerResult(action="fallback", updated_state=ds)

    top = candidates[0]
    top_intent = top["intent"]
    top_confidence = top["confidence"]

    if top.get("slots"):
        current_slots = merge_slots(current_slots, top["slots"])
        ds["slots"] = current_slots

    result = _rule_high_confidence_execute(message, ds, current_slots, top_intent, top_confidence)
    if result:
        return result

    result = _rule_ambiguous(ds, candidates, top_confidence)
    if result:
        return result

    # REGOLA 4: Nessun candidato valido
    if top_confidence < CONFIDENCE_MIN:
        return DialogueManagerResult(action="fallback", updated_state=ds)

    # Default: intent con confidence media — prova a eseguire
    ds["confirmed_intent"] = top_intent
    missing = _get_missing_slots(top_intent, current_slots)

    if missing and top_intent not in SELF_SUFFICIENT_INTENTS:
        ds["missing_slots"] = missing
        question = _build_slot_question(top_intent, missing)
        return DialogueManagerResult(action="ask_user", question=question, updated_state=ds)

    tool_name = _resolve_tool(top_intent)
    ds["last_tool_intent"] = top_intent
    ds["last_tool_slots"] = current_slots
    return DialogueManagerResult(
        action="execute", target_tool=tool_name,
        updated_state=ds, intent=top_intent, slots=current_slots,
    )
