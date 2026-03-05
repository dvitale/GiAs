-- evolve_intents_schema.sql
-- Evoluzione tabella intents come single source of truth
-- Aggiunge colonne mancanti, crea tabella intent_examples e vista di controllo
-- Idempotente: usa IF NOT EXISTS / IF EXISTS per riesecuzioni sicure

-- =============================================================================
-- 1. ALTER TABLE intents - aggiungere colonne mancanti da INTENT_REGISTRY
-- =============================================================================

ALTER TABLE intents ADD COLUMN IF NOT EXISTS category VARCHAR(60);
ALTER TABLE intents ADD COLUMN IF NOT EXISTS emoji VARCHAR(10) DEFAULT '📋';
ALTER TABLE intents ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';
ALTER TABLE intents ADD COLUMN IF NOT EXISTS context_keywords TEXT[] DEFAULT '{}';
ALTER TABLE intents ADD COLUMN IF NOT EXISTS negative_keywords TEXT[] DEFAULT '{}';
ALTER TABLE intents ADD COLUMN IF NOT EXISTS is_direct_response BOOLEAN DEFAULT FALSE;
ALTER TABLE intents ADD COLUMN IF NOT EXISTS disambiguation_rules JSONB DEFAULT '[]';
ALTER TABLE intents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- =============================================================================
-- 2. CREATE TABLE intent_examples (esempi multipli tipizzati)
-- =============================================================================

CREATE TABLE IF NOT EXISTS intent_examples (
    id SERIAL PRIMARY KEY,
    intent VARCHAR(60) NOT NULL REFERENCES intents(intent) ON DELETE CASCADE,
    text TEXT NOT NULL,
    example_type VARCHAR(30) NOT NULL DEFAULT 'few_shot',
    -- Tipi:
    --   'few_shot'         : esempi generali training (da INTENT_REGISTRY.examples)
    --   'prompt_critical'  : iniettati nel CLASSIFICATION_SYSTEM_PROMPT
    --   'disambiguation'   : coppie confuse per training disambiguazione
    --   'variation'        : variazioni linguistiche per coverage
    --   'help'             : mostrati nel help_tool
    expected_json JSONB,           -- risposta JSON attesa (per prompt_critical)
    confused_with VARCHAR(60),     -- intent confondibile (per disambiguation)
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_intent_examples_intent ON intent_examples(intent);
CREATE INDEX IF NOT EXISTS idx_intent_examples_type ON intent_examples(example_type);

-- Constraint unicità per idempotenza INSERT ... ON CONFLICT
-- (stesso intent + testo + tipo = stesso esempio)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_intent_examples_intent_text_type'
    ) THEN
        ALTER TABLE intent_examples
            ADD CONSTRAINT uq_intent_examples_intent_text_type
            UNIQUE (intent, text, example_type);
    END IF;
END $$;

-- =============================================================================
-- 3. Vista di controllo per conteggi esempi per intent
-- =============================================================================

CREATE OR REPLACE VIEW v_intent_example_counts AS
SELECT
    i.intent,
    i.title,
    i.category,
    COUNT(e.id) AS total_examples,
    COUNT(e.id) FILTER (WHERE e.example_type = 'few_shot') AS few_shot_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'prompt_critical') AS prompt_critical_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'disambiguation') AS disambiguation_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'variation') AS variation_count,
    COUNT(e.id) FILTER (WHERE e.example_type = 'help') AS help_count
FROM intents i
LEFT JOIN intent_examples e ON i.intent = e.intent
GROUP BY i.intent, i.title, i.category
ORDER BY i.section_number;
