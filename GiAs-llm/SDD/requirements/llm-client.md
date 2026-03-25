# Client LLM

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `llm/client.py`, `llm/provider_base.py`, `llm/providers.py`

## Requisiti Funzionali

### LC-001 Supporto 6 backend LLM
- **Pattern EARS**: Il sistema DEVE supportare 6 backend LLM: Ollama (API nativa /api/chat), llama.cpp (OpenAI-compatible /v1/chat/completions), OpenAI (SDK GPT-4o, GPT-4o-mini), Anthropic (SDK Claude Sonnet, Haiku), OpenAI-Compatible generico (Mistral, Groq, Together, DeepSeek, DeepInfra), OpenRouter (aggregatore OpenAI-compatible).
- **Status**: IMPLEMENTATO

### LC-002 Factory method per creazione provider
- **Pattern EARS**: QUANDO il client viene inizializzato, il sistema DEVE creare il provider appropriato tramite factory method basato sul backend_type dalla configurazione, mappando: "ollama" -> OllamaProvider, "llamacpp" -> LlamaCppProvider, "openai" -> OpenAIProvider, "anthropic" -> AnthropicProvider, "openai_compat"/"openrouter" -> OpenAICompatProvider.
- **Status**: IMPLEMENTATO

### LC-003 GDPR gate e degradazione stub
- **Pattern EARS**: QUANDO il backend configurato e' un provider esterno, il sistema DEVE verificare all'inizializzazione che il flag `gdpr.allow_external_llm` in config.json sia True; SE False, il sistema DEVE sollevare un ValueError con messaggio che spiega il rischio GDPR per dati sanitari veterinari della Regione Campania. SE il file config.json non esiste o non e' parsabile, il sistema DEVE consentire l'inizializzazione senza bloccare (modalita' sviluppo).
- **Status**: IMPLEMENTATO
- **Accorpa**: LC-003, LC-004

### LC-005 Degradazione e stub fallback
- **Pattern EARS**: SE il provider LLM non e' raggiungibile all'inizializzazione (ping fallito o eccezione), il sistema DEVE degradare a modalita' stub (use_real_llm=False) con warning. SE una chiamata query() fallisce con Timeout o altra eccezione a runtime, il sistema DEVE fare fallback allo stub per quella specifica richiesta, restituendo una risposta stub.
- **Status**: IMPLEMENTATO
- **Accorpa**: LC-005, LC-006

### LC-007 Query sincrona e streaming con temperature
- **Pattern EARS**: Il sistema DEVE esporre un metodo `query()` sincrono che accetta: prompt, temperature, max_tokens, messages (lista di dict role/content), json_mode, timeout. Il sistema DEVE esporre un metodo `query_stream()` che restituisce un generatore di token; in modalita' stub, DEVE simulare lo streaming dividendo la risposta in parole. QUANDO temperature non e' specificata, il sistema DEVE usare il default da AppConfig.RESPONSE_GENERATION_TEMPERATURE.
- **Status**: IMPLEMENTATO
- **Accorpa**: LC-007, LC-008, LC-009

### LC-010 Temperature differenziate da configurazione
- **Pattern EARS**: QUANDO temperature non e' specificata nella chiamata, il sistema DEVE usare il default da AppConfig.RESPONSE_GENERATION_TEMPERATURE. I chiamanti usano temperature specifiche: classificazione con 0.1, generazione risposta RAG con 0.3, query expansion con 0.3.
- **Status**: IMPLEMENTATO

### LC-011 Interfaccia ABC per provider
- **Pattern EARS**: Il sistema DEVE definire una classe astratta LLMProvider con 4 metodi astratti obbligatori: query() (sincrono, restituisce stringa), query_stream() (generatore di stringhe), ping() (health check, restituisce bool), provider_name (property, stringa leggibile).
- **Status**: IMPLEMENTATO

### LC-012 API key esclusivamente da variabili ambiente
- **Pattern EARS**: QUANDO un provider esterno richiede una API key, il sistema DEVE recuperarla esclusivamente da variabili ambiente (os.getenv), usando il nome variabile specificato nel campo `api_key_env` della configurazione del backend. SE la variabile non e' impostata, il sistema DEVE sollevare ValueError.
- **Status**: IMPLEMENTATO

### LC-013 Adattamento provider-specifico (API key, keep-alive, JSON mode, Anthropic)
- **Pattern EARS**: DOVE il backend e' Ollama, il sistema DEVE inviare il parametro `keep_alive` in ogni richiesta (default -1, modello sempre in memoria). QUANDO json_mode e' True, il sistema DEVE adattare il formato richiesta al provider: Ollama usa `format: "json"`, llama.cpp e OpenAI-compat usano `response_format: {type: "json_object"}`, Anthropic aggiunge istruzione JSON al system prompt e prefilla assistant con '{'. QUANDO il provider e' Anthropic e json_mode e' attivo, SE la risposta non inizia con '{', il sistema DEVE preporre '{' per ricostruire il JSON completo. QUANDO il provider e' Anthropic, il sistema DEVE estrarre il primo messaggio system e passarlo come parametro `system` separato alla API.
- **Status**: IMPLEMENTATO
- **Accorpa**: LC-013, LC-015, LC-016, LC-017

### LC-014 Health check tramite ping()
- **Pattern EARS**: Il sistema DEVE esporre un metodo ping() che verifica la disponibilita' del provider LLM: per Ollama verifica GET /api/tags (status 200), per llama.cpp verifica GET /health, per OpenAI lista modelli via SDK, per Anthropic invia richiesta minimale (1 token), per OpenAI-compat invia richiesta minimale POST (1 token, status 200).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### LC-NF-001 Timeout configurabile, logging inizializzazione, zero SDK extra
- **Pattern EARS**: Il sistema DEVE utilizzare il timeout specifico del backend dalla configurazione (`timeout_seconds`), con fallback al timeout globale e override per singola chiamata. QUANDO il client viene inizializzato con successo, il sistema DEVE loggare: nome backend, URL connessione, nome modello, descrizione modello. Il provider OpenAI-Compatible DEVE funzionare con sole richieste HTTP via libreria `requests`, senza richiedere SDK aggiuntivi.
- **Status**: IMPLEMENTATO
- **Accorpa**: LC-NF-001, LC-NF-002, LC-NF-003
