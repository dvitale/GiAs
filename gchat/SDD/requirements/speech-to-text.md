# Speech-to-Text

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/transcribe.go, statics/js/chat.js (mic-related), statics/css/style.css (mic-button), app/config.go (TranscriptionConfig)

## Requisiti Funzionali

### ST-01 Feature Flag
- **Pattern EARS**: Il sistema DEVE attivare la funzionalita' speech-to-text solo se `config.json` ha `transcription.enabled=true`, passato al template come `window.transcriptionEnabled`.
- **Status**: IMPLEMENTATO
- **Note**: Attualmente disabilitato nella configurazione di default (`enabled: false`).

### ST-02 Comunicazione Whisper (endpoint, timeout, lingua, cleanup)
- **Pattern EARS**: QUANDO l'audio viene inviato per la trascrizione, il sistema DEVE chiamare l'endpoint Whisper configurato nella variabile d'ambiente `WHISPER_URL`, con fallback a `http://localhost:8090/inference`, applicando un timeout di 20 secondi. SE il parametro lingua non e' specificato, DEVE usare `"it"` come default. Il sistema DEVE salvare il file audio come temporaneo con pattern `whisper-*.webm` e rimuoverlo dopo l'elaborazione tramite `defer os.Remove`.
- **Status**: IMPLEMENTATO
- **Accorpa**: ST-02, ST-03, ST-04, ST-05

### ST-06 Profiling Logging
- **Pattern EARS**: Il sistema DEVE loggare le metriche di performance per ogni fase: ricezione file (PROFILE_HANDLER_RECEIVE), salvataggio (PROFILE_HANDLER_FILE_SAVE), chiamata Whisper (PROFILE_HANDLER_WHISPER_CALL), totale (PROFILE_HANDLER_TOTAL), in millisecondi.
- **Status**: IMPLEMENTATO

### ST-07 Mic Button Pulsating Red
- **Pattern EARS**: MENTRE il sistema sta registrando audio, il bottone microfono DEVE mostrare un'animazione pulsante rossa con classe `recording` (sfondo #fee2e2, bordo #ef4444, animazione pulse 1.5s infinite).
- **Status**: IMPLEMENTATO

### ST-08 Toast Notification
- **Pattern EARS**: QUANDO la trascrizione e' completata, il sistema DEVE mostrare un toast notification con il testo trascritto (classe `transcription-toast show`). SE la trascrizione fallisce, DEVE mostrare un toast di errore (classe `error`).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### ST-NF01 Profiling e diagnostica trascrizione
- **Pattern EARS**: Il sistema DEVE inviare il file audio come multipart form data con campo `file` e il parametro lingua come campo `language`. DEVE eseguire il trim degli spazi dal testo trascritto prima di restituirlo.
- **Status**: IMPLEMENTATO
- **Accorpa**: ST-NF01, ST-NF02
