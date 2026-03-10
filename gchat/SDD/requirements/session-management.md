# Session Management

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/session.go, app/main.go

## Requisiti Funzionali

### SM-01 Session Store Cookie-Based
- **Pattern EARS**: Il sistema DEVE utilizzare un cookie store (gin-contrib/sessions) con nome sessione `gias_session` per memorizzare i parametri utente.
- **Status**: IMPLEMENTATO

### SM-02 TTL Sessione 300 Secondi
- **Pattern EARS**: Il sistema DEVE configurare il MaxAge del cookie di sessione a 300 secondi (5 minuti), allineato al TTL del backend Python.
- **Status**: IMPLEMENTATO

### SM-03 Cookie Path
- **Pattern EARS**: Il sistema DEVE configurare il path del cookie di sessione a `/gias/webchat`.
- **Status**: IMPLEMENTATO

### SM-04 Cookie HttpOnly
- **Pattern EARS**: Il sistema DEVE configurare il cookie di sessione con flag `HttpOnly=true` per prevenire l'accesso da JavaScript.
- **Status**: IMPLEMENTATO

### SM-05 Cookie SameSite Lax
- **Pattern EARS**: Il sistema DEVE configurare il cookie di sessione con `SameSite=Lax`.
- **Status**: IMPLEMENTATO

### SM-06 Cookie Secure
- **Pattern EARS**: Il sistema DEVE configurare il cookie di sessione con `Secure=true` in produzione per trasmissione solo su HTTPS.
- **Status**: PARZIALE
- **Note**: Attualmente impostato a `false` con commento "true in produzione con HTTPS".

### SM-07 Chiave Segreta Hardcoded
- **Pattern EARS**: Il sistema DEVE utilizzare una chiave segreta per la cifratura del cookie store, idealmente da variabile d'ambiente.
- **Status**: PARZIALE
- **Note**: La chiave e' hardcoded come `gias-secret-key-32-bytes-long!!!` con commento "in produzione usare una chiave segreta da variabile d'ambiente".

### SM-08 SessionMiddleware Verifica TTL
- **Pattern EARS**: QUANDO una richiesta arriva, il middleware DEVE verificare il timestamp della sessione e, se la differenza supera 300 secondi, DEVE cancellare la sessione e salvarla.
- **Status**: IMPLEMENTATO

### SM-09 SaveUserSession Parametri Non Vuoti
- **Pattern EARS**: QUANDO si salvano i parametri utente in sessione, il sistema DEVE salvare solo i parametri con valore non vuoto, aggiornando il timestamp.
- **Status**: IMPLEMENTATO

### SM-10 MergeSessionParams Priorita'
- **Pattern EARS**: QUANDO si uniscono i parametri utente, il sistema DEVE applicare la priorita': POST JSON/Form > Query String > Sessione Cookie.
- **Status**: IMPLEMENTATO

### SM-11 MergeSessionParams POST JSON
- **Pattern EARS**: QUANDO il Content-Type e' `application/json`, il sistema DEVE parsare i parametri user_id, asl_id, asl_name e codice_fiscale dal body JSON.
- **Status**: IMPLEMENTATO

### SM-12 MergeSessionParams POST Form
- **Pattern EARS**: QUANDO il Content-Type non e' JSON in una richiesta POST, il sistema DEVE leggere i parametri user_id, asl_id, asl_name e codice_fiscale dai dati form.
- **Status**: IMPLEMENTATO

### SM-13 Username Ignorato da POST Form
- **Pattern EARS**: QUANDO si parsano parametri da POST form, il sistema DEVE ignorare il campo `username` (non leggerlo dal form).
- **Status**: IMPLEMENTATO

### SM-14 Double-Write Pattern
- **Pattern EARS**: QUANDO MergeSessionParams completa il merge, il sistema DEVE salvare automaticamente i parametri aggiornati nella sessione tramite SaveUserSession (pattern double-write: lettura + scrittura ad ogni richiesta).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### SM-NF01 Type Assertion Sicura
- **Pattern EARS**: Il sistema DEVE utilizzare type assertion sicura (con check `ok`) per leggere valori dalla sessione, restituendo stringa vuota in caso di tipo non corretto.
- **Status**: IMPLEMENTATO

### SM-NF02 Logging Sessione
- **Pattern EARS**: Il sistema DEVE loggare gli eventi di sessione con prefissi strutturati: SESSION_SAVE_ERROR, SESSION_CLEAR_ERROR, SESSION_EXPIRED, SESSION_SAVED.
- **Status**: IMPLEMENTATO
