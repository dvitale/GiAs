# Whisper Speech Recognition - Setup Guide

Guida completa per integrare Whisper (OpenAI) self-hosted nel client GChat.

---

## Architettura

```
Browser (MediaRecorder API)
    ↓ POST /gias/webchat/api/transcribe
Golang Backend (/opt/lang-env/gchat)
    ↓ Chiama whisper CLI localmente
Whisper Python (OpenAI)
    ↓ Trascrizione audio
Auto-fill textarea con testo trascritto
```

---

## 1. Installazione Whisper

### Prerequisiti

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y ffmpeg python3-pip

# Verifica Python 3.8+
python3 --version
# Output atteso: Python 3.10.x o superiore
```

### Installazione Whisper via pip

```bash
# Installa Whisper da repository GitHub ufficiale
pip install git+https://github.com/openai/whisper.git

# Verifica installazione
whisper --help

# Output atteso:
# usage: whisper [-h] [--model {tiny,base,small,medium,large}] ...
```

### Download Modello

Whisper scarica automaticamente i modelli al primo utilizzo. I modelli disponibili:

| Modello | Dimensione | RAM Richiesta | Velocità | Accuracy (IT) |
|---------|------------|---------------|----------|---------------|
| tiny | ~75 MB | ~1 GB | Velocissimo | 80-85% |
| base | ~142 MB | ~1 GB | Veloce | 85-90% |
| small | ~466 MB | ~2 GB | Medio | 90-95% ✅ CONSIGLIATO |
| medium | ~1.5 GB | ~5 GB | Lento | 95-98% |
| large | ~2.9 GB | ~10 GB | Molto lento | 98%+ |

**Pre-download modello (raccomandato per produzione)**:

```bash
# Scarica modello small (raccomandato)
whisper --model small --language Italian --output_format txt /dev/null

# I modelli vengono salvati in ~/.cache/whisper/
ls -lh ~/.cache/whisper/

# Output atteso:
# -rw-r--r-- 1 root root 466M small.pt

# Download altri modelli (opzionale)
whisper --model tiny --language Italian --output_format txt /dev/null    # 75 MB
whisper --model base --language Italian --output_format txt /dev/null    # 142 MB
whisper --model medium --language Italian --output_format txt /dev/null  # 1.5 GB
```

**IMPORTANTE**: Il primo utilizzo di Whisper può richiedere 2-5 minuti per scaricare il modello. Per evitare timeout in produzione, esegui il pre-download durante l'installazione.

---

## 2. Test Whisper CLI

### Test Manuale

```bash
# Crea file audio di test (5 secondi di silenzio)
ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 5 -acodec pcm_s16le /tmp/test.wav

# Trascrivi con Whisper
whisper /tmp/test.wav --model small --language Italian --output_format txt

# Output atteso:
# Detecting language using up to the first 30 seconds. Use `--language` to specify the language
# Detected language: Italian
# [00:00.000 --> 00:05.000]
# (vuoto perché audio è silenzio)

# File output: /tmp/test.txt
cat /tmp/test.txt
```

### Test con Audio Reale

```bash
# Registra 5 secondi di audio dal microfono (se disponibile)
arecord -d 5 -f cd -t wav /tmp/voice.wav

# Trascrivi
whisper /tmp/voice.wav --model small --language Italian --output_format txt

# Verifica trascrizione
cat /tmp/voice.txt
```

---

## 3. Modifica Backend GChat per Whisper CLI

Il backend Golang deve chiamare il comando `whisper` invece di chiamare un server HTTP.

### Modifica `transcribe.go`

```bash
# Backup file originale
cp /opt/lang-env/gchat/app/transcribe.go /opt/lang-env/gchat/app/transcribe.go.bak
```

Modifica la funzione `callWhisper` in `/opt/lang-env/gchat/app/transcribe.go`:

```go
func callWhisper(audioPath, whisperURL, language string) (string, error) {
    // Ignora whisperURL, usa Whisper CLI locale

    model := os.Getenv("WHISPER_MODEL")
    if model == "" {
        model = "small"  // Default: small (90-95% accuracy)
    }

    outputDir := filepath.Dir(audioPath)

    // Esegui whisper CLI
    cmd := exec.Command("whisper",
        audioPath,
        "--model", model,
        "--language", "Italian",
        "--output_format", "txt",
        "--output_dir", outputDir,
    )

    var stderr bytes.Buffer
    cmd.Stderr = &stderr

    if err := cmd.Run(); err != nil {
        return "", fmt.Errorf("whisper command failed: %w, stderr: %s", err, stderr.String())
    }

    // Leggi file output (.txt)
    baseName := strings.TrimSuffix(filepath.Base(audioPath), filepath.Ext(audioPath))
    outputFile := filepath.Join(outputDir, baseName+".txt")
    defer os.Remove(outputFile)

    content, err := os.ReadFile(outputFile)
    if err != nil {
        return "", fmt.Errorf("failed to read transcription: %w", err)
    }

    return strings.TrimSpace(string(content)), nil
}
```

Aggiungi import necessario in cima al file:

```go
import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "mime/multipart"
    "net/http"
    "os"
    "os/exec"        // NUOVO
    "path/filepath"
    "strings"        // NUOVO

    "github.com/gin-gonic/gin"
)
```

---

## 4. Configurazione Variabili Ambiente (Opzionale)

Puoi cambiare modello Whisper senza ricompilare:

```bash
# Aggiungi in ~/.bashrc o in systemd service
export WHISPER_MODEL=small  # Opzioni: tiny, base, small, medium, large

# Per systemd service di GChat
sudo systemctl edit gchat.service

# Aggiungi sotto [Service]
[Service]
Environment="WHISPER_MODEL=small"
```

---

## 5. Build e Deploy GChat

### File Modificati

#### ✅ Backend Golang

**File**: `/opt/lang-env/gchat/app/transcribe.go` - **GIÀ CREATO**

Handler per endpoint `/api/transcribe`:
- Riceve audio blob da browser
- Salva temporaneamente
- Inoltra a Whisper.cpp (`http://localhost:8090/inference`)
- Ritorna JSON `{"text": "...", "language": "it"}`

**File**: `/opt/lang-env/gchat/app/main.go:120` - **GIÀ MODIFICATO**

Route aggiunta:
```go
api.POST("/api/transcribe", TranscribeHandler)
```

#### ✅ Frontend JavaScript

**File**: `/opt/lang-env/gchat/statics/js/chat.js` - **GIÀ MODIFICATO**

Aggiunte nel costruttore:
```javascript
this.isRecording = false;
this.mediaRecorder = null;
this.audioChunks = [];
this.initSpeechRecognition();
```

Nuovi metodi:
- `initSpeechRecognition()` - Crea pulsante microfono
- `toggleRecording()` - Avvia/ferma registrazione
- `startRecording()` - MediaRecorder API + auto-stop 30s
- `stopRecording()` - Cleanup stream audio
- `transcribeAudio()` - POST a `/api/transcribe`
- `showTranscriptionPreview()` - Toast "Trascritto: ..."
- `showError()` - Toast errori

#### ✅ CSS Styling

**File**: `/opt/lang-env/gchat/statics/css/style.css` - **GIÀ MODIFICATO**

Aggiunti alla fine del file:
- `.mic-button` - Pulsante microfono circolare
- `.mic-button.recording` - Animazione pulsante rosso
- `@keyframes pulse` - Animazione pulsante
- `.transcription-toast` - Toast trascrizione
- Dark theme variants
- Responsive mobile

### Rebuild Golang Binary

```bash
cd /opt/lang-env/gchat

# Stop server se attivo
./stop.sh

# Rebuild
go build -o bin/gchat app/*.go

# Verifica compilazione
ls -lh bin/gchat
# Output atteso: -rwxr-xr-x 1 root root 15M Dec 30 13:00 bin/gchat

# Avvia server
./run.sh
```

---

## 6. Test End-to-End

### 1. Verifica Whisper CLI

```bash
# Test con file audio vuoto
ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 3 -acodec pcm_s16le /tmp/test.wav
whisper /tmp/test.wav --model small --language Italian --output_format txt

# Dovrebbe completare senza errori
```

### 2. Verifica Endpoint GChat

```bash
# Crea audio test
ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 3 -acodec pcm_s16le /tmp/dummy.wav

curl -X POST \
  -F "audio=@/tmp/dummy.wav" \
  -F "language=it" \
  http://localhost:8080/gias/webchat/api/transcribe

# Output atteso:
{"text":"","language":"it"}  # Vuoto perché silenzio
```

### 3. Test Browser

1. **Apri browser**: `http://localhost:8080/gias/webchat?user_id=42145&asl_name=AVELLINO`
2. **Verifica presenza pulsante microfono** (cerchio giallo/blu accanto textarea)
3. **Clicca pulsante microfono**:
   - Browser chiede permesso microfono → **ACCETTA**
   - Pulsante diventa rosso pulsante
4. **Parla**: "Di cosa tratta il piano A1?"
5. **Clicca di nuovo per fermare** (o aspetta 30 secondi)
6. **Verifica**:
   - Toast appare in basso: "**Trascritto:** di cosa tratta il piano a1"
   - Textarea auto-riempita con testo
7. **Invia messaggio** premendo Enter o pulsante Send

---

## 7. Ottimizzazione Performance

### 7.1 Riduzione RAM Whisper

Se Whisper usa troppa RAM:

```bash
# Modifica service unit
sudo systemctl edit whisper.service

# Aggiungi sotto [Service]
MemoryMax=1500M
CPUQuota=40%
```

### 7.2 Pre-warm Whisper (Riduce First Request Latency)

```bash
# Aggiungi in whisper.service
ExecStartPost=/bin/bash -c 'sleep 5 && curl -X POST -F "file=@/opt/whisper.cpp/samples/jfk.wav" http://localhost:8090/inference'
```

Questo carica il modello in memoria al boot.

### 7.3 Logging Dettagliato

GChat logga automaticamente:
- `TRANSCRIBE_REQUEST`: Nome file, dimensione, lingua
- `TRANSCRIBE_WHISPER`: URL chiamata Whisper
- `TRANSCRIBE_SUCCESS`: Lunghezza testo trascritto
- `ERROR_TRANSCRIBE`: Errori in qualsiasi fase

Controlla log:
```bash
tail -f /opt/lang-env/gchat/log/*.log
```

---

## 8. Troubleshooting

### Problema 1: Whisper Non Trovato

**Errore**: `whisper: command not found`

```bash
# Verifica installazione
which whisper

# Se non trovato, reinstalla
pip install --upgrade --force-reinstall git+https://github.com/openai/whisper.git

# Verifica PATH
echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Problema 2: Errore 500 su /api/transcribe

**Causa**: Whisper CLI fallisce

```bash
# Controlla log GChat
tail -f /opt/lang-env/gchat/log/*.log | grep TRANSCRIBE

# Test whisper manualmente
whisper /tmp/test.wav --model small --language Italian --output_format txt
```

### Problema 3: Trascrizione Vuota

**Causa**: Audio troppo corto o silenzio

**Fix**: Whisper OpenAI supporta automaticamente WAV, MP3, OGG, WebM. Se la trascrizione è vuota:

```bash
# Verifica file audio generato
ls -lh /tmp/whisper-*.wav

# Testa manualmente
whisper /tmp/whisper-*.wav --model small --language Italian --output_format txt
```

### Problema 4: Latency Alta (>10 secondi)

**Causa**: CPU lenta o modello troppo grande

**Fix**: Usa modello più piccolo

```bash
# Cambia variabile ambiente
export WHISPER_MODEL=base  # invece di small

# OPPURE modifica systemd service GChat
sudo systemctl edit gchat.service

[Service]
Environment="WHISPER_MODEL=tiny"  # Più veloce ma meno accurato

# Riavvia GChat
sudo systemctl restart gchat.service
```

### Problema 5: Browser Non Chiede Permessi Microfono

**Causa**: HTTPS richiesto (eccetto localhost)

**Fix**: Se accedi via IP remoto, abilita HTTPS con nginx reverse proxy:

```nginx
# /etc/nginx/sites-available/gchat
server {
    listen 443 ssl;
    server_name gias.example.com;

    ssl_certificate /etc/ssl/certs/gias.crt;
    ssl_certificate_key /etc/ssl/private/gias.key;

    location /gias/webchat {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Problema 6: GChat Non Compila

**Errore**: `undefined: exec` o `undefined: strings`

**Fix**: Verifica import in `transcribe.go`:

```bash
# Controlla import
head -20 /opt/lang-env/gchat/app/transcribe.go

# Dovrebbe contenere:
# import (
#     "os/exec"
#     "strings"
#     ...
# )

# Ricompila
cd /opt/lang-env/gchat
go build -o bin/gchat app/*.go
```

---

## 9. Benchmark Performance

### Metriche Attese

| Modello | RAM Usata | Latenza (5s audio) | Latenza (15s audio) | Accuracy (IT) |
|---------|-----------|--------------------|--------------------|---------------|
| tiny | ~200 MB | 0.5-1s | 1-2s | 80-85% |
| base | ~400 MB | 1-2s | 3-5s | 85-90% |
| small | ~1 GB | 2-4s | 6-10s | 90-95% ✅ |
| medium | ~2.5 GB | 5-10s | 15-25s | 95-98% |

**Hardware test**: Intel i5, 4 core, 8GB RAM, CPU only

---

## 10. Alternative: Whisper Cloud API (Se Server Troppo Lento)

Se server locale non ha risorse sufficienti, usa Whisper API di OpenAI:

### Modifica `transcribe.go`:

```go
func callWhisper(audioPath, whisperURL, language string) (string, error) {
    // Usa OpenAI API invece di whisper.cpp
    apiKey := os.Getenv("OPENAI_API_KEY")
    if apiKey == "" {
        return "", fmt.Errorf("OPENAI_API_KEY not set")
    }

    // Implementa chiamata a https://api.openai.com/v1/audio/transcriptions
    // Costo: $0.006 / minuto (~€0.30 per 50 trascrizioni da 1 minuto)
}
```

**Pro**:
- No overhead RAM/CPU sul server
- Latency bassa (1-3s)
- Accuracy massima (98%+)

**Contro**:
- Costo pay-per-use
- Dipendenza da servizio esterno
- Privacy: audio inviato a OpenAI

---

## 11. Riepilogo File Modificati

```bash
# Backend
/opt/lang-env/gchat/app/transcribe.go       # ✅ CREATO (da modificare callWhisper)
/opt/lang-env/gchat/app/main.go             # ✅ MODIFICATO (route aggiunta)

# Frontend
/opt/lang-env/gchat/statics/js/chat.js      # ✅ MODIFICATO (metodi speech rec)
/opt/lang-env/gchat/statics/css/style.css   # ✅ MODIFICATO (CSS appeso)

# Whisper Python
~/.cache/whisper/small.pt                   # ⬜ Scaricato automaticamente al primo uso
```

---

## 12. Checklist Installazione

- [ ] 1. Installato ffmpeg: `sudo apt-get install ffmpeg`
- [ ] 2. Installato Whisper: `pip install git+https://github.com/openai/whisper.git`
- [ ] 3. Verificato comando: `whisper --help`
- [ ] 4. Modificato `transcribe.go` → `callWhisper()` usa `exec.Command("whisper", ...)`
- [ ] 5. Rebuild GChat: `go build -o bin/gchat app/*.go`
- [ ] 6. Testato endpoint `/api/transcribe` con curl
- [ ] 7. Riavviato GChat server
- [ ] 8. Testato nel browser: pulsante microfono visibile
- [ ] 9. Testato registrazione + trascrizione end-to-end
- [ ] 10. Verificato log GChat per `TRANSCRIBE_SUCCESS`

---

**Tempo stimato**: 15-20 minuti
**RAM aggiuntiva richiesta**: +1-2 GB (per modello small durante trascrizione)
**Performance attesa**: Trascrizione 5s audio → 2-4s latenza (modello small, CPU)

---

## Contatti e Supporto

Per problemi o domande:
1. Verifica Whisper: `whisper --help`
2. Test manuale: `whisper /tmp/test.wav --model small --language Italian`
3. Controlla log GChat: `tail -f /opt/lang-env/gchat/log/*.log | grep TRANSCRIBE`
4. Verifica RAM disponibile: `free -h`
