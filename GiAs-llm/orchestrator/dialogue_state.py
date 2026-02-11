"""
Dialogue State Tracking (DST) per conversazioni multi-turno.

Gestisce lo stato strutturato del dialogo tra turni HTTP,
sostituendo i campi sparsi in _session_store.
"""

import time
import copy
from typing import TypedDict, Optional, List, Dict, Any


class IntentCandidate(TypedDict):
    intent: str
    confidence: float
    slots: Dict[str, Any]


class ClarificationRecord(TypedDict):
    turn: int
    question: str
    answer: str
    resolved: str  # "intent", "strategy", "slot:<nome_slot>"


class DialogueState(TypedDict, total=False):
    # Obiettivo conversazionale
    goal: Optional[str]
    intent_candidates: List[IntentCandidate]

    # Stato confermato
    confirmed_intent: Optional[str]
    confirmed_strategy: Optional[str]
    confirmed_strategy_id: Optional[str]

    # Slot e filtri accumulati cross-turno
    slots: Dict[str, Any]
    missing_slots: List[str]
    filters: Dict[str, Any]

    # Storia dialogo
    clarification_history: List[ClarificationRecord]
    turn_count: int

    # Per refinement
    last_tool_result: Optional[Any]
    last_tool_intent: Optional[str]
    last_tool_strategy: Optional[str]
    last_tool_slots: Optional[Dict[str, Any]]

    # Per risoluzione riferimenti anaforici (es. "le varianti" -> "varianti del piano A2")
    last_response_context: Optional[str]  # Breve descrizione del contenuto della risposta

    # Timestamp per TTL
    timestamp: float


# TTL per dialogue state (5 minuti, come la sessione attuale)
DIALOGUE_STATE_TTL = 300


def create_empty_state() -> DialogueState:
    """Crea un DialogueState vuoto."""
    return DialogueState(
        goal=None,
        intent_candidates=[],
        confirmed_intent=None,
        confirmed_strategy=None,
        confirmed_strategy_id=None,
        slots={},
        missing_slots=[],
        filters={},
        clarification_history=[],
        turn_count=0,
        last_tool_result=None,
        last_tool_intent=None,
        last_tool_strategy=None,
        last_tool_slots=None,
        last_response_context=None,
        timestamp=time.time(),
    )


def is_state_valid(ds: Optional[Dict[str, Any]]) -> bool:
    """Verifica se lo state è valido (non scaduto, struttura corretta)."""
    if not ds or not isinstance(ds, dict):
        return False
    ts = ds.get("timestamp", 0)
    if time.time() - ts > DIALOGUE_STATE_TTL:
        return False
    return True


def merge_slots(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge slot: i nuovi hanno priorità sugli esistenti."""
    merged = {**existing}
    for k, v in new.items():
        if v is not None and v != "":
            merged[k] = v
    return merged


def add_clarification(
    ds: DialogueState,
    question: str,
    answer: str,
    resolved: str
) -> DialogueState:
    """Aggiunge un record di disambiguazione alla storia."""
    ds = copy.deepcopy(ds)
    history = ds.get("clarification_history", [])
    history.append(ClarificationRecord(
        turn=ds.get("turn_count", 0),
        question=question,
        answer=answer,
        resolved=resolved,
    ))
    ds["clarification_history"] = history
    return ds


def from_session(session_data: Dict[str, Any]) -> DialogueState:
    """
    Converte i dati sessione legacy in DialogueState.

    Backwards-compatible: se la sessione ha già un 'dialogue_state',
    lo restituisce. Altrimenti popola dai campi legacy.
    """
    if "dialogue_state" in session_data:
        ds = session_data["dialogue_state"]
        if is_state_valid(ds):
            return ds

    # Conversione da campi legacy
    ds = create_empty_state()
    ds["confirmed_intent"] = session_data.get("last_intent")
    ds["slots"] = session_data.get("last_slots", {})
    ds["timestamp"] = session_data.get("timestamp", time.time())

    # Converti workflow_context legacy
    wf = session_data.get("workflow_context")
    if wf and isinstance(wf, dict):
        ds["confirmed_strategy_id"] = wf.get("selected_strategy_id")
        ds["filters"] = wf.get("accumulated_filters", {})
        if wf.get("last_query_intent"):
            ds["last_tool_intent"] = wf["last_query_intent"]

    return ds


def to_session(ds: DialogueState) -> Dict[str, Any]:
    """
    Serializza DialogueState per storage in _session_store.

    Produce sia il nuovo formato (dialogue_state) che i campi legacy
    per backwards compatibility.
    """
    ds["timestamp"] = time.time()
    return {
        # Nuovo formato
        "dialogue_state": dict(ds),
        # Campi legacy per backwards compatibility
        "last_intent": ds.get("confirmed_intent") or "",
        "last_slots": ds.get("slots", {}),
        "conversation_summary": (
            f"intent={ds.get('confirmed_intent', '')}, "
            f"slots={ds.get('slots', {})}, "
            f"turn={ds.get('turn_count', 0)}"
        ),
        # Contesto semantico per risoluzione anaforica
        "last_response_context": ds.get("last_response_context"),
        "timestamp": ds.get("timestamp", time.time()),
    }
