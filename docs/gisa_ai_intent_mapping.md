# GISA-AI Intent Mapping

Documentazione del sistema di mapping tra domande utente, intent, tool e query per il chatbot GISA-AI.

> **Nota:** Le query riportate sono pseudo-SQL illustrativo. L'implementazione reale carica i dati PostgreSQL in DataFrame pandas all'avvio e opera su di essi in memoria tramite `DataRetriever`, `BusinessLogic` e `RiskAnalyzer` (modulo `agents/data_agent.py`).

---

## 1. Saluto

**Domanda tipo:** "Ciao", "Buongiorno"

| Campo | Valore |
|-------|--------|
| Intent | `greet` |
| Tool | nessuno (risposta statica) |
| Graph Node | `greet_tool` |

**Risposta:** Messaggio di benvenuto statico.

---

## 2. Congedo

**Domanda tipo:** "Arrivederci", "A presto"

| Campo | Valore |
|-------|--------|
| Intent | `goodbye` |
| Tool | nessuno (risposta statica) |
| Graph Node | `goodbye_tool` |

**Risposta:** Messaggio di congedo statico.

---

## 3. Aiuto

**Domanda tipo:** "Cosa puoi fare?", "Aiuto"

| Campo | Valore |
|-------|--------|
| Intent | `ask_help` |
| Tool | nessuno (risposta statica) |
| Graph Node | `help_tool` |

**Risposta:** Elenco delle funzionalita' disponibili.

---

## 4. Descrizione Piano

**Domanda tipo:** "Di cosa tratta il piano A1?"

| Campo | Valore |
|-------|--------|
| Intent | `ask_piano_description` |
| Tool | `piano_tool(action="description", piano_code=...)` |
| Graph Node | `piano_description_tool` |
| Data Retriever | `DataRetriever.get_piano_by_id()` |
| Business Logic | `BusinessLogic.extract_unique_piano_descriptions()` |

**Query equivalente:**
```sql
SELECT *
FROM piani_monitoraggio
WHERE UPPER(alias) = UPPER(:piano_code)
   OR UPPER(alias_indicatore) = UPPER(:piano_code);
```

---

## 5. Stabilimenti Controllati da Piano

**Domanda tipo:** "Stabilimenti controllati dal piano A1", "Quali OSA controllati per il piano A1?"

| Campo | Valore |
|-------|--------|
| Intent | `ask_piano_stabilimenti` |
| Tool | `piano_tool(action="stabilimenti", piano_code=...)` |
| Graph Node | `piano_stabilimenti_tool` |
| Data Retriever | `DataRetriever.get_controlli_by_piano()` |
| Business Logic | `BusinessLogic.aggregate_stabilimenti_by_piano()` |
| Two-Phase | Soglia: 3 stabilimenti unici |

**Query equivalente - Lista controlli:**
```sql
SELECT c.*
FROM cu_eseguiti c
WHERE UPPER(c.descrizione_indicatore) LIKE UPPER(:piano_code) || '%';
```

**Query equivalente - Aggregazione con non conformita':**
```sql
SELECT
    c.macroarea_cu,
    c.aggregazione_cu,
    c.attivita_cu,
    COUNT(*) AS count,
    COALESCE(SUM(o.numero_nc_gravi), 0) AS numero_nc_gravi,
    COALESCE(SUM(o.numero_nc_non_gravi), 0) AS numero_nc_non_gravi
FROM cu_eseguiti c
LEFT JOIN ocse_isp_semp o ON c.id_controllo = o.id_controllo_ufficiale
WHERE UPPER(c.descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
GROUP BY c.macroarea_cu, c.aggregazione_cu, c.attivita_cu
ORDER BY count DESC
LIMIT 10;
```

---

## 6. Statistiche Piani

**Domanda tipo:** "Quale piano e' piu' frequente?"

| Campo | Valore |
|-------|--------|
| Intent | `ask_piano_statistics` |
| Tool | `piano_tool(action="stabilimenti")` (se piano presente), altrimenti `get_piano_statistics(asl, top_n)` |
| Graph Node | `piano_statistics_tool` |
| Data Retriever | `DataRetriever.get_controlli_by_piano()` |
| Business Logic | `BusinessLogic.get_piano_statistics()` |

**Query equivalente - Statistiche per piano specifico:**
```sql
SELECT
    COUNT(*) AS total_controls,
    MIN(data_inizio_controllo) AS data_primo,
    MAX(data_inizio_controllo) AS data_ultimo
FROM cu_eseguiti
WHERE UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%';
```

**Query equivalente - Filtro per ASL:**
```sql
SELECT COUNT(*) AS asl_controls
FROM cu_eseguiti
WHERE UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
  AND UPPER(descrizione_asl) LIKE '%' || UPPER(:asl) || '%';
```

**Query equivalente - Statistiche aggregate su tutti i piani:**
```sql
WITH controlli_norm AS (
    SELECT
        UPPER(SPLIT_PART(descrizione_piano, ' ', 1)) AS piano_code,
        descrizione_piano,
        id_controllo,
        macroarea_cu
    FROM cu_eseguiti
    WHERE (:asl IS NULL OR UPPER(descrizione_asl) LIKE '%' || UPPER(:asl) || '%')
)
SELECT
    piano_code,
    descrizione_piano,
    COUNT(*) AS num_controlli,
    COUNT(DISTINCT macroarea_cu) AS num_stabilimenti
FROM controlli_norm
GROUP BY piano_code, descrizione_piano
ORDER BY num_controlli DESC
LIMIT :top_n;
```

---

## 7. Ricerca Piani per Topic

**Domanda tipo:** "Piani riguardanti mangimi"

| Campo | Valore |
|-------|--------|
| Intent | `search_piani_by_topic` |
| Tool | `search_tool(query=topic)` → `search_piani_by_topic()` |
| Graph Node | `search_piani_tool` |
| Data Retriever | `DataRetriever.search_piani_semantic()` (Qdrant), fallback `DataRetriever.search_piani_by_keyword()` |
| Two-Phase | Soglia: 3 risultati |

**Ricerca vettoriale (Qdrant):**

Usa la collection Qdrant `piani_monitoraggio` con embedding `paraphrase-multilingual-MiniLM-L12-v2`:
```python
qdrant_client.query_points(
    collection_name="piani_monitoraggio",
    query=embedding_vector,
    limit=top_k,
    score_threshold=0.3
)
```

**Fallback keyword (similarita' testuale su DataFrame `piani_monitoraggio`):**
```sql
-- Pseudo-SQL: in realta' usa enhanced_similarity() su pandas
SELECT *
FROM piani_monitoraggio
WHERE desc_full ILIKE '%' || :keyword || '%'
   OR text_similarity(:keyword, desc_full) >= :threshold
ORDER BY text_similarity(:keyword, desc_full) DESC
LIMIT 15;
```

---

## 8. Priorita' Stabilimenti da Controllare

**Domanda tipo:** "Chi devo controllare per primo?"

| Campo | Valore |
|-------|--------|
| Intent | `ask_priority_establishment` |
| Tool | `priority_tool(asl, uoc)` → `get_priority_establishment()` |
| Graph Node | `priority_establishment_tool` |
| Data Retriever | `DataRetriever.get_diff_programmati_eseguiti()` + `DataRetriever.get_osa_mai_controllati()` |
| Business Logic | `BusinessLogic.calculate_delayed_plans()` + `RiskAnalyzer.find_priority_establishments()` |
| Two-Phase | Soglia: 3 stabilimenti |

**Query equivalente - Piani in ritardo:**
```sql
SELECT *
FROM cu_diff_programmati_eseguiti
WHERE descrizione_uoc ILIKE '%' || :uoc || '%'
  AND anno = :target_year
  AND (programmati - eseguiti) > 0;
```

**Query equivalente - Stabilimenti prioritari con ritardo:**
```sql
WITH delayed AS (
    SELECT
        indicatore,
        descrizione_indicatore,
        programmati,
        eseguiti,
        (programmati - eseguiti) AS ritardo
    FROM cu_diff_programmati_eseguiti
    WHERE anno = :target_year
      AND (programmati - eseguiti) > 0
      AND (:piano_code IS NULL OR UPPER(indicatore) = UPPER(:piano_code))
),
piano_attivita AS (
    SELECT
        UPPER(SPLIT_PART(descrizione_piano, ' ', 1)) AS piano_code,
        attivita_cu
    FROM cu_eseguiti
    GROUP BY 1, 2
),
osa AS (
    SELECT *
    FROM osa_mai_controllati
    WHERE asl = :asl
)
SELECT
    d.indicatore AS piano,
    d.ritardo,
    o.macroarea,
    o.aggregazione,
    o.attivita,
    o.comune,
    o.indirizzo,
    o.num_riconoscimento
FROM delayed d
JOIN piano_attivita pa ON pa.piano_code = UPPER(SPLIT_PART(d.indicatore, ' ', 1))
JOIN osa o ON UPPER(o.attivita) = UPPER(pa.attivita_cu)
ORDER BY d.ritardo DESC;
```

---

## 9. Stabilimenti a Rischio Non Conformita'

**Domanda tipo:** "Stabilimenti a rischio non conformita'"

| Campo | Valore |
|-------|--------|
| Intent | `ask_risk_based_priority` |
| Tool | `risk_tool(asl, piano_code)` (statistico) oppure `get_ml_risk_prediction(asl, piano_code)` (ML) |
| Graph Node | `risk_predictor_tool` (configurabile via `config.json` → `risk_predictor.type`) |
| Data Retriever | `DataRetriever.get_osa_mai_controllati()` |
| Business Logic | `RiskAnalyzer.calculate_risk_scores()` + `RiskAnalyzer.rank_osa_by_risk()` |
| Two-Phase | Soglia: 3 stabilimenti |

**Configurazione Predittore di Rischio:**

Il sistema supporta due modalità di predizione configurabili via `config.json` o variabile ambiente `GIAS_RISK_PREDICTOR`:

1. **Statistical Predictor** (default): Approccio rule-based basato su dati storici
   - Tool: `risk_tool(asl, piano_code)`
   - Formula: Risk Score = P(NC) × Impatto × 100
   - Più veloce, deterministico, non richiede training

2. **ML Predictor**: Modello machine learning addestrato su dati storici NC
   - Tool: `get_ml_risk_prediction(asl, piano_code)`
   - Basato su modello trained con scikit-learn
   - Più accurato ma richiede modello pre-addestrato

Configurazione in `config.json`:
```json
{
  "risk_predictor": {
    "type": "statistical",  // oppure "ml"
    "options": ["ml", "statistical"]
  }
}
```

**Formula Risk Score (Statistical Predictor):**
```
Risk Score = P(NC) x Impatto x 100
P(NC) = (NC gravi + NC non gravi) / controlli totali
Impatto = NC gravi / controlli totali
```

**Query equivalente:**
```sql
WITH risk_scores AS (
    SELECT
        macroarea_sottoposta_a_controllo AS macroarea,
        aggregazione_sottoposta_a_controllo AS aggregazione,
        linea_attivita_sottoposta_a_controllo AS linea_attivita,
        SUM(numero_nc_gravi) AS tot_nc_gravi,
        SUM(numero_nc_non_gravi) AS tot_nc_non_gravi,
        COUNT(*) AS numero_controlli_totali,
        (SUM(numero_nc_gravi) + SUM(numero_nc_non_gravi))::float / NULLIF(COUNT(*), 0) AS prob_nc,
        SUM(numero_nc_gravi)::float / NULLIF(COUNT(*), 0) AS impatto,
        ((SUM(numero_nc_gravi) + SUM(numero_nc_non_gravi))::float / NULLIF(COUNT(*), 0)) *
        (SUM(numero_nc_gravi)::float / NULLIF(COUNT(*), 0)) * 100 AS punteggio_rischio_totale
    FROM ocse_isp_semp
    GROUP BY 1, 2, 3
),
osa AS (
    SELECT *
    FROM osa_mai_controllati
    WHERE asl = :asl
),
attivita_piano AS (
    SELECT DISTINCT
        macroarea_cu AS macroarea,
        aggregazione_cu AS aggregazione,
        attivita_cu AS linea_attivita
    FROM cu_eseguiti
    WHERE :piano_code IS NULL
       OR UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
)
SELECT
    o.*,
    r.punteggio_rischio_totale,
    r.tot_nc_gravi,
    r.tot_nc_non_gravi,
    r.numero_controlli_totali
FROM osa o
JOIN risk_scores r ON o.macroarea = r.macroarea
                  AND o.aggregazione = r.aggregazione
                  AND o.attivita = r.linea_attivita
JOIN attivita_piano ap ON ap.macroarea = r.macroarea
                      AND ap.aggregazione = r.aggregazione
                      AND ap.linea_attivita = r.linea_attivita
ORDER BY r.punteggio_rischio_totale DESC
LIMIT 20;
```

---

## 10. Stabilimenti Mai Controllati

**Domanda tipo:** "Stabilimenti mai controllati"

| Campo | Valore |
|-------|--------|
| Intent | `ask_suggest_controls` |
| Tool | `suggest_controls(asl, limit=20)` |
| Graph Node | `suggest_controls_tool` |
| Data Retriever | `DataRetriever.get_osa_mai_controllati()` |
| Two-Phase | Soglia: 3 stabilimenti |

**Query equivalente:**
```sql
SELECT *
FROM osa_mai_controllati
WHERE (:asl IS NULL OR asl = :asl)
LIMIT :limit;
```

---

## 11. Piani in Ritardo

**Domanda tipo:** "Piani in ritardo"

| Campo | Valore |
|-------|--------|
| Intent | `ask_delayed_plans` |
| Tool | `priority_tool(asl, uoc, action="delayed_plans")` → `get_delayed_plans()` |
| Graph Node | `delayed_plans_tool` |
| Data Retriever | `DataRetriever.get_diff_programmati_eseguiti()` |
| Business Logic | `BusinessLogic.calculate_delayed_plans()` |

**Query equivalente:**
```sql
WITH delayed AS (
    SELECT
        indicatore,
        descrizione_indicatore,
        programmati,
        eseguiti,
        (programmati - eseguiti) AS ritardo
    FROM cu_diff_programmati_eseguiti
    WHERE descrizione_uoc ILIKE '%' || :uoc || '%'
      AND anno = :target_year
      AND (programmati - eseguiti) > 0
)
SELECT
    indicatore,
    descrizione_indicatore,
    SUM(ritardo) AS ritardo,
    SUM(programmati) AS programmati,
    SUM(eseguiti) AS eseguiti
FROM delayed
GROUP BY indicatore, descrizione_indicatore
ORDER BY ritardo DESC;
```

---

## 12. Verifica Ritardo Piano Specifico

**Domanda tipo:** "Ritardo del piano A1"

| Campo | Valore |
|-------|--------|
| Intent | `check_if_plan_delayed` |
| Tool | `get_delayed_plans(asl, uoc, piano_code=...)` |
| Graph Node | `check_plan_delayed_tool` |
| Data Retriever | `DataRetriever.get_diff_programmati_eseguiti()` |
| Business Logic | `BusinessLogic.calculate_delayed_plans(piano_id=...)` |

**Query equivalente:**
```sql
WITH delayed AS (
    SELECT
        indicatore,
        descrizione_indicatore,
        programmati,
        eseguiti,
        (programmati - eseguiti) AS ritardo
    FROM cu_diff_programmati_eseguiti
    WHERE descrizione_uoc ILIKE '%' || :uoc || '%'
      AND anno = :target_year
      AND (programmati - eseguiti) > 0
)
SELECT
    indicatore,
    SUM(ritardo) AS ritardo,
    SUM(programmati) AS programmati,
    SUM(eseguiti) AS eseguiti
FROM delayed
WHERE UPPER(indicatore) = UPPER(:piano_code)
   OR UPPER(indicatore) LIKE UPPER(:piano_code) || '_%'
GROUP BY indicatore;
```

---

## 13. Storico Controlli Stabilimento

**Domanda tipo:** "Storico controlli stabilimento IT 2287"

| Campo | Valore |
|-------|--------|
| Intent | `ask_establishment_history` |
| Tool | `get_establishment_history(num_registrazione, partita_iva, ragione_sociale)` |
| Graph Node | `establishment_history_tool` |
| Data Retriever | `DataRetriever.get_establishment_history()` |
| Two-Phase | Soglia: 3 controlli |

**Identificatori accettati (almeno uno):** `num_registrazione`, `partita_iva`, `ragione_sociale`

**Query equivalente:**
```sql
SELECT
    c.*,
    o.numero_nc_gravi,
    o.numero_nc_non_gravi,
    o.tipo_non_conformita,
    o.oggetto_non_conformita
FROM cu_eseguiti c
LEFT JOIN ocse_isp_semp o ON c.id_controllo = o.id_controllo_ufficiale
WHERE (
    :num_registrazione IS NOT NULL AND
    REPLACE(UPPER(c.num_registrazione), ' ', '') = REPLACE(UPPER(:num_registrazione), ' ', '')
) OR (
    :partita_iva IS NOT NULL AND
    CAST(c.partita_iva AS TEXT) LIKE '%' || :partita_iva || '%'
) OR (
    :ragione_sociale IS NOT NULL AND
    c.ragione_sociale ILIKE '%' || :ragione_sociale || '%'
)
ORDER BY c.data_inizio_controllo DESC
LIMIT 50;
```

---

## 14. Classifica Attivita' per Rischio

**Domanda tipo:** "Classifica attivita' per rischio"

| Campo | Valore |
|-------|--------|
| Intent | `ask_top_risk_activities` |
| Tool | `get_top_risk_activities(limit=10)` |
| Graph Node | `top_risk_activities_tool` |
| Business Logic | `RiskAnalyzer.calculate_risk_scores()` |

**Query equivalente:**
```sql
SELECT
    macroarea_sottoposta_a_controllo AS macroarea,
    aggregazione_sottoposta_a_controllo AS aggregazione,
    linea_attivita_sottoposta_a_controllo AS linea_attivita,
    SUM(numero_nc_gravi) AS tot_nc_gravi,
    SUM(numero_nc_non_gravi) AS tot_nc_non_gravi,
    COUNT(*) AS numero_controlli_totali,
    ((SUM(numero_nc_gravi) + SUM(numero_nc_non_gravi))::float / NULLIF(COUNT(*), 0)) *
    (SUM(numero_nc_gravi)::float / NULLIF(COUNT(*), 0)) * 100 AS risk_score
FROM ocse_isp_semp
GROUP BY 1, 2, 3
ORDER BY risk_score DESC
LIMIT :limit;
```

---

## 15. Analisi Non Conformita' per Categoria

**Domanda tipo:** "Non conformita' igiene degli alimenti"

| Campo | Valore |
|-------|--------|
| Intent | `analyze_nc_by_category` |
| Tool | `analyze_nc_by_category(categoria, asl)` |
| Graph Node | `analyze_nc_tool` |
| Data Retriever | `DataRetriever.get_nc_by_category()` + `DataRetriever.get_establishments_with_nc_category()` |

**Categorie NC valide:**
`HACCP`, `IGIENE DEGLI ALIMENTI`, `CONDIZIONI DELLA STRUTTURA E DELLE ATTREZZATURE`, `CONDIZIONI DI PULIZIA E SANIFICAZIONE`, `IGIENE DELLE LAVORAZIONI`, `RINTRACCIABILITA'/RITIRO/RICHIAMO`, `IGIENE DEL PERSONALE`, `RICONOSCIMENTO/REGISTRAZIONE`, `ETICHETTATURA`, `LOTTA AGLI INFESTANTI`, `MOCA`

**Query equivalente - Lista dettagliata:**
```sql
SELECT *
FROM ocse_isp_semp
WHERE oggetto_non_conformita ILIKE '%' || :categoria || '%'
  AND (:asl IS NULL OR asl = :asl);
```

**Query equivalente - Aggregazione per stabilimento:**
```sql
SELECT
    numero_riconoscimento,
    asl,
    comune,
    macroarea_sottoposta_a_controllo AS macroarea,
    aggregazione_sottoposta_a_controllo AS aggregazione,
    SUM(numero_nc_gravi) AS tot_nc_gravi,
    SUM(numero_nc_non_gravi) AS tot_nc_non_gravi,
    COUNT(*) AS controlli_totali
FROM ocse_isp_semp
WHERE oggetto_non_conformita ILIKE '%' || :categoria || '%'
  AND (:asl IS NULL OR asl = :asl)
GROUP BY 1, 2, 3, 4, 5
ORDER BY (SUM(numero_nc_gravi) + SUM(numero_nc_non_gravi)) DESC
LIMIT 20;
```

---

## 16. Informazioni su Procedure Operative (RAG)

**Domanda tipo:** "Come si esegue un controllo ufficiale?", "Procedura ispezione semplice", "Cos'e' la preaccettazione?"

| Campo | Valore |
|-------|--------|
| Intent | `info_procedure` |
| Tool | `get_procedure_info(query=...)` |
| Graph Node | `info_procedure_tool` |
| Data Retriever | Qdrant collection `procedure_documents` + LLM RAG |

**Descrizione:**

Intent dedicato a domande su procedure operative documentate. Utilizza un sistema RAG (Retrieval-Augmented Generation) che:
1. Cerca nei documenti indicizzati (PDF manuali operativi) tramite Qdrant
2. Recupera i chunk piu' rilevanti
3. Genera una risposta contestualizzata tramite LLM

**Pattern riconosciuti:**
- "procedura", "come si fa", "come si procede"
- "passi per", "step per", "guida per", "istruzioni per"
- "cos'e'", "cosa significa", "definizione di"
- Domande su argomenti specifici GISA (preaccettazione, checklist, matrix, etc.)

---

## 17. Ricerca Stabilimenti per Prossimita'

**Domanda tipo:** "Stabilimenti vicino a Piazza Garibaldi, Napoli", "Controlli entro 3 km da Via Roma, Benevento"

| Campo | Valore |
|-------|--------|
| Intent | `ask_nearby_priority` |
| Tool | `get_nearby_priority(location, radius_km, asl)` |
| Graph Node | `nearby_priority_tool` |
| Data Retriever | `DataRetriever.get_osa_mai_controllati()` + Geocoding |
| Two-Phase | Soglia: 10 stabilimenti |

**Slot:**
- `location` (obbligatorio): Indirizzo o luogo di riferimento
- `radius_km` (opzionale, default 5): Raggio di ricerca in km

**Flusso:**
1. Geocodifica l'indirizzo fornito (via Nominatim/OSM)
2. Calcola distanza da tutti gli OSA mai controllati
3. Filtra per raggio e ASL utente
4. Ordina per distanza crescente
5. Applica two-phase se > 10 risultati

**Pattern riconosciuti:**
- "vicino a", "nei dintorni di", "nei pressi di"
- "zona di", "intorno a"
- "entro X km da"

---

## 18. Conferma Dettagli (Two-Phase)

**Domanda tipo:** "Si", "Mostrami i dettagli"

| Campo | Valore |
|-------|--------|
| Intent | `confirm_show_details` |
| Tool | nessuno (recupera `detail_context` dalla sessione) |
| Graph Node | `confirm_details_tool` |

**Prerequisito:** Sessione attiva con `detail_context` (impostato dal turno precedente).

---

## 19. Rifiuto Dettagli (Two-Phase)

**Domanda tipo:** "No grazie", "Basta"

| Campo | Valore |
|-------|--------|
| Intent | `decline_show_details` |
| Tool | nessuno (risposta statica) |
| Graph Node | `decline_details_tool` |

---

## 20. Fallback

**Domanda tipo:** Qualsiasi domanda fuori dominio o non classificabile.

| Campo | Valore |
|-------|--------|
| Intent | `fallback` |
| Tool | nessuno |
| Graph Node | `fallback_tool` |

Se `needs_clarification=True`, genera messaggio mirato per gli slot mancanti. Altrimenti risponde con messaggio generico di non comprensione.

---

## Tabelle del Database (PostgreSQL)

| Nome logico | Tabella PostgreSQL | Descrizione |
|-------------|-------------------|-------------|
| `piani` | `piani_monitoraggio` | Anagrafica piani di monitoraggio (730 record unici) |
| `attivita` | `masterlist` | Master list delle attivita' (538 record unici) |
| `controlli` | `cu_eseguiti` | Controlli ufficiali eseguiti (355.448 record) |
| `ocse` | `ocse_isp_semp` | Esiti controlli e non conformita' (807.290 record) |
| `diff_prog_eseg` | `cu_diff_programmati_eseguiti` | Differenza programmati vs eseguiti per piano/UOC (272.610 record) |
| `osa_mai_controllati` | `osa_mai_controllati` | Operatori del settore alimentare mai controllati (118.729 record) |
| `personale` | `personale` | Anagrafica personale ispettivo (1.494 utenti unici) |

**Qdrant (ricerca semantica):**

| Collection | Modello embedding | Descrizione |
|------------|------------------|-------------|
| `piani_monitoraggio` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding piani per ricerca semantica |
| `procedure_documents` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding documenti procedure operative (RAG) |

---

## Parametri Comuni

| Parametro | Descrizione |
|-----------|-------------|
| `:piano_code` | Codice piano (es. "A1", "B2") |
| `:asl` | Codice o descrizione ASL (es. "NA1", "BENEVENTO") |
| `:uoc` | Unita' Operativa Complessa |
| `:target_year` | Anno di riferimento (default: 2025 da config) |
| `:top_n` / `:limit` | Numero massimo di risultati |
| `:threshold` | Soglia di similarita' per ricerca semantica (default: 0.3 vector, 0.4 keyword) |
| `:num_registrazione` | Numero di registrazione stabilimento (es. "IT 2287") |
| `:partita_iva` | Partita IVA operatore (10-11 cifre) |
| `:ragione_sociale` | Ragione sociale operatore |
| `:categoria` | Categoria non conformita' (es. "HACCP", "IGIENE DEGLI ALIMENTI") |
| `:location` | Indirizzo o luogo per ricerca per prossimita' (es. "Via Roma 15, Napoli") |
| `:radius_km` | Raggio di ricerca in km (default: 5, max: 50) |

---

## Slot Obbligatori per Intent

| Intent | Slot richiesti | Note |
|--------|---------------|------|
| `ask_piano_description` | `piano_code` | |
| `ask_piano_stabilimenti` | `piano_code` | |
| `check_if_plan_delayed` | `piano_code` | |
| `search_piani_by_topic` | `topic` | |
| `ask_establishment_history` | `num_registrazione` \| `partita_iva` \| `ragione_sociale` | Almeno uno |
| `analyze_nc_by_category` | `categoria` | Deve essere in `VALID_NC_CATEGORIES` |
| `ask_nearby_priority` | `location` | `radius_km` opzionale (default 5) |

Se manca uno slot obbligatorio, `needs_clarification=True` e il sistema chiede esplicitamente all'utente.

---

## Architettura di Classificazione

```
Messaggio utente
    |
    v
+-----------------------------+
| Layer 1: Heuristics         | <-- Regex pattern matching (bypass LLM)
|  - Saluti, aiuto, conferme  |
|  - Piani in ritardo         |
|  - Mai controllati, rischio |
|  - Piano description/stab.  |
+-------------+---------------+
              | (nessun match)
              v
+-----------------------------+
| Layer 2: Pre-parsing slot   | <-- Estrazione deterministica via regex
|  - piano_code, asl, topic   |
|  - num_registrazione, etc.  |
+-------------+---------------+
              |
              v
+-----------------------------+
| Layer 3: Cache check        | <-- TTL 3600s, chiave = messaggio + contesto
+-------------+---------------+
              | (cache miss)
              v
+-----------------------------+
| Layer 4: LLM classification | <-- llama3.2:3b, system+user roles, json_mode
|  - Intent + slots + clarif. |
+-------------+---------------+
              |
              v
+-----------------------------+
| Post-validation             | <-- Verifica slot obbligatori, needs_clarification
| + Slot carry-forward        | <-- Merge con slot sessione precedente
+-----------------------------+
```

---

## Two-Phase Display

Per intent che possono restituire molti risultati, il sistema mostra prima un riepilogo e chiede conferma:

| Intent | Soglia |
|--------|--------|
| `ask_piano_stabilimenti` | > 3 stabilimenti unici |
| `search_piani_by_topic` | > 3 risultati |
| `ask_priority_establishment` | > 3 stabilimenti |
| `ask_risk_based_priority` | > 3 stabilimenti |
| `ask_suggest_controls` | > 3 stabilimenti |
| `ask_establishment_history` | > 3 controlli |
| `ask_nearby_priority` | > 10 stabilimenti |

Flusso: Riepilogo → "Vuoi vedere tutti i dettagli?" → `confirm_show_details` / `decline_show_details`

---

## Flussi di Risposta per Intent

Il sistema supporta tre modalità di risposta in base alla complessità e alla quantità di dati restituiti:

### 1. Single Turn (Risposta Diretta)

**Definizione:** Intent che forniscono una risposta completa in un singolo turno conversazionale, senza richiedere conferme o interazioni aggiuntive.

| Intent | Tipo Risposta | Note |
|--------|---------------|------|
| `greet` | Statica | Messaggio di benvenuto predefinito |
| `goodbye` | Statica | Messaggio di congedo predefinito |
| `ask_help` | Statica | Elenco funzionalità disponibili |
| `ask_piano_description` | Dati strutturati | Descrizione completa del piano richiesto |
| `ask_piano_statistics` | Dati aggregati | Statistiche numeriche sui piani |
| `ask_delayed_plans` | Lista | Elenco piani in ritardo con ritardo numerico |
| `check_if_plan_delayed` | Booleana + dati | Verifica specifica su piano singolo |
| `ask_top_risk_activities` | Classifica | Top N attività ordinate per rischio |
| `analyze_nc_by_category` | Analisi | Statistiche NC per categoria specifica |
| `info_procedure` | RAG + LLM | Risposta generata da documenti procedure |
| `fallback` | Statica | Messaggio di non comprensione o chiarimento |

**Caratteristiche:**
- ✅ Risposta immediata e completa
- ✅ Nessuna interazione aggiuntiva richiesta
- ✅ Formato fisso o template-based
- ✅ Latency bassa (1-3s per dati, <1s per statiche)

**Esempio di flusso:**
```
User: "Quali piani sono in ritardo?"
Bot:  "📊 Trovati 5 piani in ritardo:
       - Piano A1: 12 controlli in ritardo
       - Piano B2: 8 controlli in ritardo
       ..."
[FINE CONVERSAZIONE]
```

---

### 2. Two-Phase (Sintesi + Dettaglio su Richiesta)

**Definizione:** Intent che possono restituire grandi quantità di dati. Il sistema mostra prima una sintesi e chiede conferma prima di visualizzare tutti i dettagli.

| Intent | Soglia Two-Phase | Tipo Dati | Detail Context |
|--------|------------------|-----------|----------------|
| `ask_piano_stabilimenti` | > 3 stabilimenti unici | Lista stabilimenti controllati | Controlli aggregati per macroarea/attività |
| `search_piani_by_topic` | > 3 risultati | Lista piani trovati | Dettagli piani con score similarità |
| `ask_priority_establishment` | > 3 stabilimenti | Lista OSA prioritari | Stabilimenti con ritardo piano + dati OSA |
| `ask_risk_based_priority` | > 3 stabilimenti | Lista OSA ad alto rischio | Stabilimenti con risk score + storico NC |
| `ask_suggest_controls` | > 3 stabilimenti | Lista OSA mai controllati | Dati anagrafici OSA completi |
| `ask_establishment_history` | > 3 controlli | Storico controlli | Controlli con esiti e NC dettagliate |
| `ask_nearby_priority` | > 10 stabilimenti | Lista OSA vicini | Stabilimenti con distanza + dati anagrafici |

**Caratteristiche:**
- ✅ Prima risposta: sintesi numerica + primi N risultati
- ✅ Seconda risposta: dettagli completi su conferma
- ✅ Session state: `detail_context` salvato per conferma
- ✅ Timeout: 5 minuti (TTL sessione)

**Esempio di flusso:**
```
User: "Stabilimenti a rischio per il piano A1"
Bot:  "📊 Trovati 15 stabilimenti ad alto rischio per il piano A1.
       Top 3:
       1. Macelleria Rossi (risk score: 42.3)
       2. Caseificio Bianchi (risk score: 38.7)
       3. Salumificio Verdi (risk score: 35.1)

       Vuoi vedere l'elenco completo dei 15 stabilimenti?"

User: "Sì"
Bot:  "📋 Elenco completo stabilimenti ad alto rischio:
       [... dettagli di tutti i 15 stabilimenti ...]"

[FINE CONVERSAZIONE]
```

**Gestione risposta utente:**
- ✅ "Sì", "Mostrami", "Certo" → `confirm_show_details`
- ✅ "No", "Basta così", "No grazie" → `decline_show_details`
- ❌ Timeout o messaggio non pertinente → `detail_context` viene perso

---

### 3. Multiturn (Conversazione con Chiarimenti)

**Definizione:** Intent che richiedono slot obbligatori mancanti o necessitano di disambiguazione. Il sistema chiede esplicitamente all'utente le informazioni mancanti.

| Intent | Slot Richiesti | Chiarimento Richiesto | Carry-forward |
|--------|----------------|----------------------|---------------|
| `ask_piano_description` | `piano_code` | "Quale piano ti interessa? (es. A1, B2)" | ✅ Sessione |
| `ask_piano_stabilimenti` | `piano_code` | "Per quale piano vuoi conoscere gli stabilimenti?" | ✅ Sessione |
| `check_if_plan_delayed` | `piano_code` | "Quale piano vuoi verificare?" | ✅ Sessione |
| `search_piani_by_topic` | `topic` | "Quale argomento/settore ti interessa?" | ✅ Sessione |
| `ask_establishment_history` | `num_registrazione` \| `partita_iva` \| `ragione_sociale` | "Fornisci almeno uno tra: numero riconoscimento, P.IVA, ragione sociale" | ❌ Non carrier |
| `analyze_nc_by_category` | `categoria` (da VALID_NC_CATEGORIES) | "Quale categoria NC vuoi analizzare? (HACCP, IGIENE DEGLI ALIMENTI, ...)" | ❌ Non carrier |
| `ask_nearby_priority` | `location` | "Quale indirizzo o zona vuoi cercare?" | ❌ Non carrier |

**Caratteristiche:**
- ✅ `needs_clarification = True` quando mancano slot obbligatori
- ✅ Slot carry-forward: i parametri forniti precedentemente (piano_code, asl, uoc) vengono mantenuti nella sessione
- ✅ Prompt specifici: il sistema genera messaggi mirati per ogni slot mancante
- ✅ Validazione post-LLM: verifica che slot estratti siano conformi

**Esempio di flusso (slot mancante):**
```
User: "Dammi lo storico controlli"
Bot:  "Per recuperare lo storico controlli mi serve almeno uno tra:
       - Numero di riconoscimento (es. IT 2287)
       - Partita IVA
       - Ragione sociale dello stabilimento

       Quale preferisci fornirmi?"

User: "IT 2287"
Bot:  "📋 Storico controlli per IT 2287:
       [... elenco controlli ...]"

[FINE CONVERSAZIONE]
```

**Esempio di flusso (carry-forward):**
```
User: "Parlami del piano A1"
Bot:  "✅ Piano A1 - Residui farmaci alimenti origine animale
       [... descrizione ...]"

[Sessione salva: piano_code = "A1"]

User: "È in ritardo?"
Bot:  "🔍 Verifico lo stato del piano A1...
       ✅ Piano A1: 3 controlli in ritardo
       [... dettagli ritardo ...]"

[FINE CONVERSAZIONE - piano_code recuperato da sessione]
```

---

### Matrice Riepilogativa Flussi

| Categoria | N. Intent | Latency Media | Interazioni | Session State |
|-----------|-----------|---------------|-------------|---------------|
| **Single Turn** | 11 | 1-3s | 1 turno | Non richiesto |
| **Two-Phase** | 7 | 2-5s (sintesi) + 1-2s (dettaglio) | 2 turni | `detail_context` (TTL 5min) |
| **Multiturn Chiarimenti** | 7 | Variabile | 2+ turni | `last_slots` carry-forward (TTL 5min) |

**Totale Intent Implementati:** 20 (di cui 2 dedicati al two-phase flow: `confirm_show_details`, `decline_show_details`)

---

### Ottimizzazioni per Esperienza Utente

**1. Intent Cache (Layer 3):**
- Riduce latency per domande ripetute
- TTL: 3600s (1 ora)
- Hit rate tipico: 15-25%

**2. DataFrame Pre-load:**
- Tutte le tabelle PostgreSQL caricate in memoria all'avvio
- Evita query DB durante conversazione
- Trade-off: ~500MB RAM per 355k+ record

**3. LLM Keep-Alive:**
- Modello `llama3.2:3b` mantenuto in memoria Ollama
- Elimina cold start (5-10s → <1s)
- Configurabile via `OLLAMA_KEEP_ALIVE=-1`

**4. Prompt Compatto:**
- Classificazione LLM < 500 token
- Riduce latency e costo computazionale
- JSON mode per parsing affidabile

**5. Two-Phase Thresholds:**
- Bilanciamento tra completezza e usabilità
- Soglie configurabili per dominio
- Previene wall of text in chat

---

## Runtime Flow - Architettura del Backend

### 1. Avvio del Server (start_server.sh)

**Sequenza di avvio:**
```
1. Verifica server già in esecuzione (via PID file)
2. Verifica dataset (data/dataset.10/*.csv)
3. Pre-caricamento modello LLM (llama3.2:3b, keep_alive=-1)
4. Avvio API server FastAPI su porta 5005
5. Health check endpoint /status
```

**Modello LLM configurato:**
- Default: `llama3.2:3b` (veloce e leggero)
- Configurabile via `GIAS_LLM_MODEL`
- Kept in memory permanentemente (OLLAMA_KEEP_ALIVE=-1)

### 2. Inizializzazione FastAPI (app/api.py)

**Lifespan startup:**
```python
1. Pre-load dati PostgreSQL in DataFrame cache
   - piani_monitoraggio (730 record)
   - cu_eseguiti (355.448 record)
   - osa_mai_controllati (118.729 record)
   - ocse_isp_semp (807.290 record)

2. Initialize ConversationGraph singleton
   - Router (con LLMClient e IntentCache)
   - LangGraph workflow con 19 nodi

3. Load intent metadata da tabella intents
   - Per chat_log enrichment
```

**Endpoints disponibili:**
- `POST /webhooks/rest/webhook` → Conversazione principale (compatibile Rasa)
- `POST /model/parse` → NLU parsing (debug/testing)
- `GET /status` → Stato server + dati caricati
- `GET /config` → Configurazione corrente
- `GET /` → Health check

### 3. Flusso Richiesta Utente

**Step 1 - Webhook Request:**
```
User → POST /webhooks/rest/webhook
{
  "sender": "user123",
  "message": "Stabilimenti a rischio per il piano A1",
  "metadata": {"asl": "NA1", "uoc": "Veterinaria", ...}
}
```

**Step 2 - Session Management:**
```
1. Recupera/crea sessione utente (TTL: 5min)
2. Inject conversational context:
   - _session_last_intent
   - _session_last_slots
   - _session_summary
3. Recupera detail_context per two-phase flow
```

**Step 3 - ConversationGraph Execution:**
```
LangGraph Flow:
┌─────────────┐
│  classify   │ ← Router ibrido (heuristics + LLM)
└──────┬──────┘
       │
       v
┌─────────────────┐
│  Tool Node      │ ← Esecuzione tool specifico per intent
│  (19 nodi)      │   - piano_tool, risk_tool, etc.
└──────┬──────────┘
       │
       v
┌─────────────────┐
│ response_gen    │ ← Formattazione risposta (LLM o template)
└──────┬──────────┘
       │
       v
    END
```

**Step 4 - Router Classification (Hybrid 4-Layer):**
```
Layer 1: Heuristics (regex patterns)
  ├─ Saluti, aiuto, conferme
  ├─ Piani in ritardo
  └─ Mai controllati, rischio

Layer 2: Pre-parsing slots (regex extraction)
  ├─ piano_code (A1, B2, ...)
  ├─ asl (NA1, AV1, ...)
  ├─ num_registrazione (IT ...)
  └─ topic, categoria, etc.

Layer 3: Intent Cache (TTL: 3600s)
  └─ Cache key = message + context

Layer 4: LLM Classification (llama3.2:3b)
  ├─ Prompt compatto (<500 token)
  ├─ JSON mode output
  ├─ Post-validation + slot carry-forward
  └─ needs_clarification logic
```

**Step 5 - Tool Execution:**
```
Ogni tool node:
1. Estrae parametri da slots + metadata
2. Chiama DataRetriever (cache-aware)
3. Applica BusinessLogic / RiskAnalyzer
4. Two-phase check (se applicabile)
5. Formatta risposta (ResponseFormatter)
```

**Step 6 - Response Generation:**
```
Se tool_output.formatted_response:
  └─ Usa risposta pre-formattata

Altrimenti:
  └─ LLM generation con prompt specifico per intent
     - System prompt: contesto veterinario
     - User prompt: intent + dati + domanda originale
     - Output: risposta professionale in italiano
```

**Step 7 - Logging & Session Update:**
```
1. Insert record in chat_log table:
   - ask, intent, tool, answer
   - two_phase_resp, dataretriever_class, sql
   - who (user_id-codice_fiscale), when (timestamp)

2. Update session store:
   - detail_context (se two-phase)
   - last_intent, last_slots
   - conversation_summary
   - timestamp
```

**Step 8 - Response:**
```
HTTP 200 OK
[
  {
    "text": "📊 Trovati 12 stabilimenti ad alto rischio...",
    "recipient_id": "user123"
  }
]
```

### 4. Ottimizzazioni di Performance

**Caching multi-livello:**
1. **DataFrame Cache** (class-level PostgreSQLDataSource)
   - Preload all'avvio
   - Shared across requests
   - Evita query ripetute al DB

2. **Intent Cache** (IntentCache con TTL 3600s)
   - Cache classificazioni LLM
   - Key = message + context
   - Stats tracking (hit rate, time saved)

3. **ConversationGraph Singleton**
   - Evita re-init LLMClient/Router
   - Condiviso tra richieste

4. **Connection Pooling** (SQLAlchemy)
   - Pool size: 5 connessioni
   - Max overflow: 10
   - Pool pre-ping + recycle 1h

**LLM Optimization:**
- Modello leggero (llama3.2:3b)
- Kept in Ollama memory (keep_alive=-1)
- Prompt compatto (<500 token)
- JSON mode per parsing affidabile

### 5. Monitoraggio e Debugging

**Log files:**
- `runtime/logs/api-server.log` → Log applicazione
- `runtime/logs/api-server.pid` → PID del processo

**Tabelle audit:**
- `chat_log` → Storico conversazioni con metadata
- `intents` → Mapping intent → tool → dataretriever

**Endpoint debug:**
- `POST /model/parse` → Test classificazione NLU
- `GET /status` → Verifica dati caricati + LLM mode
- `GET /config` → Configurazione attiva

### 6. Compatibilità Rasa

Il backend è **100% compatibile** con Rasa REST API per integrazione con GChat:
- Request format: `{sender, message, metadata}`
- Response format: `[{text, recipient_id}]`
- Endpoints: `/webhooks/rest/webhook`, `/model/parse`, `/status`

---

## Documentazione Allineamento

**Ultimo aggiornamento:** 2026-02-12
**Versione runtime:** 1.0.0
**Database schema version:** Allineato con codice
**Intent implementati:** 20/20 ✓
**Status:** ✅ PRODUCTION READY

**Verifica effettuata:**
- ✅ Codice sorgente (router.py, graph.py, api.py)
- ✅ Tabella intents PostgreSQL (19 record)
- ✅ Documentazione gisa_ai_intent_mapping.md
- ✅ Slot richiesti (7 intent con required_slots)
- ✅ Two-phase thresholds (6 intent configurati)
- ✅ Tool mappings (tutti corretti)
- ✅ Graph nodes (19 nodi LangGraph)
