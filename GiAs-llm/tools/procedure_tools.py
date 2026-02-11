"""
Tool RAG per informazioni su procedure operative.

Recupera chunk rilevanti dalla collection Qdrant 'procedure_documents'
e genera una risposta sintetizzata tramite LLM (Ollama).
"""

from typing import Dict, Any, List, Tuple
import re

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(name):
        def decorator(func):
            return func
        return decorator

try:
    from agents.data_agent import DataRetriever
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever


# Termini di dominio GISA per valutare specificità query
DOMAIN_TERMS = {
    # Procedure e controlli
    "controllo ufficiale", "ispezione", "audit", "verifica", "sopralluogo",
    "non conformità", "nc", "prescrizione", "sanzione", "diffida",
    # Settori
    "haccp", "igiene", "sicurezza alimentare", "benessere animale",
    "macellazione", "caseificio", "lattiero", "apicoltura", "zootecnia",
    "mangimificio", "ristorante", "mensa", "bar", "panificio",
    # Entità GISA
    "stabilimento", "osa", "operatore", "asl", "uoc", "sian", "siav",
    "master list", "suap", "registrazione", "riconoscimento",
    # Documenti
    "verbale", "checklist", "campione", "referto", "certificato",
    # Animali
    "bovini", "suini", "ovini", "avicoli", "cani", "gatti", "animali d'affezione",
}

# Pattern per query generiche (threshold alto)
GENERIC_PATTERNS = re.compile(
    r'^(come|procedura|guida|passi|step)\s+(per|di|su)?\s*$',
    re.IGNORECASE
)


def _compute_dynamic_threshold(query: str) -> Tuple[float, int, str]:
    """
    Calcola threshold dinamico basato sulla complessità della query.

    Logica:
    - Query brevi/generiche → threshold ALTO (0.55) per evitare rumore
    - Query medie con termini dominio → threshold MEDIO (0.45)
    - Query lunghe/specifiche → threshold BASSO (0.38) per catturare varianti

    Args:
        query: La query dell'utente

    Returns:
        Tuple (threshold, top_k, complexity_level)
    """
    query_lower = query.lower()
    words = query_lower.split()
    word_count = len(words)

    # Conta termini di dominio presenti
    domain_matches = sum(1 for term in DOMAIN_TERMS if term in query_lower)

    # Calcola score di complessità (0-10)
    complexity_score = 0

    # Fattore 1: Lunghezza query
    if word_count <= 3:
        complexity_score += 1  # Query molto breve
    elif word_count <= 6:
        complexity_score += 3  # Query media
    elif word_count <= 10:
        complexity_score += 5  # Query lunga
    else:
        complexity_score += 7  # Query molto dettagliata

    # Fattore 2: Termini di dominio
    complexity_score += min(domain_matches * 2, 6)  # Max +6 per termini dominio

    # Fattore 3: Presenza di specificatori
    if re.search(r'\b(specifico|dettaglio|esatto|preciso)\b', query_lower):
        complexity_score += 2
    if re.search(r'\b(grave|critico|urgente|importante)\b', query_lower):
        complexity_score += 1

    # Fattore 4: Penalità per query troppo generiche
    if GENERIC_PATTERNS.match(query):
        complexity_score = max(0, complexity_score - 3)

    # Mappa score → threshold e top_k
    if complexity_score <= 3:
        # Query generica: threshold alto, pochi risultati
        return (0.55, 8, "low")
    elif complexity_score <= 6:
        # Query media: threshold bilanciato
        return (0.45, 10, "medium")
    elif complexity_score <= 9:
        # Query specifica: threshold più basso per varianti
        return (0.40, 12, "high")
    else:
        # Query molto specifica: threshold basso, più candidati
        return (0.38, 15, "very_high")


RAG_SYSTEM_PROMPT = """Sei un esperto di procedure operative del sistema GISA (Gestione Integrata Attivita' Sanitarie) della Regione Campania.

COMPETENZE:
- Procedure di ispezione e controllo ufficiale
- Registrazione non conformita' (NC)
- Gestione pratiche SUAP
- Classificazione attivita' via Master List
- Settori: apicoltura, zootecnia, animali d'affezione

REGOLE FONDAMENTALI:
1. Rispondi SOLO con informazioni presenti nel contesto documentale
2. Se il contesto non contiene la procedura richiesta, dillo esplicitamente
3. IGNORA completamente riferimenti a figure, immagini o screenshot
4. Usa SEMPRE liste numerate (1. 2. 3.) per i passaggi procedurali
5. NON mescolare procedure diverse nella stessa risposta
6. NON inventare passaggi non documentati
7. Usa terminologia GISA/ASL (non generica)

FORMATO RISPOSTA:
- Passaggi chiari e sequenziali
- Prerequisiti all'inizio (se presenti)
- Nessun riferimento a elementi visivi (figure, screenshot)
- Linguaggio diretto senza formule introduttive
"""

RAG_USER_TEMPLATE = """CONTESTO DOCUMENTALE:
{context}

DOMANDA: {query}

Rispondi basandoti sul contesto documentale fornito."""


@tool("info_procedure")
def get_procedure_info(query: str) -> Dict[str, Any]:
    """
    RAG tool: recupera chunk dalla documentazione procedure e genera risposta con LLM.

    Args:
        query: Domanda dell'utente sulla procedura (es. "procedura ispezione semplice")

    Returns:
        Dict con formatted_response (risposta LLM + fonti) e metadata.
    """
    if not query or not query.strip():
        return {
            "error": "Domanda non specificata",
            "formatted_response": "Devi specificare quale procedura desideri conoscere."
        }

    query = query.strip()

    # 1. Calcola threshold dinamico basato sulla complessità della query
    threshold, top_k, complexity = _compute_dynamic_threshold(query)
    print(f"[RAG] Query complexity: {complexity}, threshold: {threshold}, top_k: {top_k}")

    # 2. Retrieve chunk dalla collection procedure_documents
    chunks = DataRetriever.search_procedure_docs(
        query=query, top_k=top_k, score_threshold=threshold
    )

    # 3. Post-filtering adattivo basato sulla complessità
    # Query generiche: filtro più aggressivo (score >= threshold + 0.10)
    # Query specifiche: filtro più permissivo (score >= threshold + 0.05)
    if len(chunks) > 3:
        filter_delta = 0.10 if complexity == "low" else 0.05
        min_score = threshold + filter_delta
        high_quality = [c for c in chunks if c.get("score", 0) >= min_score]
        if len(high_quality) >= 2:
            chunks = high_quality

    # 4. Limita a 5 chunk migliori per il contesto LLM
    chunks = chunks[:5]

    if not chunks:
        return {
            "error": "no_results",
            "formatted_response": (
                "Non ho trovato informazioni nelle procedure documentate "
                "per la tua domanda.\n\n"
                "Prova a riformulare la domanda, ad esempio:\n"
                "- *Qual e' la procedura per ispezione semplice?*\n"
                "- *Come si esegue un controllo ufficiale?*\n"
                "- *Quali sono i passi per registrare una non conformita'?*"
            )
        }

    # 2. Assembla contesto dai chunk
    context = _build_rag_context(chunks)

    # 3. Chiama LLM per generare risposta
    llm_response = _generate_rag_response(query, context)

    if not llm_response:
        # Fallback: restituisci i chunk grezzi formattati
        llm_response = _format_chunks_fallback(chunks)

    # 4. Aggiungi attribution (fonti)
    sources = _format_sources(chunks)
    formatted = llm_response
    if sources:
        formatted += f"\n\n**Fonti:**\n{sources}"

    # Calcola confidence score
    avg_score = sum(c["score"] for c in chunks) / len(chunks) if chunks else 0
    confidence = "high" if avg_score >= 0.65 else "medium" if avg_score >= 0.50 else "low"

    # Estrai metadati chunk per suggerimenti dinamici (senza content per leggerezza)
    chunks_metadata = [
        {
            "title": c.get("title", ""),
            "section": c.get("section", ""),
            "source_file": c.get("source_file", ""),
            "score": round(c.get("score", 0), 3)
        }
        for c in chunks
    ]

    return {
        "query": query,
        "formatted_response": formatted,
        "chunks_found": len(chunks),
        "top_score": chunks[0]["score"] if chunks else 0,
        "avg_score": round(avg_score, 3),
        "confidence": confidence,
        # Parametri dinamici usati
        "dynamic_threshold": threshold,
        "query_complexity": complexity,
        # Metadati chunk per suggerimenti dinamici
        "chunks_metadata": chunks_metadata,
    }


def _build_rag_context(chunks: List[Dict]) -> str:
    """Assembla i chunk in un contesto testuale per il prompt LLM."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        header = f"[Fonte {i}: {chunk['title']}"
        if chunk.get("section"):
            header += f" - {chunk['section']}"
        header += "]"
        parts.append(f"{header}\n{chunk['content']}")
    return "\n\n".join(parts)


def _generate_rag_response(query: str, context: str) -> str:
    """Chiama LLM (Ollama) per generare risposta dal contesto RAG."""
    try:
        from llm.client import LLMClient
        llm = LLMClient()
        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": RAG_USER_TEMPLATE.format(
                context=context, query=query
            )}
        ]
        return llm.query(messages=messages, temperature=0.3)
    except Exception as e:
        print(f"⚠️  Errore generazione RAG response: {e}")
        return ""


def _format_chunks_fallback(chunks: List[Dict]) -> str:
    """Formatta i chunk grezzi come fallback se LLM non disponibile."""
    parts = ["**Informazioni trovate nella documentazione:**\n"]
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Documento")
        section = chunk.get("section", "")
        header = f"**{title}**"
        if section:
            header += f" - {section}"
        parts.append(f"{i}. {header}")
        parts.append(f"   {chunk['content'][:300]}...")
    return "\n\n".join(parts)


def _format_sources(chunks: List[Dict]) -> str:
    """Formatta le fonti per attribution (deduplicate)."""
    seen = set()
    sources = []
    for c in chunks:
        key = c.get("source_file", "")
        if key and key not in seen:
            seen.add(key)
            title = c.get("title", key)
            sources.append(f"- {title} ({key})")
    return "\n".join(sources)


def procedure_tool(query: str = None) -> Dict[str, Any]:
    """
    Router per il tool procedure (compatibilita' con pattern search_tool).

    Args:
        query: Domanda sulla procedura

    Returns:
        Dict con risultati
    """
    try:
        func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
        return func(query)
    except Exception as e:
        return {"error": f"Errore in procedure_tool: {str(e)}"}
