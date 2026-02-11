# Guida Implementazione: Agente Predittore ML (V4)

## 1. Introduzione
Questa guida è destinata all'AI (Claude Code) incaricata di implementare l'Agente Predittore in `gisa-2026`.
L'obiettivo è sostituire la logica attuale di `risk_tools.py` con il modello di Machine Learning **V4** fornito.

## 2. Risorse di Produzione
Le risorse necessarie si trovano in `predictor_ml_handoff/production_assets/`:
*   **Modello**: `risk_model_v4.json` (Formato XGBoost JSON).
*   **Schema Dati**: `training_data_v4.parquet` (Snapshot dati usati per il training, utile per verifica schema).

## 3. Requisiti Features
Il modello V4 richiede un DataFrame in ingresso con le seguenti colonne (dtypes: `category` per le stringhe):

| Feature | Tipo | Descrizione | Note Importanti |
| :--- | :--- | :--- | :--- |
| `macroarea_norm` | Category | Categoria Macroarea | Normalizzare vs tassonomia standard |
| `aggregazione_norm` | Category | Categoria Aggregazione | Normalizzare vs tassonomia standard |
| `asl` | Category | Codice ASL | Es. "AVELLINO", "SA1" |
| `linea_attivita` | Category | Dettaglio attività | Es. "MACELLERIE" (Upper case) |
| **`norma`** | Category | Riferimento normativo | **Feature Critica V4**. Es. "REG CE 852-04" |
| `years_never_controlled` | Float | Anni senza controlli | `(Oggi - Data Inizio) / 365.25` |

> **Nota su `norma`**: Per gli stabilimenti mai controllati, questa informazione potrebbe mancare. Implementare una logica di fallback (es. assegnare norma più frequente per quella `linea_attivita` o "REG CE 852-04").

## 4. Snippet di Integrazione
Esempio di codice per caricare ed eseguire il modello in Python:

```python
import xgboost as xgb
import pandas as pd
import json

def load_predictor():
    # Caricamento del modello JSON
    model = xgb.XGBClassifier()
    model.load_model("predictor_ml_handoff/production_assets/risk_model_v4.json")
    return model

def predict_risk(model, establishment_data):
    """
    establishment_data: Dict con i dati dello stabilimento
    """
    # 1. Preparazione DataFrame singolo record
    df = pd.DataFrame([establishment_data])
    
    # 2. Casting esplicito a category (Richiesto da XGBoost)
    cat_cols = ['macroarea_norm', 'aggregazione_norm', 'asl', 'linea_attivita', 'norma']
    for col in cat_cols:
        df[col] = df[col].astype('category')
        
    # 3. Predizione (Probabilità classe 1)
    # SOGLIA DI DECISIONE V4: 0.40
    prob_risk = model.predict_proba(df)[:, 1][0]
    is_risky = prob_risk >= 0.40
    
    return {
        "risk_score": float(prob_risk),
        "is_risky": bool(is_risky),
        "risk_category": "ALTO" if prob_risk > 0.7 else ("MEDIO" if prob_risk > 0.4 else "BASSO")
    }
```

## 5. Specifiche Output
Fare riferimento a `PREDICTOR_AGENT_SPEC.md` per il formato esatto del JSON di ritorno richiesto dal tool (`get_ml_risk_prediction`).

L'output deve includere:
*   `risky_establishments`: Lista ordinata per `risk_score` decrescente.
*   `formatted_response`: Markdown per l'utente finale.
*   `explain`: Se richiesto, usare SHAP (o euristiche basate su feature importance) per motivare il rischio.
