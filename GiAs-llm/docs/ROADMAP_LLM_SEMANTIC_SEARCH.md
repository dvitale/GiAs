# Roadmap: Migrazione da Vector Search a LLM-First Semantic Search

**Data Creazione**: 2026-01-09
**Ultima Modifica**: 2026-01-09
**Status**: 🟡 Pianificazione
**Obiettivo**: Eliminare l'inconsistenza architetturale tra vector embeddings e LLM reasoning

---

## Problema Identificato

### Inconsistenza Architetturale Attuale

Il sistema GiAs-llm presenta una **contraddizione fondamentale**:

```
🤖 LLM classifica intent semanticamente → "attività zootecniche"
     ↓
📊 Vector search usa embeddings statici → similarità vettoriale
     ↓
❌ Risultati subottimali per comprensione semantica complessa
```

**Core Issue**: Stiamo usando due "cervelli" diversi per lo stesso compito semantico:
- **LLM**: Dynamic reasoning, context-aware, domain-specific
- **Vector Model**: Static embeddings, generic model, no reasoning

### Problemi Specifici

1. **Coerenza**: LLM capisce "apicoltura" ma vector model restituisce "funghi"
2. **Maintenance**: Due sistemi da sincronizzare (LLM + embeddings)
3. **Performance gap**: LLM migliora nel tempo, embeddings statici
4. **Context loss**: Embeddings 384D vs infinite context LLM
5. **Domain mismatch**: Vector model generico vs LLM specializzabile

---

## Roadmap di Migrazione

### FASE 1: Analysis & Baseline (Settimana 1)
**Durata**: 3 giorni
**Obiettivo**: Quantificare problema attuale e stabilire metriche

#### Task 1.1: Performance Audit Attuale
```bash
# Benchmark systematic delle query problematiche
python3 tools/benchmark_semantic_search.py
```

**Deliverable**: Report con:
- Accuracy vector search su 50 query test
- Latency breakdown (vector vs LLM components)
- False positive/negative analysis
- Query categories più problematiche

#### Task 1.2: LLM Capability Assessment
```python
# Test LLM semantic understanding su stesso dataset
test_llm_semantic_reasoning.py
```

**Deliverable**: Baseline LLM performance per:
- Intent classification accuracy
- Semantic similarity judgment
- Domain-specific reasoning (veterinario)
- Context utilization effectiveness

#### Task 1.3: Metrics Definition
**Metriche di successo**:
- **Accuracy**: F1-score su query semantiche complesse
- **Latency**: P95 response time
- **Consistency**: Variance in risposte ripetute
- **Coverage**: % query con risultati rilevanti

---

### FASE 2: LLM-First Prototype (Settimana 2)
**Durata**: 5 giorni
**Obiettivo**: Implementare search semantico puramente LLM-based

#### Task 2.1: Core LLM Search Implementation
```python
# File: tools/semantic_search_llm.py
@tool("search_piani_llm_semantic")
def search_piani_llm_semantic(query: str, max_results: int = 10) -> Dict[str, Any]:
    """Pure LLM semantic search con reasoning esplicito"""
```

**Features**:
- Prompt engineering per semantic understanding
- JSON structured output con rationale
- Confidence scoring per ogni risultato
- Domain-specific reasoning prompts

#### Task 2.2: Context Optimization
**Sfide**:
- 730 piani × ~100 chars = ~73K tokens (vicino ai limiti)
- Context window management
- Prompt structure per max relevance

**Solutions**:
- Hierarchical search: categoria → piano specifico
- Chunked context con summarization
- Template ottimizzati per token efficiency

#### Task 2.3: Error Handling & Fallbacks
```python
def search_with_fallbacks(query: str) -> Dict:
    try:
        # Primary: Full LLM semantic
        return llm_semantic_search(query)
    except (TimeoutError, TokenLimitError):
        # Fallback 1: LLM con context ridotto
        return llm_search_reduced_context(query)
    except LLMError:
        # Fallback 2: Current vector approach
        return vector_search_fallback(query)
```

---

### FASE 3: A/B Testing Framework (Settimana 3)
**Durata**: 4 giorni
**Obiettivo**: Comparazione sistematica LLM vs Vector approach

#### Task 3.1: Parallel Execution System
```python
# File: tools/search_ab_testing.py
class SearchABTester:
    def __init__(self):
        self.vector_searcher = VectorSearcher()
        self.llm_searcher = LLMSearcher()

    def compare_approaches(self, query: str) -> ABTestResult:
        """Execute both approaches in parallel, log results"""
```

**Metrics tracked**:
- Side-by-side result comparison
- User preference simulation
- Latency distribution
- Error rate per approach

#### Task 3.2: Automated Evaluation Suite
```python
# Test suite con ground truth
test_queries = [
    {"query": "piani apicoltura", "expected_top3": ["B19", "A9", "A13"]},
    {"query": "benessere animale", "expected_top3": ["A13", "B36", "B56"]},
    {"query": "allevamenti bovini", "expected_top3": ["A1", "A9", "B2"]},
    # ... 50 queries totali
]
```

#### Task 3.3: User Simulation Framework
```python
def simulate_user_preferences(results_vector, results_llm):
    """Simula preferenze utente basate su criteri oggettivi"""
    criteria = [
        "semantic_relevance",
        "domain_specificity",
        "result_completeness",
        "explanation_quality"
    ]
```

---

### FASE 4: Hybrid Architecture (Settimana 4-5)
**Durata**: 7 giorni
**Obiettivo**: Best-of-both-worlds durante transition period

#### Task 4.1: Smart Routing Logic
```python
class SmartSearchRouter:
    def route_query(self, query: str) -> SearchStrategy:
        """Decide dinamicamente quale approccio usare"""

        if self.is_simple_query(query):
            return SearchStrategy.VECTOR_FAST
        elif self.is_complex_semantic(query):
            return SearchStrategy.LLM_REASONING
        else:
            return SearchStrategy.HYBRID_RERANKING
```

**Routing criteria**:
- Query complexity (lunghezza, termini tecnici)
- Available latency budget
- User context (expert vs novice)
- Historical success rate per query type

#### Task 4.2: LLM Reranking Implementation
```python
def hybrid_search_reranking(query: str) -> List[Result]:
    """Vector retrieval + LLM reranking"""

    # Stage 1: Fast vector retrieval (top-20)
    candidates = vector_search(query, top_k=20)

    # Stage 2: LLM semantic reranking (top-10)
    reranked = llm_rerank(query, candidates)

    return reranked
```

**Benefits**:
- Mantiene velocità vector search per recall
- Aggiunge precision LLM per final ranking
- Gradual migration path

#### Task 4.3: Configuration Management
```python
# config.json extension
"semantic_search": {
    "default_strategy": "hybrid",
    "strategies": {
        "vector_only": {"max_latency_ms": 200},
        "llm_only": {"min_confidence": 0.8},
        "hybrid": {"vector_candidates": 20, "llm_rerank": true}
    },
    "routing_rules": [
        {"condition": "query_length > 5", "strategy": "llm_only"},
        {"condition": "complex_domain_terms", "strategy": "llm_only"}
    ]
}
```

---

### FASE 5: Full LLM Migration (Settimana 6-7)
**Durata**: 8 giorni
**Obiettivo**: Migration completa a LLM-first con vector fallback

#### Task 5.1: Production LLM Search
**Optimizations**:
- Prompt caching per query comuni
- Context compression techniques
- Batch processing per query multiple
- Model selection per use case

```python
class ProductionLLMSearch:
    def __init__(self):
        self.prompt_cache = PromptCache(ttl=3600)
        self.context_compressor = ContextCompressor()
        self.model_selector = ModelSelector()

    def search(self, query: str) -> SearchResult:
        """Production-ready LLM semantic search"""
        model = self.model_selector.select_optimal(query)
        context = self.context_compressor.optimize(query)
        prompt = self.prompt_cache.get_or_create(query, context)

        return model.generate(prompt)
```

#### Task 5.2: Performance Optimization
**Techniques**:
- Model warming per cold starts
- Connection pooling per Ollama
- Context preprocessing
- Response streaming

**Target Performance**:
- P95 latency: <2s (vs current 3-4s)
- Accuracy: >95% su test suite
- Cache hit rate: >60% per query comuni

#### Task 5.3: Monitoring & Alerting
```python
# File: monitoring/semantic_search_metrics.py
class LLMSearchMetrics:
    def track_query(self, query, results, latency, accuracy):
        """Track real-time performance metrics"""

    def alert_on_degradation(self):
        """Alert se performance scende sotto threshold"""

    def generate_daily_report(self):
        """Report daily con insights e recommendations"""
```

---

### FASE 6: Vector Deprecation (Settimana 8)
**Durata**: 3 giorni
**Obiettivo**: Cleanup completo e removal vector dependencies

#### Task 6.1: Code Cleanup
**Files da modificare/rimuovere**:
```bash
# Deprecate vector search implementation
rm -rf qdrant_storage/
rm tools/indexing/build_qdrant_index.py
rm -f requirements_vector.txt

# Update core files
agents/agents/data_agent.py  # Remove vector methods
tools/search_tools.py        # Remove vector fallback
config.json                  # Remove qdrant config
```

#### Task 6.2: Dependencies Cleanup
```bash
# Remove from requirements.txt
pip uninstall qdrant-client sentence-transformers torch

# Update imports
grep -r "qdrant\|sentence_transformers" . --exclude-dir=.git
# Replace con LLM-only imports
```

#### Task 6.3: Documentation Update
**Files da aggiornare**:
- `SEMANTIC_SEARCH.md` → `LLM_SEMANTIC_SEARCH.md`
- `README.md` → Remove vector search sections
- `ARCHITECTURE_PRESENTATION.md` → Update search flow
- `CLAUDE.md` → Update search patterns

---

## Implementation Details

### Core LLM Search Prompt Template

```python
SEMANTIC_SEARCH_PROMPT = """
Sei un esperto del sistema di monitoraggio veterinario della Regione Campania.

Query operatore ASL: "{query}"
Metadata: ASL {asl}, UOC {uoc}

Analizza semanticamente la query e seleziona i piani di monitoraggio più rilevanti.

PIANI DISPONIBILI:
{plans_context}

CRITERI DI SELEZIONE:
1. Comprensione semantica (non solo keyword matching)
2. Rilevanza nel dominio veterinario
3. Considerazione di sinonimi e concetti correlati
4. Contesto operativo ASL/UOC

RISPOSTA (JSON):
{{
    "reasoning": "analisi semantica della query e logica di selezione",
    "selected_plans": [
        {{
            "alias": "A1",
            "confidence": 0.95,
            "rationale": "motivo specifico di rilevanza per la query",
            "semantic_match": ["keyword1", "keyword2"]
        }}
    ],
    "query_interpretation": "come hai interpretato la richiesta dell'operatore",
    "alternatives": ["suggerimenti per query correlate"]
}}

Seleziona massimo {max_results} piani ordinati per rilevanza.
"""
```

### Context Compression Strategy

```python
def compress_plans_context(all_plans: List[Dict], query: str) -> str:
    """Optimize context per token efficiency"""

    # 1. Pre-filter per relevance keywords
    relevant_plans = keyword_prefilter(all_plans, query)

    # 2. Hierarchical context: category → detailed
    context = []
    for category in group_by_category(relevant_plans):
        context.append(f"CATEGORIA {category}:")
        for plan in relevant_plans:
            # Compact format: alias, keywords, core description
            context.append(f"  {plan.alias}: {plan.core_keywords} - {plan.summary}")

    # 3. Token budget management
    max_tokens = 4000  # Leave room for response
    return truncate_to_tokens(context, max_tokens)
```

### Error Handling & Resilience

```python
class ResilientLLMSearch:
    def __init__(self):
        self.retry_config = RetryConfig(max_attempts=3, backoff=exponential)
        self.fallback_strategies = [
            LLMSearchReducedContext(),
            LLMSearchCategorical(),
            VectorSearchFallback()  # Ultimate fallback
        ]

    @retry(**self.retry_config)
    def search(self, query: str) -> SearchResult:
        """Search con retry automatici e fallback strategies"""
        for strategy in self.fallback_strategies:
            try:
                result = strategy.execute(query)
                if result.confidence > 0.6:
                    return result
            except Exception as e:
                logger.warning(f"Strategy {strategy} failed: {e}")
                continue

        # Se tutto fallisce, ritorna risultato minimale
        return SearchResult.empty_with_error()
```

---

## Timeline & Milestones

| Fase | Durata | Milestone | Success Criteria |
|------|--------|-----------|------------------|
| **Fase 1** | 3 giorni | Baseline Analysis | Vector search performance quantificato |
| **Fase 2** | 5 giorni | LLM Prototype | LLM search funzionante con accuracy >90% |
| **Fase 3** | 4 giorni | A/B Framework | Comparison framework completo |
| **Fase 4** | 7 giorni | Hybrid System | Hybrid search production-ready |
| **Fase 5** | 8 giorni | Full LLM | LLM-first approach live |
| **Fase 6** | 3 giorni | Cleanup | Vector dependencies rimosse |

**Totale**: 30 giorni (6 settimane)

---

## Risk Mitigation

### Risk 1: LLM Latency Regression
**Mitigation**:
- Mantenere vector fallback durante migration
- Implement aggressive caching
- Model selection ottimizzata per velocità

### Risk 2: Accuracy Degradation
**Mitigation**:
- Extensive A/B testing prima di switch
- Gradual rollout con feature flags
- Quick rollback capability

### Risk 3: Token Cost Explosion
**Mitigation**:
- Local Ollama (no API costs)
- Context compression techniques
- Smart caching per query frequenti

### Risk 4: Context Window Limits
**Mitigation**:
- Hierarchical search strategy
- Context chunking algorithms
- Fallback to category-based search

---

## Success Metrics

### Primary KPIs
- **Semantic Accuracy**: >95% relevance su test suite (vs current ~85%)
- **User Satisfaction**: Query resolution rate >90%
- **System Consistency**: Architectural coherence (LLM-only reasoning)

### Performance KPIs
- **Latency P95**: <2s (acceptable per use case ASL)
- **Availability**: >99.5% uptime
- **Error Rate**: <1% su query normali

### Technical KPIs
- **Code Simplicity**: -50% search-related LOC
- **Maintenance Overhead**: -100% vector dependencies
- **Documentation Coherence**: Single search paradigm

---

## Dependencies & Prerequisites

### Technical Requirements
- ✅ Ollama LLM già configurato e performante
- ✅ Structured JSON parsing da LLM responses
- ✅ Error handling robusto per LLM calls
- ⚠️ Context window validation per 730 piani

### Organizational Requirements
- 📅 **Timeline**: 6 settimane di development focus
- 👥 **Resources**: 1 senior developer full-time
- 🧪 **Testing**: Environment separato per A/B testing
- 📊 **Monitoring**: Dashboards per tracking migration progress

---

## Next Steps

### Immediate Actions (Questa Settimana)
1. **Setup tracking**: Implement current metrics collection
2. **Baseline establishment**: Run comprehensive vector search audit
3. **LLM prompt design**: Design e test initial semantic search prompts
4. **Stakeholder buy-in**: Present roadmap per approval

### Week 1 Deliverables
- Performance audit report di sistema attuale
- LLM semantic search proof-of-concept
- A/B testing framework design document
- Updated project timeline con resource allocation

---

**Conclusione**: Questa roadmap elimina l'inconsistenza architetturale identificata, sfruttando pienamente la potenza semantica dell'LLM già integrato nel sistema, risultando in una soluzione più coerente, mantenibile e performante per le esigenze specifiche del dominio veterinario ASL.

---

**Author**: GiAs-llm Development Team
**Review**: Technical Architecture Committee
**Approval**: Pending stakeholder review