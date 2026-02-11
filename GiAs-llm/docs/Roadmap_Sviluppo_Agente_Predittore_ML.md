# **Roadmap di Sviluppo: Agente Predittore ML**

---

## **FASE 0: Definizione Contratto Interfaccia**

**Obiettivo:** Garantire compatibilità con architettura GiAs-llm esistente prima di iniziare lo sviluppo.

### **0.1 Firma Funzione Tool**

Il modulo predittore deve implementare questa interfaccia esatta:

```python
def get_ml_risk_prediction(
    asl: str,                          # REQUIRED: "AVELLINO", "NA1", "SALERNO", etc.
    piano_code: Optional[str] = None,  # OPTIONAL: "A1", "B47", "AO24_A", etc.
    limit: int = 20,                   # Max numero stabilimenti ritornati
    min_score: float = 0.0,            # Soglia minima score predittivo (0.0-1.0)
    explain: bool = True               # Include SHAP feature importance
) -> Dict[str, Any]:
    """
    Predice rischio NC per stabilimenti mai controllati usando ML.

    Returns:
        Dict conforme a schema definito in PREDICTOR_AGENT_SPEC.md
    """
```

**Parametri dettagliati:**
- `asl`: Codice ASL da filtrare. Sistema normalizza varianti ("AVELLINO" = "AV" = "AV1")
- `piano_code`: Se specificato, filtra solo attività correlate al piano (via controlli_df)
- `limit`: Performance - evitare predizioni su interi dataset (150K stabilimenti)
- `min_score`: Filtra stabilimenti sotto soglia rischio (utile per "solo alto rischio")
- `explain`: Se True, calcola SHAP values (costoso - ~100ms extra per stabilimento)

---

### **0.2 Schema Output JSON**

**Struttura OBBLIGATORIA** (conforme a `PREDICTOR_AGENT_SPEC.md`):

```json
{
  "asl": "AVELLINO",
  "piano_code": "A1",
  "prediction_timestamp": "2025-01-02T15:30:45Z",
  "model_version": "v1.0.0-xgboost",

  "total_never_controlled": 1247,
  "total_predicted_risky": 156,
  "activities_analyzed": 23,

  "risky_establishments": [
    {
      "macroarea": "MACELLERIA BOVINA ROSSI SRL",
      "aggregazione": "MACELLERIE",
      "linea_attivita": "Macellerie - vendita carni bovine",
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
        "piano_ritardo": 0.08
      },
      "explanation": "Alto rischio: attività MACELLERIE con 47 NC gravi storiche in zona AVELLINO. Stabilimento mai controllato da 7 anni.",

      "prediction_confidence": 0.82,
      "uncertainty": 0.18
    }
  ],

  "formatted_response": "**Analisi Predittiva Rischio NC - Machine Learning**\n\n**ASL:** AVELLINO\n...",

  "model_metrics": {
    "training_date": "2025-01-15",
    "test_auc_roc": 0.89,
    "test_precision": 0.78,
    "test_recall": 0.71,
    "feature_count": 24
  }
}
```

**Campi CRITICI (il sistema crasha se mancanti):**
- `risky_establishments` (lista, anche vuota `[]`)
- `formatted_response` (stringa markdown italiano, user-facing)
- `asl`, `total_never_controlled`, `total_predicted_risky`

**Campi OPZIONALI (consigliati):**
- `feature_importance` (richiesto se `explain=True`)
- `model_metrics` (utile per debugging)
- `prediction_confidence`, `uncertainty` (per UI avanzate)

---

### **0.3 Validazione Pre-Training**

**Prima di iniziare FASE 1 (Feature Engineering):**

1. Creare **mock function** che ritorna JSON vuoto ma conforme:
   ```python
   def get_ml_risk_prediction_mock(asl, piano_code=None, ...):
       return {
           "asl": asl,
           "piano_code": piano_code,
           "risky_establishments": [],
           "formatted_response": "Modello non ancora addestrato.",
           "total_never_controlled": 0,
           "total_predicted_risky": 0
       }
   ```

2. Testare integrazione con GiAs-llm:
   ```python
   # Test manuale
   from orchestrator.graph import ConversationGraph

   graph = ConversationGraph()
   result = graph.run(
       message="stabilimenti ad alto rischio",
       metadata={"asl": "AVELLINO"}
   )
   assert "formatted_response" in result["tool_output"]
   ```

**✅ Checkpoint:** Mock integrato e funzionante in GiAs-llm prima di procedere.

---

## **FASE 1: Feature Engineering**

**Obiettivo:** Creare dataset unificato che permetta al modello di imparare dal passato (OCSE) per predire il futuro sugli stabilimenti sconosciuti (`osa_mai_controllati`).

### **1.1 Unificazione Tassonomie**

* **Azione:** Creare mapping dictionaries usando `Master list rev 11_filtered.csv`.
* **Dettaglio:** Le colonne `macroarea`, `aggregazione`, `attivita` hanno nomenclature leggermente diverse tra dataset storici (OCSE) e anagrafiche (OSA). Normalizzare in unico standard categoriale.
* **Motivazione:** Senza questo step, modello tratterebbe "MACELLERIA" e "MACELLO - VENDITA AL DETTAGLIO" come entità diverse, perdendo potere predittivo.

**Output:** File `mappings/taxonomy_map.json`

---

### **1.2 Soluzione al "Cold Start": Geo-Clustering**

* **Azione:** Sfruttare `latitudine_stab` e `longitudine_stab`.
* **Dettaglio:** Calcolare features di prossimità spaziale:
  - **Feature:** `risk_density_1km` - Numero NC gravi rilevate in raggio 1km ultimi 3 anni
  - **Feature:** `cluster_risk_score` - Assegnare ogni stabilimento a micro-cluster (es. quartiere) e calcolare tasso NC medio cluster
* **Motivazione:** Stabilimenti target non hanno storico. Unico modo per predire rischio: principio **"Rischio per Associazione"**. Se ristorante apre in zona dove 8/10 ristoranti hanno problemi igienici, eredita rischio base elevato.

**Librerie:** `scikit-learn.cluster.KMeans`, `scipy.spatial.distance`

---

### **1.3 Calcolo Anzianità (Time-based Features)**

* **Azione:** Trasformare `data_inizio_attivita`.
* **Dettaglio:** Calcolare:
  - `days_since_start` = (oggi - data_inizio_attivita).days
  - `years_never_controlled` = days_since_start / 365.25
* **Motivazione:** Ipotesi operativa: nuove aperture (molto recenti) o attività molto vecchie mai controllate hanno profili rischio diversi. Attività "fantasma" operative da 10 anni senza controlli = priorità massima.

---

### **1.4 Features da Dataset Esistenti**

**Da implementare (vedi `PREDICTOR_AGENT_SPEC.md` sezione Feature Engineering):**

#### A. Features Storiche NC (da `ocse_df`)
```python
tot_nc_gravi_attivita = ocse_df.groupby('linea_attivita')['numero_nc_gravi'].sum()
tot_nc_non_gravi_attivita = ocse_df.groupby('linea_attivita')['numero_nc_non_gravi'].sum()
nc_rate_attivita = (tot_nc_gravi + tot_nc_non_gravi) / controlli_count
```

#### B. Features Geografiche
```python
nc_per_comune = ocse_df.groupby('comune')['numero_nc_gravi'].sum()
densita_osa_comune = osa_df.groupby('comune').size()
```

#### C. Features Contestuali (da `diff_prog_eseg_df`)
```python
piano_in_ritardo = piano_code in delayed_plans
ritardo_piano = diff_prog_eseg_df[piano_code]['ritardo']
```

**Output FASE 1:** File `data/features_engineered.parquet` (150K righe × 24 colonne)

---

## **FASE 2: Model Development & Training**

**Obiettivo:** Addestrare modello robusto capace di distinguere vero rischio da "rumore".

### **2.1 Gestione Sbilanciamento (Imbalance Handling)**

* **Problema:** Analisi dati: ~72.000 casi "NESSUNA NC" vs ~9.000 con NC. Modello classico predirebbe sempre "Tutto OK" (90% accuracy) ma fallirebbe obiettivo.
* **Azione:**
  1. **Target Encoding:** Trasformare `tipo_non_conformita` in:
     - Binario: `0=Ok, 1=Rischio`
     - Ternario: `0=Ok, 1=NC_Non_Grave, 2=NC_Grave`
  2. **Class Weights:** `scale_pos_weight` in XGBoost = 10 (dare 10x peso a errori su NC)
  3. **Stratified Sampling:** Mantenere rapporto classi in train/validation/test split
* **Motivazione:** Penalizzare pesantemente falsi negativi (dire stabilimento sano quando è rischioso).

---

### **2.2 Selezione Algoritmo**

* **Scelta:** **XGBoost** (o LightGBM)
* **Motivazione:**
  1. Gestisce nativamente NaN (valori mancanti frequenti in dati anagrafici)
  2. Modello ad alberi → non richiede normalizzazione scalare (StandardScaler)
  3. Supporta nativamente feature importance (essenziale per SHAP)
  4. Ottimo su dati tabulari strutturati
  5. Libreria matura con hyperparameter tuning efficace

**Hyperparameters iniziali:**
```python
params = {
    'n_estimators': 500,
    'max_depth': 8,
    'learning_rate': 0.05,
    'scale_pos_weight': 10,  # gestione imbalance
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'objective': 'binary:logistic',  # o 'multi:softprob' se ternario
    'eval_metric': 'auc'
}
```

---

### **2.3 Training & Validation Strategy**

* **Azione:** Time-Series Split o Geographic Split
* **Dettaglio:**
  - **Opzione A (Temporale):** Train su dati 2023-2024, Test su primi mesi 2025 (se disponibili)
  - **Opzione B (Geografica):** Train su Napoli/Salerno, Test su Avellino/Caserta (verificare generalizzazione territoriale)
  - **Cross-Validation:** Stratified K-Fold (K=5) per ASL
* **Motivazione:** Evitare "Data Leakage". Modello non deve "vedere" il futuro.

**Metriche target:**
- **AUC-ROC:** > 0.85 (discriminazione rischio)
- **Precision@20:** > 0.75 (top-20 stabilimenti predetti sono davvero rischiosi)
- **Recall@100:** > 0.60 (catturare maggioranza stabilimenti rischiosi veri)

**Output FASE 2:**
- `models/risk_model.pkl` (modello serializzato)
- `models/scaler.pkl` (se necessario preprocessing)
- `models/feature_names.json` (lista features in ordine)

---

## **FASE 3: Context & Business Logic**

**Obiettivo:** Rischio sanitario non è unico driver. Integrare urgenza amministrativa.

### **3.1 Integrazione "Urgenza Operativa"**

**Azione:** Creare Priority Score finale combinando ML + contesto operativo.

**Formula Estesa:**

```
Score_finale = (W1 × P_ML) + (W2 × P_ritardo)

dove:
- P_ML = probabilità NC da modello ML (0.0-1.0)
- P_ritardo = urgenza piano normalizzata:

  P_ritardo = max(0, (programmati - eseguiti) / programmati)

  Esempio: Piano A1 con 100 programmati, 20 eseguiti
  → P_ritardo = (100-20)/100 = 0.80

- W1, W2 = pesi configurabili
  Default: W1=0.7 (70% peso al rischio ML)
           W2=0.3 (30% peso urgenza amministrativa)
```

**Ranking Finale:** Ordinare stabilimenti per `Score_finale` decrescente.

**Caso Edge:** Se `piano_code=None` (query generica ASL), usare `P_ritardo` medio di tutti piani in ritardo per UOC utente.

**Implementazione:**
```python
def calculate_priority_score(ml_score, piano_code, diff_prog_eseg_df, w1=0.7, w2=0.3):
    if piano_code and piano_code in diff_prog_eseg_df.index:
        ritardo_data = diff_prog_eseg_df.loc[piano_code]
        p_ritardo = max(0, ritardo_data['ritardo'] / ritardo_data['programmati'])
    else:
        p_ritardo = 0.0  # Nessun piano specificato o non in ritardo

    return (w1 * ml_score) + (w2 * p_ritardo)
```

**Motivazione:** Agente serve operatore ASL. Anche se stabilimento è basso rischio sanitario, se rientra in piano obbligatorio in forte ritardo, va segnalato.

---

### **3.2 Explainability Layer (SHAP)**

**Azione:** Implementare wrapper che genera frasi linguaggio naturale da SHAP values.

**Template Spiegazioni:**

```python
# predictor_ml/explainer.py

import shap

def generate_explanation(
    shap_values: dict,
    establishment: dict,
    risk_score: float
) -> str:
    """Converte SHAP values in testo italiano comprensibile."""

    # Estrai top-3 features per contributo assoluto
    top_features = sorted(
        shap_values.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )[:3]

    risk_cat = categorize_score(risk_score)
    explanation = f"Rischio {risk_cat} ({risk_score:.2f}) per: "

    for feature, contribution in top_features:
        if feature == "storico_nc_attivita":
            n_nc = int(establishment.get('tot_nc_gravi_attivita', 0))
            explanation += f"Storico {n_nc} NC gravi in attività simili (+{contribution:.2f}). "

        elif feature == "anzianita_stabilimento":
            years = int(establishment.get('years_never_controlled', 0))
            explanation += f"Mai controllato da {years} anni (+{contribution:.2f}). "

        elif feature == "densita_territoriale":
            explanation += f"Zona ad alta incidenza NC (+{contribution:.2f}). "

        elif feature == "piano_ritardo":
            ritardo = int(establishment.get('ritardo_piano', 0))
            explanation += f"Piano in ritardo di {ritardo} controlli (+{contribution:.2f}). "

    return explanation.strip()

def categorize_score(score: float) -> str:
    """Categorizza score numerico in etichetta qualitativa."""
    if score >= 0.7:
        return "ALTO"
    elif score >= 0.4:
        return "MEDIO"
    else:
        return "BASSO"
```

**Output Esempio:**
```
"Rischio ALTO (0.87) per: Storico 47 NC gravi in attività MACELLERIE
in zona AVELLINO (+0.42). Mai controllato da 7 anni (+0.18).
Zona ad alta densità NC (+0.15)."
```

**Motivazione:** Come richiesto da Specifica, utente veterinario deve fidarsi del sistema. "Black Box" non accettabile in sanità pubblica.

**Output FASE 3:** Modulo `predictor_ml/explainer.py` funzionante.

---

## **FASE 4: Integration**

**Obiettivo:** Packaging agente per GiAs-llm con integrazione LangGraph completa.

### **4.1 Sviluppo Modulo Python**

**Struttura Directory Completa:**

```
predictor_ml/
├── __init__.py
├── predictor.py              # Classe RiskPredictor principale
├── feature_engineering.py    # Feature extraction e preprocessing
├── model_loader.py           # Caricamento modelli serializzati
├── explainer.py              # SHAP → testo italiano (da FASE 3.2)
├── config.py                 # Configurazione (paths, thresholds, pesi W1/W2)
├── models/
│   ├── risk_model.pkl        # Modello XGBoost serializzato
│   ├── scaler.pkl            # Scaler (se necessario)
│   ├── feature_names.json    # Lista features in ordine
│   └── metadata.json         # Versione, metriche, hyperparams
├── mappings/
│   └── taxonomy_map.json     # Mapping tassonomie (da FASE 1.1)
├── tests/
│   ├── test_predictor.py     # Unit tests
│   ├── test_features.py
│   └── test_integration.py   # Integration con LangGraph
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_training.ipynb
│   └── 04_model_evaluation.ipynb
├── requirements.txt          # Dependencies
└── README.md                 # Documentazione installazione
```

---

### **4.2 Classe RiskPredictor**

**Implementazione Core:**

```python
# predictor_ml/predictor.py

import pandas as pd
import joblib
import shap
from typing import Dict, Any, Optional
from datetime import datetime
from .feature_engineering import FeatureEngineer
from .explainer import generate_explanation, categorize_score

class RiskPredictor:
    """
    ML Risk Predictor per stabilimenti mai controllati.
    Compatibile con interfaccia GiAs-llm tool layer.
    """

    def __init__(self, model_path: str, config: Dict = None):
        """Carica modello, scaler, metadata."""
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(model_path.replace('model', 'scaler'))

        with open(model_path.replace('.pkl', '_metadata.json')) as f:
            self.metadata = json.load(f)

        self.config = config or {}
        self.feature_engineer = FeatureEngineer()
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

        Conforme a contratto PREDICTOR_AGENT_SPEC.md (FASE 0.2).
        """

        # 1. Carica dati GiAs-llm
        from agents.data import (
            osa_mai_controllati_df,
            ocse_df,
            controlli_df,
            diff_prog_eseg_df
        )

        # 2. Filtra per ASL
        osa_filtered = osa_mai_controllati_df[
            osa_mai_controllati_df['asl'].str.upper() == asl.upper()
        ]

        if osa_filtered.empty:
            return self._empty_response(asl, piano_code,
                                       "Nessuno stabilimento mai controllato per ASL")

        # 3. Feature Engineering
        features_df = self.feature_engineer.transform(
            osa_df=osa_filtered,
            ocse_df=ocse_df,
            controlli_df=controlli_df,
            diff_prog_eseg_df=diff_prog_eseg_df,
            piano_code=piano_code
        )

        # 4. Preprocessing e Scaling
        X = self.scaler.transform(features_df[self.metadata['feature_names']])

        # 5. Predizione
        risk_scores = self.model.predict_proba(X)[:, 1]

        # 6. Calcola Priority Score (P_ML + P_ritardo)
        priority_scores = []
        for idx, ml_score in enumerate(risk_scores):
            priority_score = self._calculate_priority_score(
                ml_score,
                piano_code,
                diff_prog_eseg_df
            )
            priority_scores.append(priority_score)

        # 7. Filtra e ordina
        predictions = pd.DataFrame({
            'risk_score': risk_scores,
            'priority_score': priority_scores,
            'establishment_idx': features_df.index
        })
        predictions = predictions[predictions['risk_score'] >= min_score]
        predictions = predictions.sort_values('priority_score', ascending=False)
        predictions = predictions.head(limit)

        # 8. Explainability (SHAP)
        explanations = []
        if explain and not predictions.empty:
            X_explain = X[predictions['establishment_idx'].values]
            shap_values = self.explainer.shap_values(X_explain)
            explanations = self._generate_explanations(
                shap_values,
                features_df,
                predictions
            )

        # 9. Formatta output conforme a contratto
        return self._format_output(
            asl=asl,
            piano_code=piano_code,
            osa_filtered=osa_filtered,
            predictions=predictions,
            features_df=features_df,
            explanations=explanations
        )

    def _calculate_priority_score(self, ml_score, piano_code, diff_df):
        """Implementa formula FASE 3.1"""
        w1 = self.config.get('w1', 0.7)
        w2 = self.config.get('w2', 0.3)

        p_ritardo = 0.0
        if piano_code and piano_code in diff_df.index:
            ritardo_row = diff_df.loc[piano_code]
            programmati = ritardo_row.get('programmati', 1)
            if programmati > 0:
                p_ritardo = max(0, ritardo_row.get('ritardo', 0) / programmati)

        return (w1 * ml_score) + (w2 * p_ritardo)

    def _format_output(self, **kwargs) -> Dict[str, Any]:
        """Formatta output conforme FASE 0.2"""
        # Implementazione dettagliata formato JSON
        # (vedi PREDICTOR_AGENT_SPEC.md esempio)
        pass
```

---

### **4.3 Tool Decorator LangGraph**

**Creare nuovo file:**

```python
# tools/predictor_tools.py (NUOVO FILE)

from langchain_core.tools import tool
from typing import Dict, Any, Optional

try:
    from predictor_ml import RiskPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[WARNING] predictor_ml non disponibile, fallback a risk_tools")

from tools.risk_tools import get_risk_based_priority as fallback_predictor

# Inizializza predictor (singleton)
if ML_AVAILABLE:
    predictor = RiskPredictor(
        model_path="/opt/lang-env/GiAs-llm/predictor_ml/models/risk_model.pkl",
        config={'w1': 0.7, 'w2': 0.3}
    )

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

    Sostituisce risk_tools.get_risk_based_priority() con modello predittivo.
    Fallback automatico a logica rule-based se ML non disponibile.

    Args:
        asl: Codice ASL (es. "AVELLINO")
        piano_code: Codice piano opzionale (es. "A1")
        limit: Max stabilimenti ritornati (default: 20)
        min_score: Soglia minima score (default: 0.0)
        explain: Include SHAP explanations (default: True)

    Returns:
        Dict con formato definito in PREDICTOR_AGENT_SPEC.md
    """

    if not ML_AVAILABLE:
        print("[Fallback] Usando risk_tools rule-based")
        return fallback_predictor(asl=asl, piano_code=piano_code)

    try:
        result = predictor.predict(
            asl=asl,
            piano_code=piano_code,
            limit=limit,
            min_score=min_score,
            explain=explain
        )

        # Validazione output conforme a contratto
        assert "risky_establishments" in result, "Missing risky_establishments"
        assert "formatted_response" in result, "Missing formatted_response"

        return result

    except Exception as e:
        print(f"[ML Predictor Error] {e}, falling back to rule-based")
        import traceback
        traceback.print_exc()
        return fallback_predictor(asl=asl, piano_code=piano_code)
```

---

### **4.4 Registrazione in LangGraph**

**Modificare file esistente:**

```python
# orchestrator/graph.py (MODIFICARE)

from tools.predictor_tools import get_ml_risk_prediction

class ConversationGraph:
    def _build_graph(self):
        # ... existing nodes

        # NUOVO: Nodo predittore ML (sostituisce risk_tool)
        workflow.add_node("ml_risk_predictor_tool", self._ml_risk_predictor_tool)

        # Routing da intent 'ask_risk_based_priority'
        workflow.add_conditional_edges(
            "classify",
            self._route_by_intent,
            {
                "ask_risk_based_priority": "ml_risk_predictor_tool",  # ← Cambiato da "risk_tool"
                # ... altri mappings invariati
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

### **4.5 Fallback Mechanism (Safety Net)**

**Logica:** `try... except` con logging dettagliato.

**Dettaglio:** Se modello ML fallisce (input corrotti, modello non caricato, score incerto), sistema chiama automaticamente `risk_tools.get_risk_based_priority()`.

**Trigger Fallback:**
- Exception durante `predictor.predict()`
- Import `predictor_ml` fallisce
- Output JSON non conforme a schema
- (Opzionale) Score medio < 0.5 per tutti stabilimenti → possibile overfitting

**Logging:**
```python
import logging

logger = logging.getLogger("predictor_ml")

if exception:
    logger.error(f"ML Prediction failed: {exception}", extra={
        "asl": asl,
        "piano_code": piano_code,
        "traceback": traceback.format_exc()
    })
```

**Motivazione:** Continuità servizio prioritaria rispetto a precisione predittiva.

---

## **FASE 4.5: Testing & Validation**

**Obiettivo:** Garantire affidabilità produzione.

### **4.5.1 Unit Tests**

```python
# tests/test_predictor.py

import pytest
from predictor_ml import RiskPredictor

@pytest.fixture
def predictor():
    return RiskPredictor(
        model_path="models/risk_model.pkl",
        config={'w1': 0.7, 'w2': 0.3}
    )

def test_output_format(predictor):
    """Verifica conformità JSON a PREDICTOR_AGENT_SPEC.md"""
    result = predictor.predict(asl="AVELLINO", piano_code="A1")

    # Campi obbligatori
    assert "asl" in result
    assert "risky_establishments" in result
    assert "formatted_response" in result
    assert "total_never_controlled" in result

    # Struttura stabilimenti
    if result["risky_establishments"]:
        est = result["risky_establishments"][0]
        assert 0.0 <= est["risk_score"] <= 1.0
        assert "macroarea" in est
        assert "feature_importance" in est
        assert "explanation" in est

def test_empty_asl(predictor):
    """ASL senza stabilimenti ritorna lista vuota"""
    result = predictor.predict(asl="FAKE_ASL")
    assert result["total_never_controlled"] == 0
    assert result["risky_establishments"] == []

def test_min_score_filter(predictor):
    """min_score filtra correttamente"""
    result = predictor.predict(asl="AVELLINO", min_score=0.8)
    for est in result["risky_establishments"]:
        assert est["risk_score"] >= 0.8

def test_priority_score_calculation(predictor):
    """Priority score combina ML + ritardo"""
    result = predictor.predict(asl="AVELLINO", piano_code="A1")
    # Verificare che priority_score sia usato per ranking
    scores = [e["risk_score"] for e in result["risky_establishments"]]
    # Non necessariamente ordinati per risk_score puro se piano in ritardo
```

---

### **4.5.2 Integration Tests**

```python
# tests/test_integration.py

from orchestrator.graph import ConversationGraph

def test_langgraph_integration():
    """Testa integrazione con ConversationGraph"""
    graph = ConversationGraph()

    result = graph.run(
        message="stabilimenti ad alto rischio per piano A1",
        metadata={"asl": "AVELLINO", "user_id": "12345"}
    )

    assert result["intent"] == "ask_risk_based_priority"
    assert "tool_output" in result
    assert "formatted_response" in result["tool_output"]
    assert "risky_establishments" in result["tool_output"]

def test_fallback_mechanism():
    """Verifica fallback a rule-based se ML fallisce"""
    # Simulare failure (es. modello corrotto)
    import predictor_ml.predictor as pred_module
    original_predict = pred_module.RiskPredictor.predict

    def broken_predict(*args, **kwargs):
        raise RuntimeError("Modello corrotto")

    pred_module.RiskPredictor.predict = broken_predict

    from tools.predictor_tools import get_ml_risk_prediction
    result = get_ml_risk_prediction(asl="AVELLINO")

    # Deve ritornare comunque risultato (da fallback)
    assert "formatted_response" in result

    # Ripristina
    pred_module.RiskPredictor.predict = original_predict
```

**Target Coverage:** > 80% (unit + integration)

**Comando:**
```bash
pytest tests/ --cov=predictor_ml --cov-report=html
```

---

## **FASE 5: Deployment & Monitoring**

**Obiettivo:** Produzione robusta e manutenibile.

### **5.1 Versionamento Modello**

**Schema:** `vMAJOR.MINOR.PATCH-{algorithm}`

Esempi:
- `v1.0.0-xgboost` - Primo rilascio produzione
- `v1.1.0-xgboost` - Nuove features aggiunte, ritraining
- `v2.0.0-lightgbm` - Cambio algoritmo

**Incremento:**
- **MAJOR:** Cambio algoritmo, features strutturali, breaking changes
- **MINOR:** Nuove features, ritraining con più dati, tuning hyperparams
- **PATCH:** Bugfix, ottimizzazioni performance

---

### **5.2 Model Metadata**

```json
// models/metadata.json

{
  "version": "v1.0.0-xgboost",
  "algorithm": "XGBoost",
  "training_date": "2025-01-15T10:30:00Z",
  "training_samples": 150000,
  "features_count": 24,
  "feature_names": [
    "storico_nc_attivita",
    "anzianita_stabilimento",
    "densita_territoriale",
    ...
  ],
  "test_metrics": {
    "auc_roc": 0.89,
    "precision_at_20": 0.78,
    "recall_at_20": 0.71,
    "precision_at_100": 0.65,
    "recall_at_100": 0.60
  },
  "hyperparameters": {
    "n_estimators": 500,
    "max_depth": 8,
    "learning_rate": 0.05,
    "scale_pos_weight": 10,
    "subsample": 0.8,
    "colsample_bytree": 0.8
  },
  "dataset_stats": {
    "total_samples": 81000,
    "positive_samples": 9000,
    "negative_samples": 72000,
    "imbalance_ratio": 8.0
  }
}
```

---

### **5.3 Performance Monitoring**

**Requisiti Non Funzionali:**

| Metrica | Target | Misurazione |
|---------|--------|-------------|
| Latency predizione | < 500ms | Per 20 stabilimenti (limit default) |
| Throughput | > 10 req/s | Servizio dedicato (se microservizio) |
| Memory footprint | < 2GB RAM | Modello + feature cache |
| Model size | < 100MB | File .pkl serializzato |

**Logging Predizioni:**

```python
# predictor_ml/predictor.py

import logging
from datetime import datetime

logger = logging.getLogger("predictor_ml")

def predict(self, asl, piano_code, **kwargs):
    start_time = datetime.now()

    result = self._predict_internal(asl, piano_code, **kwargs)

    latency_ms = (datetime.now() - start_time).total_seconds() * 1000

    logger.info("Prediction completed", extra={
        "asl": asl,
        "piano_code": piano_code,
        "num_predictions": len(result["risky_establishments"]),
        "avg_score": np.mean([e["risk_score"] for e in result["risky_establishments"]]) if result["risky_establishments"] else 0,
        "latency_ms": latency_ms,
        "model_version": self.metadata["version"]
    })

    return result
```

---

### **5.4 Drift Detection**

**Problema:** Distribuzione features produzione può divergere da training (es. nuove tipologie stabilimenti, cambio normative).

**Soluzione:** Monitorare drift periodicamente.

```python
# predictor_ml/drift_monitor.py

from scipy.stats import ks_2samp
import pandas as pd

def check_feature_drift(
    production_features: pd.DataFrame,
    training_features: pd.DataFrame,
    threshold: float = 0.05
) -> dict:
    """
    Kolmogorov-Smirnov test per rilevare drift distributivo.

    Returns:
        dict con features in drift (p-value < threshold)
    """
    drift_detected = {}

    for feature in production_features.columns:
        if feature not in training_features.columns:
            continue

        prod_values = production_features[feature].dropna()
        train_values = training_features[feature].dropna()

        statistic, pvalue = ks_2samp(prod_values, train_values)

        if pvalue < threshold:
            drift_detected[feature] = {
                'statistic': statistic,
                'pvalue': pvalue,
                'prod_mean': prod_values.mean(),
                'train_mean': train_values.mean()
            }

    return drift_detected

# Schedulare settimanalmente
if drift_detected:
    logger.warning(f"Feature drift detected: {list(drift_detected.keys())}")
    # Alert team data science per retraining
```

---

### **5.5 Continuous Retraining**

**Trigger Retraining:**
- Ogni 3 mesi (dati nuovi controlli disponibili)
- Drift detection critico (> 5 features in drift)
- Performance degradation (AUC-ROC cala sotto 0.80)

**Workflow:**
1. Export nuovi dati OCSE/controlli
2. Re-run notebook `03_model_training.ipynb`
3. Validare metriche su nuovo test set
4. Se AUC-ROC > vecchio modello + 0.02 → deploy
5. Incrementare versione (MINOR se solo ritraining)

---

## **FASE 6: Documentazione**

**Obiettivo:** Consegna autosufficiente per team esterno.

### **6.1 README.md**

```markdown
# Predictor ML - Risk Prediction per GiAs-llm

## Installazione

### Requisiti
- Python 3.8+
- Accesso a dataset GiAs-llm (`/opt/lang-env/GiAs-llm/dataset/`)

### Setup
```bash
cd predictor_ml
pip install -r requirements.txt
```

## Quick Start

### Predizione Singola
```python
from predictor_ml import RiskPredictor

predictor = RiskPredictor(model_path="models/risk_model.pkl")
result = predictor.predict(asl="AVELLINO", piano_code="A1")

print(result["formatted_response"])
```

### Integrazione GiAs-llm
```python
from tools.predictor_tools import get_ml_risk_prediction

result = get_ml_risk_prediction(asl="AVELLINO", limit=10)
```

## Testing
```bash
pytest tests/ --cov=predictor_ml
```

## Model Metadata
- **Versione:** v1.0.0-xgboost
- **AUC-ROC:** 0.89
- **Precision@20:** 0.78
- **Training Date:** 2025-01-15
```

---

### **6.2 Notebooks Jupyter**

1. **01_data_exploration.ipynb**
   - Analisi esplorativa OCSE, OSA, controlli
   - Visualizzazioni distribuzioni NC
   - Analisi imbalance classi

2. **02_feature_engineering.ipynb**
   - Implementazione features (geo, temporali, storiche)
   - Validazione tassonomie
   - Output: `features_engineered.parquet`

3. **03_model_training.ipynb**
   - Training XGBoost con hyperparameter tuning
   - Cross-validation
   - Output: `risk_model.pkl`, `metadata.json`

4. **04_model_evaluation.ipynb**
   - Metriche test set (AUC-ROC, Precision@K, Recall@K)
   - SHAP global feature importance
   - Esempi predizioni con explanations

---

### **6.3 API Documentation**

Generare con Sphinx o MkDocs:

```bash
cd predictor_ml
sphinx-apidoc -o docs/ .
cd docs && make html
```

---

## **Checklist Conformità (Pre-Consegna)**

### **Output e Interfaccia**
- [ ] Output JSON conforme a `PREDICTOR_AGENT_SPEC.md` FASE 0.2
- [ ] Campo `formatted_response` in italiano markdown presente
- [ ] Campo `risky_establishments` lista ordinata per priority score
- [ ] Feature importance SHAP disponibile per ogni stabilimento (se `explain=True`)
- [ ] Firma funzione `get_ml_risk_prediction()` esatta (FASE 0.1)

### **Integrazione**
- [ ] Tool registrato in `orchestrator/graph.py` come `ml_risk_predictor_tool`
- [ ] Fallback automatico a `risk_tools.py` se ML non disponibile
- [ ] Gestione errori con logging strutturato
- [ ] Import opzionale (`try/except`) per compatibilità

### **Testing**
- [ ] Test coverage > 80% (unit + integration)
- [ ] Test end-to-end con ConversationGraph passa
- [ ] Test fallback mechanism funziona
- [ ] Validazione output JSON automatica in tests

### **Performance**
- [ ] Latency < 500ms per 20 stabilimenti (misurato)
- [ ] Memory footprint < 2GB RAM (verificato)
- [ ] Model size < 100MB (verificato)

### **Documentazione**
- [ ] README.md con istruzioni installazione completo
- [ ] Notebook Jupyter training disponibile in `notebooks/`
- [ ] Model metadata.json completo (versione, metriche, hyperparams)
- [ ] Requirements.txt con dipendenze (xgboost, shap, pandas, scikit-learn)

### **Modello**
- [ ] AUC-ROC test set > 0.85
- [ ] Precision@20 > 0.75
- [ ] Explainability SHAP funzionante
- [ ] Priority Score (ML + ritardo) implementato

### **Deployment**
- [ ] Schema versionamento modello applicato (vX.Y.Z-algorithm)
- [ ] Logging predizioni implementato
- [ ] Drift detection preparato (opzionale per v1.0)

### **Opzionale (Raccomandato)**
- [ ] Test end-to-end con GChat frontend
- [ ] Docker container per deploy isolato
- [ ] CI/CD pipeline per retraining automatico

---

## **Timeline Prevista**

| Fase | Durata | Deliverable Chiave |
|------|--------|-------------------|
| FASE 0 | 2 giorni | Mock function integrata, contratto validato |
| FASE 1 | 1 settimana | `features_engineered.parquet` (24 features) |
| FASE 2 | 1 settimana | `risk_model.pkl`, `metadata.json`, AUC > 0.85 |
| FASE 3 | 3 giorni | Priority score, SHAP explanations funzionanti |
| FASE 4 | 1 settimana | Modulo `predictor_ml/` completo, tool registrato |
| FASE 4.5 | 2 giorni | Test coverage > 80% |
| FASE 5 | 2 giorni | Logging, metadata, drift monitor |
| FASE 6 | 2 giorni | Documentazione completa, notebooks |
| **TOTALE** | **3-4 settimane** | Sistema produzione pronto |

---

## **Contatti e Supporto**

**Team GiAs-llm:** Sviluppo interno Regione Campania - Monitoraggio Veterinario

**Riferimenti Tecnici:**
- Specifica completa: `PREDICTOR_AGENT_SPEC.md`
- Architettura sistema: `ARCHITECTURE_PRESENTATION.md`
- Istruzioni sviluppo: `CLAUDE.md`

**Dataset Sample:** Richiedere export CSV anonimizzato per sviluppo esterno (se necessario).

---

**Documento Versione:** 2.0
**Data:** 2025-01-03
**Autore:** GiAs-llm Architecture Team
**Status:** Roadmap Esecutiva - Pronta per Sviluppo Esterno
