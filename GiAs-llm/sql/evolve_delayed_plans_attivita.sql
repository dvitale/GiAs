-- Migration: "attività in ritardo" → ask_delayed_plans
-- Fix: "attività in ritardo" veniva classificato come check_if_plan_delayed

-- 1. Aggiungi keyword "attività in ritardo" a ask_delayed_plans
UPDATE intents SET keywords = array_append(keywords, 'attività in ritardo')
WHERE intent = 'ask_delayed_plans'
  AND NOT ('attività in ritardo' = ANY(keywords));

UPDATE intents SET keywords = array_append(keywords, 'attività scadute')
WHERE intent = 'ask_delayed_plans'
  AND NOT ('attività scadute' = ANY(keywords));

-- 2. Aggiorna llm_description per menzionare attività
UPDATE intents SET llm_description = 'analisi dei piani o attività in ritardo'
WHERE intent = 'ask_delayed_plans';

-- 3. Aggiorna anaphora_context
UPDATE intents SET anaphora_context = 'piani/attività in ritardo'
WHERE intent = 'ask_delayed_plans';

-- 4. Aggiungi few-shot examples per "attività in ritardo"
INSERT INTO intent_examples (intent, text, example_type, display_order) VALUES
('ask_delayed_plans', 'attività in ritardo', 'prompt_critical', 10),
('ask_delayed_plans', 'quali attività sono in ritardo', 'few_shot', 11),
('ask_delayed_plans', 'attività scadute', 'few_shot', 12)
ON CONFLICT DO NOTHING;
