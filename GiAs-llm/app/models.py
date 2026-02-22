"""
Modelli API nativi per GiAs-llm.
Sostituiscono il protocollo Rasa con un contratto tipizzato.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class UserMetadata(BaseModel):
    """Metadata utente tipizzato (sostituisce Dict non tipizzato)."""
    asl: Optional[str] = None
    asl_id: Optional[str] = None
    user_id: Optional[str] = None
    codice_fiscale: Optional[str] = None
    username: Optional[str] = None
    uoc: Optional[str] = None


class ChatMessage(BaseModel):
    """Messaggio chat in ingresso. Sostituisce RasaMessage."""
    sender: str
    message: str
    metadata: Optional[UserMetadata] = None


class ExecutionInfo(BaseModel):
    """Informazioni esecuzione grafo per debug/monitoring."""
    execution_path: List[str] = []
    node_timings: Dict[str, float] = {}
    total_execution_ms: Optional[float] = None


class Suggestion(BaseModel):
    """Suggerimento follow-up strutturato."""
    text: str
    query: Optional[str] = None


class ChatResult(BaseModel):
    """Risultato chat completo. Espone TUTTI i campi del grafo."""
    text: str
    intent: str = ""
    slots: Dict[str, Any] = {}
    suggestions: List[Suggestion] = []
    execution: Optional[ExecutionInfo] = None
    needs_clarification: bool = False
    has_more_details: bool = False
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Wire format per /api/v1/chat."""
    result: ChatResult
    sender: str


class ParseRequest(BaseModel):
    """Richiesta parsing NLU. Sostituisce RasaParseRequest."""
    text: str
    metadata: Optional[UserMetadata] = None


class ParseResult(BaseModel):
    """Risultato parsing NLU con confidence reale."""
    text: str
    intent: str
    confidence: float
    slots: Dict[str, Any] = {}
    needs_clarification: bool = False


class SSEFinalEvent(BaseModel):
    """Evento SSE finale tipizzato per streaming v1."""
    type: str = "final"
    timestamp: int
    result: ChatResult
