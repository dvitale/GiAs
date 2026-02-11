# Guida al Rilascio: Agente Predittore ML (Versione V4)

## 1. Stato Attuale del Progetto
Il modello scelto per la produzione è il **V4**.

| Versione | Dataset | Features Chiave | Performance (Test) | Note |
| :--- | :--- | :--- | :--- | :--- |
| **V4** | 2016-2025 | Macroarea, Aggregazione, ASL, Linea Attivita, **Norma** | **Precision 25% @ Recall 70%** | **Consigliato per Produzione**. Soglia ottimale: **0.40**. |

### 1.1 Perché V4?
Il modello V4 introduce la feature `norma`, che distingue nettamente il rischio (15% per REG 852 vs 1.8% per REG 853).
Questo ha permesso di rompere il trade-off precisione/recall:
- Trova il 70% dei rischi reali.
- Mantiene un tasso di falsi positivi accettabile (1 su 4 è un rischio, contro 1 su 6 delle versioni precedenti).

---

## 2. Contenuto del Pacchetto
Ogni elemento di questa cartella ha uno scopo preciso per garantire la riproducibilità e l'integrazione.

```text
predictor_ml_handoff/
├── HANDOFF_GUIDE.md          # Guida tecnica all'integrazione (questo file)
├── PROJECT_REPORT.md         # Documento di alto livello su evoluzione e scelta V4
├── production_assets/        # ARTIFATTI PER IL DEPLOY (Output Finale)
    ├── risk_model_v4.json    # Il modello XGBoost V4 pronto per la produzione
    └── training_data_v4.parquet # Snapshot dei dati usati per il training V4

```

---

## 3. Come Ripetere l'Esperimento
Per ri-eseguire il training di qualsiasi versione (da V1 a V4), posizionarsi nella cartella `predictor_ml_handoff/code/` e seguire questi passaggi.

All'interno di `predictor_ml_handoff/code/`:
1.  **Installare dipendenze**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Dataset (Export)**:
    Ogni versione ha il suo script di export che genera il `.parquet` appropriato in `predictor_ml/data/`.
    *NOTA: Gli script assumono che il CSV sorgente originale sia disponibile al percorso relativo atteso o vada configurato.*
    ```bash
    # Per V4 (Produzione)
    python scripts/export_v4.py
    ```

3.  **Training**:
    Ogni versione ha il suo script di training che legge il parquet corrispondente e salva il modello.
    ```bash
    # Per V4 (Produzione)
    python predictor_ml/train_v4.py
    # Output: predictor_ml/models/risk_model_v4.json
    ```

### Storico Versioni (Comandi Rapidi)
*   **V1 (Prototype)**: `python scripts/export_training_data.py` -> `python predictor_ml/train_model.py`
*   **V2 (History)**: `python scripts/export_v2.py` -> `python predictor_ml/train_v2.py`
*   **V3 (Precision)**: `python scripts/export_v3.py` -> `python predictor_ml/train_v3.py`
*   **V4 (Best)**: `python scripts/export_v4.py` -> `python predictor_ml/train_v4.py`

---

## 4. Guida all'Integrazione in GiAs-llm
Per integrare il modello `risk_model_v4.json` nell'agente esistente (come definito in `Definizione Contratto Interfaccia`), seguire questi step.

### 4.1 Feature Engineering (Runtime)
Il modello in produzione si aspetta un DataFrame con le seguenti colonne esatte.
È necessario implementare un trasformatore che prenda i dati "live" dell'agente (da `osa_mai_controllati_df` unito ad anagrafiche) e produca queste feature:

1.  **`macroarea_norm`** (Category): Normalizzata usando `mappings/taxonomy_map.json`.
2.  **`aggregazione_norm`** (Category): Normalizzata usando `mappings/taxonomy_map.json`.
3.  **`asl`** (Category): Codice ASL (es. "AVELLINO", "SA1").
4.  **`linea_attivita`** (Category): Descrizione attività (es. "MACELLERIE"). **Upper-case e strip**.
5.  **`norma`** (Category): Riferimento normativo del controllo (es. "REG CE 852-04"). **Cruciale**.
    *   *Nota*: Se il dato `norma` non è presente nell'anagrafica OSA (poiché mai controllati), va dedotto o impostato al valore "most frequent" per quella tipologia di attività, oppure il modello userà il default (missing value handling di XGBoost).
    *   *Action Item*: Verificare se `norma` è disponibile per OSA mai controllati. Se non lo è, usare "REG CE 852-04" come fallback (più rischioso/comune) o addestrare una versione V4-Light senza norma (che sarebbe equivalente alla V3).
6.  **`years_never_controlled`** (Float): `(Oggi - Data Inizio Attività) / 365`.

### 4.2 Caricamento e Predizione
```python
import xgboost as xgb
import pandas as pd

# 1. Carica Modello
model = xgb.XGBClassifier()
model.load_model("predictor_ml_handoff/production_assets/risk_model_v4.json")

# 2. Prepara Dati (Esempio riga singola)
# Assicurarsi che i dtypes siano Category dove necessario
input_data = pd.DataFrame([{
    'macroarea_norm': 'MACELLERIA',
    'aggregazione_norm': 'VENDITA',
    'asl': 'AVELLINO',
    'linea_attivita': 'MACELLERIA - VENDITA CARNI', # Upper
    'norma': 'REG CE 852-04',                   # Upper
    'years_never_controlled': 5.2
}])

# Casting category (importante per XGBoost con enable_categorical=True)
for col in ['macroarea_norm', 'aggregazione_norm', 'asl', 'linea_attivita', 'norma']:
    input_data[col] = input_data[col].astype('category')

# 3. Predizione
# SOGLIA OTTIMALE V4: 0.40
threshold = 0.40
y_prob = model.predict_proba(input_data)[:, 1]
is_risky = (y_prob > threshold).astype(int)

print(f"Probabilità Rischio: {y_prob[0]:.2%}")
print(f"Alert: {is_risky[0]}")
```

### 4.3 Output per l'Agente
Integrare il risultato nel `Dict` di risposta definito nel contratto:
```json
{
  "asl": "...",
  "risky_establishments": [
    {
      "numero_id": "...",
      "risk_score": 0.85,  // y_prob
      "risk_category": "ALTO" // se > 0.7
      // ...
    }
  ]
  // ...
}
```
