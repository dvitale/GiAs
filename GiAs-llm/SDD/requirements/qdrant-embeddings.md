# Qdrant e Embeddings

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `agents/qdrant_singleton.py`, `agents/embedding_singleton.py`

## Requisiti Funzionali

### QE-01 Singleton QdrantClient con lazy init e fallback
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton globale di QdrantClient in modalita' locale file-based (path: `data/qdrant_storage`), poiche' Qdrant locale usa un lock esclusivo sulla directory. Il sistema DEVE creare il QdrantClient solo al primo utilizzo (lazy loading tramite flag _initialized); tutte le chiamate successive DEVONO restituire la stessa istanza. SE la directory di storage non esiste O la libreria qdrant_client non e' installata O l'inizializzazione fallisce, il sistema DEVE restituire None (non sollevare eccezioni), impostando _initialized=True per evitare tentativi ripetuti.
- **Status**: IMPLEMENTATO
- **Accorpa**: QE-01, QE-02, QE-03

### QE-04 Singleton embedding model con lazy loading
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton globale del modello SentenceTransformer `paraphrase-multilingual-MiniLM-L12-v2` per evitare il caricamento duplicato (~300MB RAM). Il sistema DEVE caricare il modello solo al primo utilizzo tramite get_embedding_model(), generando vettori a 384 dimensioni e supportando piu' lingue.
- **Status**: IMPLEMENTATO
- **Accorpa**: QE-04, QE-05

## Requisiti Non Funzionali

### QE-NF01 Condivisione tra componenti
- **Pattern EARS**: Il sistema DEVE garantire che DataRetriever e FewShotRetriever condividano la stessa istanza di QdrantClient e dello stesso modello embedding, evitando errori "already accessed by another instance" e consumo RAM duplicato.
- **Status**: IMPLEMENTATO
