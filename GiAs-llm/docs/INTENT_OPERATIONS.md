# Intent e Operazioni per la Generazione della Risposta

Questo documento descrive gli intent supportati (non triviali) e le operazioni eseguite per generare la risposta in base all'intent classificato.

## Flusso generale (alto livello)

1. **Ingresso API**: l'endpoint `/webhooks/rest/webhook` crea o riusa `ConversationGraph` e recupera `detail_context` dalla sessione per il sistema a 2 fasi (TTL 5 minuti).
2. **Classificazione intent**: `Router.classify` applica:
   - Heuristics (pattern matching per intent comuni).
   - Pre-parsing slot via regex.
   - Cache LRU + TTL (se abilitata).
   - LLM per casi ambigui, con validazione output e post-validazione `needs_clarification`.
3. **Routing**: `ConversationGraph` invoca il tool associato all'intent.
4. **Tool execution**: recupero dati (DataRetriever/BusinessLogic/RiskAnalyzer) + formattazione (ResponseFormatter o formattazione inline).
5. **Generazione risposta**:
   - Se `formatted_response` presente o intent "diretti", risposta immediata.
   - Altrimenti, prompt LLM con risultati strutturati per generare testo finale.
6. **Two-phase (opzionale)**: per intent con molte righe, si salva `detail_context` e si mostra un sommario con richiesta di conferma.

## Elenco intent e operazioni dettagliate

### ask_piano_description
- **Tool**: `piano_tool(action="description")` → `get_piano_description`.
  - `DataRetriever.get_piano_by_id` per recuperare il piano.
  - `BusinessLogic.extract_unique_piano_descriptions` per aggregare descrizioni.
  - `ResponseFormatter.format_piano_description` per testo.
  - Error handling se `piano_code` mancante o piano assente.
- **Risposta**: usa `formatted_response` se presente.
- **Domande tipo**: "di cosa tratta il piano A1?", "di cosa si occupa il piano B2", "descrizione del piano A1", "cosa prevede il piano C3".
- **Pseudo-SQL**:
```sql
SELECT *
FROM piani
WHERE UPPER(alias) = UPPER(:piano_code)
   OR UPPER(alias_indicatore) = UPPER(:piano_code);
```

### ask_piano_stabilimenti
- **Tool**: `piano_tool(action="stabilimenti")` → `get_piano_attivita`.
  - `DataRetriever.get_controlli_by_piano` per controlli del piano.
  - `BusinessLogic.aggregate_stabilimenti_by_piano` per top stabilimenti.
  - `ResponseFormatter.format_stabilimenti_analysis`.
- **Two-phase**: se `unique_establishments` supera soglia (2), genera sommario con `ResponseFormatter.format_stabilimenti_analysis_summary` e salva `detail_context`.
- **Risposta**: sommario o dettaglio formattato.
- **Domande tipo**: "stabilimenti controllati dal piano A1", "dove e stato applicato il piano B2", "stabilimenti del piano C3".
- **Pseudo-SQL**:
```sql
SELECT c.*
FROM controlli c
WHERE UPPER(c.descrizione_indicatore) LIKE UPPER(:piano_code) || '%';

SELECT
  c.macroarea_cu,
  c.aggregazione_cu,
  c.attivita_cu,
  COUNT(*) AS count,
  COALESCE(SUM(o.numero_nc_gravi), 0) AS numero_nc_gravi,
  COALESCE(SUM(o.numero_nc_non_gravi), 0) AS numero_nc_non_gravi
FROM controlli c
LEFT JOIN ocse o
  ON c.id_controllo = o.id_controllo_ufficiale
WHERE UPPER(c.descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
GROUP BY c.macroarea_cu, c.aggregazione_cu, c.attivita_cu
ORDER BY count DESC
LIMIT 10;
```

### ask_piano_generic
- **Tool**: `piano_tool(action="generic")` → `get_piano_attivita`.
  - Stesso flusso dati di `ask_piano_stabilimenti`.
- **Risposta**: usa `formatted_response`.
- **Domande tipo**: "dimmi del piano A1", "parlami del piano B2", "info sul piano C3", "piano A1".
- **Pseudo-SQL**: stesso di `ask_piano_stabilimenti`.

### ask_piano_statistics
- **Se `piano_code` presente**:
  - `piano_tool(action="stabilimenti")` per controlli del piano.
  - Se la domanda contiene keyword di conteggio (`quanti`, `numero di`, ecc.):
    - `DataRetriever.get_controlli_by_piano` per calcolare totali, intervallo date, filtri ASL.
    - Risposta costruita direttamente (stringa formattata).
- **Se `piano_code` assente**:
  - `BusinessLogic.get_piano_statistics` per statistiche aggregate (con filtro ASL).
  - `ResponseFormatter.format_piano_statistics`.
- **Risposta**: usa `formatted_response` se disponibile.
- **Domande tipo**: "statistiche sui piani", "piani piu usati", "quanti piani", "quale piano e piu frequente".
- **Pseudo-SQL**:
```sql
-- Statistiche per piano specifico (conteggio e range date)
SELECT
  COUNT(*) AS total_controls,
  MIN(data_inizio_controllo) AS data_primo,
  MAX(data_inizio_controllo) AS data_ultimo
FROM controlli
WHERE UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%';

SELECT COUNT(*) AS asl_controls
FROM controlli
WHERE UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
  AND UPPER(descrizione_asl) LIKE '%' || UPPER(:asl) || '%';

-- Statistiche aggregate su tutti i piani
WITH controlli_norm AS (
  SELECT
    UPPER(SPLIT_PART(descrizione_piano, ' ', 1)) AS piano_code,
    descrizione_piano,
    id_controllo,
    macroarea_cu
  FROM controlli
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

### search_piani_by_topic
- **Tool**: `search_tool` → `search_piani_by_topic`.
  - Hybrid search se disponibile (`HybridSearchEngine.search` con smart routing).
  - Fallback legacy: `DataRetriever.search_piani_semantic`, poi keyword fallback.
  - `ResponseFormatter.format_search_results`.
- **Two-phase**: se `total_found` supera soglia (5), usa `ResponseFormatter.format_search_results_summary` e salva `detail_context`.
- **Risposta**: sommario o dettaglio formattato.
- **Domande tipo**: "piani su latte", "piani per bovini", "piani riguardanti mangimi", "cerca piani su apicoltura".
- **Pseudo-SQL**:
```sql
-- Variante ANN (vector search, Qdrant)
SELECT *
FROM piani_monitoraggio_vector
ORDER BY cosine_similarity(embedding(desc_full), embedding(:query)) DESC
LIMIT :top_k
HAVING similarity >= :threshold;

-- Fallback keyword (similarita testuale)
SELECT *
FROM piani
WHERE desc_full ILIKE '%' || :keyword || '%'
   OR text_similarity(:keyword, desc_full) >= :threshold
ORDER BY text_similarity(:keyword, desc_full) DESC
LIMIT 15;
```

### ask_priority_establishment
- **Tool**: `priority_tool` → `get_priority_establishment`.
  - `DataRetriever.get_diff_programmati_eseguiti` per differenze programmate/eseguite.
  - `BusinessLogic.calculate_delayed_plans`.
  - `DataRetriever.get_osa_mai_controllati`.
  - `RiskAnalyzer.find_priority_establishments`.
  - `ResponseFormatter.format_priority_establishments`.
- **Two-phase**: se `total_found` supera soglia (5), usa `ResponseFormatter.format_priority_establishments_summary`.
- **Risposta**: sommario o dettaglio formattato.
- **Domande tipo**: "chi devo controllare per primo?", "priorita", "cosa devo fare oggi", "quali stabilimenti controllare".
- **Pseudo-SQL**:
```sql
SELECT *
FROM diff_prog_eseg
WHERE descrizione_uoc ILIKE '%' || :uoc || '%';

WITH delayed AS (
  SELECT
    indicatore,
    descrizione_indicatore,
    programmati,
    eseguiti,
    (programmati - eseguiti) AS ritardo
  FROM diff_prog_eseg
  WHERE anno = :target_year
    AND (programmati - eseguiti) > 0
    AND (:piano_code IS NULL OR UPPER(indicatore) = UPPER(:piano_code))
),
piano_attivita AS (
  SELECT
    UPPER(REGEXP_SUBSTR(descrizione_piano, '[A-Z]+\\d+')) AS piano_code,
    attivita_cu
  FROM controlli
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
JOIN piano_attivita pa
  ON pa.piano_code = UPPER(REGEXP_SUBSTR(d.indicatore, '[A-Z]+\\d+'))
JOIN osa o
  ON UPPER(o.attivita) = UPPER(pa.attivita_cu)
ORDER BY d.ritardo DESC;
```

### ask_risk_based_priority
- **Tool**: `_risk_predictor_tool`, seleziona predittore:
  - **ML**: `get_ml_risk_prediction` (modello ML o fallback rule-based).
  - **Statistico**: `risk_tool` → `get_risk_based_priority`.
    - `RiskAnalyzer.calculate_risk_scores`.
    - `DataRetriever.get_osa_mai_controllati`.
    - Filtri per `piano_code` (attivita correlate).
    - `RiskAnalyzer.rank_osa_by_risk`.
    - `ResponseFormatter.format_risk_based_priority`.
- **Two-phase**: se `total_risky` supera soglia (5), usa `ResponseFormatter.format_risk_based_priority_summary`.
- **Risposta**: sommario o dettaglio formattato (o LLM se mancano formattazioni).
- **Domande tipo**: "stabilimenti a rischio", "rischiosi", "stabilimenti ad alto rischio", "non conformita".
- **Pseudo-SQL**:
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
  FROM ocse
  GROUP BY 1, 2, 3
),
osa AS (
  SELECT *
  FROM osa_mai_controllati
  WHERE asl = :asl
),
attivita_piano AS (
  SELECT DISTINCT macroarea_cu AS macroarea, aggregazione_cu AS aggregazione, attivita_cu AS linea_attivita
  FROM controlli
  WHERE :piano_code IS NULL
     OR UPPER(descrizione_indicatore) LIKE UPPER(:piano_code) || '%'
)
SELECT o.*, r.punteggio_rischio_totale, r.tot_nc_gravi, r.tot_nc_non_gravi, r.numero_controlli_totali
FROM osa o
JOIN risk_scores r
  ON o.macroarea = r.macroarea
 AND o.aggregazione = r.aggregazione
 AND o.attivita = r.linea_attivita
JOIN attivita_piano ap
  ON ap.macroarea = r.macroarea
 AND ap.aggregazione = r.aggregazione
 AND ap.linea_attivita = r.linea_attivita
ORDER BY r.punteggio_rischio_totale DESC
LIMIT 20;
```

### ask_suggest_controls
- **Tool**: `suggest_controls`.
  - `DataRetriever.get_osa_mai_controllati` per ASL.
  - `ResponseFormatter.format_suggest_controls`.
- **Two-phase**: se `total_never_controlled` supera soglia (5), riduce a 5 risultati e salva `detail_context`.
- **Risposta**: sommario o dettaglio formattato.
- **Domande tipo**: "mai controllati", "non sono stati controllati", "da controllare".
- **Pseudo-SQL**:
```sql
SELECT *
FROM osa_mai_controllati
WHERE (:asl IS NULL OR asl = :asl)
LIMIT :limit;
```

### ask_delayed_plans
- **Tool**: `priority_tool(action="delayed_plans")` → `get_delayed_plans`.
  - `DataRetriever.get_diff_programmati_eseguiti`.
  - `BusinessLogic.calculate_delayed_plans`.
  - `ResponseFormatter.format_delayed_plans` (include `detail_response`).
- **Risposta**: `formatted_response` (nessun two-phase).
- **Domande tipo**: "piani in ritardo", "quali piani sono in ritardo", "ritardo piani".
- **Pseudo-SQL**:
```sql
WITH delayed AS (
  SELECT
    indicatore,
    descrizione_indicatore,
    programmati,
    eseguiti,
    (programmati - eseguiti) AS ritardo
  FROM diff_prog_eseg
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

### check_if_plan_delayed
- **Tool**: `get_delayed_plans` con `piano_code`.
  - Se match su piano o sottopiani, aggrega ritardo, programmati, eseguiti.
  - `ResponseFormatter.format_check_plan_delayed`.
- **Risposta**: `formatted_response`.
- **Domande tipo**: "il piano B47 e in ritardo?", "ritardo del piano A1".
- **Pseudo-SQL**:
```sql
WITH delayed AS (
  SELECT
    indicatore,
    descrizione_indicatore,
    programmati,
    eseguiti,
    (programmati - eseguiti) AS ritardo
  FROM diff_prog_eseg
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

### ask_establishment_history
- **Tool**: `get_establishment_history`.
  - Validazione parametri (num_registrazione/partita_iva/ragione_sociale).
  - `DataRetriever.get_establishment_history`.
  - `ResponseFormatter.format_establishment_history`.
- **Two-phase**: se `total_controls` supera soglia (5), usa `ResponseFormatter.format_establishment_history_summary` e salva `detail_context`.
- **Risposta**: sommario o dettaglio formattato.
- **Domande tipo**: "storico controlli stabilimento IT 2287", "storia controlli stabilimento", "controlli per partita iva 01234567890".
- **Pseudo-SQL**:
```sql
SELECT c.*, o.numero_nc_gravi, o.numero_nc_non_gravi, o.tipo_non_conformita, o.oggetto_non_conformita
FROM controlli c
LEFT JOIN ocse o
  ON c.id_controllo = o.id_controllo_ufficiale
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

### ask_top_risk_activities
- **Tool**: `get_top_risk_activities`.
  - `RiskAnalyzer.calculate_risk_scores`.
  - Selezione top N, statistiche generali.
  - `ResponseFormatter.format_top_risk_activities`.
- **Risposta**: `formatted_response`.
- **Domande tipo**: "attivita rischiose", "top 10 attivita", "classifica attivita per rischio".
- **Soglie rischio** (calibrate su distribuzione reale P90=6.6, P75=3.0):
  - ALTO: > 7 (top 10%)
  - MEDIO: 3-7 (top 25%)
  - BASSO: 1-3 (25-50%)
  - MINIMO: < 1 (bottom 50%)
- **Pseudo-SQL** (con fix NULL e ordinamento):
```sql
SELECT
  macroarea_sottoposta_a_controllo AS macroarea,
  aggregazione_sottoposta_a_controllo AS aggregazione,
  linea_attivita_sottoposta_a_controllo AS linea_attivita,
  COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) AS tot_nc_gravi,
  COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0) AS tot_nc_non_gravi,
  COUNT(*) AS numero_controlli_totali,
  ROUND(
    ((COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
      COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::float / NULLIF(COUNT(*), 0)) *
    (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::float / NULLIF(COUNT(*), 0)) * 100
  , 3) AS risk_score
FROM ocse_isp_semp
GROUP BY 1, 2, 3
HAVING risk_score > 0
ORDER BY risk_score DESC NULLS LAST
LIMIT :limit;
```
- **VIEW SQL**: Vedi `sql/risk_score_view.sql` per VIEW completa con categoria rischio.

### analyze_nc_by_category
- **Tool**: `analyze_nc_by_category`.
  - Validazione categoria via `VALID_NC_CATEGORIES`.
  - `DataRetriever.get_nc_by_category`.
  - Statistiche aggregate + `DataRetriever.get_establishments_with_nc_category`.
  - `formatted_response` costruita inline.
- **Risposta**: `formatted_response`.
- **Domande tipo**: "analizza NC HACCP", "analizza non conformita", "non conformita categoria igiene".
- **Pseudo-SQL**:
```sql
SELECT *
FROM ocse
WHERE oggetto_non_conformita ILIKE '%' || :categoria || '%'
  AND (:asl IS NULL OR asl = :asl);

SELECT
  numero_riconoscimento,
  asl,
  comune,
  macroarea_sottoposta_a_controllo AS macroarea,
  aggregazione_sottoposta_a_controllo AS aggregazione,
  SUM(numero_nc_gravi) AS tot_nc_gravi,
  SUM(numero_nc_non_gravi) AS tot_nc_non_gravi,
  COUNT(*) AS controlli_totali
FROM ocse
WHERE oggetto_non_conformita ILIKE '%' || :categoria || '%'
  AND (:asl IS NULL OR asl = :asl)
GROUP BY 1, 2, 3, 4, 5
ORDER BY (SUM(numero_nc_gravi) + SUM(numero_nc_non_gravi)) DESC
LIMIT 20;
```

## Note sulla generazione LLM (quando usata)

Se un tool non fornisce `formatted_response`, `ConversationGraph._build_response_prompt` costruisce un prompt con:
- descrizione intent contestuale,
- domanda originale,
- output strutturato del tool,
- linee guida per formattazione e interpretazione.

Il testo finale e generato da `LLMClient.query`, con pulizia delle nuove linee in eccesso.
