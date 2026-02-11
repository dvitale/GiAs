per integrare il modello risk_model_v4.json nell'agente esistente (come definito in Definizione Contratto Interfaccia), seguire questi step.

4.1 Feature Engineering (Runtime)

Il modello in produzione si aspetta un DataFrame con le seguenti colonne esatte. È necessario implementare un trasformatore che prenda i dati “live” dell'agente (da osa_mai_controllati_df unito ad anagrafiche) e produca queste feature:

macroarea_norm (Category): Normalizzata usando mappings/taxonomy_map.json.
aggregazione_norm (Category): Normalizzata usando mappings/taxonomy_map.json.
asl (Category): Codice ASL (es. “AVELLINO”, “SA1”).
linea_attivita (Category): Descrizione attività (es. “MACELLERIE”). Upper-case e strip.
norma (Category): Riferimento normativo del controllo (es. “REG CE 852-04”). Cruciale.
Nota: Se il dato norma non è presente nell'anagrafica OSA (poiché mai controllati), va dedotto o impostato al valore “most frequent” per quella tipologia di attività, oppure il modello userà il default (missing value handling di XGBoost).
Action Item: Verificare se norma è disponibile per OSA mai controllati. Se non lo è, usare “REG CE 852-04” come fallback (più rischioso/comune) o addestrare una versione V4-Light senza norma (che sarebbe equivalente alla V3).
years_never_controlled (Float): (Oggi - Data Inizio Attività) / 365.
4.2 Caricamento e Predizione

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
4.3 Output per l'Agente

Integrare il risultato nel Dict di risposta definito nel contratto: json { "asl": "...", "risky_establishments": [ { "numero_id": "...", "risk_score": 0.85, // y_prob "risk_category": "ALTO" // se > 0.7 // ... } ] // ... }