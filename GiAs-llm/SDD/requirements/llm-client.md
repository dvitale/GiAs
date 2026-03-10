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

### LC-003 GDPR gate per provider esterni
- **Pattern EARS**: QUANDO il backend configurato e' un provider esterno, il sistema DEVE verificare all'inizializzazione che il flag `gdpr.allow_external_llm` in config.json sia True. SE il flag e' False, il sistema DEVE sollevare un ValueError con messaggio che spiega il rischio di invio dati a server esterni e la necessita' di conformita' GDPR per dati sanitari veterinari della Regione Campania.
- **Status**: IMPLEMENTATO

### LC-004 GDPR consent permissivo in sviluppo
- **Pattern EARS**: SE il file config.json non esiste o non e' parsabile (FileNotFoundError, JSONDecodeError), il sistema DEVE consentire l'inizializzazione senza bloccare (modalita' sviluppo).
- **Status**: IMPLEMENTATO

### LC-005 Degradazione a stub quando LLM non raggiungibile
- **Pattern EARS**: SE il provider LLM non e' raggiungibile all'inizializzazione (ping fallito o eccezione), il sistema DEVE degradare a modalita' stub (use_real_llm=False) con warning, garantendo che il sistema continui a funzionare senza LLM.
- **Status**: IMPLEMENTATO

### LC-006 Degradazione a stub per errori a runtime
- **Pattern EARS**: SE una chiamata query() fallisce con Timeout o altra eccezione a runtime, il sistema DEVE fare fallback allo stub per quella specifica richiesta, restituendo una risposta stub anziches' propagare l'errore.
- **Status**: IMPLEMENTATO

### LC-007 Metodo sincrono query()
- **Pattern EARS**: Il sistema DEVE esporre un metodo `query()` sincrono che accetta: prompt (stringa), temperature, max_tokens, messages (lista di dict role/content), json_mode (bool), timeout (override). SE messages e' fornito, il prompt viene ignorato.
- **Status**: IMPLEMENTATO

### LC-008 Metodo streaming query_stream()
- **Pattern EARS**: Il sistema DEVE esporre un metodo `query_stream()` che restituisce un generatore di token (stringhe) man mano che arrivano dal provider, con la stessa interfaccia parametrica di query().
- **Status**: IMPLEMENTATO

### LC-009 Streaming stub come fallback
- **Pattern EARS**: QUANDO query_stream() opera in modalita' stub, il sistema DEVE simulare lo streaming dividendo la risposta stub in parole e restituendo ciascuna come token separato con spazio finale.
- **Status**: IMPLEMENTATO

### LC-010 Temperature differenziate da configurazione
- **Pattern EARS**: QUANDO temperature non e' specificata nella chiamata, il sistema DEVE usare il default da AppConfig.RESPONSE_GENERATION_TEMPERATURE. I chiamanti usano temperature specifiche: classificazione con 0.1, generazione risposta RAG con 0.3, query expansion con 0.3.
- **Status**: IMPLEMENTATO

### LC-011 Interfaccia ABC per provider
- **Pattern EARS**: Il sistema DEVE definire una classe astratta LLMProvider con 4 metodi astratti obbligatori: query() (sincrono, restituisce stringa), query_stream() (generatore di stringhe), ping() (health check, restituisce bool), provider_name (property, stringa leggibile).
- **Status**: IMPLEMENTATO

### LC-012 API key esclusivamente da variabili ambiente
- **Pattern EARS**: QUANDO un provider esterno richiede una API key, il sistema DEVE recuperarla esclusivamente da variabili ambiente (os.getenv), usando il nome variabile specificato nel campo `api_key_env` della configurazione del backend. SE la variabile non e' impostata, il sistema DEVE sollevare ValueError.
- **Status**: IMPLEMENTATO

### LC-013 Keep-alive configurabile per Ollama
- **Pattern EARS**: DOVE il backend e' Ollama, il sistema DEVE inviare il parametro `keep_alive` in ogni richiesta (sia sync che streaming), con valore da AppConfig.KEEP_ALIVE_DURATION (default -1, modello sempre in memoria).
- **Status**: IMPLEMENTATO

### LC-014 Health check tramite ping()
- **Pattern EARS**: Il sistema DEVE esporre un metodo ping() che verifica la disponibilita' del provider LLM: per Ollama verifica GET /api/tags (status 200), per llama.cpp verifica GET /health, per OpenAI lista modelli via SDK, per Anthropic invia richiesta minimale (1 token), per OpenAI-compat invia richiesta minimale POST (1 token, status 200).
- **Status**: IMPLEMENTATO

### LC-015 JSON mode per provider
- **Pattern EARS**: QUANDO json_mode e' True, il sistema DEVE adattare il formato richiesta al provider: Ollama usa `format: "json"`, llama.cpp e OpenAI-compat usano `response_format: {type: "json_object"}`, OpenAI usa `response_format: {type: "json_object"}`, Anthropic aggiunge istruzione JSON al system prompt e prefilla assistant con '{'.
- **Status**: IMPLEMENTATO

### LC-016 Ricostruzione JSON per Anthropic
- **Pattern EARS**: QUANDO il provider e' Anthropic e json_mode e' attivo, SE la risposta non inizia con '{', il sistema DEVE preporre '{' alla risposta per ricostruire il JSON completo (compensando il prefill assistant). In streaming, DEVE emettere '{' come primo token.
- **Status**: IMPLEMENTATO

### LC-017 Separazione system message per Anthropic
- **Pattern EARS**: QUANDO il provider e' Anthropic, il sistema DEVE estrarre il primo messaggio con role "system" dalla lista messages e passarlo come parametro `system` separato alla API, inviando solo i messaggi non-system nella lista messages.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### LC-NF-001 Timeout configurabile per provider
- **Pattern EARS**: Il sistema DEVE utilizzare il timeout specifico del backend dalla configurazione (`timeout_seconds`), con fallback al timeout globale AppConfig.LLM_TIMEOUT_SECONDS. Il timeout e' overridabile per singola chiamata.
- **Status**: IMPLEMENTATO

### LC-NF-002 Logging inizializzazione
- **Pattern EARS**: QUANDO il client viene inizializzato con successo, il sistema DEVE loggare: nome backend, URL connessione, nome modello, descrizione modello.
- **Status**: IMPLEMENTATO

### LC-NF-003 Nessun SDK aggiuntivo per OpenAI-compat
- **Pattern EARS**: Il provider OpenAI-Compatible DEVE funzionare con sole richieste HTTP via libreria `requests`, senza richiedere SDK aggiuntivi.
- **Status**: IMPLEMENTATO
