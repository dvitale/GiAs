# PWA e Geolocalizzazione GPS

**Componente**: Frontend (gchat)
**Provenienza**: Requisiti 2026-03-13
**File sorgente**: `statics/sw.js`, `statics/manifest.webmanifest`, `statics/offline.html`, `statics/js/chat.js`, `template/index.html`, `app/llm_client.go`, `app/main.go`, `app/config.go`, `statics/css/style.css`, `config/config.json`

## PWA — Infrastruttura

### PG-01 Configurazione PWA manifest e meta tag
**UBIQUITOUS**: Il sistema DEVE servire un file `manifest.webmanifest` con `name`, `short_name`, `start_url` (`/gias/webchat/`), `display: standalone`, `theme_color`, `background_color` e almeno 3 icone (192x192, 384x384, 512x512). Il template `index.html` DEVE includere `<link rel="manifest">` e i meta tag `theme-color`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`. Il sistema DEVE registrare un Service Worker (`sw.js`) che implementa strategia cache-first per asset statici (CSS, JS, immagini) e network-first per chiamate API (`/chat`, `/chat/stream`).
- [IMPLEMENTATO]
- **Accorpa**: PG-01, PG-02, PG-03

### PG-04 Service Worker caching strategies
**WHEN** l'utente e' offline, **THEN** il Service Worker DEVE mostrare una pagina di fallback offline che indica l'indisponibilita' del servizio. **WHEN** il browser supporta `beforeinstallprompt` E l'utente non ha gia' installato la PWA, **THEN** il sistema DEVE mostrare un banner in basso con testo configurabile da `config.json` (`ui.pwa_install_message`), pulsante "Installa", pulsante chiudi (x), con scomparsa automatica dopo N secondi (`ui.pwa_install_timeout_seconds`) solo dopo approvazione installazione. Se chiuso senza installare, non riappare nella sessione (flag `localStorage`). **UBIQUITOUS**: Il Service Worker DEVE aggiornare la cache degli asset statici ad ogni nuova versione tramite numero di versione in `sw.js`.
- [IMPLEMENTATO]
- **Accorpa**: PG-04, PG-05, PG-06

### PG-NF01 [IMPLEMENTATO]
**NON-FUNZIONALE**: Il tempo di caricamento dalla cache DEVE essere < 2 secondi per asset statici.

## Geolocation — Frontend

### PG-07 Install banner configurabile
**WHEN** l'utente invia un messaggio chat, **THEN** il sistema DEVE acquisire le coordinate GPS tramite `navigator.geolocation.getCurrentPosition()` con `enableHighAccuracy: true` e includerle nel payload. **IF** l'utente concede il permesso GPS, **THEN** `latitude`, `longitude` e `accuracy` (metri) DEVONO essere inclusi nel payload chat.
- [IMPLEMENTATO]
- **Accorpa**: PG-07, PG-08

### PG-09 GPS on-demand con coordinate nel payload
**IF** l'utente nega il permesso GPS o il browser non supporta Geolocation API, **THEN** il sistema DEVE continuare normalmente senza coordinate (campi assenti nel payload). **UBIQUITOUS**: L'UI DEVE mostrare un indicatore GPS nell'header: attivo (verde), negato (grigio), non disponibile (nascosto). I campi `latitude`, `longitude`, `gps_accuracy_m` DEVONO essere aggiunti a `ChatRequest` e `NativeUserMetadata` in `llm_client.go` come `float64` con `omitempty`. **WHEN** il payload contiene `latitude` e `longitude`, **THEN** il server Go DEVE inoltrarli nel campo `metadata` della richiesta al backend Python.
- [IMPLEMENTATO]
- **Accorpa**: PG-09, PG-10, PG-11, PG-12

## Privacy / GDPR

### PG-13 Indicatore GPS nell'header
**UBIQUITOUS**: I parametri GPS NON DEVONO essere salvati nella sessione cookie (GDPR). Inviati fresh dal client ad ogni richiesta. Le coordinate GPS NON DEVONO essere loggate nei file di log del server Go ne' persistite in database (`chat_log`).
- [IMPLEMENTATO]
- **Accorpa**: PG-13, PG-14
