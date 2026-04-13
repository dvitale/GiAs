-- evolve_unify_intent_examples.sql
-- Unifica domande_risposte in intent_examples (single source of truth)
-- Idempotente: usa IF NOT EXISTS / IF EXISTS per riesecuzioni sicure
--
-- Workflow post-migrazione:
--   INSERT INTO intent_examples (text, intent, ...) VALUES (...)
--   POST /api/admin/domande-rag/reindex   (oppure python tools/indexing/build_intent_examples_index.py)
--   scripts/server.sh restart

-- =============================================================================
-- 1. ALTER TABLE intent_examples — aggiungere colonne da domande_risposte
-- =============================================================================

ALTER TABLE intent_examples ADD COLUMN IF NOT EXISTS risposta TEXT;
ALTER TABLE intent_examples ADD COLUMN IF NOT EXISTS source VARCHAR(100);
ALTER TABLE intent_examples ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE intent_examples ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE intent_examples ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Indice per query admin filtrate per active
CREATE INDEX IF NOT EXISTS idx_intent_examples_active ON intent_examples(active);

-- =============================================================================
-- 2. Migra dati da domande_risposte → intent_examples
--    ON CONFLICT DO UPDATE per arricchire record gia' sincronizzati
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'domande_risposte') THEN
        INSERT INTO intent_examples (intent, text, example_type, confused_with, risposta, source, active, notes, updated_at)
        SELECT
            intent,
            domanda,
            example_type,
            confused_with,
            risposta,
            source,
            active,
            notes,
            COALESCE(updated_at, created_at)
        FROM domande_risposte
        ON CONFLICT (intent, text, example_type) DO UPDATE SET
            risposta   = COALESCE(EXCLUDED.risposta, intent_examples.risposta),
            source     = COALESCE(EXCLUDED.source, intent_examples.source),
            active     = EXCLUDED.active,
            notes      = COALESCE(EXCLUDED.notes, intent_examples.notes),
            updated_at = EXCLUDED.updated_at;

        RAISE NOTICE 'Migrati record da domande_risposte → intent_examples';
    END IF;
END $$;

-- =============================================================================
-- 3. Aggiorna vista conteggi — filtra solo active = TRUE
-- =============================================================================

CREATE OR REPLACE VIEW v_intent_example_counts AS
SELECT
    i.intent,
    i.title,
    i.category,
    COUNT(e.id) FILTER (WHERE e.active = TRUE) AS total_examples,
    COUNT(e.id) FILTER (WHERE e.example_type = 'few_shot' AND e.active = TRUE) AS few_shot_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'prompt_critical' AND e.active = TRUE) AS prompt_critical_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'disambiguation' AND e.active = TRUE) AS disambiguation_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'variation' AND e.active = TRUE) AS variation_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'help' AND e.active = TRUE) AS help_count
FROM intents i
LEFT JOIN intent_examples e ON i.intent = e.intent
GROUP BY i.intent, i.title, i.category
ORDER BY i.section_number;

-- =============================================================================
-- 4. Rinomina vecchia tabella (safety net per rollback)
--    DROP dopo periodo di validazione
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'domande_risposte')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'domande_risposte_deprecated')
    THEN
        ALTER TABLE domande_risposte RENAME TO domande_risposte_deprecated;
        RAISE NOTICE 'Tabella domande_risposte rinominata a domande_risposte_deprecated';
    END IF;
END $$;
