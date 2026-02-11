# Piano Fine-Tuning: Llama 3.2 3B e Falcon-GIAS

---

## 1. Analisi dello stato attuale — Dove il modello LLM interviene

Il sistema usa il modello LLM in **4 punti** distinti:

| # | Componente | File | Compito | Temp | JSON | Timeout |
|---|-----------|------|---------|------|------|---------|
| 1 | **Router** | `router.py:386` | Intent classification + slot extraction | 0.1 | Sì | 60s |
| 2 | **Response Generator** | `response_node.py:166` | Generazione risposta finale in italiano | 0.3 | No | 60s |
| 3 | **Fallback Recovery** | `fallback_recovery.py:271` | Scoring semantico intent (fase 2 fallback) | 0.1 | No | 5s |
| 4 | **LLM Reranker** | `llm_reranker.py:207` | Riordinamento risultati ricerca semantica | 0.1 | Sì | 5s |

Il **dialogue_manager** è rule-based (nessun LLM). L'estrazione di entità (slot) è fatta **interamente via regex** in `router.py` (21 pattern compilati).

---

## 2. Valutazione: Il fine-tuning è utile?

### 2.1 Mappa costi/benefici per punto di chiamata

| Punto LLM | Accuratezza attuale (llama3.2:3b) | Impatto errore | Beneficio fine-tuning | Priorità |
|-----------|-----------------------------------|----------------|----------------------|----------|
| **Router (classification)** | 85% (da config.py) | **CRITICO** — intent sbagliato = risposta inutile | **ALTO** — 19 intent fissi, dominio chiuso | ⭐⭐⭐ |
| **Response Generator** | Qualitativa, non misurata | MEDIO — risposta brutta ma dati corretti | **MEDIO** — formato specifico, terminologia veterinaria | ⭐⭐ |
| **Fallback Recovery** | Non misurata | BASSO — è già un fallback del fallback | **BASSO** — usato solo quando heuristics falliscono | ⭐ |
| **LLM Reranker** | Non misurata | BASSO — ordine subottimale ma risultati presenti | **BASSO** — solo per `search_piani_by_topic` | ⭐ |

### 2.2 Fattori che riducono l'urgenza del fine-tuning

Il sistema ha **difese profonde** che compensano le debolezze del modello 3B:

1. **Heuristics layer**: 21 pattern regex coprono TUTTI i 19 intent. Per i messaggi comuni (saluti, "piani in ritardo", "stabilimenti a rischio"), il router **non chiama mai il LLM** — usa regex dirette con confidence 0.95.

2. **Pre-parsing slot**: Tutti gli slot (piano_code, asl, topic, num_registrazione, partita_iva, ragione_sociale, categoria) sono estratti via regex PRIMA della chiamata LLM. Il modello riceve già `SLOT PRE-ESTRATTI: {"piano_code": "A1"}` nel prompt.

3. **JSON parsing a 3 stadi**: Se il modello genera JSON malformato, c'è: parse diretto → estrazione da blocco ` ```json` → estrazione bracket bilanciati.

4. **Validazione post-LLM**: Intent validato contro `VALID_INTENTS`, slot keys validati contro `VALID_SLOT_KEYS`. Output invalido → fallback.

5. **Fallback recovery a 3 fasi**: keyword → LLM → menu categorie. Anche se il router fallisce, l'utente raggiunge il risultato.

6. **Intent cache**: Classificazioni identiche servite da cache (TTL 3600s), riducendo le chiamate LLM del ~60-70%.

### 2.3 Dove il 3B effettivamente fallisce

Nonostante le difese, il modello 3B ha problemi reali quando:

1. **Ambiguità semantica tra intent simili**: Confonde `ask_risk_based_priority` (stabilimenti) con `ask_top_risk_activities` (tipologie attività). Confonde `ask_delayed_plans` (lista tutti) con `check_if_plan_delayed` (verifica uno). Il prompt ha regole di disambiguazione esplicite, ma il 3B le ignora nel ~15% dei casi.

2. **Messaggi atipici che aggirano le heuristics**: "come mi organizzo oggi?" (dovrebbe → `ask_priority_establishment`), "problemi nelle macellerie?" (dovrebbe → `ask_risk_based_priority` o `analyze_nc_by_category`). Le heuristics non matchano; il LLM deve decidere da solo.

3. **Formato risposta instabile**: Il 3B a volte aggiunge testo prima/dopo il JSON, o usa chiavi alternative ("tipo" invece di "intent"). Il parser a 3 stadi compensa, ma rallenta.

4. **Response generation troppo verbosa**: Il modello 3B produce risposte prolisse, ripetitive, e a volte inventa informazioni non presenti nei dati forniti (allucinazione). Per risposte da dati strutturati (tabelle, elenchi), questo è problematico.

### 2.4 Verdetto

**Sì, il fine-tuning è utile**, ma con priorità selettiva:

- **TASK 1 — Intent Classification**: Beneficio alto, dataset facile da costruire, miglioramento misurabile. **Procedere.**
- **TASK 2 — Structured Response**: Beneficio medio, richiede dataset più complesso. **Procedere come seconda fase.**
- **TASK 3 — Fallback/Reranker**: Beneficio marginale rispetto al costo. **Non procedere** — le difese esistenti sono sufficienti.

---

## 3. Piano Fine-Tuning

### 3.1 Modelli target

| Modello | Dimensione | Uso attuale | Strategia |
|---------|-----------|-------------|-----------|
| **Llama 3.2 3B** | 3B params, 2GB VRAM | Default, 0.8s/query | Fine-tune per classification + response |
| **falcon-gias** | Sconosciuto (da Ollama) | Candidato alternativo | Fine-tune parallelo, poi confronto A/B |

Entrambi i modelli vengono fine-tunati con lo **stesso dataset**, poi confrontati con lo script `compare_models.py` già presente nel progetto.

### 3.2 TASK 1 — Fine-tuning per Intent Classification

#### Obiettivo

Portare l'accuratezza della classificazione dal 85% al 97%+ per llama3.2:3b, con:
- Zero allucinazioni di intent (mai restituire un intent non in `VALID_INTENTS`)
- Formato JSON rigoroso al primo tentativo (eliminare la necessità del parser multi-stadio)
- Disambiguazione perfetta tra le 4 coppie confuse

#### Dataset

**Formato**: JSONL con coppie prompt-completion in formato chat (compatibile Ollama/Unsloth)

```jsonl
{"messages":[{"role":"system","content":"<system_prompt>"},{"role":"user","content":"MESSAGGIO: \"piani in ritardo\"\nMETADATA: {\"asl\":\"AVELLINO\"}\nSLOT PRE-ESTRATTI: {}\nOUTPUT:"},{"role":"assistant","content":"{\"intent\":\"ask_delayed_plans\",\"slots\":{},\"needs_clarification\":false}"}]}
```

**Dimensione target**: 800-1200 esempi, così distribuiti:

| Categoria | Esempi | Note |
|-----------|--------|------|
| **Coppie ambigue** (disambiguazione) | 250 | 4 coppie × ~60 varianti ciascuna |
| **Intent standard** (copertura completa) | 400 | 19 intent × ~20 varianti |
| **Slot extraction** | 150 | Combinazioni intent + slot diversi |
| **needs_clarification** | 100 | Slot mancanti per intent che li richiedono |
| **Edge cases** | 100 | Fuori dominio → fallback, messaggi ambigui, errori ortografici |

#### Coppie ambigue prioritarie (250 esempi)

**Coppia 1: `ask_risk_based_priority` vs `ask_top_risk_activities`**
```
"stabilimenti a rischio" → ask_risk_based_priority
"stabilimenti più rischiosi" → ask_risk_based_priority
"attività più rischiose" → ask_top_risk_activities
"classifica attività per rischio" → ask_top_risk_activities
"rischio maggiore tra gli stabilimenti" → ask_risk_based_priority
"quali tipologie di attività sono più rischiose" → ask_top_risk_activities
```
La regola: "stabilimenti/OSA" → risk_based_priority, "attività/tipologie" → top_risk_activities.

**Coppia 2: `ask_delayed_plans` vs `check_if_plan_delayed`**
```
"piani in ritardo" → ask_delayed_plans
"quali piani sono in ritardo?" → ask_delayed_plans
"il piano A1 è in ritardo?" → check_if_plan_delayed
"ritardo del piano B2" → check_if_plan_delayed
"un piano è in ritardo" → check_if_plan_delayed (needs_clarification: true)
"controlla ritardi" → ask_delayed_plans
```
La regola: codice piano presente/implicito → check_if_plan_delayed, lista generica → ask_delayed_plans.

**Coppia 3: `ask_piano_description` vs `ask_piano_generic` vs `ask_piano_stabilimenti`**
```
"di cosa tratta il piano A1" → ask_piano_description
"piano A1" → ask_piano_generic
"stabilimenti piano A1" → ask_piano_stabilimenti
"cos'è il piano B2" → ask_piano_description
"info piano A1" → ask_piano_generic
"dove si applica il piano C3" → ask_piano_stabilimenti
```

**Coppia 4: `ask_priority_establishment` vs `ask_suggest_controls`**
```
"chi devo controllare per primo" → ask_priority_establishment
"stabilimenti mai controllati" → ask_suggest_controls
"priorità controlli" → ask_priority_establishment
"suggerisci controlli" → ask_suggest_controls
"cosa devo fare oggi" → ask_priority_establishment
"stabilimenti da ispezionare" → ask_suggest_controls
```

#### Generazione del dataset

Strategia ibrida:

1. **Seed manuale** (200 esempi): Dalle `INTENT_TESTS_FULL` (28 test) + `TRUE_INTENT_TESTS` (30+ test) + `CLARIFICATION_TESTS` (9 test) + esempi dal registry `intent_metadata.py` (~3 per intent × 19). Totale seed: ~120 esempi verificati.

2. **Augmentation programmatica** (400 esempi):
   - Variazioni linguistiche: sinonimi, forme colloquiali, errori ortografici comuni
   - Variazioni di slot: diversi codici piano (A1-A45, B1-B50, C1-C10), ASL (NA1-3, AV1, CE1-2, SA1-3, BN1), topic vari
   - Template con permutazioni: "SLOT + INTENT_PHRASE", "INTENT_PHRASE + SLOT", "FILLER + INTENT_PHRASE"

3. **Augmentation con LLM grande** (400 esempi): Usare un modello più capace (llama3.1:8b o Velvet 14B — già disponibili nel sistema) per generare varianti, poi validarle manualmente/automaticamente.

4. **Hard negatives** (100 esempi): Messaggi fuori dominio che superficialmente assomigliano a intent validi:
   ```
   "il piano del comune per i parcheggi" → fallback (non è un piano di monitoraggio)
   "rischio terremoto" → fallback (non è rischio NC)
   "controlla la posta" → fallback
   ```

#### Script di generazione

Creare `scripts/generate_training_data.py`:

```python
# Input:
#   - INTENT_TESTS_FULL da test_server.py
#   - TRUE_INTENT_TESTS da test_server.py
#   - INTENT_REGISTRY da intent_metadata.py (examples, keywords)
#   - CLASSIFICATION_SYSTEM_PROMPT da router.py
#
# Output:
#   - data/training/classification_train.jsonl (80%)
#   - data/training/classification_val.jsonl (20%)
#
# Pipeline:
#   1. Raccogliere seed da tutte le fonti
#   2. Augment con template
#   3. Augment con LLM (opzionale, richiede modello grande attivo)
#   4. Deduplicare
#   5. Validare formato JSON
#   6. Split train/val stratificato per intent
```

#### Training

**Metodo**: LoRA (Low-Rank Adaptation) — non full fine-tune

**Tool**: [Unsloth](https://github.com/unslothai/unsloth) (supporta Llama 3.2, 2x più veloce, 60% meno memoria)

**Iperparametri consigliati per classificazione**:

| Parametro | Valore | Motivazione |
|-----------|--------|-------------|
| LoRA rank | 16 | Sufficiente per 19 classi, veloce |
| LoRA alpha | 32 | 2× rank, standard |
| LoRA target | q_proj, k_proj, v_proj, o_proj | Attention layers |
| Learning rate | 2e-4 | Standard LoRA |
| Epochs | 3-5 | Monitorare val loss, early stop |
| Batch size | 4 (gradient accumulation 4 = effective 16) | Per GPU 8-16GB |
| Max seq length | 512 | Il prompt classification è ~400 token |
| Weight decay | 0.01 | Regolarizzazione leggera |
| Warmup ratio | 0.03 | Standard |

**Requisiti HW**: GPU con 8GB+ VRAM (RTX 3060, 4060, T4, o superiore). Con Unsloth + LoRA, il training di 1000 esempi su 3B richiede ~20 minuti su RTX 4060.

**Alternativa senza GPU**: QLoRA con 4-bit quantizzazione, gira su 6GB VRAM.

#### Conversione per Ollama

Dopo il training con Unsloth:

```bash
# 1. Merge LoRA weights nel modello base
python merge_lora.py --base llama3.2:3b --lora output/lora_model --output output/merged

# 2. Esportare in GGUF (formato Ollama)
python -m llama_cpp.convert --outtype q4_K_M output/merged output/llama32-gias-classification.gguf

# 3. Creare Modelfile per Ollama
cat > Modelfile.classification << 'EOF'
FROM ./llama32-gias-classification.gguf
PARAMETER temperature 0.1
PARAMETER num_predict 200
PARAMETER stop "</s>"
SYSTEM """Classificatore intent veterinario. Rispondi SOLO con JSON valido.
...(CLASSIFICATION_SYSTEM_PROMPT)..."""
EOF

# 4. Importare in Ollama
ollama create llama32-gias:classification -f Modelfile.classification

# 5. Testare
ollama run llama32-gias:classification "MESSAGGIO: \"piani in ritardo\"\nMETADATA: {}\nSLOT PRE-ESTRATTI: {}\nOUTPUT:"
```

Per falcon-gias, procedura identica con modello base diverso.

#### Valutazione

Usare lo script `compare_models.py` già presente:

```bash
# Confronto modello base vs fine-tuned
python3 scripts/compare_models.py \
    --baseline llama3.2 \
    --candidate llama32-gias-classification

# Sezioni critiche (da compare_models_config.json):
# Section 2: Intent Classification (weight 3.0)
# Section 14: TRUE Intent Classification (weight 3.0)
# Section 12: Clarification Rules (weight 2.5)
# Section 22: Parse Endpoint (weight 2.5)
```

**Metriche target**:

| Metrica | Base (llama3.2:3b) | Target fine-tuned |
|---------|-------------------|-------------------|
| Accuracy intent (Section 2) | 85% | **≥97%** |
| TRUE intent (Section 14) | ~85% | **≥97%** |
| Clarification (Section 12) | Non misurata | **≥95%** |
| Slot extraction (Section 22) | Non misurata | **≥95%** |
| Tempo medio risposta | 0.8s | **≤1.0s** (non deve peggiorare) |
| JSON valido al primo parse | ~80% | **≥98%** |

---

### 3.3 TASK 2 — Fine-tuning per Response Generation

#### Obiettivo

Insegnare al modello a generare risposte:
- Fedeli ai dati (zero allucinazioni — non inventare punteggi, nomi, numeri)
- Strutturate (markdown con section header, liste, campi)
- Concise (eliminare ripetizioni e testo di riempimento)
- In terminologia veterinaria ASL corretta

#### Dataset

**Formato**: JSONL con coppie (contesto dati + domanda) → risposta ideale

```jsonl
{"messages":[{"role":"system","content":"<RESPONSE_SYSTEM_PROMPT>"},{"role":"user","content":"**CONTESTO:**\nL'utente ha richiesto: Piani in ritardo\n\n**DOMANDA ORIGINALE:**\n\"piani in ritardo\"\n\n**TIPO DI ANALISI:**\nask_delayed_plans\n\n**RISULTATI OTTENUTI:**\n{...dati reali...}"},{"role":"assistant","content":"**📊 Piani in Ritardo — ASL Avellino**\n\n...risposta ideale formattata..."}]}
```

**Dimensione target**: 300-500 esempi

| Categoria | Esempi | Note |
|-----------|--------|------|
| Risposte da dati reali | 200 | Per ogni intent con tool_output, catturare input/output reale e scrivere risposta ideale |
| Risposte con zero dati | 50 | "Nessun risultato trovato" — risposta corretta, non inventare |
| Risposte two-phase (sommario) | 50 | Sommari concisi per risultati >20 item |
| Risposte con filtri | 50 | "Filtrato per comune X: 5 su 87 risultati" |
| Hard negatives | 50 | Dati che contengono numeri — verificare che il modello non inventi altri numeri |

#### Generazione

1. **Cattura log reali**: Modificare temporaneamente `response_node.py` per loggare il prompt completo e la risposta generata. Raccogliere 200+ interazioni reali.

2. **Riscrittura umana**: Per ogni risposta catturata, riscrivere la versione ideale: concisa, fedele, ben formattata.

3. **Varianti sintetiche**: Usare gli stessi dati con domande diverse.

#### Training

Stessi iperparametri di TASK 1, ma:
- **Max seq length**: 2048 (le risposte sono più lunghe)
- **Epochs**: 2-3 (rischio overfitting su risposte formulaiche)
- **LoRA rank**: 32 (task più complesso)

#### Modello unico o separato?

**Opzione A**: Un unico modello fine-tunato per entrambi i task (classification + response).
- Pro: Un solo modello da gestire in produzione
- Contro: Task molto diversi, rischio di degradazione su uno dei due

**Opzione B**: Due modelli LoRA separati sullo stesso base, caricati dinamicamente.
- Pro: Ottimizzazione indipendente
- Contro: Due modelli in VRAM (o swap costoso)

**Raccomandazione**: **Opzione A** — singolo modello. Il fine-tuning su dati di classification (JSON rigoroso) e response (testo formattato) non conflittua perché i system prompt sono diversi. Il modello impara a "switchare modalità" in base al system prompt. Questo è il pattern standard per modelli instruction-tuned.

---

## 4. Pipeline operativa

### Fase 1: Preparazione dataset (1-2 settimane)

```
Settimana 1:
├── Creare scripts/generate_training_data.py
├── Raccogliere seed da test_server.py + intent_metadata.py
├── Generare augmentation programmatica
├── Validare e deduplicare
└── Output: data/training/classification_{train,val}.jsonl

Settimana 2:
├── Attivare logging risposte in response_node.py
├── Raccogliere 200+ interazioni reali
├── Riscrivere risposte ideali (manuale)
└── Output: data/training/response_{train,val}.jsonl
```

### Fase 2: Training (2-3 giorni)

```
Giorno 1:
├── Setup Unsloth + dipendenze
├── Training classification (Llama 3.2 3B) — ~20min
├── Training classification (Falcon-GIAS) — ~20min
├── Valutazione con compare_models.py
└── Se accuracy <95%: analizzare errori, aggiungere esempi, ri-trainare

Giorno 2:
├── Training response (Llama 3.2 3B) — ~40min (seq più lunghe)
├── Training response (Falcon-GIAS) — ~40min
├── Training combinato (classification + response) — ~60min
└── Valutazione qualitativa risposte

Giorno 3:
├── Confronto A/B: llama32-gias vs falcon-gias vs baseline
├── Selezione modello migliore
├── Conversione GGUF + Ollama import
└── Test end-to-end su sistema completo
```

### Fase 3: Integrazione (1 giorno)

```
├── Aggiungere modello a AVAILABLE_MODELS in configs/config.py
├── Aggiungere a start_server.sh (opzione menu)
├── Test con scripts/server.sh test
├── Confronto finale con compare_models.py (tutte le sezioni)
└── Se supera thresholds: rendere default
```

### Fase 4: Monitoraggio (continuo)

```
├── Loggare accuracy classificazione in produzione
├── Raccogliere errori di classificazione come nuovi esempi di training
├── Re-training periodico (ogni 2-4 settimane) con nuovi dati
└── Drift detection: se accuracy scende sotto 93%, trigger re-training
```

---

## 5. Struttura file da creare

```
GiAs-llm/
├── data/training/
│   ├── classification_train.jsonl     # Training classification
│   ├── classification_val.jsonl       # Validation classification
│   ├── response_train.jsonl           # Training response generation
│   ├── response_val.jsonl             # Validation response generation
│   └── combined_train.jsonl           # Dataset combinato
├── scripts/
│   ├── generate_training_data.py      # Generazione dataset da fonti esistenti
│   ├── train_classification.py        # Script training (Unsloth/LoRA)
│   ├── train_response.py              # Script training response
│   ├── evaluate_model.py              # Valutazione modello fine-tuned
│   ├── export_ollama.py               # Conversione GGUF + Modelfile
│   └── Modelfile.gias-classification  # Template Ollama
└── docs/
    └── FINE_TUNING_PLAN.md            # Questo documento
```

---

## 6. Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| Overfitting su pochi esempi | Media | Alto — generalizza male su input nuovi | Augmentation aggressiva, val set separato, early stopping |
| Regressione su intent "facili" | Bassa | Medio — le heuristics comunque matchano | Test completo con INTENT_TESTS_FULL prima del deploy |
| Dataset sbilanciato | Alta | Medio — intent rari sotto-rappresentati | Oversampling intent rari, stratified split |
| Allucinazione response peggiorata | Media | Alto — dati inventati in contesto ASL | Hard negatives nel dataset, validazione output |
| Tempo di risposta degradato | Bassa | Medio — LoRA aggiunge ~0ms su GPU | Benchmark latenza nel compare_models.py |
| Incompatibilità GGUF | Bassa | Alto — modello non caricabile | Testare conversione prima del training completo |

---

## 7. Riepilogo decisioni

| Decisione | Scelta | Motivazione |
|-----------|--------|-------------|
| Fine-tune sì/no | **Sì** per classification e response | 85% accuracy non sufficiente per intent ambigui |
| Metodo | **LoRA** (non full fine-tune) | 10x meno risorse, risultati comparabili per 3B |
| Tool | **Unsloth** | Supporto nativo Llama 3.2, 2x velocità, gratis |
| Modello unico/separato | **Unico** | Classification + response non conflittuano |
| Fallback/Reranker fine-tune | **No** | Difese esistenti sufficienti, ROI basso |
| Entità/slot fine-tune | **No** | Regex extraction funziona al 100% |
| Dataset size | **800-1200** (classification) + **300-500** (response) | Standard per LoRA su task dominio-specifico |
