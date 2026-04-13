-- DEPRECATED: domande_risposte e' stata unificata in intent_examples.
-- Vedi sql/evolve_unify_intent_examples.sql per la migrazione.
--
-- create_domande_risposte.sql (legacy)
-- Tabella per raccogliere domande curate dall'utente (few-shot enrichment)
-- Idempotente: usa IF NOT EXISTS / DO $$ per riesecuzioni sicure
--
-- Workflow:
--   1. INSERT INTO domande_risposte (domanda, risposta, source) VALUES (...)
--   2. python scripts/sync_domande_risposte.py
--   3. scripts/server.sh restart

-- =============================================================================
-- 1. CREATE TABLE domande_risposte
-- =============================================================================

CREATE TABLE IF NOT EXISTS domande_risposte (
    id              SERIAL PRIMARY KEY,
    domanda         TEXT NOT NULL,
    risposta        TEXT,                               -- risposta attesa (documentazione)
    intent          VARCHAR(60) NOT NULL DEFAULT 'info_procedure',
    example_type    VARCHAR(30) NOT NULL DEFAULT 'few_shot',
    confused_with   VARCHAR(60),                        -- intent confondibile
    source          VARCHAR(100),                       -- fonte documento (es. "help_matrix_rev1.5.pdf")
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Constraint unicita' per idempotenza (stessa domanda + intent = stessa riga)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_domande_risposte_domanda_intent'
    ) THEN
        ALTER TABLE domande_risposte
            ADD CONSTRAINT uq_domande_risposte_domanda_intent
            UNIQUE (domanda, intent);
    END IF;
END $$;

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_domande_risposte_intent ON domande_risposte(intent);
CREATE INDEX IF NOT EXISTS idx_domande_risposte_active ON domande_risposte(active);

-- =============================================================================
-- 2. UPDATE intents - aggiorna titolo info_procedure
-- =============================================================================

UPDATE intents
SET title = 'Informazioni Procedure e Terminologia GISA',
    updated_at = NOW()
WHERE intent = 'info_procedure';
