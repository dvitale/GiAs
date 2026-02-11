# Specifica Agente Predittore ML
**Sistema di Prioritizzazione Basato su Machine Learning**

---

## 🎯 Executive Summary

Questo documento definisce i requisiti di interfacciamento per un **Agente Predittore ML** esterno, progettato per sostituire il modulo `risk_tools.py` con un approccio data science avanzato. L'agente deve essere conforme all'architettura LangGraph esistente e integrarsi senza modifiche strutturali al sistema GiAs-llm.

**Obiettivo**: Predire il rischio di non conformità (NC) per stabilimenti mai controllati, basandosi su:
- Storico NC da dataset OCSE
- Caratteristiche stabilimento (tipologia, localizzazione, anzianità)
- Pattern temporali e territoriali
- Features ingegnerizzate da business logic esistente

**Output**: Lista prioritizzata di stabilimenti con score predittivo e interpretabilità.

---

## 📐 Architettura di Integrazione

### Posizionamento nell'Architettura GiAs-llm

```
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph Orchestrator                     │
│                  orchestrator/graph.py                      │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┬─────────────┐
        ↓                           ↓             ↓
┌───────────────┐  ┌─────────────────────────┐  ┌──────────────┐
│ piano_tools   │  │  priority_tools         │  │ search_tools │
└───────────────┘  └─────────────────────────┘  └──────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ↓                         ↓
         ┌──────────────────┐     ┌─────────────────────┐
         │  risk_tools.py   │     │ PREDICTOR_AGENT     │
         │  (ATTUALE)       │ ──> │ (NUOVO - ML-based)  │
         │  Rule-based      │     │ Predictive model    │
         └──────────────────┘     └─────────────────────┘
                                           │
                              ┌────────────┴────────────┐
                              ↓                         ↓
                   ┌──────────────────┐    ┌──────────────────┐
                   │ ML Model Service │    │ Feature Engineer │
                   │ (Inference)      │    │ (Preprocessing)  │
                   └──────────────────┘    └──────────────────┘
```

### Pattern di Integrazione: Tool as Service

L'agente predittore si integra tramite:

1. **Opzione A - Tool Decorator (Raccomandato)**:
   ```python
   # tools/predictor_tools.py
   from langchain_core.tools import tool

   @tool("ml_risk_predictor")
   def get_ml_risk_prediction(asl: str, piano_code: Optional[str] = None) -> Dict[str, Any]:
       """
       Predice rischio NC per stabilimenti mai controllati usando ML.

       Sostituisce: risk_tools.get_risk_based_priority()
       """
       # Chiamata HTTP al servizio ML esterno
       response = requests.post(
           "http://predictor-service:8000/predict",
           json={"asl": asl, "piano_code": piano_code}
       )
       return response.json()
   ```

2. **Opzione B - Libreria Python Importabile**:
   ```python
   # tools/predictor_tools.py
   from predictor_ml import RiskPredictor

   predictor = RiskPredictor(model_path="/models/risk_model.pkl")

   @tool("ml_risk_predictor")
   def get_ml_risk_prediction(asl: str, piano_code: Optional[str] = None):
       return predictor.predict(asl=asl, piano_code=piano_code)
   ```

3. **Opzione C - Microservizio REST**:
   - Servizio separato (FastAPI/Flask)
   - Comunicazione HTTP/gRPC
   - Scalabilità indipendente

---

## 🔌 Interfaccia di Input

### Funzione Tool: `get_ml_risk_prediction()`

**Firma**:
```python
def get_ml_risk_prediction(
    asl: str,
    piano_code: Optional[str] = None,
    limit: int = 20,
    min_score: float = 0.0,
    explain: bool = True
) -> Dict[str, Any]:
    """
    Predice rischio NC per stabilimenti mai controllati usando modello ML.

    Args:
        asl: Codice ASL (es. "NA1", "SA1", "AVELLINO")
        piano_code: Codice piano opzionale per filtrare attività correlate (es. "A1", "B47")
        limit: Numero massimo stabilimenti da ritornare (default: 20)
        min_score: Score minimo predittivo (0.0-1.0, default: 0.0)
        explain: Se True, include feature importance e spiegazioni (default: True)

    Returns:
        Dict conforme al formato tool LangGraph (vedi sezione Output)
    """
```

### Parametri Dettagliati

#### `asl` (required)
- **Tipo**: `str`
- **Valori**: Codice ASL normalizzato (es. "NA1", "AVELLINO", "SALERNO")
- **Normalizzazione**: Il sistema effettua lookup in `personale_df` per risolvere varianti
- **Validazione**: Deve esistere in dataset `osa_mai_controllati_df`

#### `piano_code` (optional)
- **Tipo**: `Optional[str]`
- **Formato**: Alphanumerico (es. "A1", "B47", "AO24_A")
- **Comportamento**:
  - Se specificato: filtra solo attività correlate al piano (via `controlli_df`)
  - Se `None`: considera tutte le attività con NC storiche

#### `limit` (optional)
- **Tipo**: `int`
- **Default**: 20
- **Range**: 1-100
- **Note**: Per performance, limitare inferenza ML a top-K stabilimenti

#### `min_score` (optional)
- **Tipo**: `float`
- **Range**: 0.0 - 1.0
- **Default**: 0.0
- **Uso**: Filtra stabilimenti con score predittivo < soglia

#### `explain` (optional)
- **Tipo**: `bool`
- **Default**: `True`
- **Uso**: Se True, ritorna feature importance SHAP/LIME per interpretabilità

---

## 📊 Contratto Dati di Input

### Dataset Disponibili

Il modulo predittore ha accesso ai seguenti dataset caricati in `agents/data.py`:

#### 1. `osa_mai_controllati_df` (154,406 record)
**Stabilimenti mai controllati - Target della predizione**

| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| `asl` | str | Codice ASL | "AVELLINO" |
| `comune` | str | Comune localizzazione | "NAPOLI" |
| `indirizzo` | str | Indirizzo | "VIA ROMA 123" |
| `macroarea` | str | Nome stabilimento | "MACELLERIA ROSSI" |
| `aggregazione` | str | Tipo attività | "MACELLERIE" |
| `attivita` | str | Linea attività (dettaglio) | "Macellerie - vendita carni fresche" |
| `num_riconoscimento` | str | ID univoco | "IT01NA1234CE" |
| `n_reg` | str | Numero registrazione (fallback) | "REG123456" |
| `codice_fiscale` | str | CF (fallback ID) | "RSSMRA80A01F839W" |
| `data_inizio_attivita` | date | Data inizio attività | "2020-01-15" |

**Note**:
- Priorità ID: `num_riconoscimento` > `n_reg` > `codice_fiscale`
- `macroarea`, `aggregazione`, `attivita`: join key con altri dataset

#### 2. `ocse_df` (101,343 record)
**Non conformità storiche - Features per training**

| Colonna | Tipo | Descrizione | Esempio |
|---------|------|-------------|---------|
| `macroarea_sottoposta_a_controllo` | str | Join key → `macroarea` | "MACELLERIE" |
| `aggregazione_sottoposta_a_controllo` | str | Join key → `aggregazione` | "MACELLERIE" |
| `linea_attivita_sottoposta_a_controllo` | str | Join key → `attivita` | "Macellerie - vendita carni fresche" |
| `numero_nc_gravi` | int | NC gravi (peso 3) | 5 |
| `numero_nc_non_gravi` | int | NC non gravi (peso 1) | 12 |
| `id_controllo_ufficiale` | str | ID controllo | "CTR2025001234" |
| `data_controllo` | date | Data controllo (se disponibile) | "2025-03-15" |

**Aggregazione attuale (rule-based)**:
```python
punteggio_rischio = numero_nc_gravi * 3 + numero_nc_non_gravi * 1
```

**Suggerimento ML**: Usare come target per training classificatore o regressore.

#### 3. `controlli_df` (61,247 record)
**Controlli eseguiti 2025 - Correlazione piano-attività**

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `descrizione_piano` | str | Nome piano completo |
| `piano_code` | str | Estratto con regex `^([A-Z]+\d+[A-Z_]*)` |
| `macroarea_cu` | str | Join key → `macroarea` |
| `aggregazione_cu` | str | Join key → `aggregazione` |
| `attivita_cu` | str | Join key → `attivita` |

**Uso**: Filtrare attività rilevanti quando `piano_code` specificato.

#### 4. `piani_df` (730 record)
**Descrizioni piani**

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `alias` | str | Codice piano (A1, B2) |
| `alias_indicatore` | str | Codice variante (A1_A, A1_B) |
| `sezione` | str | Categoria piano |
| `descrizione` | str | Descrizione estesa |
| `descrizione-2` | str | Dettagli aggiuntivi |

**Uso**: Metadata per feature engineering semantiche (es. embedding descrizioni).

#### 5. `diff_prog_eseg_df` (3,002 record)
**Programmati vs Eseguiti - Contesto ritardi**

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `descrizione_uoc` | str | Nome UOC |
| `piano` | str | Codice piano |
| `programmati` | int | Controlli programmati |
| `eseguiti` | int | Controlli eseguiti |
| `ritardo` | int | Differenza (computed: programmati - eseguiti) |

**Uso**: Feature contestuale per prioritizzazione (piani in ritardo hanno urgenza maggiore).

---

## 📤 Contratto Dati di Output

### Formato Risposta Tool

**Struttura JSON conforme a LangGraph**:

```python
{
    # Metadata della predizione
    "asl": str,                          # ASL richiesta
    "piano_code": Optional[str],         # Piano filtrato (se specificato)
    "prediction_timestamp": str,         # ISO 8601 timestamp predizione
    "model_version": str,                # Versione modello ML (es. "v2.1.0")

    # Statistiche dataset
    "total_never_controlled": int,       # Tot stabilimenti mai controllati per ASL
    "total_predicted_risky": int,        # Tot stabilimenti sopra min_score
    "activities_analyzed": int,          # Numero attività con NC storiche

    # Lista stabilimenti predetti ad alto rischio (ordinati per score desc)
    "risky_establishments": [
        {
            # Identificazione stabilimento
            "macroarea": str,            # Nome stabilimento
            "aggregazione": str,         # Tipo attività
            "linea_attivita": str,       # Linea attività dettaglio
            "comune": str,               # Comune
            "indirizzo": str,            # Indirizzo
            "numero_id": str,            # num_riconoscimento/n_reg/CF
            "data_inizio_attivita": str, # Data inizio (ISO 8601)

            # Predizioni ML
            "risk_score": float,         # Score predittivo 0.0-1.0
            "risk_category": str,        # "ALTO" | "MEDIO" | "BASSO"
            "predicted_nc_gravi": float, # Predizione numero NC gravi attese
            "predicted_nc_non_gravi": float, # Predizione numero NC non gravi attese

            # Interpretabilità (se explain=True)
            "feature_importance": {
                "storico_nc_attivita": float,      # Contributo NC storiche attività
                "anzianita_stabilimento": float,   # Contributo età stabilimento
                "densita_territoriale": float,     # Contributo cluster geografico
                "stagionalita": float,             # Contributo pattern temporali
                # ... altre features
            },
            "explanation": str,          # Testo interpretabile (es. "Alto rischio per storico NC gravi in attività simili nella zona")

            # Confidence metrics
            "prediction_confidence": float,  # 0.0-1.0 (confidence intervallo predizione)
            "uncertainty": float             # 0.0-1.0 (incertezza modello)
        },
        # ... fino a 'limit' stabilimenti
    ],

    # Risposta formattata per utente finale (Italian)
    "formatted_response": str,           # Testo markdown user-friendly

    # Metriche modello (opzionali)
    "model_metrics": {
        "training_date": str,            # Data ultimo training
        "test_auc_roc": float,           # AUC-ROC su test set
        "test_precision": float,         # Precision @ top-20
        "test_recall": float,            # Recall @ top-20
        "feature_count": int             # Numero features utilizzate
    },

    # Errori (se presenti)
    "error": Optional[str]               # Messaggio errore se fallimento
}
```

### Esempio Output Concreto

```json
{
    "asl": "AVELLINO",
    "piano_code": "A1",
    "prediction_timestamp": "2025-01-02T15:30:45Z",
    "model_version": "v2.1.0-xgboost",

    "total_never_controlled": 1247,
    "total_predicted_risky": 156,
    "activities_analyzed": 23,

    "risky_establishments": [
        {
            "macroarea": "MACELLERIA BOVINA ROSSI SRL",
            "aggregazione": "MACELLERIE",
            "linea_attivita": "Macellerie - vendita al dettaglio carni bovine fresche",
            "comune": "AVELLINO",
            "indirizzo": "VIA ROMA 45",
            "numero_id": "IT01AV0234CE",
            "data_inizio_attivita": "2018-03-15",

            "risk_score": 0.87,
            "risk_category": "ALTO",
            "predicted_nc_gravi": 2.3,
            "predicted_nc_non_gravi": 5.1,

            "feature_importance": {
                "storico_nc_attivita": 0.42,
                "anzianita_stabilimento": 0.18,
                "densita_territoriale": 0.15,
                "stagionalita": 0.12,
                "piano_ritardo": 0.08,
                "tipo_aggregazione": 0.05
            },
            "explanation": "Alto rischio: attività 'MACELLERIE' ha storico 47 NC gravi in area AVELLINO. Stabilimento attivo da 7 anni senza controlli. Piano A1 in ritardo di 15 controlli.",

            "prediction_confidence": 0.82,
            "uncertainty": 0.18
        },
        {
            "macroarea": "SALUMIFICIO CAMPANO DI VERDI GIUSEPPE",
            "aggregazione": "STABILIMENTI PRODUZIONE CARNI",
            "linea_attivita": "Produzione salumi e insaccati",
            "comune": "ARIANO IRPINO",
            "indirizzo": "ZONA INDUSTRIALE LOTTO 12",
            "numero_id": "IT01AV0567CE",
            "data_inizio_attivita": "2015-11-20",

            "risk_score": 0.79,
            "risk_category": "ALTO",
            "predicted_nc_gravi": 1.8,
            "predicted_nc_non_gravi": 4.2,

            "feature_importance": {
                "storico_nc_attivita": 0.38,
                "anzianita_stabilimento": 0.22,
                "densita_territoriale": 0.18,
                "stagionalita": 0.10,
                "piano_ritardo": 0.07,
                "tipo_aggregazione": 0.05
            },
            "explanation": "Rischio elevato: attività produzione salumi con 35 NC gravi storiche. Zona Ariano Irpino cluster ad alto rischio. Nessun controllo da apertura nel 2015.",

            "prediction_confidence": 0.76,
            "uncertainty": 0.24
        }
    ],

    "formatted_response": "**Analisi Predittiva Rischio NC - Machine Learning**\n\n**ASL:** AVELLINO\n**Piano filtrato:** A1\n**Stabilimenti analizzati:** 1247\n**Stabilimenti ad alto rischio predetto:** 156\n\n**Top 2 Stabilimenti Prioritari:**\n\n1. **MACELLERIA BOVINA ROSSI SRL** (Score: 0.87 - ALTO)\n   Comune: AVELLINO - VIA ROMA 45\n   N. Riconoscimento: IT01AV0234CE\n   **Predizione:** 2.3 NC gravi attese, 5.1 NC non gravi\n   **Motivazione:** Alto rischio per storico 47 NC gravi in attività MACELLERIE zona AVELLINO. Stabilimento attivo da 7 anni senza controlli.\n\n2. **SALUMIFICIO CAMPANO DI VERDI GIUSEPPE** (Score: 0.79 - ALTO)\n   Comune: ARIANO IRPINO - ZONA INDUSTRIALE LOTTO 12\n   N. Riconoscimento: IT01AV0567CE\n   **Predizione:** 1.8 NC gravi attese, 4.2 NC non gravi\n   **Motivazione:** Attività produzione salumi con 35 NC gravi storiche. Zona Ariano cluster alto rischio.\n\n**Metodologia ML:**\n- Modello: XGBoost v2.1.0 (AUC-ROC: 0.89)\n- Features: storico NC territoriale, anzianità, cluster geografici, pattern temporali\n- Interpretabilità: SHAP values per trasparenza decisionale\n\n**Raccomandazione:** Prioritizzare controlli per i primi 5 stabilimenti. Validare predizioni con ispezioni sul campo.",

    "model_metrics": {
        "training_date": "2025-01-01",
        "test_auc_roc": 0.89,
        "test_precision": 0.78,
        "test_recall": 0.71,
        "feature_count": 24
    }
}
```

---

## 🧠 Requisiti Machine Learning

### Tipologie Modelli Raccomandati

#### 1. **Classificazione Binaria** (Approccio Semplice)
**Target**: Stabilimento avrà NC grave? (Sì/No)

- **Algoritmi**: XGBoost, Random Forest, LightGBM
- **Metriche**: AUC-ROC, Precision@K, Recall@K
- **Output**: Probabilità classe 1 → `risk_score`

**Pro**: Semplice, interpretabile, buone performance
**Contro**: Perde informazione quantità NC

#### 2. **Regressione Multi-target** (Approccio Avanzato)
**Target**: Numero NC gravi e non gravi attese

- **Algoritmi**: Multi-output XGBoost, Neural Network
- **Metriche**: MAE, RMSE, R²
- **Output**: `(predicted_nc_gravi, predicted_nc_non_gravi)` → `risk_score` derivato

**Pro**: Predizione quantitativa, maggiore info
**Contro**: Più complesso, richiede più dati

#### 3. **Ranking Model** (Approccio Learning-to-Rank)
**Target**: Ordine relativo stabilimenti per rischio

- **Algoritmi**: LambdaMART, RankNet
- **Metriche**: NDCG, MAP@K
- **Output**: Score relativo per ordinamento

**Pro**: Ottimizzato per top-K predizioni
**Contro**: Richiede annotazioni pairwise

### Feature Engineering Raccomandato

**Categorie Features**:

#### A. Features Storiche NC (da `ocse_df`)
```python
# Aggregazione per attività
features = {
    'tot_nc_gravi_attivita': ocse_df.groupby('linea_attivita')['numero_nc_gravi'].sum(),
    'tot_nc_non_gravi_attivita': ocse_df.groupby('linea_attivita')['numero_nc_non_gravi'].sum(),
    'avg_nc_gravi_attivita': ocse_df.groupby('linea_attivita')['numero_nc_gravi'].mean(),
    'nc_rate_attivita': (tot_nc_gravi + tot_nc_non_gravi) / controlli_count
}
```

#### B. Features Temporali
```python
features = {
    'anni_senza_controlli': (today - data_inizio_attivita).days / 365,
    'stagione_apertura': extract_season(data_inizio_attivita),
    'giorni_dalla_apertura': (today - data_inizio_attivita).days
}
```

#### C. Features Geografiche
```python
features = {
    'nc_comune': ocse_df.groupby('comune')['numero_nc_gravi'].sum(),
    'densita_osa_comune': osa_df.groupby('comune').size(),
    'cluster_geografico': kmeans_cluster(lat, lon, k=10)
}
```

#### D. Features Categoriche
```python
features = {
    'aggregazione_encoded': label_encode(aggregazione),
    'macroarea_encoded': target_encode(macroarea, target=nc_gravi),
    'asl_encoded': label_encode(asl)
}
```

#### E. Features Contestuali (da `diff_prog_eseg_df`)
```python
features = {
    'piano_in_ritardo': piano_code in delayed_plans,
    'ritardo_piano': diff_prog_eseg_df[piano_code]['ritardo'],
    'percentuale_eseguiti': eseguiti / programmati
}
```

### Interpretabilità Richiesta

**SHAP Values** (SHapley Additive exPlanations):
```python
import shap

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Per singolo stabilimento
feature_importance = {
    feature_names[i]: shap_values[idx, i]
    for i in range(len(feature_names))
}
```

**Spiegazione Testuale**:
```python
def generate_explanation(establishment, shap_values, threshold=0.1):
    top_features = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

    explanation = f"Alto rischio per: "
    for feature, value in top_features:
        if value > threshold:
            explanation += interpret_feature(feature, value) + ". "

    return explanation
```

---

## 🔄 Workflow di Integrazione

### 1. Sviluppo Esterno (Data Scientist)

```
┌────────────────────────────────────────────────────────┐
│  1. Data Extraction                                    │
│     - Export CSV: osa_mai_controllati, ocse, controlli │
│     - Script: export_training_data.py                  │
└────────────────┬───────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────────────────────┐
│  2. Feature Engineering                                │
│     - Notebook: feature_engineering.ipynb              │
│     - Output: features_df.parquet                      │
└────────────────┬───────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────────────────────┐
│  3. Model Training                                     │
│     - Notebook: model_training.ipynb                   │
│     - Hyperparameter tuning (Optuna/GridSearch)        │
│     - Output: risk_model.pkl, scaler.pkl               │
└────────────────┬───────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────────────────────┐
│  4. Evaluation                                         │
│     - Metrics: AUC-ROC, Precision@20, SHAP analysis    │
│     - Validation: stratified k-fold per ASL            │
└────────────────┬───────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────────────────────┐
│  5. Packaging                                          │
│     - Opzione A: Python package (predictor_ml/)        │
│     - Opzione B: Docker container (FastAPI service)    │
│     - Include: model, scaler, feature transformers     │
└────────────────────────────────────────────────────────┘
```

### 2. Integrazione in GiAs-llm

```python
# tools/predictor_tools.py

from langchain_core.tools import tool
from typing import Dict, Any, Optional

# Import del modulo ML sviluppato esternamente
try:
    from predictor_ml import RiskPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[WARNING] ML Predictor not available, fallback to rule-based")

# Import fallback rule-based
from tools.risk_tools import get_risk_based_priority as fallback_predictor

@tool("ml_risk_predictor")
def get_ml_risk_prediction(
    asl: str,
    piano_code: Optional[str] = None,
    limit: int = 20,
    min_score: float = 0.0,
    explain: bool = True
) -> Dict[str, Any]:
    """
    Predice rischio NC per stabilimenti mai controllati usando ML.

    Fallback automatico a rule-based se ML non disponibile.
    """

    if not ML_AVAILABLE:
        # Fallback a logica attuale
        return fallback_predictor(asl=asl, piano_code=piano_code)

    try:
        # Chiamata al modulo ML
        predictor = RiskPredictor(
            model_path="/models/risk_model.pkl",
            scaler_path="/models/scaler.pkl"
        )

        result = predictor.predict(
            asl=asl,
            piano_code=piano_code,
            limit=limit,
            min_score=min_score,
            explain=explain
        )

        # Validazione output conforme a contratto
        assert "risky_establishments" in result
        assert "formatted_response" in result

        return result

    except Exception as e:
        print(f"[ML Predictor Error] {e}, falling back to rule-based")
        return fallback_predictor(asl=asl, piano_code=piano_code)
```

### 3. Registrazione in LangGraph

```python
# orchestrator/graph.py

from tools.predictor_tools import get_ml_risk_prediction

class ConversationGraph:
    def _build_graph(self):
        # ... existing nodes

        # NUOVO: Nodo predittore ML
        workflow.add_node("ml_risk_predictor_tool", self._ml_risk_predictor_tool)

        # Routing da intent 'ask_risk_based_priority'
        workflow.add_conditional_edges(
            "classify",
            self._route_by_intent,
            {
                "ask_risk_based_priority": "ml_risk_predictor_tool",  # Sostituisce risk_tool
                # ... altri mappings
            }
        )

        workflow.add_edge("ml_risk_predictor_tool", "response_generator")

    def _ml_risk_predictor_tool(self, state: ConversationState):
        """Nodo LangGraph per predittore ML."""
        asl = state["metadata"].get("asl")
        piano_code = state["slots"].get("piano_code")

        # Chiamata al tool
        result = get_ml_risk_prediction(asl=asl, piano_code=piano_code)

        state["tool_output"] = result
        return state
```

---

## 📋 Deliverable Attesi

### Modulo Python: `predictor_ml/`

Struttura directory:
```
predictor_ml/
├── __init__.py
├── predictor.py           # Classe RiskPredictor principale
├── feature_engineering.py # Feature extraction e preprocessing
├── model_loader.py        # Caricamento modelli serializzati
├── explainer.py           # SHAP/LIME interpretability
├── config.py              # Configurazione (paths, thresholds)
├── models/
│   ├── risk_model.pkl     # Modello serializzato (pickle/joblib)
│   ├── scaler.pkl         # StandardScaler/RobustScaler
│   └── feature_names.json # Lista features in ordine
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_training.ipynb
│   └── 04_model_evaluation.ipynb
├── tests/
│   ├── test_predictor.py
│   └── test_features.py
├── requirements.txt       # Dependencies ML (scikit-learn, xgboost, shap, pandas)
└── README.md             # Documentazione tecnica
```

### Classe Principale: `RiskPredictor`

```python
# predictor_ml/predictor.py

import pandas as pd
from typing import Dict, Any, Optional, List
import joblib
import shap

class RiskPredictor:
    """
    Machine Learning Risk Predictor per stabilimenti mai controllati.

    Compatibile con interfaccia GiAs-llm tool layer.
    """

    def __init__(self, model_path: str, scaler_path: str, config: Dict = None):
        """
        Inizializza predittore caricando modello e scaler.

        Args:
            model_path: Path al modello serializzato (.pkl)
            scaler_path: Path allo scaler (.pkl)
            config: Configurazione opzionale (threshold, features, etc.)
        """
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.config = config or {}

        # SHAP explainer (pre-calcola per performance)
        self.explainer = shap.TreeExplainer(self.model)

    def predict(
        self,
        asl: str,
        piano_code: Optional[str] = None,
        limit: int = 20,
        min_score: float = 0.0,
        explain: bool = True
    ) -> Dict[str, Any]:
        """
        Predice rischio NC per stabilimenti mai controllati.

        Conforme a contratto output tool GiAs-llm.

        Returns:
            Dict con struttura definita in PREDICTOR_AGENT_SPEC.md
        """

        # 1. Carica dati (assume accesso a dataset GiAs-llm)
        from agents.data import osa_mai_controllati_df, ocse_df, controlli_df

        # 2. Filtra stabilimenti per ASL
        osa_filtered = osa_mai_controllati_df[
            osa_mai_controllati_df['asl'].str.upper() == asl.upper()
        ]

        # 3. Feature engineering
        features_df = self._engineer_features(
            osa_df=osa_filtered,
            ocse_df=ocse_df,
            controlli_df=controlli_df,
            piano_code=piano_code
        )

        # 4. Preprocessing e scaling
        X = self.scaler.transform(features_df[self.feature_names])

        # 5. Predizione
        risk_scores = self.model.predict_proba(X)[:, 1]  # Probabilità classe 1

        # 6. Filtra per min_score e ordina
        predictions = pd.DataFrame({
            'risk_score': risk_scores,
            'establishment_idx': features_df.index
        })
        predictions = predictions[predictions['risk_score'] >= min_score]
        predictions = predictions.sort_values('risk_score', ascending=False).head(limit)

        # 7. Interpretabilità (SHAP)
        explanations = []
        if explain:
            shap_values = self.explainer.shap_values(X[predictions['establishment_idx']])
            explanations = self._generate_explanations(shap_values, features_df)

        # 8. Formatta output conforme a contratto
        return self._format_output(
            asl=asl,
            piano_code=piano_code,
            osa_filtered=osa_filtered,
            predictions=predictions,
            features_df=features_df,
            explanations=explanations
        )

    def _engineer_features(self, osa_df, ocse_df, controlli_df, piano_code) -> pd.DataFrame:
        """Estrae features da dataset grezzi."""
        # Implementazione feature engineering
        # (vedere sezione Feature Engineering)
        pass

    def _generate_explanations(self, shap_values, features_df) -> List[Dict]:
        """Genera spiegazioni interpretabili da SHAP values."""
        # Implementazione SHAP → testo
        pass

    def _format_output(self, **kwargs) -> Dict[str, Any]:
        """Formatta output conforme a contratto tool."""
        # Implementazione formato output
        pass
```

### Testing e Validazione

**Unit Tests**:
```python
# tests/test_predictor.py

def test_predictor_output_format():
    """Verifica conformità output a contratto."""
    predictor = RiskPredictor(
        model_path="models/risk_model.pkl",
        scaler_path="models/scaler.pkl"
    )

    result = predictor.predict(asl="AVELLINO", piano_code="A1")

    # Validazione struttura
    assert "asl" in result
    assert "risky_establishments" in result
    assert "formatted_response" in result

    # Validazione contenuto
    assert result["asl"] == "AVELLINO"
    assert len(result["risky_establishments"]) <= 20

    # Validazione singolo stabilimento
    if result["risky_establishments"]:
        est = result["risky_establishments"][0]
        assert 0.0 <= est["risk_score"] <= 1.0
        assert "macroarea" in est
        assert "feature_importance" in est
```

**Integration Test**:
```python
# tests/test_integration.py

def test_langgraph_integration():
    """Testa integrazione con LangGraph."""
    from orchestrator.graph import ConversationGraph

    graph = ConversationGraph()

    result = graph.run(
        message="stabilimenti ad alto rischio per piano A1",
        metadata={"asl": "AVELLINO", "user_id": "12345"}
    )

    assert result["intent"] == "ask_risk_based_priority"
    assert "formatted_response" in result["tool_output"]
    assert "risky_establishments" in result["tool_output"]
```

---

## 🚀 Deployment e Versioning

### Versionamento Modello

**Schema**: `vX.Y.Z-{algorithm}`

Esempio: `v2.1.0-xgboost`

- **X (major)**: Cambio algoritmo o features strutturali
- **Y (minor)**: Nuove features, ritraining con più dati
- **Z (patch)**: Bugfix, ottimizzazioni performance

**Metadata Modello**:
```python
# models/model_metadata.json
{
    "version": "v2.1.0-xgboost",
    "algorithm": "XGBoost",
    "training_date": "2025-01-01",
    "training_samples": 150000,
    "features_count": 24,
    "test_metrics": {
        "auc_roc": 0.89,
        "precision_at_20": 0.78,
        "recall_at_20": 0.71
    },
    "hyperparameters": {
        "n_estimators": 500,
        "max_depth": 8,
        "learning_rate": 0.05
    }
}
```

### Monitoraggio Performance

**Logging Predizioni**:
```python
# predictor_ml/predictor.py

def predict(self, asl, piano_code, **kwargs):
    result = self._predict_internal(...)

    # Log predizione per monitoring
    self._log_prediction(
        asl=asl,
        piano_code=piano_code,
        num_predictions=len(result["risky_establishments"]),
        avg_score=np.mean([e["risk_score"] for e in result["risky_establishments"]]),
        timestamp=datetime.now()
    )

    return result
```

**Drift Detection**:
```python
# Monitora distribuzione features in produzione vs training
from scipy.stats import ks_2samp

def check_feature_drift(production_features, training_features):
    drift_detected = []
    for feature in feature_names:
        statistic, pvalue = ks_2samp(
            production_features[feature],
            training_features[feature]
        )
        if pvalue < 0.05:
            drift_detected.append(feature)

    return drift_detected
```

---

## 📚 Requisiti Non Funzionali

### Performance

| Metrica | Target | Note |
|---------|--------|------|
| Latency predizione | < 500ms | Per 20 stabilimenti |
| Throughput | > 10 req/s | Servizio dedicato |
| Memory footprint | < 2GB RAM | Modello + feature cache |
| Model size | < 100MB | File .pkl serializzato |

### Robustezza

- **Fallback graceful**: Se modello non disponibile, fallback a `risk_tools.py` rule-based
- **Input validation**: Validare ASL, piano_code, limit prima di predizione
- **Error handling**: Catch exceptions ML e ritorna `{"error": "..."}` conforme a contratto

### Manutenibilità

- **Codice documentato**: Docstrings completi per ogni metodo
- **Type hints**: Annotazioni tipo Python 3.8+
- **Testing**: Coverage > 80% (unit + integration)
- **Logging**: Logging strutturato (JSON) per debugging

---

## 🔗 Riferimenti e Risorse

### Dataset Location
- CSV files: `/opt/lang-env/GiAs-llm/dataset/`
- Data loader: `agents/data.py`
- Config: `config.json` (data source configurabile CSV/PostgreSQL)

### Codice Esistente da Studiare
- **Rule-based attuale**: `tools/risk_tools.py` (linee 1-166)
- **Feature engineering**: `agents/agents/data_agent.py` (RiskAnalyzer, linee 440-526)
- **Response formatting**: `agents/agents/response_agent.py` (format_risk_based_priority)
- **LangGraph integration**: `orchestrator/graph.py` (pattern tool node)

### Architettura Sistema
- **Documentazione completa**: `ARCHITECTURE_PRESENTATION.md`
- **Setup istruzioni**: `CLAUDE.md`
- **API endpoint**: `app/api.py` (FastAPI Rasa-compatible)

### ML Libraries Raccomandate
- **Modeling**: scikit-learn, xgboost, lightgbm
- **Feature engineering**: pandas, numpy, category_encoders
- **Interpretabilità**: shap, lime
- **Evaluation**: scikit-learn.metrics, yellowbrick
- **Hyperparameter tuning**: optuna, scikit-optimize

---

## ✅ Checklist Conformità

Prima della consegna, verificare:

- [ ] Output conforme a formato JSON specificato
- [ ] Campo `formatted_response` in italiano markdown
- [ ] Feature importance disponibile (SHAP)
- [ ] Gestione errori con campo `"error"` nel JSON
- [ ] Fallback a rule-based se modello non disponibile
- [ ] Test coverage > 80%
- [ ] Documentazione README.md completa
- [ ] Esempio notebook training disponibile
- [ ] Model metadata.json con metriche test
- [ ] Performance target rispettati (< 500ms)
- [ ] Compatibilità Python 3.8+
- [ ] Dependencies specificate in requirements.txt
- [ ] Licenza codice specificata (se open source)

---

## 📞 Contatti e Supporto

**Team GiAs-llm**: Sviluppo interno Regione Campania - Monitoraggio Veterinario

**Integrazione Support**:
- Issue tracker: (da definire)
- Documentazione tecnica: `ARCHITECTURE_PRESENTATION.md`, `CLAUDE.md`
- Dataset sample: Fornire export CSV anonimizzato per sviluppo esterno

**Timeline Prevista**:
1. **Settimana 1-2**: Data exploration, feature engineering
2. **Settimana 3-4**: Model training, hyperparameter tuning
3. **Settimana 5**: Evaluation, interpretabilità, documentazione
4. **Settimana 6**: Packaging, testing, integration in GiAs-llm

---

**Documento Versione**: 1.0
**Data**: 2025-01-02
**Autore**: GiAs-llm Architecture Team
**Status**: Specifica Pronta per Sviluppo Esterno
