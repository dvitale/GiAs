# Piano di Miglioramento RAG Pipeline - GiAs-llm

## Contesto

Il sistema RAG di GiAs-llm presenta due problemi principali:

1. **cpu_mode disabilita erroneamente il reranking LLM**: Il flag `hybrid_search.cpu_mode: true` in `configs/config.json` forza `VECTOR_ONLY` in `SmartRouter.select_strategy()`, disabilitando il reranking LLM. Ma il backend LLM attuale è **OpenRouter** (cloud, `google/gemini-2.5-flash`): le chiamate cloud non impattano la CPU locale, quindi il reranking dovrebbe restare attivo.

2. **Le risposte RAG non integrano i chunk**: I chunk recuperati vengono passati all'LLM senza istruzioni esplicite di fusione, citazione inline o gestione conflitti. Il prompt attuale non chiede di sintetizzare una risposta coerente da fonti multiple.

Il piano include 5 miglioramenti progressivi, ordinati per priorità e indipendenza. Ogni step è autocontenuto e può essere verificato isolatamente.

---

## Step 1: Fix cpu_mode / Decoupling reranking LLM cloud

### File da modificare

**`GiAs-llm/tools/hybrid_search/smart_router.py`**

### Cosa fare

1. Aggiungere `self._llm_cloud = None` nell'`__init__` (linea 51-63)

2. Aggiungere metodo `_is_llm_cloud_based()`:
```python
def _is_llm_cloud_based(self) -> bool:
    """Check se il backend LLM e' cloud (non risente di cpu_mode)."""
    if self._llm_cloud is not None:
        return self._llm_cloud
    try:
        from configs.config import LLMBackendConfig
        self._llm_cloud = LLMBackendConfig.is_external_provider()
    except Exception:
        self._llm_cloud = False
    return self._llm_cloud
```

Nota: `LLMBackendConfig.is_external_provider()` esiste già in `configs/config.py:210` e usa `EXTERNAL_BACKENDS = ["openai", "anthropic", "openai_compat", "openrouter"]` (linea 109).

3. Modificare `select_strategy()` (linea 79-83): sostituire `if self._is_cpu_mode():` con:
```python
# cpu_mode con LLM locale: forza vector_only
# cpu_mode con LLM cloud: lascia decidere alle routing rules (reranking non impatta CPU)
if self._is_cpu_mode() and not self._is_llm_cloud_based():
    analysis = self.query_analyzer.analyze(query)
    self._track_routing_decision(query, analysis, SearchStrategy.VECTOR_ONLY)
    return SearchStrategy.VECTOR_ONLY
```

### Verifica

```bash
cd /opt/lang-env/GiAs-llm && python -m pytest tests/unit/test_smart_router.py -v
```

Creare `tests/unit/test_smart_router.py` con test per:
- `cpu_mode=True + LLM cloud` → NON forza vector_only (routing rules normali)
- `cpu_mode=True + LLM locale` → forza vector_only
- `cpu_mode=False` → routing rules normali in ogni caso

### Rollback

Ripristinare `if self._is_cpu_mode():` nella condizione originale.

---

## Step 2: Miglioramento sintesi RAG (fusione chunk)

### File da modificare

**`GiAs-llm/tools/procedure_tools.py`**

### Cosa fare

1. **Aggiornare `RAG_SYSTEM_PROMPT`** (linea 116-139): Aggiungere istruzioni esplicite per fusione chunk, citazioni inline e gestione conflitti. Aggiungere dopo "Usa terminologia GISA/ASL (non generica)":

```
INTEGRAZIONE FONTI:
8. INTEGRA le informazioni da fonti diverse in una risposta COERENTE e UNIFICATA
9. NON elencare le fonti separatamente - sintetizza il contenuto in una narrazione
10. Se le fonti forniscono dettagli complementari, combinali in un discorso unico
11. Se le fonti si CONTRADDICONO, segnalalo indicando le versioni diverse
12. Aggiungi CITAZIONI INLINE nel formato [Fonte N] dopo ogni affermazione chiave
```

2. **Migliorare `_build_rag_context()`** (linea 250-261): Aggiungere deduplicazione chunk con contenuto quasi identico e separatori più chiari:

```python
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
```

### Verifica

```bash
cd /opt/lang-env/GiAs-llm && python -m pytest tests/integration/test_rag_consistency.py -v
```

Test manuale:
```bash
curl -X POST http://localhost:5005/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"come si registra un controllo ufficiale","metadata":{"asl":"AVELLINO"}}'
```

Verificare che la risposta contenga citazioni `[Fonte N]` e sia narrativa (non elenco di chunk).

### Rollback

Ripristinare `RAG_SYSTEM_PROMPT` e `_build_rag_context()` originali.

---

## Step 3: Query Expansion per RAG

### File da modificare

**`GiAs-llm/tools/procedure_tools.py`**

### Cosa fare

1. Aggiungere funzione `_expand_query()` prima di `get_procedure_info()`:

```python
def _expand_query(query: str) -> List[str]:
    """Genera varianti della query via LLM per retrieval piu' ampio."""
    try:
        from llm.client import LLMClient
        llm = LLMClient()
        prompt = (
            f'Data la domanda su procedure GISA: "{query}"\n'
            'Genera 2 riformulazioni con sinonimi e termini alternativi.\n'
            'Rispondi SOLO con JSON: {"variants": ["variante1", "variante2"]}'
        )
        response = llm.query(prompt=prompt, temperature=0.3, max_tokens=150,
                           json_mode=True, timeout=5)
        import json
        parsed = json.loads(response)
        variants = parsed.get("variants", [])[:2]
        return [query] + variants
    except Exception as e:
        print(f"[RAG] Query expansion fallita: {e}")
        return [query]
```

2. Modificare `get_procedure_info()` (dopo linea 174): usare query expansion per query medio-alte:

```python
# Query expansion per complessità medio-alta
if complexity in ("medium", "high", "very_high"):
    expanded_queries = _expand_query(query)
else:
    expanded_queries = [query]

# Retrieve per ogni variante e merge (deduplica)
all_chunks = []
seen_contents = set()
for q in expanded_queries:
    results = DataRetriever.search_procedure_docs(
        query=q, top_k=top_k, score_threshold=threshold
    )
    for chunk in results:
        content_key = chunk["content"][:80].strip()
        if content_key not in seen_contents:
            seen_contents.add(content_key)
            all_chunks.append(chunk)

# Ordina per score e usa come chunks
all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
chunks = all_chunks
```

### Verifica

```bash
cd /opt/lang-env/GiAs-llm && python -m pytest tests/integration/test_rag_consistency.py -v
```

Test manuale con query colloquiale (diversa dalla terminologia documenti):
```bash
curl -X POST http://localhost:5005/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"come faccio a mettere una multa","metadata":{"asl":"AVELLINO"}}'
```

### Rollback

Rimuovere `_expand_query()` e ripristinare la chiamata diretta a `DataRetriever.search_procedure_docs()` in `get_procedure_info()`.

---

## Step 4: Parent-Child Chunking

### File da modificare

1. **`GiAs-llm/tools/indexing/doc_chunker.py`**
2. **`GiAs-llm/tools/indexing/build_docs_index.py`**
3. **`GiAs-llm/agents/data_agent.py`**
4. **`GiAs-llm/configs/config.json`**

### Cosa fare

1. **`doc_chunker.py`**: Aggiungere metodo `chunk_text_with_parents()` alla classe `DocumentChunker`:
   - Genera parent chunks (1800 char, overlap 200) per contesto ampio
   - Genera child chunks (600 char, overlap 100) per retrieval preciso
   - Mappa ogni child al parent che lo contiene (match testuale `child.content in parent.content`)
   - Aggiunge `parent_content` e `parent_metadata` a ogni child chunk

2. **`build_docs_index.py`**: Usare `chunk_text_with_parents()` e salvare `parent_content` nel payload Qdrant:
   ```python
   payload={
       "content": chunk["content"],         # Child (per retrieval)
       "parent_content": chunk.get("parent_content", chunk["content"]),  # Parent (per LLM)
       ...
   }
   ```

3. **`data_agent.py`** in `search_procedure_docs()`: restituire `parent_content` quando disponibile:
   ```python
   "content": hit.payload.get("parent_content", hit.payload.get("content", "")),
   ```

4. **`configs/config.json`**: Aggiungere a `rag_documents`:
   ```json
   "parent_chunk_size": 1800,
   "parent_chunk_overlap": 200
   ```

### Verifica

1. Re-indicizzare: `cd /opt/lang-env/GiAs-llm && python3 tools/indexing/build_docs_index.py`
2. Verificare payload: query Qdrant per confermare `parent_content` presente e più lungo di `content`
3. Test RAG: `python -m pytest tests/integration/test_rag_consistency.py -v`

### Rollback

1. Ripristinare `data_agent.py` per usare `content` (non `parent_content`)
2. Re-indicizzare con `build_docs_index.py` senza parent-child
3. Il codice è backward-compatible: `payload.get("parent_content", payload.get("content"))` funziona anche senza `parent_content`

---

## Step 5: Abilitare Hybrid Search per search_piani_by_topic

### File da modificare

**`GiAs-llm/tools/search_tools.py`**

### Cosa fare

Modificare `search_piani_by_topic()` (linea 23) per tentare prima hybrid search, poi fallback a DB ILIKE:

1. Aggiungere lazy singleton `_hybrid_engine`:
```python
_hybrid_engine = None

def _get_hybrid_engine():
    global _hybrid_engine
    if _hybrid_engine is None:
        try:
            from tools.hybrid_search import HybridSearchEngine
            from llm.client import LLMClient
            _hybrid_engine = HybridSearchEngine(llm_client=LLMClient())
            print("[SEARCH] HybridSearchEngine inizializzato")
        except Exception as e:
            print(f"[SEARCH] HybridSearchEngine non disponibile: {e}")
    return _hybrid_engine
```

2. In `search_piani_by_topic()`, prima di `DataRetriever.search_piani_by_db()`:
```python
engine = _get_hybrid_engine()
if engine is not None:
    try:
        result = engine.search(search_term)
        if result.get("matches") and not result.get("error"):
            return result
    except Exception as e:
        print(f"[SEARCH] Hybrid fallback a DB ILIKE: {e}")
```

Il fallback a DB ILIKE resta invariato come safety net.

**Dipendenza**: Richiede Step 1 completato (altrimenti cpu_mode forza vector_only e l'hybrid search non aggiunge reranking).

### Verifica

```bash
cd /opt/lang-env/GiAs-llm && python -m pytest tests/integration/test_search_real.py -v
cd /opt/lang-env/GiAs-llm && python -m pytest tests/e2e/test_intents.py -k "search_piani" -v
```

### Rollback

Rimuovere il blocco hybrid engine e ripristinare la chiamata diretta a `DataRetriever.search_piani_by_db()`.

---

## Sequenza di implementazione

```
Step 1 (cpu_mode fix)  ─────► Step 5 (hybrid per piani) [dipendenza]
Step 2 (sintesi RAG)   ─────► indipendente
Step 3 (query expansion) ───► indipendente
Step 4 (parent-child)  ─────► richiede re-indicizzazione
```

**Steps 1, 2, 3** sono indipendenti e possono essere implementati in parallelo.
**Step 5** dipende da Step 1.
**Step 4** richiede re-indicizzazione dei documenti (schedule durante manutenzione).

## Aggiornamento documentazione

Dopo l'implementazione, aggiornare **`GiAs-llm/docs/CLAUDE.md`**:
- Sezione hybrid search: documentare comportamento cpu_mode con provider cloud
- Sezione RAG: documentare parent-child chunking, query expansion, sintesi con citazioni
- Non duplicare nei CLAUDE.md root o gchat (principio singola fonte di verità)
