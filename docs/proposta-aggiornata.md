***Documentazione tecnica aggiornata al: FEBBRAIO 2026***

**GiAs-LLM: Architettura LLM + Agents**

STATO ATTUALE DELL'INTEGRAZIONE DI SERVIZI DI AI IN GISA

---

**Introduzione**

Sulla base del documento "Final Report Bridge Campania", e' stata realizzata un'architettura software ad agenti per il sistema **"Hey GISA"**, progettata per supportare gli ispettori sul campo attraverso l'integrazione di Intelligenza Artificiale applicata ai dati del sistema GISA Controlli Ufficiali. Il modulo di Intelligenza Artificiale e' stato integrato all'interno della piattaforma GISA per ottimizzare i controlli ufficiali attraverso un approccio basato sul rischio. I dati storici sono stati trasformati in modelli predittivi (XGBoost V4) capaci di stimare le probabilita' di non conformita' delle imprese. L'assistente virtuale e' operativo e in grado di fornire informazioni in tempo reale e suggerire priorita' geografiche e operative agli ispettori.

---

**Overview del modulo di chat bot (GChat)**

**GiAs-LLM** e' un sistema basato su backend LangGraph + tools, agenti specializzati e LLM per interagire in modalita' conversazionale con i dati dell'ecosistema GISA della Regione Campania. Il front-end e' rappresentato da una web app scritta in **Go (Gin framework)** che fa da interfaccia utente (GUI) al chatbot. L'interazione col backend avviene attraverso l'uso di **FastAPI**.

L'uso di LangGraph permette di definire flussi di lavoro complessi attraverso l'uso di agenti. A differenza delle catene lineari, introduce il concetto di loop e gestione del persisted state, garantendo un controllo granulare su come l'informazione evolve durante l'esecuzione. La struttura a nodi e archi facilita il coordinamento di piu' agenti specializzati rendendo il sistema robusto, prevedibile e facilmente monitorabile.

Per la parte di backend l'uso di FastAPI, framework Python ad alte prestazioni, garantisce la capacita' di gestire migliaia di richieste simultanee in modo non bloccante.

---

**Architettura attuale del sistema**

```
┌─────────────────────────────────────────────────────────────┐
│  Nginx Reverse Proxy (Port 80/443)                          │
│  - SSL termination                                          │
│  - Load balancing                                           │
└──────────────┬────────────────────────────────────────┬─────┘
               │                                        │
  ┌────────────┴────────────┐          ┌────────────────┴────────────────┐
  │  GChat Frontend (8080)  │          │  GiAs-llm Backend (5005)        │
  │  Go + Gin framework     │  HTTP    │  FastAPI + Uvicorn              │
  │  HTML/CSS/JS vanilla    │──POST──→ │  LangGraph Orchestrator         │
  │  Tema light/dark        │          │                                 │
  │  Analytics + Monitor    │          │  ┌──────────────────────────┐   │
  └─────────────────────────┘          │  │ Router Ibrido (7 fasi)  │   │
                                       │  │ Gibberish → SlotFill →  │   │
                                       │  │ Heuristics → PreParse → │   │
                                       │  │ Cache → LLM → Fallback  │   │
                                       │  └───────────┬──────────────┘   │
                                       │              │                  │
                                       │  ┌───────────┴─────────────┐    │
                                       │  │ Dialogue Manager        │    │
                                       │  │ (rule-based, no LLM)    │    │
                                       │  └───────────┬─────────────┘    │
                                       │              │                  │
                                       │  ┌───────────┴─────────────┐    │
                                       │  │ Tool Layer (19 tools)   │    │
                                       │  └───────────┬─────────────┘    │
                                       │              │                  │
                                       │  ┌───────────┴─────────────┐    │
                                       │  │ Response Generator (LLM)│    │
                                       │  └─────────────────────────┘    │
                                       └──────────┬──────────────────────┘
                                                  │
                          ┌───────────────────────┼──────────────────────┐
                          │                       │                      │
               ┌──────────┴──────────┐  ┌─────────┴───────────┐  ┌───────┴────────┐
               │  PostgreSQL (GIAS)  │  │  Qdrant (Vector)    │  │  LLM Provider  │
               │  gias_db            │  │  3 collezioni:      │  │  Multi-backend │
               │  10 tabelle         │  │- piani_monitoraggio │  │  Ollama/OpenAI │
               │                     │  │    (730 piani)      │  │  Anthropic/    │
               └─────────────────────┘  │- procedure_documents│  │  OpenAI-compat │
                                        │    (7 PDF, ~29 MB)  │  └────────────────┘
                                        │- intent_examples    │
                                        │  384 dimensioni     │
                                        └─────────────────────┘
```

---

**Layer 1: LLM Router - Intent Classification**

Il Router e' stato implementato con un'architettura **ibrida a 7 fasi** che massimizza velocita' e precisione:

0. **Gibberish Detection**: rileva messaggi senza senso prima di processare, bypass LLM per input non conformi
1. **Pending Slot Fill**: gestisce slot mancanti da richieste precedenti, controlla topic change
2. **Heuristics** (pattern matching): risolve saluti, conferme/rifiuti, comandi diretti in <1ms. Flag `MINIMAL_HEURISTICS` per produzione (solo heuristics essenziali quando LLM affidabile)
3. **Pre-parsing deterministico**: estrazione slot via regex (piano_code, asl, partita_iva, categoria, topic, location); passato al LLM come suggerimento
4. **Cache** (MD5 + TTL configurabile): evita chiamate LLM ripetute per query identiche
5. **LLM Classification**: prompt V2 template-based con contenuti dinamici da DB, few-shot retrieval da Qdrant, contesto sessione per riferimenti anaforici, soglie di confidenza adattive per modello
6. **Fallback locale**: se LLM non disponibile, risolve greet/goodbye/help senza LLM; fallback response con error reason

Questo approccio ibrido riduce drasticamente le chiamate al modello linguistico: la maggior parte delle query viene risolta nelle prime fasi senza alcun intervento LLM. I contenuti del prompt LLM (catalogo intent, esempi few-shot, regole di disambiguazione) sono caricati dinamicamente dalla tabella `intents` del database tramite `IntentMetadataService`, con fallback a una registry Python locale.

**Intent supportati (20 totali)**

| # | Intent | Descrizione | Slot richiesti |
|---|--------|-------------|----------------|
| 1 | `greet` | Saluti (es. "ciao", "buongiorno") | - |
| 2 | `goodbye` | Saluti finali | - |
| 3 | `ask_help` | Richieste aiuto | - |
| 4 | `ask_piano_description` | Descrizione piano | `piano_code` |
| 5 | `ask_piano_stabilimenti` | Stabilimenti per piano | `piano_code` |
| 6 | `ask_piano_statistics` | Statistiche frequenze piano | - (auto) |
| 7 | `search_piani_by_topic` | Ricerca semantica piani per argomento | `topic` |
| 8 | `ask_priority_establishment` | Priorita' programmazione (ritardi) | - (auto, usa metadata) |
| 9 | `ask_risk_based_priority` | Priorita' basata su rischio (ML/statistico) | - (auto, usa metadata) |
| 10 | `ask_suggest_controls` | Stabilimenti mai controllati ad alto rischio | - (auto, usa metadata) |
| 11 | `ask_delayed_plans` | Piani in ritardo | - (auto, usa metadata) |
| 12 | `check_if_plan_delayed` | Verifica ritardo singolo piano | `piano_code` |
| 13 | `ask_establishment_history` | Storico controlli stabilimento | `num_registrazione`, `numero_riconoscimento`, `partita_iva`, o `ragione_sociale` (almeno uno) |
| 14 | `ask_top_risk_activities` | Attivita' a piu' alto rischio NC | - (auto, usa metadata) |
| 15 | `analyze_nc_by_category` | Analisi non conformita' per categoria | `categoria` |
| 16 | `info_procedure` | Informazioni su procedure operative (RAG) | - (auto) |
| 17 | `ask_nearby_priority` | Stabilimenti vicini per prossimita' geografica | `location`, `radius_km` (opt, default 5) |
| 18 | `confirm_show_details` | Conferma visualizzazione dettagli | - |
| 19 | `decline_show_details` | Rifiuto visualizzazione dettagli | - |
| 20 | `fallback` | Non classificabile | - |

Nota: gli intent contrassegnati "auto, usa metadata" utilizzano `asl` e `uoc` dal metadata utente (risolto automaticamente dalla sessione e dalla tabella `personale`), senza richiederli esplicitamente all'utente.

**Slot Extraction**

L'estrazione degli slot avviene in modo deterministico tramite regex nel pre-parser, prima ancora della classificazione LLM. Gli slot supportati sono:

| Slot | Descrizione | Esempio |
|------|-------------|---------|
| `piano_code` | Codice piano (A1, B2, C3_F) | "Di cosa tratta il piano **A22**?" |
| `topic` | Argomento ricerca | "Piani su **allevamenti bovini**" |
| `asl` | Azienda Sanitaria Locale | Da metadata utente |
| `uoc` | Unita' Operativa Complessa | Da metadata o risolto da user_id |
| `partita_iva` | Partita IVA stabilimento | "Storico controlli per **12345678901**" |
| `num_registrazione` | Numero registrazione | "Controlli stabilimento **IT123AB456**" |
| `numero_riconoscimento` | Numero riconoscimento stabilimento | "Stabilimento **123/AB**" |
| `ragione_sociale` | Nome impresa | "Cerca **Rossi SRL**" |
| `categoria` | Categoria non conformita' | "Analisi NC per **HACCP**" |
| `location` | Indirizzo da geocodificare | "Stabilimenti vicino **Piazza Garibaldi, Napoli**" |
| `radius_km` | Raggio ricerca in km (default 5) | "Entro **3 km** da Via Roma" |

---

**Layer 2: Tool Layer**

Il Tool Layer e' il braccio operativo del sistema. Sono stati implementati **19 tool** organizzati in moduli specializzati, registrati nel `TOOL_REGISTRY` e invocabili dall'orchestratore.

**Piano Tools (`tools/piano_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `piano_description_tool` | Descrizione completa piano | `piano_code` |
| `piano_stabilimenti_tool` | Stabilimenti controllati per piano | `piano_code` |
| `piano_statistics_tool` | Statistiche frequenze di controllo | `piano_code` |

**Priority Tools (`tools/priority_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `priority_establishment_tool` | Stabilimenti prioritari (da ritardi programmazione) | `asl`, `uoc`, `piano_code` |
| `delayed_plans_tool` | Piani con ritardi rispetto alla programmazione | `asl`, `uoc` |
| `check_plan_delayed_tool` | Verifica ritardo singolo piano | `piano_code` |
| `suggest_controls_tool` | Mai controllati ad alto rischio | `asl` |

**Risk Tools (`tools/risk_tools.py`, `tools/predictor_tools.py`, `tools/risk_analysis_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `risk_predictor_tool` | Predizione rischio ML (XGBoost V4) o statistico | `asl`, `piano_code` |
| `top_risk_activities_tool` | Attivita' a maggior rischio NC | `asl` |
| `analyze_nc_tool` | Analisi non conformita' per categoria | `categoria` |

**Search Tools (`tools/search_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `search_piani_tool` | Ricerca semantica ibrida su piani | `query` |

**Establishment Tools (`tools/establishment_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `establishment_history_tool` | Storico controlli di uno stabilimento | `num_registrazione` / `numero_riconoscimento` / `partita_iva` / `ragione_sociale` |

**Procedure Tools (`tools/procedure_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `info_procedure_tool` | Ricerca RAG su procedure operative | `topic` |

**Proximity Tools (`tools/proximity_tools.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `nearby_priority_tool` | Stabilimenti mai controllati per prossimita' geografica | `location`, `radius_km`, `asl` |

Il tool utilizza **geocodifica Nominatim (OpenStreetMap)** con strategia "city-first": prima geocodifica il comune per avere coordinate di riferimento, poi cerca l'indirizzo specifico con viewbox centrato sulla citta'. I 5 capoluoghi campani (Napoli, Salerno, Caserta, Avellino, Benevento) sono mappati con coordinate predefinite per disambiguare omonimi. Include verifica che la location sia nel territorio dell'ASL dell'utente prima di restituire risultati. Ordinamento per distanza (primaria) + risk score (secondaria). Cache LRU (500 entry) per ottimizzare chiamate ripetute. Two-phase threshold: 10 risultati.

**Conversation Tools (`orchestrator/tool_nodes.py`)**

| Tool | Descrizione | Input |
|------|-------------|-------|
| `greet_tool` | Messaggio di benvenuto | - |
| `goodbye_tool` | Messaggio di saluto finale | - |
| `help_tool` | Menu domande suggerite (contenuti da IntentMetadataService) | - |
| `confirm_details_tool` | Mostra dettagli aggiuntivi | contesto precedente |
| `decline_details_tool` | Declina dettagli aggiuntivi | - |

**Two-Phase Thresholds per tool**:

| Tool | Soglia (n. risultati) |
|------|-----------------------|
| `piano_stabilimenti_tool` | 2 |
| `search_piani_tool` | 5 |
| `priority_establishment_tool` | 5 |
| `risk_predictor_tool` | 5 |
| `suggest_controls_tool` | 5 |
| `establishment_history_tool` | 5 |
| `nearby_priority_tool` | 10 |

Quando i risultati superano la soglia, il sistema restituisce un riepilogo e offre all'utente la possibilita' di visualizzare i dettagli completi (flusso two-phase).

---

**Ricerca Semantica Ibrida**

Il sistema di ricerca sui piani di monitoraggio utilizza un motore ibrido avanzato (`tools/hybrid_search/`) con routing intelligente:

**Componenti**:
- **QueryAnalyzer**: Classifica complessita' della query
- **SmartRouter**: Seleziona strategia ottimale (vector_only, llm_only, hybrid)
- **HybridEngine**: Orchestratore principale della ricerca
- **LLMReranker**: Riordinamento risultati tramite LLM per maggiore precisione
- **PerformanceTracker**: Monitoraggio prestazioni in tempo reale

**Regole di routing (per priorita')**:

| Priorita' | Regola | Strategia | Latenza |
|-----------|--------|-----------|---------|
| 10 | Query con codice esatto (es. "piano A1") | vector_only | 15-30ms |
| 9 | Sistema sotto carico (load >= 0.8) | vector_only | 15-30ms |
| 8 | Alta complessita' semantica (>= 0.7) | llm_only | variabile |
| 6 | Keyword semplici (<= 0.3) | vector_only | 15-30ms |
| 5 | Default | hybrid | variabile |

**Storage vettoriale**: Qdrant con **730 piani indicizzati** in 384 dimensioni (sentence-transformers).

---

**Layer 3: Agents Layer - Business Logic**

L'Agents Layer e' organizzato in componenti specializzati seguendo il pattern a 3 layer:

**Data Agent (`agents/data_agent.py`)**

Responsabile dell'accesso ai dati e della logica di business:

- **DataRetriever**: Accesso puro ai dati (15+ metodi)
  - `get_piano_by_id()`: Recupero piano per codice
  - `get_controlli_by_piano()`: Controlli associati a un piano
  - `get_osa_mai_controllati()`: Stabilimenti mai controllati
  - `get_diff_programmati_eseguiti()`: Differenza programmati vs eseguiti per struttura
  - `search_piani_semantic()`: Ricerca semantica Qdrant con embedding cache
  - `search_procedure_docs()`: RAG ricerca procedure operative
  - `get_user_structure()`: Risoluzione struttura organizzativa (ASL, UOC) da user_id
  - `find_establishment()`: Ricerca unificata stabilimento per piu' identificativi
  - `get_establishment_history()`: Storico controlli per stabilimento con join NC
  - `get_osa_near_location()`: Proximity search geocodificato
  - `get_nc_by_category()`: Filtra non conformita' per categoria (HACCP, IGIENE, ecc.)
  - `get_establishments_with_nc_category()`: Stabilimenti con NC storiche per categoria
  - `get_establishments_with_most_sanctions()`: Top stabilimenti per numero NC totali

- **BusinessLogic**: Aggregazioni e correlazioni
  - `correlate_piano_attivita()`: Correlazione piano-attivita'
  - `aggregate_stabilimenti_by_piano()`: Aggregazione stabilimenti con join NC
  - `compare_plans_metrics()`: Confronto metriche tra piani
  - `calculate_delayed_plans()`: Piani in ritardo (programmati > eseguiti) per anno
  - `get_piano_statistics()`: Statistiche aggregate piani eseguiti

- **RiskAnalyzer**: Analisi del rischio con caching
  - `calculate_risk_scores()`: Calcolo punteggio rischio per attivita'
  - `calculate_categorized_risk_scores()`: Risk score per attivita' + categoria NC con pesi
  - `analyze_nc_category_trends()`: Trend temporali NC per categoria e ASL
  - `rank_osa_by_risk()`: Incrocio stabilimenti mai controllati con risk score
  - `find_priority_establishments_optimized()`: Stabilimenti prioritari da ritardi + correlazioni

**Response Agent (`agents/response_agent.py`)**

Responsabile della formattazione delle risposte in italiano:

- **ResponseFormatter**: Formattazione template-based (18+ metodi statici)
  - `format_piano_description()`: Formattazione descrizione piano con sottopiani
  - `format_stabilimenti_analysis()`: Top 10 tipologie stabilimenti
  - `format_search_results()`: Risultati ricerca piani con relevanza
  - `format_risk_based_priority()`: OSA a rischio con risk score
  - `format_delayed_plans()`: Piani in ritardo con dettagli per UOC/UOS
  - `format_establishment_history()`: Storico controlli stabilimento
  - `format_top_risk_activities()`: Classifica attivita' rischiose
  - `format_nearby_priority()`: Stabilimenti entro raggio con distanza/risk score
  - `format_piano_statistics()`: Statistiche aggregate per piani
  - `format_nc_category_analysis()`: Non conformita' per categoria

- **SuggestionGenerator** (`agents/response_agent.py`): Suggerimenti follow-up contestuali con 6 metodi per-intent

**Intent Metadata Service (`orchestrator/intent_metadata_service.py`)**

Componente singleton che funge da broker tra database e consumatori di metadati intent:

- **DB-first, Python-fallback**: Carica metadati dalla tabella `intents` e esempi da `intent_examples`; fallback automatico alla registry Python locale (`intent_metadata.py`) se DB non disponibile
- **Generazione contenuti per prompt**: catalogo intent, esempi critici, regole disambiguazione
- **Contenuti per help_tool**: genera markdown dinamico dalle descrizioni DB
- **Metadati operativi per chat_log**: mapping intent-to-tool, soglie two-phase, query SQL equivalenti

---

**Modello Predittivo del Rischio**

Sono stati implementati **due approcci complementari**, selezionabili via configurazione:

**1. Predittore ML - XGBoost V4 (`predictor_ml/predictor.py`)**

Il modello predittivo e' stato realizzato e messo in produzione. Si tratta di un modello **XGBoost** (versione 4) addestrato sui dati storici 2016-2025 delle non conformita'.

- **Modello**: `production_assets/risk_model_v4.json`
- **Dati di training**: `production_assets/training_data_v4.parquet`
- **Feature (6)**: `macroarea_norm`, `aggregazione_norm`, `years_never_controlled`, `asl`, `linea_attivita`, `norma`
- **Output**: Score di rischio individuale per stabilimento (0.0 - 1.0)
- **Soglie**: ALTO > 0.70, MEDIO > 0.40
- **Fallback**: Se XGBoost non disponibile, scoring statistico rule-based

Rispetto all'ipotesi iniziale che proponeva una formula semplificata (`risk_score = tot_NC + 3 x tot_NC_gravi`), il sistema attuale utilizza un modello ML completo con feature autoregressive derivate dallo storico, coerente con i requisiti del documento OCSE. Il modello opera su popolazione sbilanciata ed e' calibrato per privilegiare l'intercettazione dei casi a rischio.

**2. Predittore Statistico (`tools/risk_tools.py`)**

Mantenuto come alternativa leggera:

- **Formula**: `Risk Score = P(NC) x Impatto x 100`
- **P(NC)**: (totale NC) / (controlli)
- **Impatto**: (NC gravi) / (controlli)
- **Output**: Rischio aggregato per tipologia di attivita' a livello regionale
- **Categorie NC pesate**: 11 categorie con pesi di criticita' (HACCP = 1.0, IGIENE ALIMENTI = 0.9, ecc.)

**Selezione**: Via variabile d'ambiente `GIAS_RISK_PREDICTOR`, `config.json`, o default (`ml`).

---

**Data Layer**

Il Data Layer e' stato implementato con un **pattern Factory + Singleton** per l'accesso ai dati:

**Sorgenti dati (`data_sources/`)**:
- **CSVDataSource**: Lettura da file CSV locali (sviluppo/test)
- **PostgreSQLDataSource**: Connessione via SQLAlchemy con connection pooling (pool_size=5, max_overflow=10, pool_recycle=1h) e fallback psycopg2
- **Factory**: `get_data_source()` restituisce istanza singleton in base a `config.json`

**Database PostgreSQL (GIAS) - 10 tabelle**:

| Tabella | Contenuto |
|---------|-----------|
| `piani_monitoraggio` | Piani di controllo (alias, indicatore, sezione, descrizione) |
| `masterlist` | Attivita' di riferimento |
| `cu_eseguiti` | Controlli ufficiali 2025 (macroarea, aggregazione, attivita') |
| `osa_mai_controllati` | Stabilimenti mai controllati |
| `ocse_isp_semp` | Storico non conformita' 2016-2025 (macroarea, NC gravi, NC non gravi) |
| `cu_diff_programmati_eseguiti` | Differenze programmati vs eseguiti (per piano, ASL, UOC) |
| `personale` | Struttura organizzativa (user_id, ASL, UOC, UOS) - filtrata per anno corrente |
| `chat_log` | Log conversazioni (session_id, asl, intent, slots JSONB, response_time_ms, error) |
| `intents` | Source of truth per metadati intent (title, tool, required_slots, keywords, disambiguation_rules) |
| `intent_examples` | Esempi tipizzati per intent (few_shot, prompt_critical, disambiguation, variation, help) |

**Views SQL aggregate**:
- `v_chat_stats_daily`, `v_chat_recent`, `v_top_intents_by_asl`, `v_chat_errors`
- `v_intent_performance`, `v_chat_by_hour`, `v_session_summary`
- `v_intent_example_counts`

**Database vettoriale (Qdrant) - 3 collezioni**:

| Collezione | Contenuto | Dimensioni |
|------------|-----------|------------|
| `piani_monitoraggio` | 730 piani di monitoraggio indicizzati | 384 |
| `procedure_documents` | Chunk da 7 PDF di procedure operative (~29 MB) | 384 |
| `intent_examples` | Esempi tipizzati per few-shot retrieval | 384 |

Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Qdrant e embedding model sono gestiti come singleton condivisi per evitare conflitti di accesso.

---

**Dialogue Manager**

Il **Dialogue Manager** (`orchestrator/dialogue_manager.py`) e' un motore decisionale **rule-based** (nessuna chiamata LLM aggiuntiva) che coordina il flusso conversazionale:

**Funzionalita'**:
- Valuta `RouterResult` + `DialogueState` per decidere l'azione
- Soglie di confidenza adattive per modello LLM
- Gestione conversazioni multi-turno con tracking dello stato
- Meccanismo two-phase per risposte con dettagli opzionali

**Soglie di confidenza per modello**:

| Modello | High | Min | Delta |
|---------|------|-----|-------|
| Velvet (14B) | 0.80 | 0.50 | 0.20 |
| LLaMA 3.1 (8B) | 0.75 | 0.45 | 0.20 |
| Mistral-Nemo (12B) | 0.80 | 0.50 | 0.20 |
| LLaMA 3.2 (3B) | 0.60 | 0.35 | 0.15 |
| Ministral (3B) | 0.65 | 0.40 | 0.18 |
| Falcon (3B) | 0.65 | 0.40 | 0.18 |

I modelli piu' piccoli (<=7B) hanno soglie abbassate perche' producono confidenze meno calibrate.

**Decisioni possibili**:
1. **execute**: Eseguire il tool se slot completi e confidenza alta
2. **ask_user**: Chiedere chiarimenti se mancano informazioni
3. **fallback**: Risposta di fallback se intent fuori dominio

---

**DialogueState (Stato Multi-Turno)**

Lo stato del dialogo multi-turno e' gestito tramite un `TypedDict` con TTL di 5 minuti:

**Campi principali**:
- `goal`: Obiettivo conversazionale corrente
- `intent_candidates`: Lista di candidati `{intent, confidence, slots}`
- `confirmed_intent`, `confirmed_strategy`: Intent e strategia confermati
- `slots`: Dizionario slot accumulati cross-turno
- `missing_slots`: Slot obbligatori ancora mancanti
- `clarification_history`: Storico chiarimenti `{turn, question, answer, resolved}`
- `turn_count`: Contatore turni
- `last_tool_result`, `last_tool_intent`, `last_tool_slots`: Per refinement
- `last_response_context`: Per risoluzione anaforica (es. "le varianti" → "varianti del piano X")
- `timestamp`: Per validazione TTL

**ConversationState (Stato del Grafo LangGraph)**:

Lo stato complessivo che attraversa il grafo include:
- `message`, `metadata`: Input utente
- `intent`, `slots`, `needs_clarification`: Output del router
- `dialogue_state`: Contesto multi-turno (DialogueState sopra descritto)
- `dm_action`, `dm_target_tool`, `dm_question`: Decisioni del dialogue manager
- `tool_output`: Risultato esecuzione tool (tipo + dati)
- `final_response`: Risposta generata dall'LLM in italiano
- `has_more_details`, `detail_context`: Flusso two-phase
- `execution_path`, `node_timings`: Tracciamento per debug

---

**Flusso di esecuzione del grafo**

```
User Message → classify_node → dialogue_manager → (routing condizionale)
                                      │
                          ┌───────────┼───────────────┐
                          │           │               │
                          ▼           ▼               ▼
                    ask_user     tool_node      fallback_tool
                   (chiarire)   (eseguire)     (fuori dominio)
                                    │
                                    ▼
                            response_generator
                                    │
                                    ▼
                                   END
```

**Esempio di esecuzione: "Di cosa tratta il piano A1?"**

1. **classify_node**: Layer 3 (Pre-parsing) rileva pattern "piano + codice" → intent `ask_piano_description`, slot `piano_code=A1` (nessuna chiamata LLM necessaria)
2. **dialogue_manager**: Slot completi, confidenza alta → azione `execute`, target `piano_description_tool`
3. **tool_node**: `piano_description_tool` → `DataRetriever.get_piano_by_id("A1")` → `ResponseFormatter.format_piano_description()`
4. **response_generator**: LLM arricchisce risposta + genera suggerimenti follow-up
5. **END**: Risposta finale all'utente

---

**Frontend GChat**

Il frontend e' stato realizzato come server Go con framework Gin:

**Funzionalita' UI**:
- Interfaccia chat responsive con tema light/dark (toggle + localStorage persistence)
- Pulsanti domande predefinite con colori e emoji (7 domande, caricamento dinamico da API)
- Indicatore di digitazione animato
- Download conversazione in formato `.txt`
- Visualizzazione nome utente, ASL e gerarchia organizzativa
- Greeting dinamico in base all'ora (Buongiorno/Buon pomeriggio/Buonasera)
- Retry con backoff esponenziale (1s, 2s, 4s, max 5s)
- Health check con caching (30s success, 5s failure)
- Debug shortcuts: Ctrl+Click logo → debug mode, Shift+Click logo → LangGraph visualizer

**Endpoint frontend**:

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/gias/webchat/` | GET | Interfaccia chat principale |
| `/gias/webchat/chat` | POST | Invio messaggio al backend |
| `/gias/webchat/chat/stream` | POST | Streaming risposte (SSE) |
| `/gias/webchat/api/predefined-questions` | GET | Domande predefinite |
| `/gias/webchat/api/transcribe` | POST | Speech-to-text |
| `/gias/webchat/debug` | GET | Pagina debug intent/entities |
| `/gias/webchat/debug/langgraph` | GET | Visualizzatore workflow LangGraph |
| `/gias/webchat/debug/chat` | POST | Debug request con parse NLU |
| `/gias/webchat/history` | GET | Cronologia chat utente |
| `/gias/webchat/analytics` | GET | Dashboard analytics chat |
| `/gias/webchat/monitor` | GET | Monitor qualita' conversazioni |
| `/gias/webchat/api/chat-log/*` | GET | Proxy API chat-log (evita CORS) |

**Endpoint backend API**:

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/v1/chat` | POST | Chat sincrono (API V1) |
| `/api/v1/chat/stream` | POST | Chat streaming SSE |
| `/api/v1/parse` | POST | Parsing NLU |
| `/status` | GET | Stato + dati caricati + modello LLM |
| `/config` | GET | Info configurazione |
| `/api/chat-log/stats` | GET | Statistiche aggregate chat |
| `/api/chat-log/recent` | GET | Ultimi messaggi con paginazione |
| `/api/chat-log/by-asl` | GET | Raggruppamento per ASL |
| `/api/chat-log/by-intent` | GET | Raggruppamento per intent |
| `/api/chat-log/errors` | GET | Errori recenti e classificazione |
| `/api/chat-log/timeline` | GET | Timeline per grafici (hour/day) |
| `/api/chat-log/user-conversations` | GET | Conversazioni per codice fiscale |
| `/api/chat-log/conversation/{sid}` | GET | Messaggi di una conversazione |
| `/api/chat-log/quality` | GET | Qualita' conversazioni (fallback loop, ripetizioni) |
| `/api/monitor/intelligent` | GET | Analisi completa (bug, root cause, trend) |
| `/api/monitor/suggestions` | GET | Suggerimenti actionable per miglioramenti |
| `/api/monitor/health` | GET | Health score 0-100 |

**Protocollo di comunicazione (API V1 nativa)**:
```json
// Request
{
  "sender": "user_id",
  "message": "testo utente",
  "metadata": {
    "asl": "AVELLINO",
    "asl_id": "...",
    "user_id": "...",
    "codice_fiscale": "...",
    "username": "...",
    "uoc": "...",
    "uos": "..."
  }
}

// Response
{
  "result": {
    "text": "risposta formattata",
    "intent": "ask_piano_description",
    "slots": {"piano_code": "A1"},
    "suggestions": [{"text": "domanda suggerita", "query": "query per il backend"}],
    "execution": {
      "execution_path": ["classify_node", "dialogue_manager", "piano_description_tool", "response_generator"],
      "node_timings": {"classify_node": 0.12, "...": "..."},
      "total_execution_ms": 1250.5
    },
    "needs_clarification": false,
    "has_more_details": false,
    "error": null
  },
  "sender": "user_id"
}
```

**Timeout chain**: JS (75s) > Go (60s) > Backend streaming (120s) > Graph invoke (50s)

---

**Supporto Multi-Provider LLM**

Il sistema supporta **5 backend LLM** selezionabili, con gate GDPR per provider esterni:

**Backend supportati**:

| Backend | Tipo | Modelli | API Key (env var) |
|---------|------|---------|-------------------|
| **Ollama** | Locale | Velvet, LLaMA 3.2, Mistral-Nemo, LLaMA 3.1, Ministral, Falcon | - |
| **Llama.cpp** | Locale | GGUF quantizzati | - |
| **OpenAI** | Esterno | GPT-4o, GPT-4o-mini | `OPENAI_API_KEY` |
| **Anthropic** | Esterno | Claude Sonnet/Opus | `ANTHROPIC_API_KEY` |
| **OpenAI-compat** | Esterno | Mistral, Groq, Together, ecc. | `MISTRAL_API_KEY` / custom |

**Gate GDPR**: `gdpr.allow_external_llm` in `config.json` deve essere `true` per abilitare provider esterni. Default: bloccato. API key solo via variabili d'ambiente (mai in config).

**Modelli locali Ollama**:

| Modello | Dimensione | VRAM | Latenza media | Accuratezza | Note |
|---------|-----------|------|---------------|-------------|------|
| Almawave/Velvet | 14B | ~10GB | 4.2s | Alta | Raccomandato, GDPR-compliant |
| LLaMA 3.2 | 3B | 2.0GB | 0.8s | 85% | Default, veloce |
| Mistral 3B | 3B | ~2GB | 1.0s | Buona | Context 256K, function calling |
| Mistral-Nemo | 12B | ~8GB | 24.6s | 100% | Massima accuratezza, lento |
| Ministral | 3B | ~2GB | ~1.0s | Buona | Alternativa leggera |
| LLaMA 3.1 | 8B | ~6GB | ~2.0s | Buona | Bilanciato |

**Temperature**: Classificazione 0.1 (deterministico), Generazione risposta 0.3 (leggermente creativo).

---

**Stack Tecnologico in Produzione**

| Componente | Tecnologia | Versione/Note |
|-----------|-----------|---------------|
| **Frontend server** | Go + Gin | 1.21+ |
| **Frontend UI** | HTML/CSS/JS vanilla | Tema light/dark, responsive, analytics/monitor |
| **Backend API** | FastAPI + Uvicorn | Python 3.10+ |
| **Orchestrazione** | LangGraph | Workflow ad agenti con stato |
| **Intent classification** | Router ibrido 7 fasi | Gibberish → Heuristics → PreParse → Cache → LLM → Fallback |
| **Intent metadata** | IntentMetadataService | DB-first (tabella intents) + fallback Python |
| **Dialogue management** | Rule-based (custom) | Nessuna dipendenza Rasa |
| **ML Risk Prediction** | XGBoost V4 | Addestrato su dati 2016-2025 |
| **Embeddings** | sentence-transformers | 384 dimensioni (paraphrase-multilingual-MiniLM-L12-v2) |
| **Vector DB** | Qdrant | 3 collezioni (piani, procedure, intent_examples) |
| **Database** | PostgreSQL + SQLAlchemy | 10 tabelle + views aggregate |
| **LLM Inference** | Ollama + provider esterni | 5 backend (Ollama, Llama.cpp, OpenAI, Anthropic, OpenAI-compat) |
| **Data processing** | Pandas, NumPy, PyTorch | Preprocessing + feature engineering |
| **Reverse Proxy** | Nginx | SSL termination, load balancing |
| **Chat logging** | PostgreSQL + views | Persistenza conversazioni + analytics |

---

**Confronto Proposta Iniziale vs. Stato Attuale**

| Aspetto | Proposta iniziale | Stato attuale |
|---------|-------------------|---------------|
| **Intent** | 13 proposti | **20 implementati** (+54%) |
| **Tool** | ~7 ipotizzati | **19 implementati** (+171%) |
| **Router** | LLM-only | **Ibrido 7 fasi** (gibberish + heuristics + cache + LLM + fallback) |
| **Risk model** | Formula semplificata | **XGBoost V4 + statistico** (selezionabile) |
| **Ricerca piani** | Ricerca semantica base | **Hybrid search v1.0.0** con smart routing |
| **LLM** | LLaMA 3.1 singolo | **5 backend, 6+ modelli** (incluso Velvet GDPR) + provider esterni |
| **Dialogue** | Non specificato | **Dialogue Manager rule-based** con multi-turno |
| **Two-phase** | Non previsto | **Implementato** (dettagli su richiesta, soglie per tool) |
| **Data source** | PostgreSQL diretto | **Factory pattern** (CSV/PostgreSQL, switchabile) + SQLAlchemy pooling |
| **RAG** | Ipotizzato come opzionale | **Implementato** per procedure operative (Qdrant + chunk) |
| **Debug tools** | Non previsti | **Visualizzatore LangGraph + debug page** |
| **Speech-to-text** | Non previsto | **Endpoint predisposto** (configurabile) |
| **Frontend** | "Go server" generico | **Go/Gin completo** con temi, download, retry |
| **Chat logging** | Non previsto | **Implementato** (PostgreSQL, analytics, monitor qualita') |
| **Dashboard** | Non prevista | **Implementata** (analytics + monitor + cronologia) |
| **Provider LLM** | Solo locale | **5 backend** con gate GDPR per provider esterni |
| **Intent metadata** | Hardcoded | **DB-first** (tabella intents + intent_examples + Qdrant few-shot) |

---

**Scalabilita' dell'architettura**

L'architettura realizzata mantiene tutte le caratteristiche di scalabilita' previste nella proposta iniziale, con miglioramenti aggiuntivi:

- **Scalabilita' orizzontale**: FastAPI ASGI + Uvicorn, replicabile su container
- **Scalabilita' funzionale**: Separazione netta tra classificazione, decisione, esecuzione e risposta
- **Scalabilita' del dato**: Factory pattern per switchare sorgenti dati senza modifiche al codice; SQLAlchemy connection pooling
- **Scalabilita' ML**: Predittore ML isolato, sostituibile senza impatto sull'orchestratore
- **Scalabilita' LLM**: 5 backend switchabili, gate GDPR per compliance
- **Caching multi-livello**: Intent cache (MD5+TTL), embedding cache (max 100), search results cache (max 100), risk scores cache, health check cache, dati precaricati in memoria, singleton data sources
- **Monitoraggio**: Performance tracker, execution path tracking, latenza per nodo, chat logging con analytics, monitor intelligente con health score

---

**Roadmap completata e sviluppi futuri**

**Completato (rispetto alla roadmap proposta)**

- Mese 1 - Connettivita': Server FastAPI, webhook, ConversationGraph, sessioni
- Mese 2 - Intelligenza Operativa: Router LLM, slot extraction, Tool Layer completo, RAG
- Mese 3 - Orchestrazione: Agents Layer, dialogue manager, gestione errori, test

**Sviluppi aggiuntivi completati (non previsti nella proposta)**

- Modello XGBoost V4 addestrato e in produzione
- Ricerca semantica ibrida con smart routing
- Supporto multi-modello LLM (6 modelli locali) e multi-backend (5 provider)
- Dialogue Manager rule-based con soglie adattive per modello
- Sistema two-phase per risposte con dettagli (soglie configurabili per tool)
- Frontend completo con tema light/dark, debug tools, shortcuts
- Visualizzatore LangGraph per debug workflow
- Ricerca stabilimenti per prossimita' geografica (geocoding Nominatim + filtro distanza)
- Dashboard analytics per supervisori ASL (metriche chat, intents, errori, timeline)
- Monitor qualita' conversazioni (fallback loop, ripetizioni, health score)
- Cronologia chat utente con ricerca per codice fiscale
- Persistenza conversazioni su database PostgreSQL (chat_log + views aggregate)
- Provider LLM esterni (OpenAI, Anthropic, Mistral via OpenAI-compat) con gate GDPR
- Intent Metadata Service DB-first (tabella intents + intent_examples + few-shot Qdrant)
- Proxy CORS per API chat-log (evita errori cross-origin)
- Monitor intelligente con analisi automatica (bug detection, root cause, trend, unmet needs)

**Possibili sviluppi futuri**

- Ampliamento intent per nuovi domini (es. ispezioni in corso, programmazione futura)
- Evoluzione del modello predittivo (V5) con feature aggiuntive
- Integrazione speech-to-text per operatori sul campo (endpoint predisposto, provider da configurare)
- Integrazione con sistemi di notifica (alert automatici su anomalie)
