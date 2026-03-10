# Personnel Data

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/personale.go

## Requisiti Funzionali

### PD-01 CSV Loading
- **Pattern EARS**: Il sistema DEVE caricare i dati del personale dal file `data/personale.csv` in una mappa `map[int]PersonaleRecord` indicizzata per UserID.
- **Status**: IMPLEMENTATO

### PD-02 Cache Basata su Modifica File
- **Pattern EARS**: QUANDO il file CSV non e' stato modificato dall'ultimo caricamento (confronto `ModTime`), il sistema DEVE restituire i dati dalla cache senza rileggere il file.
- **Status**: IMPLEMENTATO

### PD-03 Double-Check Lock
- **Pattern EARS**: QUANDO piu' goroutine tentano di ricaricare i dati contemporaneamente, il sistema DEVE utilizzare il pattern double-check con `sync.RWMutex` (prima RLock per leggere, poi Lock per scrivere con ricontrollo).
- **Status**: IMPLEMENTATO

### PD-04 PersonaleRecord Struct
- **Pattern EARS**: Il sistema DEVE gestire record con i campi: ASL, DescrizioneAreaStrutturaComplessa, Descrizione, NameFirst, NameLast, CodiceFiscale, UserID (int), UOS.
- **Status**: IMPLEMENTATO

### PD-05 UOS Estrazione da Descrizione
- **Pattern EARS**: QUANDO il campo Descrizione contiene almeno 3 segmenti separati da `->`, il sistema DEVE estrarre il terzo segmento (indice 2) come UOS, con trim degli spazi.
- **Status**: IMPLEMENTATO

### PD-06 Header Row Skip
- **Pattern EARS**: QUANDO si legge il CSV, il sistema DEVE saltare la prima riga (header) prima di processare i record.
- **Status**: IMPLEMENTATO

### PD-07 Malformed Record Skip
- **Pattern EARS**: SE un record ha meno di 7 campi o il campo UserID (colonna 7) non e' un numero valido, il sistema DEVE saltare silenziosamente il record senza errore.
- **Status**: IMPLEMENTATO

### PD-08 GetPersonaleByUserID Lookup
- **Pattern EARS**: QUANDO si cerca un utente per UserID, il sistema DEVE caricare i dati (con cache), cercare l'ID nella mappa e restituire un errore se non trovato.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### PD-NF01 Logging Cache
- **Pattern EARS**: Il sistema DEVE loggare gli eventi di cache con prefisso PERSONALE_CACHE: hit ("Using cached data"), miss/reload ("Loading CSV file"), conteggio record caricati.
- **Status**: IMPLEMENTATO

### PD-NF02 Concorrenza Sicura
- **Pattern EARS**: Il sistema DEVE garantire la sicurezza in accesso concorrente alla cache tramite `sync.RWMutex`, usando RLock per letture e Lock per scritture.
- **Status**: IMPLEMENTATO
