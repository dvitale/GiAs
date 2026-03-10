# Schema-Aware LLM e Query Data

**Componente**: Backend (GiAs-llm)
**Provenienza**: Requisito utente 2026-03-10
**File sorgente analizzati**: `orchestrator/schema_catalog.py`, `orchestrator/intent_metadata_service.py`, `tools/query_builder_tools.py`, `sql/create_schema_metadata.sql`

## Requisiti Funzionali

### SQ-01 Tabella schema_metadata in PostgreSQL
- **Pattern EARS**: Il sistema DEVE disporre di una tabella `schema_metadata` con campi: table_key (PK), table_name, df_variable, description_it, columns (JSONB), relationships (JSONB), valid_values (JSONB), pii_columns (TEXT[]), row_count_approx, is_active, updated_at.
- **Status**: IMPLEMENTATO

### SQ-02 SchemaCatalog singleton con lazy loading
- **Pattern EARS**: Il sistema DEVE fornire un singleton `SchemaCatalog` con lazy loading che carica metadati schema da `schema_metadata` alla prima chiamata; SE il DB non e' disponibile, il sistema DEVE usare un fallback statico hardcoded.
- **Status**: IMPLEMENTATO

### SQ-03 Catalogo compatto per prompt classificazione
- **Pattern EARS**: Il sistema DEVE generare un catalogo schema compatto (~300 token) tramite `get_compact_catalog()` e iniettarlo nel prompt di classificazione LLM come sezione "DATI DISPONIBILI".
- **Status**: IMPLEMENTATO

### SQ-04 Schema completo per query builder
- **Pattern EARS**: Il sistema DEVE fornire `get_full_schema()` con colonne complete, tipi, sample_values e relazioni per l'uso nel prompt del query builder (seconda chiamata LLM dentro query_data_tool).
- **Status**: IMPLEMENTATO

### SQ-05 Blacklist PII da schema_metadata
- **Pattern EARS**: Il sistema DEVE recuperare le colonne PII da `schema_metadata.pii_columns` tramite `get_pii_columns()` e `get_all_pii_columns()` per bloccare l'accesso a dati personali nelle query.
- **Status**: IMPLEMENTATO

### SQ-06 Hot-reload SchemaCatalog
- **Pattern EARS**: QUANDO viene invocato `reload()`, il sistema DEVE resettare lo stato interno e ricaricare i metadati da DB, rigenerando il catalogo compatto e lo schema completo.
- **Status**: IMPLEMENTATO

### SQ-07 Intent query_data - Operation Descriptor
- **Pattern EARS**: QUANDO l'intent e' query_data, il sistema DEVE generare un Operation Descriptor JSON tramite una seconda chiamata LLM con schema completo, validarlo con QueryDescriptor (Pydantic), e eseguirlo su DataFrame in memoria (no SQL diretto).
- **Status**: IMPLEMENTATO

### SQ-08 QueryDescriptor - validazione struttura
- **Pattern EARS**: Il sistema DEVE validare l'Operation Descriptor con: tabella in whitelist (7 tabelle note), operazione in whitelist (count, sum, mean, filter, group_count, top_n, distinct), operatori filtro in whitelist (eq, neq, contains, gte, lte, in, not_in), limite massimo 100 righe.
- **Status**: IMPLEMENTATO

### SQ-09 SafeQueryExecutor - preprocessing filtri
- **Pattern EARS**: Il sistema DEVE pre-processare i filtri tramite `_preprocess_filters()`: (1) traduzione alias colonne concettuali a colonne reali (anno→data_inizio_controllo, asl→descrizione_asl), (2) conversione anno in range date (gte/lte), (3) normalizzazione valori ASL ("ASL Benevento"→"BENEVENTO"), (4) fuzzy match colonne, (5) upgrade eq→contains per colonne testo.
- **Status**: IMPLEMENTATO

### SQ-10 SafeQueryExecutor - filtri datetime-aware
- **Pattern EARS**: QUANDO un filtro gte/lte opera su una colonna datetime64, il sistema DEVE convertire il valore a pd.Timestamp prima della comparazione.
- **Status**: IMPLEMENTATO

### SQ-11 Regole disambiguazione query_data
- **Pattern EARS**: Il prompt di classificazione DEVE includere regole che: (1) preferiscono SEMPRE intent specifici quando applicabili, (2) assegnano a query_data confidence MAI > 0.80, (3) distinguono "quanti controlli nell'ASL X" (→query_data) da "statistiche piani" (→ask_piano_statistics).
- **Status**: IMPLEMENTATO

### SQ-12 Pagina admin schema metadata
- **Pattern EARS**: Il sistema DEVE esporre una pagina admin `/gias/webchat/admin/schema` con interfaccia CRUD per visualizzare e modificare i metadati schema, incluso bottone "Ricarica Catalogo" che invoca il reload.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### SQ-NF01 Budget token schema nel prompt
- **Pattern EARS**: L'iniezione del catalogo schema nel prompt di classificazione DEVE aggiungere non piu' di ~400 token al prompt totale.
- **Status**: IMPLEMENTATO

### SQ-NF02 Diagnostica risultati vuoti
- **Pattern EARS**: QUANDO una query restituisce zero risultati, il sistema DEVE mostrare valori esempio della prima colonna filtrata per aiutare l'utente a capire il formato atteso.
- **Status**: IMPLEMENTATO

### SQ-NF03 Limite righe risultato
- **Pattern EARS**: Il sistema DEVE limitare i risultati a MAX_RESULT_ROWS (100) per prevenire risposte troppo grandi e problemi di performance su tabelle con milioni di righe.
- **Status**: IMPLEMENTATO
