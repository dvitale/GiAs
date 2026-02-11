"""
Workflow Validator - Security Layer per Workflow Conversazionali.

SECURITY-CRITICAL MODULE
Questo modulo implementa validazione completa per prevenire:
- Session tampering (workflow_context non trusted)
- Cross-turn intent spoofing (nonce freshness validation)
- Filter injection (whitelist domain enforcement)
- TTL expiration (workflow stale > 5 minuti)
- Unsafe tool execution (strategy_id allowlist)
"""

import secrets
import time
import re
from typing import Dict, Any, Optional
from enum import Enum


class WorkflowStage(str, Enum):
    """
    Enum per stadi workflow conversazionale.

    Lifecycle completo:
    INITIAL → CLARIFYING/CHOOSING → COLLECTING → EXECUTING → REFINING → COMPLETED
    """
    INITIAL = "initial"           # Classificazione intent iniziale
    CLARIFYING = "clarifying"     # Sistema chiede chiarimenti
    CHOOSING = "choosing"         # Utente sceglie tra opzioni
    COLLECTING = "collecting"     # Raccolta parametri progressiva
    EXECUTING = "executing"       # Esecuzione tool
    REFINING = "refining"         # Raffinamento query
    COMPLETED = "completed"       # Workflow completato


class WorkflowValidator:
    """
    Validates and sanitizes workflow context to prevent injection attacks.

    Security Principles:
    1. Trust Boundary: workflow_context è server-side ma NON trusted
    2. Whitelist Enforcement: solo campi/valori esplicitamente permessi
    3. TTL Enforcement: workflow scaduti (>5min) vengono invalidati
    4. Nonce Freshness: token crittografico per prevenire spoofing
    5. Domain Validation: filtri validati contro whitelist comuni/ASL
    """

    # Whitelist dei campi permessi in workflow_context
    ALLOWED_WORKFLOW_FIELDS = {
        "workflow_id", "workflow_type", "workflow_stage", "workflow_nonce",
        "selected_strategy_id", "collected_params", "accumulated_filters",
        "current_strategy_index", "last_query_intent"
    }

    # Whitelist degli intent conversazionali
    ALLOWED_CONVERSATIONAL_INTENTS = {
        "ask_suggest_controls", "ask_priority_establishment",
        "ask_risk_based_priority", "ask_delayed_plans",
        "ask_establishment_history", "search_piani_by_topic"
    }

    # TTL workflow context (5 minuti in secondi)
    WORKFLOW_TTL = 300

    @staticmethod
    def create_workflow_nonce() -> str:
        """
        Genera token crittografico per workflow freshness.

        Returns:
            Token URL-safe a 32 byte (256 bit di entropia)
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_workflow_context(
        workflow_context: Optional[Dict[str, Any]],
        timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Valida workflow_context da session store.

        SECURITY: Questo è il trust boundary principale.
        Valida:
        1. TTL (timestamp < WORKFLOW_TTL)
        2. Whitelist campi (ALLOWED_WORKFLOW_FIELDS)
        3. workflow_type valido (ALLOWED_CONVERSATIONAL_INTENTS)
        4. workflow_stage valido (WorkflowStage enum)
        5. workflow_nonce presente

        Args:
            workflow_context: Context da session store
            timestamp: Unix timestamp creazione workflow

        Returns:
            Context sanitizzato o None se non valido
        """
        if not workflow_context:
            return None

        # Check TTL
        if time.time() - timestamp > WorkflowValidator.WORKFLOW_TTL:
            # Workflow scaduto
            return None

        # Whitelist fields
        sanitized = {}
        for key in WorkflowValidator.ALLOWED_WORKFLOW_FIELDS:
            if key in workflow_context:
                sanitized[key] = workflow_context[key]

        # Valida workflow_type
        workflow_type = sanitized.get("workflow_type")
        if workflow_type and workflow_type not in WorkflowValidator.ALLOWED_CONVERSATIONAL_INTENTS:
            # Intent non permesso
            return None

        # Valida workflow_stage
        stage = sanitized.get("workflow_stage")
        if stage:
            # Controlla se stage è un valore valido dell'enum
            try:
                WorkflowStage(stage)
            except ValueError:
                # Stage non valido
                return None

        # Valida workflow_nonce presente
        if "workflow_nonce" not in sanitized:
            # Nonce mancante
            return None

        return sanitized

    @staticmethod
    def validate_pending_question(
        pending_question: Optional[Dict[str, Any]],
        workflow_nonce: str
    ) -> bool:
        """
        Valida pending_question tied to workflow nonce.

        SECURITY: Previene cross-turn spoofing verificando nonce match.

        Args:
            pending_question: Domanda pending da session
            workflow_nonce: Nonce atteso del workflow corrente

        Returns:
            True se valido, False se tampered
        """
        if not pending_question:
            return True  # Nessuna domanda = ok

        # Check nonce match
        if pending_question.get("workflow_nonce") != workflow_nonce:
            # Nonce mismatch = tampered
            return False

        # Check question type valido
        valid_types = {"strategy_choice", "param_collection", "oppure_confirmation"}
        if pending_question.get("type") not in valid_types:
            return False

        return True

    @staticmethod
    def validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida e sanitizza filtri per prevenire injection.

        SECURITY: Whitelist enforcement per:
        - Comune: contro VALID_COMUNI
        - ASL: contro VALID_ASL
        - Limit: bounds checking [1, 500]
        - Tipo attività: pattern alfanumerici

        Args:
            filters: Filtri raw da validare

        Returns:
            Filtri sanitizzati (subset valido)
        """
        from .workflow_strategies import VALID_COMUNI, VALID_ASL

        sanitized = {}

        # Comune: valida contro whitelist
        if "comune" in filters:
            comune = str(filters["comune"]).strip().title()
            if comune in VALID_COMUNI:
                sanitized["comune"] = comune

        # ASL: valida pattern + whitelist
        if "asl" in filters:
            asl = str(filters["asl"]).strip().upper()
            # Pattern: [A-Z]{2}[0-9]
            if re.match(r'^[A-Z]{2}[0-9]$', asl) and asl in VALID_ASL:
                sanitized["asl"] = asl

        # Limit: valida range [1, 500]
        if "limit" in filters:
            try:
                limit = int(filters["limit"])
                sanitized["limit"] = max(1, min(limit, 500))  # Cap a 500
            except (ValueError, TypeError):
                pass  # Skip filtro non valido

        # UOC: valida pattern alfanumerico
        if "uoc" in filters:
            uoc = str(filters["uoc"]).strip()
            # Pattern: solo alfanumerici + spazi + trattini
            if re.match(r'^[A-Za-z0-9\s\-]+$', uoc) and len(uoc) <= 100:
                sanitized["uoc"] = uoc

        # Piano code: valida pattern
        if "piano_code" in filters:
            piano_code = str(filters["piano_code"]).strip().upper()
            # Pattern: A1, B2, C3_F, etc.
            if re.match(r'^[A-Z]+[0-9]+(?:_[A-Z]+)?$', piano_code):
                sanitized["piano_code"] = piano_code

        # Tipo attività: valida struttura composita
        if "tipo_attivita" in filters and isinstance(filters["tipo_attivita"], dict):
            tipo = {}
            for key in ["macroarea", "aggregazione", "attivita"]:
                if key in filters["tipo_attivita"]:
                    value = str(filters["tipo_attivita"][key]).strip()
                    # Sanitize: solo alfanumerici + spazi + trattini
                    if re.match(r'^[A-Za-z0-9\s\-àèéìòù]+$', value) and len(value) <= 200:
                        tipo[key] = value
            if tipo:
                sanitized["tipo_attivita"] = tipo

        # Data inizio/fine: valida formato ISO
        for date_field in ["data_inizio", "data_fine"]:
            if date_field in filters:
                date_str = str(filters[date_field]).strip()
                # Pattern: YYYY-MM-DD
                if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                    sanitized[date_field] = date_str

        # Categoria: valida contro pattern noto
        if "categoria" in filters:
            categoria = str(filters["categoria"]).strip().upper()
            # Categorie NC note
            valid_categorie = {
                "HACCP", "IGIENE", "STRUTTURE", "PULIZIA",
                "SANIFICAZIONE", "ETICHETTATURA", "MOCA", "RINTRACCIABILITA"
            }
            if categoria in valid_categorie:
                sanitized["categoria"] = categoria

        return sanitized

    @staticmethod
    def validate_strategy_id(strategy_id: str, workflow_type: str) -> bool:
        """
        Valida strategy_id contro allowlist per workflow_type.

        SECURITY: Previene execution di strategy non autorizzate.

        Args:
            strategy_id: ID strategia da validare
            workflow_type: Tipo workflow (intent)

        Returns:
            True se valido, False altrimenti
        """
        from .workflow_strategies import get_strategy_config

        config = get_strategy_config(workflow_type)
        strategies = config.get("strategies", [])

        # Verifica se strategy_id è tra le strategie configurate
        valid_ids = {s["id"] for s in strategies}
        return strategy_id in valid_ids
