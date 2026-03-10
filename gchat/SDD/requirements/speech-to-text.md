# Speech-to-Text

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: app/transcribe.go, statics/js/chat.js (mic-related), statics/css/style.css (mic-button), app/config.go (TranscriptionConfig)

## Requisiti Funzionali

### ST-01 Feature Flag
- **Pattern EARS**: Il sistema DEVE attivare la funzionalita' speech-to-text solo se `config.json` ha `transcription.enabled=true`, passato al template come `window.transcriptionEnabled`.
- **Status**: IMPLEMENTATO
- **Note**: Attualmente disabilitato nella configurazione di default (`enabled: false`).

### ST-02 Whisper Endpoint
- **Pattern EARS**: QUANDO l'audio viene inviato per la trascrizione, il sistema DEVE chiamare l'endpoint Whisper configurato nella variabile d'ambiente `WHISPER_URL`, con fallback a `http://localhost:8090/inference`.
- **Status**: IMPLEMENTATO

### ST-03 Timeout 20s
- **Pattern EARS**: Il sistema DEVE applicare un timeout di 20 secondi alla chiamata verso il server Whisper.
- **Status**: IMPLEMENTATO

### ST-04 Lingua Default Italiano
- **Pattern EARS**: SE il parametro lingua non e' specificato nella richiesta, il sistema DEVE usare `"it"` come lingua di default.
- **Status**: IMPLEMENTATO

### ST-05 File Temporaneo WebM Cleanup
- **Pattern EARS**: QUANDO il sistema riceve un file audio, DEVE salvarlo come file temporaneo con pattern `whisper-*.webm` e rimuoverlo dopo l'elaborazione tramite `defer os.Remove`.
- **Status**: IMPLEMENTATO

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

### ST-NF01 Multipart Form Upload
- **Pattern EARS**: Il sistema DEVE inviare il file audio come multipart form data con campo `file` e il parametro lingua come campo `language`.
- **Status**: IMPLEMENTATO

### ST-NF02 Risposta Trimmed
- **Pattern EARS**: Il sistema DEVE eseguire il trim degli spazi dal testo trascritto prima di restituirlo.
- **Status**: IMPLEMENTATO
