"""
SessionManager: gestione centralizzata sessioni per conversazioni multi-turno.

Elimina la duplicazione di logica sessione tra webhook sincrono e streaming.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, NamedTuple

logger = logging.getLogger(__name__)

# Session TTL in seconds (5 minutes)
SESSION_TTL = 300

# Pulizia periodica ogni N richieste
_CLEANUP_EVERY_N_REQUESTS = 100

# Intent che non rappresentano un cambio topic
CONTINUATION_INTENTS = {"confirm_show_details", "decline_show_details", "fallback"}


class SessionContext(NamedTuple):
    """Contesto sessione recuperato per un sender."""
    detail_context: Dict[str, Any]
    workflow_context: Optional[Dict[str, Any]]
    dialogue_state: Optional[Dict[str, Any]]
    metadata_enrichment: Dict[str, Any]
    session_valid: bool
    session_timestamp: float
    raw_session: Dict[str, Any]


class SessionManager:
    """Gestione thread-safe delle sessioni conversazionali."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._request_count = 0

    def get_session_context(self, sender: str) -> SessionContext:
        """
        Recupera tutto il contesto sessione per un sender.
        Thread-safe. Restituisce una copia dei dati.
        """
        with self._lock:
            raw = self._store.get(sender, {}).copy()

        session_timestamp = raw.get("timestamp", 0)
        session_valid = time.time() - session_timestamp <= SESSION_TTL

        # Detail context (scaduto se sessione non valida)
        detail_context = raw.get("detail_context", {}) if session_valid else {}

        # Metadata enrichment (campi da iniettare nel metadata del grafo)
        metadata_enrichment = {}
        if raw and session_valid:
            if raw.get("last_intent"):
                metadata_enrichment["_session_last_intent"] = raw["last_intent"]
            if raw.get("last_slots"):
                metadata_enrichment["_session_last_slots"] = raw["last_slots"]
            if raw.get("conversation_summary"):
                metadata_enrichment["_session_summary"] = raw["conversation_summary"]

            # Contesto risposta per risoluzione anaforica
            last_response_context = raw.get("last_response_context")
            if not last_response_context:
                ds = raw.get("dialogue_state") or {}
                last_response_context = ds.get("last_response_context")
            if last_response_context:
                metadata_enrichment["_session_last_response_context"] = last_response_context

            # Fallback recovery state
            if raw.get("fallback_suggestions"):
                metadata_enrichment["_fallback_suggestions"] = raw["fallback_suggestions"]
            if raw.get("fallback_phase"):
                metadata_enrichment["_fallback_phase"] = raw["fallback_phase"]
            if raw.get("fallback_count") is not None:
                metadata_enrichment["_fallback_count"] = raw["fallback_count"]
            if raw.get("fallback_selected_category"):
                metadata_enrichment["_fallback_selected_category"] = raw["fallback_selected_category"]

        # Workflow context (validato esternamente)
        workflow_context_raw = raw.get("workflow_context") if session_valid else None

        # Dialogue state
        dialogue_state = raw.get("dialogue_state") if session_valid else None

        return SessionContext(
            detail_context=detail_context,
            workflow_context=workflow_context_raw,
            dialogue_state=dialogue_state,
            metadata_enrichment=metadata_enrichment,
            session_valid=session_valid,
            session_timestamp=session_timestamp,
            raw_session=raw,
        )

    def update_session(self, sender: str, result: Dict[str, Any]) -> None:
        """
        Aggiorna il session store dal risultato del grafo.
        Include topic change detection. Thread-safe.
        """
        # Estrai last_response_context
        last_response_context = None
        ds = result.get("dialogue_state") or {}
        if ds.get("last_response_context"):
            last_response_context = ds["last_response_context"]
        elif result.get("response_context"):
            last_response_context = result["response_context"]

        current_intent = result.get("intent", "")

        if result.get("has_more_details") and result.get("detail_context"):
            session_data = {
                "detail_context": result["detail_context"],
                "last_intent": current_intent,
                "last_slots": result.get("slots", {}),
                "conversation_summary": f"intent={current_intent}, slots={result.get('slots', {})}",
                "timestamp": time.time(),
                "dialogue_state": result.get("dialogue_state"),
                "last_response_context": last_response_context,
            }
            if result.get("workflow_id"):
                session_data["workflow_context"] = self._build_workflow_context(result)
            self._apply_fallback_state(session_data, result)
            with self._lock:
                self._store[sender] = session_data
            logger.info(f"[Session] Stored detail_context + session for {sender}")

        elif current_intent in ["confirm_show_details", "decline_show_details"]:
            session_data = {
                "last_intent": current_intent,
                "last_slots": result.get("slots", {}),
                "conversation_summary": f"intent={current_intent}, slots={result.get('slots', {})}",
                "timestamp": time.time(),
                "dialogue_state": result.get("dialogue_state"),
                "last_response_context": last_response_context,
            }
            if result.get("workflow_id"):
                session_data["workflow_context"] = self._build_workflow_context(result)
            self._apply_fallback_state(session_data, result)
            with self._lock:
                self._store[sender] = session_data
            logger.info(f"[Session] Cleared detail_context, kept session for {sender}")

        else:
            # Always update conversational memory
            with self._lock:
                existing = self._store.get(sender, {}).copy()

            # Topic change detection
            previous_intent = existing.get("last_intent", "")
            is_topic_change = (
                previous_intent and
                current_intent and
                previous_intent != current_intent and
                current_intent not in CONTINUATION_INTENTS
            )

            if is_topic_change:
                existing.pop("last_response_context", None)
                existing.pop("detail_context", None)
                logger.info(f"[Session] Topic change ({previous_intent} -> {current_intent}), reset context for {sender}")

            existing["last_intent"] = current_intent
            existing["last_slots"] = result.get("slots", {})
            existing["conversation_summary"] = f"intent={current_intent}, slots={result.get('slots', {})}"
            existing["timestamp"] = time.time()
            if "detail_context" not in existing:
                existing["detail_context"] = {}
            existing["dialogue_state"] = result.get("dialogue_state")

            if last_response_context and not is_topic_change:
                existing["last_response_context"] = last_response_context

            if result.get("workflow_id"):
                existing["workflow_context"] = self._build_workflow_context(result)
            elif "workflow_context" in existing:
                del existing["workflow_context"]

            self._apply_fallback_state(existing, result)

            with self._lock:
                self._store[sender] = existing

    def invalidate_workflow(self, sender: str) -> None:
        """Rimuove solo workflow_context per un sender."""
        with self._lock:
            if sender in self._store:
                self._store[sender].pop("workflow_context", None)

    def periodic_cleanup(self) -> None:
        """Pulizia periodica sessioni scadute. Chiamata ogni N richieste."""
        self._request_count += 1
        if self._request_count % _CLEANUP_EVERY_N_REQUESTS != 0:
            return

        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if now - v.get("timestamp", 0) > SESSION_TTL * 2]
            for k in expired:
                del self._store[k]
        if expired:
            logger.info(f"[Session] Cleaned up {len(expired)} expired sessions, {len(self._store)} remaining")

    @staticmethod
    def _build_workflow_context(result: Dict[str, Any]) -> Dict[str, Any]:
        """Costruisce workflow_context dict dal risultato del grafo."""
        return {
            "workflow_id": result.get("workflow_id"),
            "workflow_nonce": result.get("workflow_nonce"),
            "workflow_type": result.get("workflow_type"),
            "workflow_stage": result.get("workflow_stage"),
            "pending_question": result.get("pending_question"),
            "available_options": result.get("available_options"),
            "workflow_history": result.get("workflow_history"),
            "accumulated_filters": result.get("accumulated_filters"),
            "selected_strategy_id": ((result.get("workflow_context") or {}).get("selected_strategy") or {}).get("id"),
            "current_strategy_index": (result.get("workflow_context") or {}).get("current_strategy_index"),
            "last_query_intent": ((result.get("workflow_context") or {}).get("last_query") or {}).get("intent"),
        }

    @staticmethod
    def _apply_fallback_state(session_data: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Aggiorna fallback recovery state in session_data."""
        if result.get("fallback_suggestions"):
            session_data["fallback_suggestions"] = result["fallback_suggestions"]
            session_data["fallback_phase"] = result.get("fallback_phase", 1)
            session_data["fallback_count"] = result.get("fallback_count", 0)
            if result.get("fallback_selected_category"):
                session_data["fallback_selected_category"] = result["fallback_selected_category"]
        elif result.get("intent") != "fallback":
            session_data.pop("fallback_suggestions", None)
            session_data.pop("fallback_phase", None)
            session_data.pop("fallback_count", None)
            session_data.pop("fallback_selected_category", None)
