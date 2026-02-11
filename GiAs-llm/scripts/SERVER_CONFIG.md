# Configurazione Server per Model Comparison

Il sistema di comparazione modelli supporta configurazione flessibile sia per Ollama che per il server GiAs-llm, permettendo setup locali, remoti o ibridi.

## Parametri Configurabili

Il sistema permette di configurare due endpoint:

1. **`ollama_host`** - Host dove è in esecuzione Ollama (default: `localhost`)
2. **`gias_server_url`** - URL del server GiAs-llm (default: `http://localhost:5005`)

---

## Metodi di Configurazione (in ordine di priorità)

### 1. Variabile d'Ambiente (Priorità MASSIMA)

**Per Ollama:**

```bash
OLLAMA_HOST=192.168.1.100 python3 scripts/compare_models.py
```

**Per GiAs Server:**

```bash
GIAS_SERVER_URL=http://192.168.1.10:5005 python3 scripts/compare_models.py
```

**Entrambi:**

```bash
OLLAMA_HOST=192.168.1.100 \
GIAS_SERVER_URL=http://192.168.1.10:5005 \
python3 scripts/compare_models.py \
    --baseline llama3.2 \
    --candidate falcon
```

### 2. Argomento CLI (Priorità ALTA)

**Per Ollama:**

```bash
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --baseline llama3.2 \
    --candidate falcon
```

**Per GiAs Server:**

```bash
python3 scripts/compare_models.py \
    --gias-server-url http://192.168.1.10:5005 \
    --baseline llama3.2 \
    --candidate falcon
```

**Entrambi:**

```bash
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --gias-server-url http://192.168.1.10:5005 \
    --baseline llama3.2 \
    --candidate falcon
```

### 3. File di Configurazione JSON (Priorità MEDIA)

Modifica `scripts/compare_models_config.json` o `scripts/compare_models_quick.json`:

```json
{
  "server": {
    "ollama_host": "192.168.1.100",
    "gias_server_url": "http://192.168.1.10:5005",
    "start_timeout": 60,
    "health_check_retries": 10,
    "health_check_interval": 3,
    "shutdown_grace_period": 5
  }
}
```

### 4. Default (Priorità BASSA)

Se non specificato, usa i default:
- **Ollama:** `localhost`
- **GiAs Server:** `http://localhost:5005`

## Priorità di Risoluzione

La priorità di risoluzione è la stessa per entrambi i parametri:

```
ENV VAR > CLI ARG > CONFIG FILE > DEFAULT
```

**Esempio per Ollama Host:**
- Default: `localhost`
- Config file: `"ollama_host": "config.example.com"`
- CLI arg: `--ollama-host cli.example.com`
- Env var: `OLLAMA_HOST=env.example.com`

**Risultato:** `env.example.com` (env var vince)

**Esempio per GiAs Server URL:**
- Default: `http://localhost:5005`
- Config file: `"gias_server_url": "http://config.example.com:5005"`
- CLI arg: `--gias-server-url http://cli.example.com:5005`
- Env var: `GIAS_SERVER_URL=http://env.example.com:5005`

**Risultato:** `http://env.example.com:5005` (env var vince)

## Differenza tra Ollama Host e GiAs Server URL

### Ollama Host (`ollama_host`)

- **Cosa configura:** L'hostname/IP dove è in esecuzione il servizio Ollama
- **Porta:** Implicita (11434, porta standard di Ollama)
- **Formato:** Solo hostname o IP (es. `192.168.1.100` o `gpu-server.local`)
- **Uso:** Il backend GiAs-llm si connette a questo host per usare i modelli LLM

### GiAs Server URL (`gias_server_url`)

- **Cosa configura:** L'URL completo del server GiAs-llm
- **Porta:** Esplicita nell'URL (di solito 5005)
- **Formato:** URL completo (es. `http://192.168.1.10:5005`)
- **Uso:** Lo script compare_models.py si connette a questo URL per:
  - Fare health check
  - Eseguire richieste di test
  - Verificare lo stato del sistema

### Modalità Operative

#### Modalità 1: Tutto Locale (Default)

```bash
# Ollama e GiAs server entrambi su localhost
python3 scripts/compare_models.py
```

Lo script:
1. Avvia il server GiAs-llm su localhost:5005 (via `scripts/server.sh start`)
2. Il server si connette a Ollama su localhost:11434
3. I test si connettono al server su http://localhost:5005

#### Modalità 2: Ollama Remoto, GiAs Locale

```bash
# Ollama su macchina remota con GPU, GiAs locale
python3 scripts/compare_models.py --ollama-host 192.168.1.100
```

Lo script:
1. Avvia il server GiAs-llm su localhost:5005
2. Il server si connette a Ollama su 192.168.1.100:11434
3. I test si connettono al server su http://localhost:5005

#### Modalità 3: GiAs Remoto (Pre-avviato)

```bash
# Server GiAs già in esecuzione su macchina remota
# Non avviare il server, solo eseguire test
python3 scripts/compare_models.py \
    --gias-server-url http://192.168.1.10:5005 \
    --no-start
```

**NOTA:** In questa modalità devi avviare manualmente il server remoto prima.

#### Modalità 4: Tutto Remoto

```bash
# Ollama e GiAs su macchine diverse
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --gias-server-url http://192.168.1.10:5005
```

Lo script:
1. Avvia il server GiAs-llm (configurato per usare Ollama remoto)
2. Il server si connette a Ollama su 192.168.1.100:11434
3. I test si connettono al server su http://192.168.1.10:5005

## Casi d'Uso Avanzati

### Scenario 1: Setup Locale (Default)

```bash
# Tutto su localhost - configurazione più semplice
cd /opt/lang-env/GiAs-llm
python3 scripts/compare_models.py \
    --baseline llama3.2 \
    --candidate falcon
```

**Architettura:**
```
[compare_models.py] → [GiAs Server localhost:5005] → [Ollama localhost:11434]
```

### Scenario 2: Ollama su GPU Server Remoto

```bash
# Ollama su macchina con GPU, GiAs locale
python3 scripts/compare_models.py \
    --ollama-host gpu-server.local \
    --baseline llama3.2 \
    --candidate falcon
```

**Architettura:**
```
[compare_models.py] → [GiAs Server localhost:5005] → [Ollama gpu-server.local:11434]
```

**Vantaggi:** Usa GPU remota mantenendo il controllo locale.

### Scenario 3: Cluster Distribuito

```bash
# Ollama su un server, GiAs su un altro
python3 scripts/compare_models.py \
    --ollama-host gpu-node-1.local \
    --gias-server-url http://app-server.local:5005 \
    --baseline llama3.2 \
    --candidate falcon
```

**Architettura:**
```
[compare_models.py] → [GiAs Server app-server.local:5005] → [Ollama gpu-node-1.local:11434]
```

### Scenario 4: Config Permanente per Lab

Modifica `scripts/compare_models_config.json`:

```json
{
  "server": {
    "ollama_host": "gpu-server.local",
    "gias_server_url": "http://localhost:5005"
  }
}
```

Poi esegui normalmente:

```bash
python3 scripts/compare_models.py --baseline llama3.2 --candidate falcon
```

### Scenario 4: Override Temporaneo

Config file usa `gpu-server.local`, ma per un test vuoi usare localhost:

```bash
python3 scripts/compare_models.py \
    --ollama-host localhost \
    --baseline llama3.2 \
    --candidate falcon
```

## Verifica Configurazione

### Output dello Script

Durante l'esecuzione, lo script stampa TUTTE le configurazioni utilizzate:

```
══════════════════════════════════════════════════════════════════════
COMPARAZIONE MODELLI LLM
Baseline: llama3.2
Candidate: falcon
Sezioni: [2, 3, 4, 12, 14, 18, 19, 22]
Ollama host: 192.168.1.100
GiAs server: http://192.168.1.10:5005
══════════════════════════════════════════════════════════════════════

🚀 Avvio server con modello: llama3.2
   Ollama host: 192.168.1.100
   GiAs server: http://192.168.1.10:5005
⏳ Attendo server... (1/10)
✅ Server pronto (modello: llama3.2:3b (real))

🧪 Esecuzione test suite (sezioni: [2, 3, 4, 12, 14, 18, 19, 22])
```

### Test Manuale Connettività

Prima di eseguire la comparazione, verifica che entrambi i servizi siano raggiungibili:

```bash
# Test 1: Ollama raggiungibile?
curl http://192.168.1.100:11434/api/tags
# Dovresti vedere: {"models":[{"name":"llama3.2:3b",...}]}

# Test 2: GiAs server raggiungibile?
curl http://192.168.1.10:5005/status
# Dovresti vedere: {"status":"ready","model_loaded":true,...}

# Test 3: GiAs può parlare con Ollama?
curl -X POST http://192.168.1.10:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"ciao","metadata":{}}'
# Dovresti vedere: {"intent":{"name":"greet",...},...}
```

## Note Tecniche

### Propagazione delle Configurazioni

Le configurazioni vengono propagate in due punti:

#### 1. All'avvio del Server (`start_server()`)

```python
env = os.environ.copy()
env['GIAS_LLM_MODEL'] = self.model_name  # Modello da usare
env['OLLAMA_HOST'] = self.ollama_host    # Host Ollama
```

Il backend GiAs legge `OLLAMA_HOST` e la usa per connettersi a Ollama.

#### 2. Durante l'esecuzione dei Test (`run_tests()`)

```python
env = os.environ.copy()
env['GIAS_SERVER_URL'] = self.server_url  # URL server per i test
env['OLLAMA_HOST'] = self.ollama_host     # Per informazione/debug
```

I test in `test_server.py` leggono `GIAS_SERVER_URL` per sapere dove connettersi:

```python
SERVER_URL = os.environ.get("GIAS_SERVER_URL", "http://localhost:5005")
WEBHOOK = f"{SERVER_URL}/webhooks/rest/webhook"
```

### Networking

Assicurati che:
1. **Ollama host** sia raggiungibile dalla macchina che esegue `compare_models.py`
2. **Ollama API** sia esposta sulla porta 11434 (default)
3. **Firewall** permetta connessioni alla porta 11434

### Testing Connettività

```bash
# Testa se Ollama è raggiungibile
curl http://192.168.1.100:11434/api/tags

# Dovresti vedere la lista dei modelli
```

## Esempi Completi

### Quick Test con Ollama Remoto

```bash
OLLAMA_HOST=gpu-server.local python3 scripts/compare_models.py \
    --config scripts/compare_models_quick.json
```

### Full Test con Config Custom

```bash
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --baseline llama3.2 \
    --candidate falcon \
    --config scripts/compare_models_config.json \
    --output-dir /tmp/comparison_results
```

### Report da Risultati Esistenti (No Ollama Richiesto)

```bash
python3 scripts/compare_models.py \
    --skip-tests \
    --results-dir runtime/comparison/2026-01-31_18-30-45
```

## Troubleshooting

### Errore: "Impossibile avviare server"

Verifica che:
- Ollama sia in esecuzione sull'host specificato
- I modelli richiesti siano disponibili (`ollama list`)
- L'host sia raggiungibile via rete

### Errore: "Timeout: server non disponibile"

Il server GiAs non risponde. Verifica:
- `scripts/server.sh status`
- Log in `runtime/logs/api-server.log`
- Che `OLLAMA_HOST` sia correttamente propagato

### Debug

Abilita verbose mode per vedere dettagli:

```bash
python3 scripts/compare_models.py \
    --ollama-host 192.168.1.100 \
    --baseline llama3.2 \
    --candidate falcon \
    -v  # ← verbose (se supportato)
```

Oppure controlla i log del server:

```bash
tail -f runtime/logs/api-server.log
```
