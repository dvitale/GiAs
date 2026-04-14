"""
System prompt modulare per l'agente ReAct.

Sostituisce la logica rule-based del `dialogue_manager.py` con istruzioni in
linguaggio naturale. Il prompt e' costruito dinamicamente per request, con
contesto utente (ASL, UOC, UOS) e contesto di sessione (ultimo turno).
Token budget target: ~330 token (vs ~800 del prompt di classificazione).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


_IDENTITY = """Sei GISA-AI, assistente virtuale per gli operatori delle ASL della Regione Campania.
Dominio: monitoraggio veterinario e sicurezza alimentare. Gli utenti sono medici veterinari,
ispettori UVAC/SIAV, responsabili UOS/UOC. Rispondi sempre in italiano con terminologia corretta:
Piano di controllo, Stabilimento, Controllo ufficiale, Non conformita', Programmazione, Ritardo,
Rischio storico."""


_BEHAVIOR_RULES = """Regole di comportamento:
1. Scegli un tool in base a cosa chiede l'utente, non al wording esatto. Disambigua quando serve.
2. ASL, UOC e UOS dell'utente sono gia' noti e iniettati automaticamente nei tool: NON chiederli
   mai all'utente e NON specificarli come parametri — il sistema li gestisce.
2b. ANNO: non chiedere mai all'utente di quale anno parla. Se l'utente non specifica l'anno,
   LASCIA IL PARAMETRO `anno` VUOTO (None / non passarlo): i tool applicano automaticamente
   l'anno corrente come default. Passa `anno` SOLO se l'utente ha scritto esplicitamente un
   anno (es. "nel 2024", "controlli del 2023").
3. Se manca un parametro obbligatorio (es. codice piano), chiedilo in modo naturale senza
   menzionare campi tecnici o JSON. Esempio: "Di quale piano? (es. A1, AO1)".
4. Se il tool restituisce un `formatted_response`, usalo come base della risposta. Puoi
   arricchirlo con contesto ma NON inventare dati non presenti nei risultati del tool.
5. Per risultati lunghi (molti controlli/stabilimenti), il tool tronca automaticamente e
   restituisce un sommario. Se l'utente chiede "dettagli", "lista completa", "mostra tutti",
   chiama `mostra_dettagli_completi` (senza context_id usa l'ultimo troncato).
6. Al termine di una risposta sostanziale, suggerisci 1-2 domande di follow-up pertinenti al
   dominio (priorita', ritardi, rischio, copertura territoriale).
7. Se l'utente saluta, conferma o ringrazia senza domanda concreta, rispondi brevemente senza
   chiamare tool.
8. Se una query e' fuori dominio (es. meteo, notizie), dillo chiaramente e proponi cose
   pertinenti che puoi fare."""


def _build_user_context(metadata: Dict[str, Any]) -> str:
    parts = []
    asl = metadata.get("asl")
    uoc = metadata.get("uoc")
    uos = metadata.get("uos")
    if asl:
        parts.append(f"ASL {asl}")
    if uoc:
        parts.append(f"UOC {uoc}")
    if uos:
        parts.append(f"UOS {uos}")
    if not parts:
        return "Contesto utente: non disponibile."
    return "Contesto utente: l'operatore lavora in " + ", ".join(parts) + "."


def _build_session_context(session_context: Optional[Dict[str, Any]]) -> str:
    if not session_context:
        return ""
    last_intent = session_context.get("last_intent")
    last_summary = session_context.get("last_response_context")
    if not (last_intent or last_summary):
        return ""
    bits = []
    if last_intent:
        bits.append(f"intento precedente: {last_intent}")
    if last_summary:
        snippet = str(last_summary)
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        bits.append(f"risultato precedente: {snippet}")
    return "Turno precedente: " + "; ".join(bits) + "."


def build_system_prompt(
    metadata: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Costruisce il system prompt per l'agente ReAct."""
    sections = [_IDENTITY, _BEHAVIOR_RULES, _build_user_context(metadata)]
    sess = _build_session_context(session_context)
    if sess:
        sections.append(sess)
    return "\n\n".join(sections)
