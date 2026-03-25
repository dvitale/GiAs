# Configuration

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `configs/config.py`, `configs/config.json`, `configs/config_loader.py`

## Requisiti Funzionali

### CF-01 Priorita' risoluzione configurazione
- **Pattern EARS**: Il sistema DEVE risolvere ogni parametro di configurazione con priorita': variabile ambiente > campo in config.json > valore default hardcoded. Questo vale per LLM_BACKEND (GIAS_LLM_BACKEND), LLM_MODEL (GIAS_LLM_MODEL), RISK_PREDICTOR (GIAS_RISK_PREDICTOR), temperature, timeout e altri parametri.
- **Status**: IMPLEMENTATO

### CF-02 Sei modelli locali preconfigurati
- **Pattern EARS**: Il sistema DEVE definire 6 modelli locali preconfigurati in ModelConfig.AVAILABLE_MODELS: falcon (7B, acc 90%), velvet (14B, acc 95%, raccomandato, GDPR compliant), mistral-nemo (12.2B, acc 100%, lento 24.6s), llama3.1 (8B, acc 100%), llama3.2 (3B, acc 85%, default, velocissimo 0.8s), ministral (3.85B, acc 90%, raccomandato, 256K context, function calling nativo).
- **Status**: IMPLEMENTATO

### CF-03 Sei backend LLM supportati
- **Pattern EARS**: Il sistema DEVE supportare 6 backend LLM in LLMBackendConfig: ollama (locale, porta 11434), llamacpp (locale, porta 11435, default), openai (GPT-4o-mini), anthropic (Claude Sonnet), openai_compat (Mistral/Groq/Together), openrouter (multi-provider, default google/gemini-2.5-flash).
- **Status**: IMPLEMENTATO

### CF-04 API key solo da variabili ambiente
- **Pattern EARS**: Il sistema DEVE leggere le API key per provider esterni esclusivamente da variabili ambiente (OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY), utilizzando il campo api_key_env nella configurazione per determinare quale variabile leggere. Le API key NON DEVONO mai essere salvate in config.json.
- **Status**: IMPLEMENTATO

### ~~CF-05~~ RIMOSSO — Duplicato di LC-003
- Vedi `llm-client.md` LC-003 per GDPR gate provider esterni.

### ~~CF-06~~ RIMOSSO — Duplicato di RA-04
- Vedi `risk-analysis.md` RA-04 per configurazione risk predictor.

### CF-07 Configurazione sottosistemi (hybrid search, data source, RAG)
- **Pattern EARS**: Il sistema DEVE leggere la configurazione hybrid search da config.json: cpu_mode e default_strategy. Il sistema DEVE leggere la configurazione data source supportando tipo "csv" (con directory, files mapping e separatori custom) e tipo "postgresql" (con host, port, database, user, password e tables mapping). Il sistema DEVE leggere la configurazione RAG da config.json: enabled, documents_dir, collection_name, chunk_size (600), chunk_overlap (100), parent_chunk_size (1800), parent_chunk_overlap (200), top_k (5), score_threshold (0.30), cache_ttl_seconds (1800), cache_max_size (200).
- **Status**: IMPLEMENTATO
- **Accorpa**: CF-07, CF-08, CF-09

### CF-10 Config loader singleton
- **Pattern EARS**: Il sistema DEVE fornire un singleton Config (get_config()) che carica config.json una sola volta, con fallback a configurazione default se il file non esiste o contiene errori.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### CF-NF01 Configurazione fallback, guided learning e streaming
- **Pattern EARS**: Il sistema DEVE leggere da config.json la configurazione fallback_recovery (enabled, keyword_threshold, max_suggestions, llm_timeout, max_consecutive_fallbacks, enable_llm_phase, enable_category_menu). Il sistema DEVE leggere il flag guided_learning.enabled (default false). Il sistema DEVE leggere la configurazione streaming (enabled, max_duration_seconds 120, heartbeat_interval_seconds 30).
- **Status**: IMPLEMENTATO
- **Accorpa**: CF-NF01, CF-NF02, CF-NF03

### CF-NF04 Cambio modello a runtime
- **Pattern EARS**: Il sistema DEVE supportare il cambio modello a runtime tramite la funzione set_model(model_key) che aggiorna AppConfig.LLM_MODEL se il modello e' tra quelli disponibili.
- **Status**: IMPLEMENTATO
