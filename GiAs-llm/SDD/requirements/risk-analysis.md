# Risk Analysis

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `predictor_ml/predictor.py`, `tools/risk_tools.py`, `tools/risk_analysis_tools.py`

## Requisiti Funzionali

### RA-01 Predittore ML XGBoost V4
- **Pattern EARS**: DOVE il predittore ML e' configurato (type="ml"), il sistema DEVE caricare il modello XGBoost V4 dal file `production_assets/risk_model_v4.json` e utilizzarlo per predire la probabilita' di non conformita' (NC) per stabilimenti mai controllati, con 6 feature: macroarea_norm, aggregazione_norm, years_never_controlled, asl, linea_attivita, norma.
- **Status**: IMPLEMENTATO

### RA-02 Soglia decisionale
- **Pattern EARS**: Il sistema DEVE utilizzare una soglia decisionale di 0.40 (configurabile via config) per classificare gli stabilimenti: ALTO (score > 0.70), MEDIO (score > 0.40), BASSO (score <= 0.40).
- **Status**: IMPLEMENTATO

### RA-03 Predittore statistico rule-based
- **Pattern EARS**: DOVE il predittore statistico e' configurato (type="statistical"), il sistema DEVE calcolare il punteggio di rischio con la formula Risk Score = P(NC) x Impatto x 100, dove P(NC) = NC totali / controlli e Impatto = NC gravi / controlli, aggregando i dati a livello regionale per linea di attivita'.
- **Status**: IMPLEMENTATO

### RA-04 Configurazione tipo predittore
- **Pattern EARS**: Il sistema DEVE determinare il tipo di predittore con priorita': variabile ambiente GIAS_RISK_PREDICTOR > campo risk_predictor.type in config.json > default "ml".
- **Status**: IMPLEMENTATO

### RA-05 Auto-degradazione senza XGBoost
- **Pattern EARS**: SE la libreria XGBoost non e' installata O il file modello non viene trovato, il sistema DEVE degradare automaticamente al predittore rule-based (fallback), loggando un warning.
- **Status**: IMPLEMENTATO

### RA-06 Fallback su errore predizione
- **Pattern EARS**: SE la predizione ML fallisce con un'eccezione, il sistema DEVE eseguire automaticamente la logica rule-based come fallback e restituire risultati con model_version="rule-based-fallback".
- **Status**: IMPLEMENTATO

### RA-07 Taxonomy map con fallback hardcoded
- **Pattern EARS**: Il sistema DEVE caricare i mapping tassonomici da `mappings/taxonomy_map.json` per normalizzare macroarea, aggregazione, ASL e norma. SE il file non esiste o contiene errori, il sistema DEVE utilizzare mapping hardcoded legacy.
- **Status**: IMPLEMENTATO

### RA-08 Top risk activities
- **Pattern EARS**: QUANDO viene richiesta l'analisi delle linee di attivita' piu' rischiose (tool get_top_risk_activities), il sistema DEVE calcolare i risk scores per tutte le linee, ordinarle per punteggio e restituire le top N con soglie calibrate (alto > 7, medio 3-7, basso < 3 basate su P90=6.6, P75=3.0, P50=0.66).
- **Status**: IMPLEMENTATO

### RA-09 Analisi NC per categoria
- **Pattern EARS**: QUANDO viene richiesta l'analisi NC per categoria (tool analyze_nc_by_category), il sistema DEVE validare la categoria contro VALID_NC_CATEGORIES (11 categorie), calcolare statistiche aggregate (totale controlli, NC gravi/non gravi, stabilimenti coinvolti) e identificare i top 5 stabilimenti critici, con filtro opzionale per ASL.
- **Status**: IMPLEMENTATO

### RA-10 Stabilimenti con piu' sanzioni
- **Pattern EARS**: QUANDO viene richiesta la lista stabilimenti con piu' sanzioni (tool establishments_with_sanctions), il sistema DEVE restituire stabilimenti ordinati per numero totale NC con percentuale NC per controllo, con gravita' visiva (rosso >= 5 NC gravi, arancio 2-4, giallo 0-1).
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### RA-NF01 Normalizzazione ASL bidirezionale
- **Pattern EARS**: Il sistema DEVE normalizzare i codici ASL in due modi: per filtro dati (_normalize_asl_for_filter, restituisce None se non riconosciuto = tutte le ASL) e per feature ML (_normalize_asl_for_ml, restituisce valore originale se non mappato). Supporta 7 ASL campane con alias multipli (es. NA1, NAPOLI 1 -> Napoli 1 Centro).
- **Status**: IMPLEMENTATO

### RA-NF02 Spiegazioni interpretabili
- **Pattern EARS**: DOVE il parametro explain=True, il sistema DEVE generare spiegazioni euristiche per ogni predizione basate su anzianita' stabilimento, tipo attivita', norma di riferimento e zona geografica.
- **Status**: IMPLEMENTATO
- **Note**: SHAP non implementato, usa euristiche semplificate con feature importance hardcoded.
