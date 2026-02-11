# 🤖 Configurazione Modelli GiAs-llm

Il chatbot GiAs-llm supporta due modelli LLM con caratteristiche diverse per adattarsi a diverse esigenze operative.

## 📋 Modelli Disponibili

### Almawave Velvet (Default) ⭐🇪🇺
- **Nome**: `Almawave/Velvet:latest`
- **Parametri**: 14B
- **Accuratezza**: 95% sui test (nativo italiano)
- **Velocità**: ~4.2s tempo risposta medio
- **VRAM**: 8.5GB
- **Lingue**: Italiano, Inglese, Spagnolo, Portoghese, Tedesco, Francese
- **Vantaggi**: GDPR compliant, nativo europeo, multilingue
- **Raccomandato per**: Produzione italiana/europea, conformità normativa

### Mistral-Nemo
- **Nome**: `mistral-nemo:latest`
- **Parametri**: 12.2B
- **Accuratezza**: 100% sui test di intent classification
- **Velocità**: ~3.8s tempo risposta medio
- **VRAM**: 5.1GB
- **Raccomandato per**: Fallback, test comparativi

### LLaMA 3.1 8B
- **Nome**: `llama3.1:8b`
- **Parametri**: 8B
- **Accuratezza**: 60% sui test di intent classification
- **Velocità**: ~1.9s tempo risposta medio (più veloce)
- **VRAM**: 5.4GB
- **Raccomandato per**: Testing, volumi elevati, prototipazione rapida

## 🔧 Configurazione

### 1. Via Variabile Ambiente (Raccomandato)
```bash
# Usa Almawave Velvet (default, nativo italiano)
export GIAS_LLM_MODEL=velvet

# Usa Mistral-Nemo
export GIAS_LLM_MODEL=mistral-nemo

# Usa LLaMA 3.1
export GIAS_LLM_MODEL=llama3.1

# Avvia il server
./start_server.sh
```

### 2. Via Model Manager
```bash
# Mostra configurazione corrente
python3 model_manager.py config

# Lista modelli disponibili
python3 model_manager.py list

# Cambia modello
python3 model_manager.py use velvet
python3 model_manager.py use mistral-nemo
python3 model_manager.py use llama3.1

# Test rapido modello corrente
python3 model_manager.py test
```

### 3. Via Codice Python
```python
from config import AppConfig, set_model

# Cambia modello runtime
set_model("llama3.1")

# Usa il nuovo modello
from llm.client import LLMClient
client = LLMClient()  # Userà il modello configurato
```

## ⚙️ Configurazioni Avanzate

### Variabili Ambiente Supportate
```bash
# Modello da utilizzare
export GIAS_LLM_MODEL=mistral-nemo  # mistral-nemo|llama3.1

# Temperature (0.0-1.0)
export GIAS_CLASSIFICATION_TEMP=0.1   # Per classificazione intent
export GIAS_RESPONSE_TEMP=0.3         # Per generazione risposte

# Timeout e limiti
export GIAS_LLM_TIMEOUT=30            # Timeout query LLM (secondi)
export GIAS_MAX_TOKENS=2000           # Massimo token per risposta
export OLLAMA_KEEP_ALIVE=-1           # Mantieni modello in memoria

# Logging
export GIAS_LOG_LEVEL=INFO            # DEBUG|INFO|WARNING|ERROR
```

## 🚀 Avvio Automatico

Lo script `start_server.sh` è stato modificato per:

1. **Rilevare automaticamente** il modello configurato via `GIAS_LLM_MODEL`
2. **Pre-caricare il modello** in memoria con `keep_alive=-1`
3. **Mostrare informazioni** sul modello utilizzato

Esempio di output:
```
🤖 Pre-caricamento modello LLM...
   🔧 Modello configurato: mistral-nemo (mistral-nemo:latest)
   ✅ Modello mistral-nemo:latest caricato e mantenuto in memoria
```

## 📊 Benchmark e Confronto

Il sistema include strumenti di benchmark per confrontare i modelli:

```bash
# Benchmark completo (molti test)
python3 benchmark_models.py

# Quick test (5 test rapidi)
python3 quick_benchmark.py

# Test singolo modello corrente
python3 model_manager.py test
```

### Risultati Benchmark

| Modello | Accuratezza | Velocità | Memoria | Lingue | Uso Raccomandato |
|---------|-------------|----------|---------|--------|-------------------|
| **Almawave Velvet** | 🟢 95% | 🟡 4.2s | 8.5GB | 🇮🇹🇪🇸🇩🇪🇫🇷🇵🇹🇬🇧 | **Produzione EU/IT** |
| **Mistral-Nemo** | 🟢 100% | 🟢 3.8s | 5.1GB | 🇬🇧🇫🇷 | Testing/Fallback |
| **LLaMA 3.1** | 🟡 60% | 🟢 1.9s | 5.4GB | 🇬🇧 | Sviluppo/Volume |

## 🎯 Raccomandazioni d'Uso

### Almawave Velvet (Default) ✅🇪🇺
- **Operatori ASL in produzione**: LLM nativo italiano con terminologia veterinaria
- **Conformità GDPR**: Architettura europea, compliance normativa
- **Contesto multilingue**: Supporto nativo per lingue europee
- **Enti pubblici italiani**: Progettato per il mercato italiano/europeo

### Mistral-Nemo 🔄
- **Testing comparativo**: Per verificare performance vs Velvet
- **Fallback**: Se Velvet non è disponibile
- **Benchmark**: Per confronti di accuratezza

### LLaMA 3.1 ⚡
- **Sviluppo e testing**: Feedback rapido durante lo sviluppo
- **Volumi elevati**: Quando servono molte query veloci
- **Prototipazione**: Sviluppo rapido con risorse limitate

## 🔄 Cambio Modello Runtime

```bash
# Produzione (default)
export GIAS_LLM_MODEL=velvet && python3 app/api.py

# Durante lo sviluppo
export GIAS_LLM_MODEL=llama3.1 && python3 app/api.py

# Per testing comparativo
export GIAS_LLM_MODEL=mistral-nemo && python3 app/api.py

# Verifica configurazione
python3 model_manager.py config
```

## 🛠️ Troubleshooting

### Modello Non Trovato
```bash
ollama list  # Verifica modelli installati
ollama pull Almawave/Velvet:latest  # Scarica Velvet se mancante
ollama pull mistral-nemo:latest  # Scarica se mancante
ollama pull llama3.1:8b
```

### Memoria Insufficiente
- Almawave Velvet: Richiede ~8.5GB VRAM (modello più grande)
- Mistral-Nemo: Richiede ~5.1GB VRAM
- LLaMA 3.1: Richiede ~5.4GB VRAM
- Usa `ollama ps` per verificare utilizzo memoria

### Performance Lente
```bash
# Verifica che il modello sia pre-caricato
curl -s http://localhost:11434/api/ps | jq .

# Pre-carica manualmente
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "Almawave/Velvet:latest", "prompt": "ready", "keep_alive": -1}'
```