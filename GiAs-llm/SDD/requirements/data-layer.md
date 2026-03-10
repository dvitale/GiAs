# Data Layer

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `data_sources/factory.py`, `data_sources/csv_source.py`, `data_sources/postgresql_source.py`, `agents/data_agent.py`

## Requisiti Funzionali

### DL-01 Factory pattern con singleton
- **Pattern EARS**: Il sistema DEVE fornire un factory method `get_data_source()` che crea l'istanza appropriata (CSV o PostgreSQL) basandosi sulla configurazione in config.json e la mantiene come singleton globale. Tutte le chiamate successive DEVONO restituire la stessa istanza.
- **Status**: IMPLEMENTATO

### DL-02 Intercambiabilita' CSV/PostgreSQL
- **Pattern EARS**: Il sistema DEVE supportare due data source intercambiabili (CSVDataSource e PostgreSQLDataSource) che implementano la stessa interfaccia base DataSource con metodi load_piani, load_attivita, load_controlli, load_osa_mai_controllati, load_ocse, load_diff_prog_eseg, load_personale.
- **Status**: IMPLEMENTATO

### DL-03 Selezione data source da configurazione
- **Pattern EARS**: QUANDO il tipo configurato in config.json e' "postgresql" E postgresql.enabled e' true, il sistema DEVE creare un PostgreSQLDataSource. In tutti gli altri casi, il sistema DEVE creare un CSVDataSource.
- **Status**: IMPLEMENTATO

### DL-04 Connection pooling SQLAlchemy
- **Pattern EARS**: QUANDO viene creato il PostgreSQLDataSource, il sistema DEVE inizializzare un engine SQLAlchemy con QueuePool (pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=3600s) come class-level singleton condiviso tra tutte le istanze.
- **Status**: IMPLEMENTATO

### DL-05 Cache DataFrame class-level
- **Pattern EARS**: Il sistema DEVE mantenere una cache DataFrame a livello di classe (_dataframe_cache) condivisa tra tutte le istanze PostgreSQLDataSource, restituendo copie dei DataFrame cached per prevenire modifiche accidentali.
- **Status**: IMPLEMENTATO

### DL-06 Deduplicazione piani PostgreSQL
- **Pattern EARS**: QUANDO i piani vengono caricati da PostgreSQL, il sistema DEVE deduplicare le righe basandosi su (sezione, alias, alias_indicatore) mantenendo la prima occorrenza, poiche' PostgreSQL contiene duplicati (5x per record).
- **Status**: IMPLEMENTATO

### DL-07 Deduplicazione attivita' PostgreSQL
- **Pattern EARS**: QUANDO le attivita' vengono caricate da PostgreSQL, il sistema DEVE deduplicare le righe basandosi su tutte le colonne eccetto 'id', poiche' PostgreSQL contiene duplicati (4x per record).
- **Status**: IMPLEMENTATO

### DL-08 Filtro personale per anno corrente
- **Pattern EARS**: QUANDO i dati personale vengono caricati (sia CSV che PostgreSQL), il sistema DEVE filtrare per anno == current_year (da config) e deduplicare per user_id mantenendo la prima occorrenza.
- **Status**: IMPLEMENTATO

### DL-09 Fallback psycopg2
- **Pattern EARS**: SE SQLAlchemy non e' disponibile, il sistema DEVE utilizzare psycopg2 come fallback per le connessioni PostgreSQL dirette.
- **Status**: IMPLEMENTATO

### DL-10 Precaricamento completo
- **Pattern EARS**: Il sistema DEVE supportare il precaricamento di tutti i dataset in cache tramite il metodo classmethod preload_all_data(), invocato durante l'inizializzazione dell'applicazione per prestazioni ottimali.
- **Status**: IMPLEMENTATO

### DL-11 DataRetriever con metodi statici
- **Pattern EARS**: Il sistema DEVE fornire una classe DataRetriever con metodi statici per il recupero dati puro (senza logica di presentazione): get_piano_by_id, get_controlli_by_piano, get_osa_mai_controllati, search_piani_semantic, search_piani_by_keyword, get_nc_by_category, get_establishments_with_most_sanctions, get_establishments_with_nc_category.
- **Status**: IMPLEMENTATO

### DL-12 Pesi categorie NC per business logic
- **Pattern EARS**: Il sistema DEVE definire pesi per 11 categorie NC (NC_CATEGORY_WEIGHTS) da HACCP (1.0) a ETICHETTATURA (0.3), utilizzati dalla logica di business per il calcolo del rischio ponderato.
- **Status**: IMPLEMENTATO

### DL-13 get_piano_by_id - fallback prefisso ATT
- **Pattern EARS**: QUANDO get_piano_by_id non trova match esatto per alias o alias_indicatore e il codice non inizia con "ATT ", il sistema DEVE tentare un secondo match con prefisso "ATT {codice}" su alias_indicatore, poiche' gli indicatori hanno formato "ATT AO5_A".
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### DL-NF01 CSV low_memory
- **Pattern EARS**: Il sistema DEVE caricare i file CSV con parametro low_memory=False per evitare errori di tipo misto su colonne con dati eterogenei.
- **Status**: IMPLEMENTATO

### DL-NF02 Gestione errori graceful
- **Pattern EARS**: SE un file CSV non viene trovato o una query PostgreSQL fallisce, il sistema DEVE restituire un DataFrame vuoto e loggare l'errore, senza propagare l'eccezione.
- **Status**: IMPLEMENTATO

### DL-NF03 Cleanup cache
- **Pattern EARS**: Il sistema DEVE fornire metodi clear_cache() e clear_data_source_cache() per invalidare la cache (per testing/reload), incluso dispose dell'engine SQLAlchemy.
- **Status**: IMPLEMENTATO
