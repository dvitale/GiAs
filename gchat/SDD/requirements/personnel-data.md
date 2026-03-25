# Personnel Data

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/personale.go

## Requisiti Funzionali

### PD-01 CSV loading con parsing PersonaleRecord
- **Pattern EARS**: Il sistema DEVE caricare i dati del personale dal file `data/personale.csv` in una mappa `map[int]PersonaleRecord` indicizzata per UserID, gestendo record con i campi ASL, DescrizioneAreaStrutturaComplessa, Descrizione, NameFirst, NameLast, CodiceFiscale, UserID (int), UOS. QUANDO il campo Descrizione contiene almeno 3 segmenti separati da `->`, DEVE estrarre il terzo segmento (indice 2) come UOS con trim degli spazi. DEVE saltare la prima riga (header) e i record con meno di 7 campi o UserID non numerico.
- **Status**: IMPLEMENTATO
- **Accorpa**: PD-01, PD-04, PD-05, PD-06, PD-07

### PD-02 Cache Basata su Modifica File
- **Pattern EARS**: QUANDO il file CSV non e' stato modificato dall'ultimo caricamento (confronto `ModTime`), il sistema DEVE restituire i dati dalla cache senza rileggere il file.
- **Status**: IMPLEMENTATO

### PD-03 Double-Check Lock
- **Pattern EARS**: QUANDO piu' goroutine tentano di ricaricare i dati contemporaneamente, il sistema DEVE utilizzare il pattern double-check con `sync.RWMutex` (prima RLock per leggere, poi Lock per scrivere con ricontrollo).
- **Status**: IMPLEMENTATO

### PD-08 GetPersonaleByUserID Lookup
- **Pattern EARS**: QUANDO si cerca un utente per UserID, il sistema DEVE caricare i dati (con cache), cercare l'ID nella mappa e restituire un errore se non trovato.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### PD-NF01 Logging e concorrenza cache personale
- **Pattern EARS**: Il sistema DEVE loggare gli eventi di cache con prefisso PERSONALE_CACHE: hit ("Using cached data"), miss/reload ("Loading CSV file"), conteggio record caricati. DEVE garantire la sicurezza in accesso concorrente alla cache tramite `sync.RWMutex`, usando RLock per letture e Lock per scritture.
- **Status**: IMPLEMENTATO
- **Accorpa**: PD-NF01, PD-NF02
