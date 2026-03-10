# Qdrant e Embeddings

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `agents/qdrant_singleton.py`, `agents/embedding_singleton.py`

## Requisiti Funzionali

### QE-01 Singleton QdrantClient file-based
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton globale di QdrantClient in modalita' locale file-based (path: `data/qdrant_storage`), poiche' Qdrant locale usa un lock esclusivo sulla directory di storage e un solo client puo' accedere alla directory in un dato momento.
- **Status**: IMPLEMENTATO

### QE-02 Lazy initialization QdrantClient
- **Pattern EARS**: Il sistema DEVE creare il QdrantClient solo al primo utilizzo (lazy loading tramite flag _initialized). Tutte le chiamate successive a get_qdrant_client() DEVONO restituire la stessa istanza senza re-inizializzazione.
- **Status**: IMPLEMENTATO

### QE-03 Ritorno None se storage non disponibile
- **Pattern EARS**: SE la directory di storage Qdrant non esiste O la libreria qdrant_client non e' installata O l'inizializzazione fallisce, il sistema DEVE restituire None (non sollevare eccezioni), impostando _initialized=True per evitare tentativi ripetuti.
- **Status**: IMPLEMENTATO

### QE-04 Singleton modello embedding
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton globale del modello SentenceTransformer `paraphrase-multilingual-MiniLM-L12-v2` per evitare il caricamento duplicato (~300MB RAM ciascuno) tra DataRetriever e FewShotRetriever.
- **Status**: IMPLEMENTATO

### QE-05 Lazy loading modello embedding
- **Pattern EARS**: Il sistema DEVE caricare il modello embedding solo al primo utilizzo tramite get_embedding_model(). Il modello genera vettori a 384 dimensioni e supporta piu' lingue (multilingue).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### QE-NF01 Condivisione tra componenti
- **Pattern EARS**: Il sistema DEVE garantire che DataRetriever e FewShotRetriever condividano la stessa istanza di QdrantClient e dello stesso modello embedding, evitando errori "already accessed by another instance" e consumo RAM duplicato.
- **Status**: IMPLEMENTATO
