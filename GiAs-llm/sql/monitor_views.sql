-- ============================================================================
-- View SQL per Monitoraggio Qualita' Conversazioni GIAS-AI
-- ============================================================================
-- Queste view supportano l'analisi di:
-- 1. Sessioni problematiche (fallback, errori, durata anomala)
-- 2. Domande ripetute (possibile misinterpretazione)
-- 3. Qualita' per intent (risposte brevi, slot ignorati)
-- 4. Fallback consecutivi (loop)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Sessioni Problematiche
-- Sessioni con 2+ fallback, 10+ messaggi, o errori
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_problem_sessions AS
SELECT
    session_id,
    asl,
    COUNT(*) as msg_count,
    COUNT(*) FILTER (WHERE intent = 'fallback') as fallback_count,
    COUNT(DISTINCT intent) as intent_variety,
    MIN("when"::timestamp) as session_start,
    MAX("when"::timestamp) as session_end,
    EXTRACT(EPOCH FROM (MAX("when"::timestamp) - MIN("when"::timestamp))) as duration_seconds,
    ARRAY_AGG(intent ORDER BY "when"::timestamp) as intent_sequence,
    BOOL_OR(error IS NOT NULL) as has_errors,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as error_count
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
  AND session_id IS NOT NULL
GROUP BY session_id, asl
HAVING COUNT(*) FILTER (WHERE intent = 'fallback') >= 2
    OR COUNT(*) > 10
    OR BOOL_OR(error IS NOT NULL)
ORDER BY MIN("when"::timestamp) DESC;

COMMENT ON VIEW v_problem_sessions IS 'Sessioni con problemi: 2+ fallback, >10 messaggi, o errori';

-- ----------------------------------------------------------------------------
-- 2. Domande Ripetute
-- Stessa domanda (normalizzata) ripetuta nella stessa sessione
-- Indica possibile insoddisfazione dell''utente
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_repeated_questions AS
SELECT
    session_id,
    asl,
    LOWER(TRIM(ask)) as normalized_ask,
    COUNT(*) as repeat_count,
    ARRAY_AGG(DISTINCT intent) as intents_assigned,
    MIN("when"::timestamp) as first_occurrence,
    MAX("when"::timestamp) as last_occurrence
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
  AND ask IS NOT NULL
  AND LENGTH(TRIM(ask)) > 5
  AND session_id IS NOT NULL
GROUP BY session_id, asl, LOWER(TRIM(ask))
HAVING COUNT(*) > 1
ORDER BY repeat_count DESC, MIN("when"::timestamp) DESC;

COMMENT ON VIEW v_repeated_questions IS 'Domande ripetute nella stessa sessione - possibile misinterpretazione';

-- ----------------------------------------------------------------------------
-- 3. Qualita' per Intent
-- Analisi qualita' delle risposte per ogni intent
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_intent_quality AS
SELECT
    intent,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE LENGTH(answer) < 50 AND answer IS NOT NULL) as short_responses,
    COUNT(*) FILTER (WHERE slots::text != '{}' AND slots::text != 'null' AND slots IS NOT NULL AND LENGTH(answer) < 100) as slots_ignored,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as errors,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / NULLIF(COUNT(*), 0), 2) as error_rate_pct,
    ROUND(AVG(response_time_ms)) as avg_time_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) as p95_time_ms
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
  AND intent IS NOT NULL
  AND intent != 'fallback'
GROUP BY intent
ORDER BY short_responses DESC, total DESC;

COMMENT ON VIEW v_intent_quality IS 'Metriche qualita'' per intent: risposte brevi, slot ignorati, errori';

-- ----------------------------------------------------------------------------
-- 4. Fallback Consecutivi (Loop Detection)
-- Identifica pattern di fallback consecutivi nelle sessioni
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_fallback_loops AS
WITH numbered AS (
    SELECT
        session_id,
        asl,
        intent,
        "when"::timestamp as when_ts,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY "when"::timestamp) as msg_num,
        CASE WHEN intent = 'fallback' THEN 1 ELSE 0 END as is_fallback
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
      AND session_id IS NOT NULL
),
runs AS (
    SELECT
        session_id,
        asl,
        msg_num,
        is_fallback,
        msg_num - SUM(is_fallback) OVER (PARTITION BY session_id ORDER BY msg_num) as run_group
    FROM numbered
    WHERE is_fallback = 1
),
consecutive AS (
    SELECT
        session_id,
        asl,
        run_group,
        COUNT(*) as consecutive_fallbacks,
        MIN(msg_num) as start_position
    FROM runs
    GROUP BY session_id, asl, run_group
    HAVING COUNT(*) >= 3
)
SELECT
    c.session_id,
    c.asl,
    c.consecutive_fallbacks,
    c.start_position,
    s.session_start
FROM consecutive c
JOIN (
    SELECT session_id, MIN("when"::timestamp) as session_start
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
    GROUP BY session_id
) s ON c.session_id = s.session_id
ORDER BY c.consecutive_fallbacks DESC, s.session_start DESC;

COMMENT ON VIEW v_fallback_loops IS 'Sessioni con 3+ fallback consecutivi (loop)';

-- ----------------------------------------------------------------------------
-- 5. Post-Intent Fallback
-- Fallback che seguono immediatamente un intent valido
-- Indica risposta insoddisfacente
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_post_intent_fallback AS
WITH ordered AS (
    SELECT
        session_id,
        asl,
        intent,
        ask,
        "when"::timestamp as when_ts,
        LEAD(intent) OVER (PARTITION BY session_id ORDER BY "when"::timestamp) as next_intent
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
      AND session_id IS NOT NULL
)
SELECT
    session_id,
    asl,
    intent as previous_intent,
    ask,
    when_ts as timestamp
FROM ordered
WHERE intent NOT IN ('fallback', 'greet', 'goodbye', 'ask_help')
  AND next_intent = 'fallback'
ORDER BY when_ts DESC;

COMMENT ON VIEW v_post_intent_fallback IS 'Fallback dopo intent valido - risposta insoddisfacente';

-- ----------------------------------------------------------------------------
-- 6. Two-Phase Abbandonati
-- Two-phase iniziati ma senza confirm/decline successivo
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_twophase_abandoned AS
WITH twophase_sessions AS (
    SELECT DISTINCT session_id
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
      AND two_phase_resp = true
),
confirmed_sessions AS (
    SELECT DISTINCT session_id
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
      AND intent IN ('confirm_show_details', 'decline_show_details')
)
SELECT
    c.session_id,
    c.asl,
    c.intent,
    c.ask,
    c."when"::timestamp as timestamp
FROM twophase_sessions t
LEFT JOIN confirmed_sessions cs ON t.session_id = cs.session_id
JOIN chat_log c ON c.session_id = t.session_id AND c.two_phase_resp = true
WHERE cs.session_id IS NULL
  AND c."when"::timestamp >= NOW() - INTERVAL '7 days'
ORDER BY c."when"::timestamp DESC;

COMMENT ON VIEW v_twophase_abandoned IS 'Two-phase avviati ma non completati con confirm/decline';

-- ----------------------------------------------------------------------------
-- 7. Riepilogo Qualita' Giornaliero
-- Aggregazione giornaliera delle metriche di qualita'
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_quality_daily AS
SELECT
    DATE("when"::timestamp) as data,
    COUNT(*) as total_messages,
    COUNT(DISTINCT session_id) as sessions,
    COUNT(*) FILTER (WHERE intent = 'fallback') as fallbacks,
    ROUND(100.0 * COUNT(*) FILTER (WHERE intent = 'fallback') / NULLIF(COUNT(*), 0), 2) as fallback_rate_pct,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as errors,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / NULLIF(COUNT(*), 0), 2) as error_rate_pct,
    ROUND(AVG(response_time_ms)) as avg_time_ms,
    COUNT(*) FILTER (WHERE LENGTH(answer) < 50 AND intent NOT IN ('fallback', 'greet', 'goodbye')) as short_responses
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE("when"::timestamp)
ORDER BY data DESC;

COMMENT ON VIEW v_quality_daily IS 'Metriche qualita'' aggregate per giorno';

-- ----------------------------------------------------------------------------
-- 8. Problemi per ASL
-- Conteggio problemi raggruppati per ASL
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_problems_by_asl AS
SELECT
    asl,
    COUNT(*) as total_messages,
    COUNT(DISTINCT session_id) as sessions,
    COUNT(*) FILTER (WHERE intent = 'fallback') as fallbacks,
    ROUND(100.0 * COUNT(*) FILTER (WHERE intent = 'fallback') / NULLIF(COUNT(*), 0), 2) as fallback_rate_pct,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as errors,
    (
        SELECT COUNT(*)
        FROM v_repeated_questions rq
        WHERE rq.asl = chat_log.asl
    ) as repeated_questions,
    (
        SELECT COUNT(*)
        FROM v_fallback_loops fl
        WHERE fl.asl = chat_log.asl
    ) as fallback_loops
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
  AND asl IS NOT NULL
GROUP BY asl
ORDER BY fallback_rate_pct DESC, total_messages DESC;

COMMENT ON VIEW v_problems_by_asl IS 'Riepilogo problemi per ASL';

-- ============================================================================
-- INDICI CONSIGLIATI (se non esistono gia')
-- ============================================================================

-- Indice su session_id per join e aggregazioni
CREATE INDEX IF NOT EXISTS idx_chatlog_session_id ON chat_log(session_id);

-- Indice su intent per filtri
CREATE INDEX IF NOT EXISTS idx_chatlog_intent ON chat_log(intent);

-- Indice su timestamp per filtri temporali
CREATE INDEX IF NOT EXISTS idx_chatlog_when ON chat_log("when");

-- Indice composito per query frequenti
CREATE INDEX IF NOT EXISTS idx_chatlog_session_when ON chat_log(session_id, "when");

-- Indice su two_phase_resp per la view v_twophase_abandoned
CREATE INDEX IF NOT EXISTS idx_chatlog_twophase ON chat_log(two_phase_resp) WHERE two_phase_resp = true;


-- ============================================================================
-- VIEW PER INTELLIGENT MONITOR (Bug Detection, Root Cause, Trends)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 9. Errori Ricorrenti (Bug Detection)
-- Errori con stessa signature che si ripetono >= 3 volte
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_recurring_errors AS
SELECT
    error_signature,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT session_id) AS affected_sessions,
    COUNT(DISTINCT asl) AS affected_asls,
    ARRAY_AGG(DISTINCT intent) AS related_intents,
    ARRAY_AGG(DISTINCT asl) AS asl_list,
    MIN("when"::timestamp) AS first_occurrence,
    MAX("when"::timestamp) AS last_occurrence,
    EXTRACT(DAY FROM MAX("when"::timestamp) - MIN("when"::timestamp)) AS span_days
FROM (
    SELECT
        session_id,
        asl,
        intent,
        error,
        "when",
        -- Normalizza l'errore per raggruppare varianti simili
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(LEFT(error, 200)),
                '[\d]+', 'N', 'g'  -- Sostituisci numeri con N
            ),
            '\s+', ' ', 'g'  -- Normalizza spazi
        ) AS error_signature
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '30 days'
      AND error IS NOT NULL
      AND LENGTH(error) > 10
) subq
GROUP BY error_signature
HAVING COUNT(*) >= 3
ORDER BY occurrence_count DESC, last_occurrence DESC;

COMMENT ON VIEW v_recurring_errors IS 'Errori ricorrenti con stessa signature (>=3 occorrenze) per bug detection';

-- ----------------------------------------------------------------------------
-- 10. Intent Slot Failures
-- Intent che falliscono per specifici valori di slot
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_intent_slot_failures AS
WITH slot_extractions AS (
    SELECT
        intent,
        asl,
        (slots::jsonb ->> 'piano') AS slot_piano,
        (slots::jsonb ->> 'anno') AS slot_anno,
        (slots::jsonb ->> 'comune') AS slot_comune,
        (slots::jsonb ->> 'stabilimento') AS slot_stabilimento,
        CASE
            WHEN error IS NOT NULL THEN 'error'
            WHEN LENGTH(answer) < 50 AND intent NOT IN ('greet', 'goodbye') THEN 'short_response'
            ELSE 'ok'
        END AS outcome
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '14 days'
      AND intent IS NOT NULL
      AND intent NOT IN ('fallback', 'greet', 'goodbye')
      AND slots IS NOT NULL
      AND slots::text != '{}'
)
SELECT
    intent,
    slot_piano,
    slot_anno,
    asl,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (WHERE outcome = 'error') AS error_count,
    COUNT(*) FILTER (WHERE outcome = 'short_response') AS short_response_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE outcome != 'ok') / NULLIF(COUNT(*), 0), 2) AS failure_rate_pct
FROM slot_extractions
WHERE slot_piano IS NOT NULL OR slot_anno IS NOT NULL OR slot_comune IS NOT NULL
GROUP BY intent, slot_piano, slot_anno, asl
HAVING COUNT(*) FILTER (WHERE outcome != 'ok') >= 2
ORDER BY failure_rate_pct DESC, error_count DESC;

COMMENT ON VIEW v_intent_slot_failures IS 'Intent che falliscono per specifiche combinazioni di slot values';

-- ----------------------------------------------------------------------------
-- 11. Correlazione ASL/Fascia Oraria
-- Pattern temporali di errori per ASL
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_asl_time_correlation AS
SELECT
    asl,
    EXTRACT(HOUR FROM "when"::timestamp) AS hour_of_day,
    CASE
        WHEN EXTRACT(HOUR FROM "when"::timestamp) BETWEEN 8 AND 13 THEN 'mattina'
        WHEN EXTRACT(HOUR FROM "when"::timestamp) BETWEEN 14 AND 18 THEN 'pomeriggio'
        ELSE 'fuori_orario'
    END AS time_slot,
    COUNT(*) AS total_messages,
    COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
    COUNT(*) FILTER (WHERE intent = 'fallback') AS fallbacks,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL OR intent = 'fallback') / NULLIF(COUNT(*), 0), 2) AS problem_rate_pct,
    ROUND(AVG(response_time_ms)) AS avg_response_ms
FROM chat_log
WHERE "when"::timestamp >= NOW() - INTERVAL '14 days'
  AND asl IS NOT NULL
GROUP BY asl, EXTRACT(HOUR FROM "when"::timestamp)
HAVING COUNT(*) >= 5
ORDER BY problem_rate_pct DESC, total_messages DESC;

COMMENT ON VIEW v_asl_time_correlation IS 'Correlazione errori/fallback per ASL e fascia oraria';

-- ----------------------------------------------------------------------------
-- 12. Fallback Clusters (Root Cause Analysis)
-- Clustering domande fallback normalizzate per identificare pattern
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_fallback_clusters AS
WITH normalized_fallbacks AS (
    SELECT
        session_id,
        asl,
        ask,
        "when",
        -- Normalizza per clustering: lowercase, rimuovi punteggiatura, numeri
        LOWER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    TRIM(ask),
                    '[^a-zA-Zàèéìòùáéíóú ]', '', 'g'
                ),
                '\s+', ' ', 'g'
            )
        ) AS normalized_ask,
        -- Estrai primi 3 token come cluster key
        ARRAY_TO_STRING(
            (STRING_TO_ARRAY(
                LOWER(REGEXP_REPLACE(TRIM(ask), '[^a-zA-Zàèéìòùáéíóú ]', ' ', 'g')),
                ' '
            ))[1:3],
            ' '
        ) AS cluster_key
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '14 days'
      AND intent = 'fallback'
      AND ask IS NOT NULL
      AND LENGTH(TRIM(ask)) > 10
)
SELECT
    cluster_key,
    COUNT(*) AS cluster_size,
    COUNT(DISTINCT session_id) AS unique_sessions,
    COUNT(DISTINCT asl) AS affected_asls,
    ARRAY_AGG(DISTINCT LEFT(ask, 100)) FILTER (WHERE ask IS NOT NULL) AS example_questions,
    MIN("when") AS first_seen,
    MAX("when") AS last_seen
FROM normalized_fallbacks
WHERE cluster_key IS NOT NULL AND LENGTH(cluster_key) > 5
GROUP BY cluster_key
HAVING COUNT(*) >= 3
ORDER BY cluster_size DESC, last_seen DESC
LIMIT 50;

COMMENT ON VIEW v_fallback_clusters IS 'Clustering domande fallback per identificare pattern ricorrenti non coperti';

-- ----------------------------------------------------------------------------
-- 13. Intent Gap Analysis
-- Analisi copertura intent per categoria/topic
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_intent_gap_analysis AS
WITH intent_categories AS (
    SELECT intent,
        CASE
            WHEN intent LIKE 'ask_piano%' OR intent LIKE 'piano_%' OR intent = 'piani_in_ritardo' THEN 'piani'
            WHEN intent LIKE 'ask_control%' OR intent LIKE 'controlli_%' THEN 'controlli'
            WHEN intent LIKE '%stabiliment%' OR intent = 'ask_osa_mai_controllati' THEN 'stabilimenti'
            WHEN intent LIKE '%risk%' THEN 'rischio'
            WHEN intent LIKE '%procedure%' OR intent LIKE '%document%' THEN 'procedure'
            WHEN intent IN ('greet', 'goodbye', 'ask_help') THEN 'conversational'
            ELSE 'altro'
        END AS category,
        COUNT(*) AS usage_count,
        COUNT(*) FILTER (WHERE error IS NOT NULL) AS error_count,
        COUNT(*) FILTER (WHERE LENGTH(answer) < 50 AND intent NOT IN ('greet', 'goodbye')) AS short_response_count
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '30 days'
      AND intent IS NOT NULL
      AND intent != 'fallback'
    GROUP BY intent
),
category_summary AS (
    SELECT
        category,
        COUNT(DISTINCT intent) AS intent_count,
        SUM(usage_count) AS total_usage,
        SUM(error_count) AS total_errors,
        SUM(short_response_count) AS total_short_responses,
        ROUND(100.0 * SUM(error_count) / NULLIF(SUM(usage_count), 0), 2) AS category_error_rate
    FROM intent_categories
    GROUP BY category
),
fallback_topics AS (
    SELECT
        CASE
            WHEN LOWER(ask) LIKE '%piano%' THEN 'piani'
            WHEN LOWER(ask) LIKE '%controll%' OR LOWER(ask) LIKE '%ispezion%' THEN 'controlli'
            WHEN LOWER(ask) LIKE '%stabiliment%' OR LOWER(ask) LIKE '%aziend%' THEN 'stabilimenti'
            WHEN LOWER(ask) LIKE '%rischio%' OR LOWER(ask) LIKE '%priorit%' THEN 'rischio'
            WHEN LOWER(ask) LIKE '%procedur%' OR LOWER(ask) LIKE '%document%' OR LOWER(ask) LIKE '%come%' THEN 'procedure'
            ELSE 'altro'
        END AS topic,
        COUNT(*) AS fallback_count
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '30 days'
      AND intent = 'fallback'
      AND ask IS NOT NULL
    GROUP BY 1
)
SELECT
    cs.category,
    cs.intent_count,
    cs.total_usage,
    cs.total_errors,
    cs.category_error_rate,
    COALESCE(ft.fallback_count, 0) AS uncovered_questions,
    ROUND(100.0 * COALESCE(ft.fallback_count, 0) / NULLIF(cs.total_usage + COALESCE(ft.fallback_count, 0), 0), 2) AS gap_percentage
FROM category_summary cs
LEFT JOIN fallback_topics ft ON cs.category = ft.topic
ORDER BY gap_percentage DESC NULLS LAST, total_usage DESC;

COMMENT ON VIEW v_intent_gap_analysis IS 'Gap analysis copertura intent per categoria topic';

-- ----------------------------------------------------------------------------
-- 14. Confronto Settimanale (Trend Analysis)
-- Confronto metriche settimana corrente vs precedente
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_weekly_comparison AS
WITH current_week AS (
    SELECT
        COUNT(*) AS messages,
        COUNT(DISTINCT session_id) AS sessions,
        COUNT(*) FILTER (WHERE intent = 'fallback') AS fallbacks,
        COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
        ROUND(AVG(response_time_ms)) AS avg_response_ms,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) AS p95_response_ms
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '7 days'
),
previous_week AS (
    SELECT
        COUNT(*) AS messages,
        COUNT(DISTINCT session_id) AS sessions,
        COUNT(*) FILTER (WHERE intent = 'fallback') AS fallbacks,
        COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
        ROUND(AVG(response_time_ms)) AS avg_response_ms,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) AS p95_response_ms
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '14 days'
      AND "when"::timestamp < NOW() - INTERVAL '7 days'
)
SELECT
    'current' AS period,
    c.messages,
    c.sessions,
    c.fallbacks,
    ROUND(100.0 * c.fallbacks / NULLIF(c.messages, 0), 2) AS fallback_rate_pct,
    c.errors,
    ROUND(100.0 * c.errors / NULLIF(c.messages, 0), 2) AS error_rate_pct,
    c.avg_response_ms,
    c.p95_response_ms,
    -- Delta rispetto settimana precedente
    ROUND((100.0 * (c.messages - p.messages) / NULLIF(p.messages, 0))::numeric, 2) AS messages_delta_pct,
    ROUND((100.0 * (c.fallbacks::numeric / NULLIF(c.messages, 0) - p.fallbacks::numeric / NULLIF(p.messages, 0)) * 100)::numeric, 2) AS fallback_rate_delta,
    ROUND((100.0 * (c.errors::numeric / NULLIF(c.messages, 0) - p.errors::numeric / NULLIF(p.messages, 0)) * 100)::numeric, 2) AS error_rate_delta,
    c.avg_response_ms - p.avg_response_ms AS avg_response_ms_delta
FROM current_week c, previous_week p
UNION ALL
SELECT
    'previous' AS period,
    p.messages,
    p.sessions,
    p.fallbacks,
    ROUND(100.0 * p.fallbacks / NULLIF(p.messages, 0), 2) AS fallback_rate_pct,
    p.errors,
    ROUND(100.0 * p.errors / NULLIF(p.messages, 0), 2) AS error_rate_pct,
    p.avg_response_ms,
    p.p95_response_ms,
    NULL, NULL, NULL, NULL
FROM previous_week p;

COMMENT ON VIEW v_weekly_comparison IS 'Confronto metriche settimana corrente vs precedente per trend analysis';

-- ----------------------------------------------------------------------------
-- 15. Alert Degradazione Performance
-- Rileva degradazioni significative nelle performance
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_degradation_alerts AS
WITH daily_metrics AS (
    SELECT
        DATE("when"::timestamp) AS day,
        intent,
        COUNT(*) AS requests,
        COUNT(*) FILTER (WHERE error IS NOT NULL) AS errors,
        ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / NULLIF(COUNT(*), 0), 2) AS error_rate_pct,
        ROUND(AVG(response_time_ms)) AS avg_response_ms,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) AS p95_response_ms
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '14 days'
      AND intent IS NOT NULL
      AND intent NOT IN ('greet', 'goodbye')
    GROUP BY DATE("when"::timestamp), intent
    HAVING COUNT(*) >= 3
),
baselines AS (
    SELECT
        intent,
        ROUND(AVG(error_rate_pct), 2) AS baseline_error_rate,
        ROUND(AVG(avg_response_ms)) AS baseline_avg_ms,
        ROUND(AVG(p95_response_ms)) AS baseline_p95_ms
    FROM daily_metrics
    WHERE day < NOW() - INTERVAL '3 days'  -- Baseline: prima degli ultimi 3 giorni
    GROUP BY intent
),
recent AS (
    SELECT
        intent,
        ROUND(AVG(error_rate_pct), 2) AS recent_error_rate,
        ROUND(AVG(avg_response_ms)) AS recent_avg_ms,
        ROUND(AVG(p95_response_ms)) AS recent_p95_ms,
        SUM(requests) AS recent_requests
    FROM daily_metrics
    WHERE day >= NOW() - INTERVAL '3 days'  -- Ultimi 3 giorni
    GROUP BY intent
)
SELECT
    r.intent,
    r.recent_requests,
    b.baseline_error_rate,
    r.recent_error_rate,
    r.recent_error_rate - b.baseline_error_rate AS error_rate_delta,
    b.baseline_avg_ms,
    r.recent_avg_ms,
    r.recent_avg_ms - b.baseline_avg_ms AS latency_delta_ms,
    CASE
        WHEN r.recent_error_rate > b.baseline_error_rate * 2 AND r.recent_error_rate > 5 THEN 'error_spike'
        WHEN r.recent_avg_ms > b.baseline_avg_ms * 1.5 AND r.recent_avg_ms > 1000 THEN 'latency_spike'
        WHEN r.recent_error_rate > b.baseline_error_rate + 10 THEN 'error_increase'
        WHEN r.recent_avg_ms > b.baseline_avg_ms + 500 THEN 'latency_increase'
        ELSE NULL
    END AS alert_type,
    CASE
        WHEN r.recent_error_rate > b.baseline_error_rate * 2 THEN 'critical'
        WHEN r.recent_avg_ms > b.baseline_avg_ms * 1.5 THEN 'high'
        WHEN r.recent_error_rate > b.baseline_error_rate + 10 THEN 'high'
        WHEN r.recent_avg_ms > b.baseline_avg_ms + 500 THEN 'medium'
        ELSE 'low'
    END AS severity
FROM recent r
JOIN baselines b ON r.intent = b.intent
WHERE (r.recent_error_rate > b.baseline_error_rate * 1.5 AND r.recent_error_rate > 3)
   OR (r.recent_avg_ms > b.baseline_avg_ms * 1.3 AND r.recent_avg_ms > 500)
ORDER BY
    CASE WHEN r.recent_error_rate > b.baseline_error_rate * 2 THEN 1 ELSE 2 END,
    r.recent_requests DESC;

COMMENT ON VIEW v_degradation_alerts IS 'Alert per degradazioni performance (error rate, latenza) rispetto a baseline';

-- ----------------------------------------------------------------------------
-- 16. User Intent Mining
-- Rileva bisogni utente non soddisfatti analizzando i fallback
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_unmet_user_needs AS
WITH fallback_analysis AS (
    SELECT
        ask,
        asl,
        session_id,
        "when",
        -- Estrai keyword principali
        LOWER(REGEXP_REPLACE(TRIM(ask), '[^a-zA-Zàèéìòùáéíóú ]', ' ', 'g')) AS clean_ask,
        -- Categorizza per topic
        CASE
            WHEN LOWER(ask) ~ '(come|cosa|quale|quando|perch[eé]|dove)' THEN 'question'
            WHEN LOWER(ask) ~ '(voglio|vorrei|posso|devo|serve)' THEN 'action_request'
            WHEN LOWER(ask) ~ '(errore|problema|non funziona|bug)' THEN 'issue_report'
            ELSE 'other'
        END AS request_type,
        -- Estrai verbo/azione principale
        CASE
            WHEN LOWER(ask) ~ 'vedere|visualizza|mostra|elenca|lista' THEN 'view_data'
            WHEN LOWER(ask) ~ 'cerca|trova|quali|dove' THEN 'search'
            WHEN LOWER(ask) ~ 'calcola|conta|quant|statistic' THEN 'analyze'
            WHEN LOWER(ask) ~ 'esporta|scarica|download|stampa' THEN 'export'
            WHEN LOWER(ask) ~ 'modifica|aggiorna|cambia|inserisci' THEN 'modify'
            WHEN LOWER(ask) ~ 'spiega|come|aiuto|help' THEN 'help'
            ELSE 'unknown'
        END AS action_type
    FROM chat_log
    WHERE "when"::timestamp >= NOW() - INTERVAL '30 days'
      AND intent = 'fallback'
      AND ask IS NOT NULL
      AND LENGTH(TRIM(ask)) > 10
)
SELECT
    request_type,
    action_type,
    COUNT(*) AS frequency,
    COUNT(DISTINCT session_id) AS unique_sessions,
    COUNT(DISTINCT asl) AS affected_asls,
    ARRAY_AGG(DISTINCT LEFT(ask, 100) ORDER BY LEFT(ask, 100)) FILTER (WHERE ask IS NOT NULL) AS sample_questions,
    -- Calcola priority score
    ROUND(
        (LOG(COUNT(*) + 1) *
        CASE request_type WHEN 'question' THEN 1.5 WHEN 'action_request' THEN 2.0 ELSE 1.0 END *
        CASE action_type WHEN 'view_data' THEN 1.5 WHEN 'search' THEN 1.3 ELSE 1.0 END)::numeric,
        2
    ) AS priority_score
FROM fallback_analysis
GROUP BY request_type, action_type
HAVING COUNT(*) >= 3
ORDER BY priority_score DESC, frequency DESC;

COMMENT ON VIEW v_unmet_user_needs IS 'Analisi bisogni utente non soddisfatti dai fallback per intent mining';

-- Indice aggiuntivo per ottimizzare le view dell'Intelligent Monitor
CREATE INDEX IF NOT EXISTS idx_chatlog_error ON chat_log(error) WHERE error IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chatlog_when_intent ON chat_log("when", intent);
