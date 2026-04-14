# pyright: reportAttributeAccessIssue=false, reportCallIssue=false
"""
Tool registry per l'agente ReAct.

Espone `build_agent_tools(metadata)` che ritorna una lista di tool LangChain
con metadata utente (ASL, UOS) iniettati via closure. L'LLM vede solo i
parametri che deve effettivamente scegliere (piano_code, anno, ecc.); asl e
user_uos non fanno parte dello schema esposto, quindi l'LLM non puo'
inventarli o chiederli all'utente.

La stessa funzione popola il `DetailStore` (dict in-memory per sessione)
quando un tool restituisce un `detail_formatted` oltre al `formatted_response`
sommario. Il two-phase diventa cosi' un tool esplicito
`mostra_dettagli_completi(context_id)` che l'agente puo' invocare in
risposta a richieste come "fammi vedere tutti", "dettagli", ecc.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from tools._tool_compat import tool

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Detail store: popolato dai tool, consumato da `mostra_dettagli_completi`.
# Una istanza per request (viene passata a build_agent_tools).
# ----------------------------------------------------------------------


class DetailStore:
    """In-memory store dei detail_formatted per l'handoff two-phase."""

    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}

    def put(self, payload: Dict[str, Any]) -> str:
        cid = uuid.uuid4().hex[:12]
        self._items[cid] = payload
        return cid

    def get(self, cid: str) -> Optional[Dict[str, Any]]:
        return self._items.get(cid)

    def last(self) -> Optional[Dict[str, Any]]:
        if not self._items:
            return None
        # ultimo inserito
        return next(reversed(self._items.values()))


# ----------------------------------------------------------------------
# Helpers: risoluzione UOS dallo user_id se non presente in metadata.
# ----------------------------------------------------------------------


def _resolve_uos(metadata: Dict[str, Any]) -> Optional[str]:
    user_uos = metadata.get("uos")
    if user_uos:
        return user_uos
    user_id = metadata.get("user_id")
    if not user_id:
        return None
    try:
        from agents.data import get_uos_from_user_id  # type: ignore
        return get_uos_from_user_id(user_id)
    except Exception:
        return None


def _normalize_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# Builder principale
# ----------------------------------------------------------------------


def build_agent_tools(
    metadata: Dict[str, Any],
    detail_store: Optional[DetailStore] = None,
) -> List[Any]:
    """Costruisce i tool per l'agente ReAct con metadata iniettato.

    Args:
        metadata: session metadata (asl, user_id, uos, uoc, ...)
        detail_store: store per il pattern two-phase. Se None, ne crea uno
            locale (ma il chiamante dovrebbe fornirlo per riusarlo tra turni).

    Returns:
        Lista di BaseTool LangChain pronti per `create_react_agent`.
    """
    user_asl = metadata.get("asl")
    user_uos = _resolve_uos(metadata)
    store = detail_store if detail_store is not None else DetailStore()

    # ------------------------------------------------------------------
    # 1) statistiche_controlli — conteggio CU eseguiti o programmati
    # ------------------------------------------------------------------
    @tool("statistiche_controlli")
    def statistiche_controlli(
        piano_code: Optional[str] = None,
        anno: Optional[int] = None,
        macroarea: Optional[str] = None,
        tipo_conteggio: str = "eseguiti",
    ) -> Dict[str, Any]:
        """Conteggio aggregato di controlli ufficiali (CU) eseguiti o programmati.

        Usare quando l'utente chiede "quanti controlli", "statistiche controlli",
        "lista dei controlli", "controlli eseguiti", "controlli programmati",
        anche filtrati per piano, anno o macroarea.

        Args:
            piano_code: codice piano/attivita (es. "A9_A", "AO1"). Opzionale.
            anno: anno di riferimento. Se None usa l'anno corrente.
            macroarea: macroarea CU (es. "BENESSERE ANIMALE"). Opzionale.
            tipo_conteggio: "eseguiti" (default) o "programmati".
        """
        from tools.cu_statistics_tools import get_cu_statistics
        result = get_cu_statistics(
            piano_code=piano_code,
            anno=_normalize_int(anno),
            asl=user_asl,
            macroarea=macroarea,
            user_uos=user_uos,
            tipo_conteggio=tipo_conteggio,
        )
        # two-phase: se il tool ha prodotto un detail_formatted, memorizzalo
        detail = result.pop("detail_formatted", None)
        if detail:
            cid = store.put({"formatted_response": detail, "type": "cu_statistics_detail"})
            result["__detail_context_id"] = cid
            summary = result.get("formatted_response", "")
            if summary and cid:
                result["formatted_response"] = (
                    f"{summary}\n\n"
                    f"Se vuoi l'elenco completo, chiama `mostra_dettagli_completi` con context_id=\"{cid}\"."
                )
        return result

    # ------------------------------------------------------------------
    # 2) descrizione_piano — metadati di un piano specifico
    # ------------------------------------------------------------------
    @tool("descrizione_piano")
    def descrizione_piano(piano_code: str) -> Dict[str, Any]:
        """Restituisce descrizione, categoria e metadati di un piano di controllo.

        Args:
            piano_code: codice piano (es. "A1", "A9_A", "AO1").
        """
        from tools.piano_tools import get_piano_description
        return get_piano_description(piano_code=piano_code)

    # ------------------------------------------------------------------
    # 3) piani_in_ritardo — piani con ritardo programmati-eseguiti
    # ------------------------------------------------------------------
    @tool("piani_in_ritardo")
    def piani_in_ritardo(anno: Optional[int] = None, top_n: int = 10) -> Dict[str, Any]:
        """Elenco dei piani con ritardo tra controlli programmati ed eseguiti.

        Args:
            anno: anno di riferimento. Default: anno corrente.
            top_n: numero massimo piani da restituire (default 10).
        """
        from tools.priority_tools import get_delayed_plans
        return get_delayed_plans(anno=_normalize_int(anno), top_n=top_n, asl=user_asl)

    # ------------------------------------------------------------------
    # 4) priorita_ispezione_rischio — stabilimenti prioritari per rischio
    # ------------------------------------------------------------------
    @tool("priorita_ispezione_rischio")
    def priorita_ispezione_rischio(top_n: int = 10) -> Dict[str, Any]:
        """Classifica degli stabilimenti da ispezionare prima in base al rischio.

        Usa il predittore (ML o statistico) per ordinare per probabilita' di NC.

        Args:
            top_n: quanti stabilimenti restituire (default 10).
        """
        from tools.risk_tools import get_risk_based_priority
        return get_risk_based_priority(top_n=top_n, asl=user_asl, user_uos=user_uos)

    # ------------------------------------------------------------------
    # 5) cerca_piani — ricerca per topic/parole chiave
    # ------------------------------------------------------------------
    @tool("cerca_piani")
    def cerca_piani(query: str, top_k: int = 5) -> Dict[str, Any]:
        """Cerca piani di controllo per argomento usando ricerca ibrida.

        Args:
            query: testo libero (es. "piani sugli allevamenti avicoli").
            top_k: numero risultati (default 5).
        """
        from tools.search_tools import search_piani_by_topic
        return search_piani_by_topic(query=query, top_k=top_k)

    # ------------------------------------------------------------------
    # 6) mostra_dettagli_completi — handoff two-phase
    # ------------------------------------------------------------------
    @tool("mostra_dettagli_completi")
    def mostra_dettagli_completi(context_id: Optional[str] = None) -> Dict[str, Any]:
        """Mostra i dettagli completi di un risultato precedente.

        Chiamare quando l'utente chiede "mostra tutto", "dettagli", "lista completa",
        "fammi vedere tutti". Se `context_id` non e' specificato, usa l'ultimo
        risultato troncato dalla sessione corrente.
        """
        payload = store.get(context_id) if context_id else store.last()
        if not payload:
            return {
                "formatted_response": "Nessun dettaglio disponibile per questa conversazione."
            }
        return payload

    # ------------------------------------------------------------------
    # 7) aiuto — catalogo capacita'
    # ------------------------------------------------------------------
    @tool("aiuto")
    def aiuto() -> Dict[str, Any]:
        """Elenca le funzionalita' disponibili dell'assistente."""
        try:
            from orchestrator.intent_metadata_service import get_intent_metadata_service
            content = get_intent_metadata_service().get_help_content()
            if content:
                return {"formatted_response": content}
        except Exception:
            pass
        return {
            "formatted_response": (
                "Posso rispondere su: statistiche controlli, descrizione piani, "
                "piani in ritardo, priorita' ispezione per rischio, ricerca piani."
            )
        }

    return [
        statistiche_controlli,
        descrizione_piano,
        piani_in_ritardo,
        priorita_ispezione_rischio,
        cerca_piani,
        mostra_dettagli_completi,
        aiuto,
    ]
