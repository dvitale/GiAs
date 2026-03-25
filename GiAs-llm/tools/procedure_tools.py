"""
Tool RAG per informazioni su procedure operative.

Recupera chunk rilevanti dalla collection Qdrant 'procedure_documents'
e genera una risposta sintetizzata tramite LLM (Ollama).
"""

import json
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

INTEGRAZIONE FONTI:
8. INTEGRA le informazioni da fonti diverse in una risposta COERENTE e UNIFICATA
9. NON elencare le fonti separatamente - sintetizza il contenuto in una narrazione
10. Se le fonti forniscono dettagli complementari, combinali in un discorso unico
11. Se le fonti si CONTRADDICONO, segnalalo indicando le versioni diverse
12. Aggiungi CITAZIONI INLINE nel formato [Fonte N] dopo ogni affermazione chiave

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


def _expand_query(query: str, conversation_context: str = "") -> List[str]:
    """Genera varianti della query via LLM per retrieval piu' ampio."""
    try:
        from llm.client import LLMClient
        llm = LLMClient()
        context_hint = ""
        if conversation_context:
            context_hint = f'\nContesto conversazione: "{conversation_context}"\n'
        prompt = (
            f'Data la domanda su procedure GISA: "{query}"\n'
            f'{context_hint}'
            'Genera 2 riformulazioni con sinonimi e termini alternativi.\n'
            'Rispondi SOLO con JSON: {"variants": ["variante1", "variante2"]}'
        )
        response = llm.query(prompt=prompt, temperature=0.3, max_tokens=150,
                           json_mode=True, timeout=5)
        parsed = json.loads(response)
        variants = parsed.get("variants", [])[:2]
        return [query] + variants
    except Exception as e:
        print(f"[RAG] Query expansion fallita: {e}")
        return [query]


@tool("info_procedure")
def get_procedure_info(query: str, conversation_context: str = "") -> Dict[str, Any]:
    """
    RAG tool: recupera chunk dalla documentazione procedure e genera risposta con LLM.

    Args:
        query: Domanda dell'utente sulla procedura (es. "procedura ispezione semplice")
        conversation_context: Contesto conversazionale dalla sessione (opzionale)

    Returns:
        Dict con formatted_response (risposta LLM + fonti) e metadata.
    """
    if not query or not query.strip():
        return {
            "error": "Domanda non specificata",
            "formatted_response": "Devi specificare quale procedura desideri conoscere."
        }

    query = query.strip()

    # Check cache RAG
    try:
        from tools.rag_cache import get_rag_cache
        _cache = get_rag_cache()
        cached = _cache.get(query)
        if cached is not None:
            print(f"[RAG] Cache HIT per query: {query[:60]}...")
            return cached
    except Exception:
        _cache = None

    # 1. Calcola threshold dinamico basato sulla complessità della query
    threshold, top_k, complexity = _compute_dynamic_threshold(query)
    print(f"[RAG] Query complexity: {complexity}, threshold: {threshold}, top_k: {top_k}")

    # 2. Query expansion per complessità medio-alta
    if complexity in ("medium", "high", "very_high"):
        expanded_queries = _expand_query(query, conversation_context=conversation_context)
        print(f"[RAG] Query expansion: {len(expanded_queries)} varianti")
    else:
        expanded_queries = [query]

    # Query di retrieval aumentata con contesto conversazionale
    if conversation_context:
        retrieval_query = f"{conversation_context} {query}"
        print(f"[RAG] Conversation-aware query: {retrieval_query[:80]}...")
    else:
        retrieval_query = query

    # 3. Retrieve per ogni variante e merge (deduplica)
    all_chunks = []
    seen_contents = set()
    # Prima query usa contesto conversazionale
    for i, q in enumerate(expanded_queries):
        search_q = f"{conversation_context} {q}" if (i == 0 and conversation_context) else q
        results = DataRetriever.search_procedure_docs(
            query=search_q, top_k=top_k, score_threshold=threshold
        )
        for chunk in results:
            content_key = chunk["content"][:80].strip()
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                all_chunks.append(chunk)

    # Ordina per score e usa come chunks
    all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)

    # BM25 + RRF re-ranking (on-the-fly sui chunk recuperati)
    if len(all_chunks) >= 3:
        try:
            from tools.hybrid_search.bm25_scorer import BM25Scorer, rrf_combine
            vector_scores = [c.get("score", 0) for c in all_chunks]
            bm25_scores = BM25Scorer.score_chunks(query, [c["content"] for c in all_chunks])
            rrf_scores = rrf_combine(vector_scores, bm25_scores)
            # Re-ordina per RRF score
            indexed = sorted(enumerate(rrf_scores), key=lambda x: x[1], reverse=True)
            all_chunks = [all_chunks[i] for i, _ in indexed]
            print(f"[RAG] RRF re-ranking applied ({len(all_chunks)} chunks)")
        except Exception as e:
            print(f"[RAG] RRF fallback to vector-only: {e}")

    chunks = all_chunks

    # 4. Post-filtering adattivo basato sulla complessità
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
            "page_num": c.get("page_num"),
            "score": round(c.get("score", 0), 3)
        }
        for c in chunks
    ]

    result = {
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

    # Store in cache RAG
    if _cache is not None:
        try:
            _cache.set(query, result)
        except Exception:
            pass

    return result


def _build_rag_context(chunks: List[Dict]) -> str:
    """Assembla i chunk in un contesto testuale per il prompt LLM con deduplicazione."""
    seen_content = set()
    parts = []
    fonte_num = 0
    for chunk in chunks:
        # Deduplicazione: skip chunk con incipit quasi identico
        content_key = chunk['content'][:100].strip().lower()
        if content_key in seen_content:
            continue
        seen_content.add(content_key)
        fonte_num += 1

        header = f"[Fonte {fonte_num}: {chunk['title']}"
        if chunk.get("section"):
            header += f" - {chunk['section']}"
        if chunk.get("page_num"):
            header += f" (pag. {chunk['page_num']})"
        header += "]"
        parts.append(f"{header}\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


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
    """Formatta le fonti per attribution con numero pagina e link download (deduplicate per file+pagina)."""
    seen = set()
    sources = []
    # Deduplica anche i file per il link download (un link per file)
    seen_files = set()
    download_links = []
    for c in chunks:
        source_file = c.get("source_file", "")
        page_num = c.get("page_num")
        if source_file:
            # Chiave univoca: file + pagina (se presente)
            key = f"{source_file}:{page_num}" if page_num else source_file
            if key not in seen:
                seen.add(key)
                title = c.get("title", source_file)
                if page_num:
                    sources.append(f"- {title} ({source_file}, pag. {page_num})")
                else:
                    sources.append(f"- {title} ({source_file})")
            # Link download (uno per file)
            if source_file not in seen_files:
                seen_files.add(source_file)
                import urllib.parse
                encoded_name = urllib.parse.quote(source_file, safe="")
                download_url = f"/gias/webchat/api/admin/documents/{encoded_name}"
                display_name = source_file.replace("_", " ").replace(".pdf", "").replace(".PDF", "")
                download_links.append(f"- [Scarica {display_name}]({download_url})")
    result = "\n".join(sources)
    if download_links:
        result += "\n\n**Documenti scaricabili:**\n" + "\n".join(download_links)
    return result


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
