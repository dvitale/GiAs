# PWA e Geolocalizzazione GPS

**Componente**: Frontend (gchat)
**Provenienza**: Requisiti 2026-03-13
**File sorgente**: `statics/sw.js`, `statics/manifest.webmanifest`, `statics/offline.html`, `statics/js/chat.js`, `template/index.html`, `app/llm_client.go`, `app/main.go`, `app/config.go`, `statics/css/style.css`, `config/config.json`

## PWA — Infrastruttura

### PG-01 [IMPLEMENTATO]
**UBIQUITOUS**: Il sistema DEVE servire un file `manifest.webmanifest` con `name`, `short_name`, `start_url` (`/gias/webchat/`), `display: standalone`, `theme_color`, `background_color` e almeno 3 icone (192x192, 384x384, 512x512).

### PG-02 [IMPLEMENTATO]
**UBIQUITOUS**: Il template `index.html` DEVE includere `<link rel="manifest">` e i meta tag `theme-color`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`.

### PG-03 [IMPLEMENTATO]
**UBIQUITOUS**: Il sistema DEVE registrare un Service Worker (`sw.js`) che implementa strategia cache-first per asset statici (CSS, JS, immagini) e network-first per chiamate API (`/chat`, `/chat/stream`).

### PG-04 [IMPLEMENTATO]
**WHEN** l'utente e' offline, **THEN** il Service Worker DEVE mostrare una pagina di fallback offline che indica l'indisponibilita' del servizio.

### PG-05 [IMPLEMENTATO]
**WHEN** il browser supporta `beforeinstallprompt` E l'utente non ha gia' installato la PWA, **THEN** il sistema DEVE mostrare un banner in basso con: testo esplicativo configurabile da `config.json` (`ui.pwa_install_message`), pulsante "Installa", pulsante chiudi (x). Il banner scompare automaticamente dopo N secondi (`ui.pwa_install_timeout_seconds`) SOLO dopo approvazione installazione. Se chiuso senza installare, non riappare nella sessione (flag `localStorage`).

### PG-06 [IMPLEMENTATO]
**UBIQUITOUS**: Il Service Worker DEVE aggiornare la cache degli asset statici ad ogni nuova versione tramite numero di versione in `sw.js`.

### PG-NF01 [IMPLEMENTATO]
**NON-FUNZIONALE**: Il tempo di caricamento dalla cache DEVE essere < 2 secondi per asset statici.

## Geolocation — Frontend

### PG-07 [IMPLEMENTATO]
**WHEN** l'utente invia un messaggio chat, **THEN** il sistema DEVE acquisire le coordinate GPS tramite `navigator.geolocation.getCurrentPosition()` con `enableHighAccuracy: true` e includerle nel payload.

### PG-08 [IMPLEMENTATO]
**IF** l'utente concede il permesso GPS, **THEN** `latitude`, `longitude` e `accuracy` (metri) DEVONO essere inclusi nel payload chat.

### PG-09 [IMPLEMENTATO]
**IF** l'utente nega il permesso GPS o il browser non supporta Geolocation API, **THEN** il sistema DEVE continuare normalmente senza coordinate (campi assenti nel payload).

### PG-10 [IMPLEMENTATO]
**UBIQUITOUS**: L'UI DEVE mostrare un indicatore GPS nell'header: attivo (verde), negato (grigio), non disponibile (nascosto).

### PG-11 [IMPLEMENTATO]
**UBIQUITOUS**: I campi `latitude`, `longitude`, `gps_accuracy_m` DEVONO essere aggiunti a `ChatRequest` e `NativeUserMetadata` in `llm_client.go` come `float64` con `omitempty`.

## Trasporto Go

### PG-12 [IMPLEMENTATO]
**WHEN** il payload contiene `latitude` e `longitude`, **THEN** il server Go DEVE inoltrarli nel campo `metadata` della richiesta al backend Python.

### PG-13 [IMPLEMENTATO]
**UBIQUITOUS**: I parametri GPS NON DEVONO essere salvati nella sessione cookie (GDPR). Inviati fresh dal client ad ogni richiesta.

## Privacy / GDPR

### PG-14 [IMPLEMENTATO]
**UBIQUITOUS**: Le coordinate GPS NON DEVONO essere loggate nei file di log del server Go ne' persistite in database (`chat_log`).
