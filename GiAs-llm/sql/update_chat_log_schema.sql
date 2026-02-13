-- Aggiornamento schema tabella chat_log
-- Aggiunge nuovi campi per tracking esteso delle conversazioni
-- Eseguire su database gias_db

\c gias_db;

-- ==============================================================================
-- 1. AGGIUNTA NUOVE COLONNE (idempotente con IF NOT EXISTS via DO block)
-- ==============================================================================

DO $$
BEGIN
    -- session_id: identificativo sessione per tracking multi-turno
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_log' AND column_name = 'session_id') THEN
        ALTER TABLE chat_log ADD COLUMN session_id VARCHAR(100);
        RAISE NOTICE 'Colonna session_id aggiunta';
    END IF;

    -- asl: ASL dell'utente per analisi territoriali
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_log' AND column_name = 'asl') THEN
        ALTER TABLE chat_log ADD COLUMN asl VARCHAR(100);
        RAISE NOTICE 'Colonna asl aggiunta';
    END IF;

    -- slots: parametri estratti (JSONB per query flessibili)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_log' AND column_name = 'slots') THEN
        ALTER TABLE chat_log ADD COLUMN slots JSONB;
        RAISE NOTICE 'Colonna slots aggiunta';
    END IF;

    -- response_time_ms: tempo di risposta in millisecondi
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_log' AND column_name = 'response_time_ms') THEN
        ALTER TABLE chat_log ADD COLUMN response_time_ms INTEGER;
        RAISE NOTICE 'Colonna response_time_ms aggiunta';
    END IF;

    -- error: messaggio di errore separato dalla risposta
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'chat_log' AND column_name = 'error') THEN
        ALTER TABLE chat_log ADD COLUMN error TEXT;
        RAISE NOTICE 'Colonna error aggiunta';
    END IF;
END $$;

-- ==============================================================================
-- 2. INDICI PER QUERY FREQUENTI
-- ==============================================================================

-- Indice su session_id per raggruppare conversazioni
CREATE INDEX IF NOT EXISTS idx_chatlog_session_id ON chat_log(session_id);

-- Indice su asl per analisi territoriali
CREATE INDEX IF NOT EXISTS idx_chatlog_asl ON chat_log(asl);

-- Indice su intent per statistiche di utilizzo
CREATE INDEX IF NOT EXISTS idx_chatlog_intent ON chat_log(intent);

-- Indice su when per query temporali (se non esiste)
CREATE INDEX IF NOT EXISTS idx_chatlog_when ON chat_log("when");

-- Indice composito per analisi per ASL e periodo
CREATE INDEX IF NOT EXISTS idx_chatlog_asl_when ON chat_log(asl, "when");

-- Indice su error per trovare conversazioni problematiche
CREATE INDEX IF NOT EXISTS idx_chatlog_error ON chat_log(error) WHERE error IS NOT NULL;

-- Indice GIN su slots per query JSONB
CREATE INDEX IF NOT EXISTS idx_chatlog_slots ON chat_log USING GIN (slots);

-- ==============================================================================
-- 3. VIEW PER CONSULTAZIONE RAPIDA
-- ==============================================================================

-- Vista: statistiche giornaliere per ASL e intent
CREATE OR REPLACE VIEW v_chat_stats_daily AS
SELECT
    DATE("when") AS giorno,
    asl,
    intent,
    COUNT(*) AS num_conversazioni,
    ROUND(AVG(response_time_ms)) AS tempo_medio_ms,
    COUNT(*) FILTER (WHERE error IS NOT NULL) AS num_errori,
    COUNT(*) FILTER (WHERE two_phase_resp = true) AS num_two_phase
FROM chat_log
WHERE "when" IS NOT NULL
GROUP BY DATE("when"), asl, intent
ORDER BY giorno DESC, num_conversazioni DESC;

-- Vista: ultimi 100 messaggi per debug rapido
CREATE OR REPLACE VIEW v_chat_recent AS
SELECT
    id,
    "when" AS timestamp,
    session_id,
    asl,
    who,
    ask,
    intent,
    slots::text AS slots_json,
    LEFT(answer, 300) AS answer_preview,
    response_time_ms,
    error
FROM chat_log
ORDER BY "when" DESC NULLS LAST, id DESC
LIMIT 100;

-- Vista: top intent per ASL (ultimo mese)
CREATE OR REPLACE VIEW v_top_intents_by_asl AS
SELECT
    asl,
    intent,
    COUNT(*) AS utilizzi,
    ROUND(AVG(response_time_ms)) AS tempo_medio_ms,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / COUNT(*), 2) AS pct_errori
FROM chat_log
WHERE "when" >= NOW() - INTERVAL '30 days'
GROUP BY asl, intent
ORDER BY asl, utilizzi DESC;

-- Vista: conversazioni con errori (per troubleshooting)
CREATE OR REPLACE VIEW v_chat_errors AS
SELECT
    id,
    "when" AS timestamp,
    session_id,
    asl,
    ask,
    intent,
    error,
    response_time_ms
FROM chat_log
WHERE error IS NOT NULL
ORDER BY "when" DESC NULLS LAST, id DESC;

-- Vista: performance per intent (ultimi 7 giorni)
CREATE OR REPLACE VIEW v_intent_performance AS
SELECT
    intent,
    COUNT(*) AS totale,
    ROUND(AVG(response_time_ms)) AS avg_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS p50_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) AS p95_ms,
    MAX(response_time_ms) AS max_ms,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / COUNT(*), 2) AS pct_errori
FROM chat_log
WHERE "when" >= NOW() - INTERVAL '7 days'
  AND response_time_ms IS NOT NULL
GROUP BY intent
ORDER BY totale DESC;

-- Vista: utilizzo per fascia oraria (analisi carico)
CREATE OR REPLACE VIEW v_chat_by_hour AS
SELECT
    EXTRACT(HOUR FROM "when") AS ora,
    COUNT(*) AS messaggi,
    ROUND(AVG(response_time_ms)) AS tempo_medio_ms
FROM chat_log
WHERE "when" >= NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM "when")
ORDER BY ora;

-- Vista: riepilogo sessioni multi-turno
CREATE OR REPLACE VIEW v_session_summary AS
SELECT
    session_id,
    asl,
    MIN("when") AS inizio_sessione,
    MAX("when") AS fine_sessione,
    COUNT(*) AS num_messaggi,
    COUNT(DISTINCT intent) AS intents_diversi,
    ARRAY_AGG(DISTINCT intent) AS intents_usati,
    COUNT(*) FILTER (WHERE error IS NOT NULL) AS errori
FROM chat_log
WHERE session_id IS NOT NULL
GROUP BY session_id, asl
ORDER BY fine_sessione DESC NULLS LAST;

-- ==============================================================================
-- 4. COMMENTI SULLE COLONNE
-- ==============================================================================

COMMENT ON COLUMN chat_log.session_id IS 'Identificativo sessione per tracking conversazioni multi-turno';
COMMENT ON COLUMN chat_log.asl IS 'ASL dell''utente per analisi territoriali';
COMMENT ON COLUMN chat_log.slots IS 'Parametri estratti dalla domanda (JSON): piano_code, asl, topic, etc.';
COMMENT ON COLUMN chat_log.response_time_ms IS 'Tempo totale di elaborazione in millisecondi';
COMMENT ON COLUMN chat_log.error IS 'Messaggio di errore se la richiesta ha fallito (NULL = successo)';

-- ==============================================================================
-- 5. VERIFICA FINALE
-- ==============================================================================

-- Mostra struttura aggiornata della tabella
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_log'
ORDER BY ordinal_position;

-- Conta record esistenti
SELECT COUNT(*) AS total_records FROM chat_log;
