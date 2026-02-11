# Model Comparison Tool - Guida Completa

Sistema di test comparativo per modelli LLM in GiAs-llm.

## File Disponibili

### Script Principale

- **`compare_models.py`** - Script orchestratore per comparazione modelli
  - Avvia server con modelli diversi
  - Esegue test suite
  - Genera report comparativi

### Configurazioni

- **`compare_models_config.json`** - Configurazione completa (8 sezioni)
  - Tempo stimato: 16-24 minuti
  - Sezioni: 2, 3, 4, 12, 14, 18, 19, 22
  - Test approfonditi di accuratezza, performance, robustezza

- **`compare_models_quick.json`** - Configurazione rapida (3 sezioni critiche)
  - Tempo stimato: 6-8 minuti
  - Sezioni: 2, 3, 14 (Intent Classification + Performance)
  - Ideale per iterazione rapida

### Documentazione

- **`SERVER_CONFIG.md`** - Guida completa alla configurazione
  - Configurazione Ollama host
  - Configurazione GiAs server URL
  - Modalità operative (locale, remoto, ibrido)
  - Esempi e troubleshooting

- **`README_COMPARISON.md`** - Questo file

## Quick Start

### Test Rapido (3 sezioni, ~6-8 min)

```bash
cd /opt/lang-env/GiAs-llm
python3 scripts/compare_models.py \
    --config scripts/compare_models_quick.json
```

### Test Completo (8 sezioni, ~16-24 min)

```bash
python3 scripts/compare_models.py \
    --baseline llama3.2 \
    --candidate falcon
```

## Configurazione Server

### Parametri Configurabili

Il sistema supporta due endpoint configurabili:

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `ollama_host` | Host Ollama (hostname/IP) | `localhost` |
| `gias_server_url` | URL server GiAs | `http://localhost:5005` |

### Modalità di Configurazione

Gerarchia (priorità decrescente):

```
1. ENV VAR      (OLLAMA_HOST, GIAS_SERVER_URL)
2. CLI ARG      (--ollama-host, --gias-server-url)
3. CONFIG FILE  (ollama_host, gias_server_url nei JSON)
4. DEFAULT      (localhost, http://localhost:5005)
```

### Esempi

**Locale (default):**
```bash
python3 scripts/compare_models.py
```

**Ollama remoto:**
```bash
python3 scripts/compare_models.py --ollama-host 192.168.1.100
```

**Via env var:**
```bash
OLLAMA_HOST=gpu-server.local \
python3 scripts/compare_models.py
```

**Configurazione completa:**
```bash
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --gias-server-url http://192.168.1.10:5005 \
    --baseline llama3.2 \
    --candidate falcon
```

## Output

### Struttura Directory

```
runtime/comparison/
└── YYYY-MM-DD_HH-MM-SS/
    ├── config.json               # Configurazione usata
    ├── llama3.2_results.json    # Risultati raw baseline
    ├── falcon_results.json      # Risultati raw candidate
    ├── comparison.json          # Metriche comparative
    └── report.md                # Report leggibile
```

### Symlink Latest

```bash
# Sempre punta all'ultima esecuzione
cat runtime/comparison/latest/report.md
```

## Metriche Calcolate

Il sistema calcola automaticamente:

1. **Intent Accuracy** (%)
   - Da sezioni 2 e 14
   - % di intent classificati correttamente
   - CRITICO per qualità

2. **Avg Response Time** (secondi)
   - Da sezione 3
   - Tempo medio di risposta
   - CRITICO per performance

3. **Slot Extraction F1** (0-1)
   - Da sezioni 12 e 22
   - Precisione estrazione entità
   - IMPORTANTE per robustezza

4. **Test Pass Rate** (%)
   - Aggregato da tutte le sezioni
   - Stabilità generale

## Verdetto Automatico

Il sistema genera uno dei seguenti verdetti:

- **`candidate_better`** - Modello candidate raccomandato
- **`baseline_better`** - Modello baseline raccomandato
- **`equivalent`** - Prestazioni equivalenti

### Logica Decisionale

```
SE accuracy_delta >= +2% E speed_delta <= +1.0s
  → candidate_better

SE accuracy_delta < -5%
  → baseline_better

SE |accuracy_delta| < 2% E speed_delta > +1.0s
  → baseline_better (più veloce)

ALTRIMENTI
  → equivalent o valutazione pass_rate
```

## Prerequisiti

### Software

- Python 3.8+
- Ollama in esecuzione
- Modelli LLM disponibili:
  ```bash
  ollama list
  # Deve mostrare: llama3.2:3b, falcon-gias:latest, ecc.
  ```

### Networking (per setup remoti)

- Ollama API esposta su porta 11434
- GiAs server API esposta su porta 5005
- Firewall configurato per permettere connessioni

## Verifica Setup

### Pre-flight Check

```bash
# 1. Ollama raggiungibile?
curl http://localhost:11434/api/tags

# 2. GiAs server non già in esecuzione?
scripts/server.sh status

# 3. Test suite modificata?
python3 tests/test_server.py --help | grep sections
# Deve mostrare: --sections SECTIONS
```

### Test Configurazione

```bash
# Verifica che i config JSON siano validi
python3 -c "import json; print(json.load(open('scripts/compare_models_config.json'))['server'])"

# Output atteso:
# {'start_timeout': 60, 'health_check_retries': 10, ...}
```

## Troubleshooting

### Errore: "Impossibile avviare server"

**Causa:** Server già in esecuzione o Ollama non disponibile

**Soluzione:**
```bash
scripts/server.sh stop
ollama list  # Verifica che Ollama funzioni
python3 scripts/compare_models.py ...
```

### Errore: "Timeout: server non disponibile"

**Causa:** Server avviato ma non risponde

**Soluzione:**
```bash
# Controlla log
tail -f runtime/logs/api-server.log

# Verifica env vars
echo $OLLAMA_HOST
echo $GIAS_SERVER_URL
```

### Test Falliscono

**Causa:** Modello non performante o bug nel backend

**Soluzione:**
```bash
# Esegui test manuale
python3 tests/test_server.py --sections "2" -v

# Controlla risposta diretta
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"ciao","metadata":{}}'
```

### Ollama Remoto Non Risponde

**Causa:** Networking o configurazione firewall

**Soluzione:**
```bash
# Test connettività
curl http://192.168.1.100:11434/api/tags

# Verifica firewall sul server remoto
# (su macchina remota)
sudo ufw allow 11434/tcp
```

## Esempi Avanzati

### Test con Modelli Custom

```bash
python3 scripts/compare_models.py \
    --baseline velvet \
    --candidate mistral-nemo \
    --config scripts/compare_models_config.json
```

### Setup Lab con Config Permanente

Modifica `scripts/compare_models_config.json`:

```json
{
  "models": {
    "baseline": "llama3.2",
    "candidate": "falcon"
  },
  "server": {
    "ollama_host": "gpu-server.lab.local",
    "gias_server_url": "http://localhost:5005"
  }
}
```

Poi esegui semplicemente:

```bash
python3 scripts/compare_models.py
```

### Batch Testing

```bash
#!/bin/bash
# test_all_models.sh

MODELS=("llama3.2" "falcon" "mistral-nemo" "velvet")
BASELINE="llama3.2"

for candidate in "${MODELS[@]}"; do
  if [ "$candidate" != "$BASELINE" ]; then
    echo "Testing $BASELINE vs $candidate..."
    python3 scripts/compare_models.py \
      --baseline $BASELINE \
      --candidate $candidate \
      --config scripts/compare_models_quick.json
  fi
done
```

### Rigenerazione Report

Se hai già i risultati e vuoi solo rigenerare il report:

```bash
python3 scripts/compare_models.py \
    --skip-tests \
    --results-dir runtime/comparison/2026-01-31_18-30-45
```

## Performance Tips

### Ridurre Tempo Esecuzione

1. **Usa quick config:** 6-8 min invece di 16-24 min
2. **Test su localhost:** Evita overhead network
3. **Ollama in memoria:** Pre-carica modelli

### Ottimizzare Accuratezza

1. **Test completo:** Usa 8 sezioni non 3
2. **Warm-up:** Esegui 1-2 richieste prima dei test
3. **Statistiche:** Esegui comparazione 3 volte e fai media

## Riferimenti

- **Documentazione server:** `scripts/SERVER_CONFIG.md`
- **Test suite:** `tests/test_server.py`
- **Backend config:** `configs/config.json`
- **Server management:** `scripts/server.sh`

## Supporto

Per problemi o domande:

1. Controlla `scripts/SERVER_CONFIG.md` per dettagli configurazione
2. Verifica log in `runtime/logs/api-server.log`
3. Esegui test manuali con `curl` per isolare il problema
4. Verifica che Ollama sia aggiornato: `ollama --version`
