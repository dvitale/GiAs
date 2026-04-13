-- evolve_cu_statistics_intent.sql
-- Aggiunge intent ask_cu_statistics per conteggio controlli eseguiti/programmati
-- Idempotente: usa ON CONFLICT DO NOTHING

-- =============================================================================
-- 1. INSERT intent
-- =============================================================================

INSERT INTO intents (
    intent, section_number, title, category, emoji,
    graph_node, required_slots, two_phase_threshold,
    self_sufficient, is_direct_response, followup_excluded,
    keywords, context_keywords, negative_keywords
) VALUES (
    'ask_cu_statistics',
    (SELECT COALESCE(MAX(section_number), 0) + 1 FROM intents),
    'Statistiche Controlli',
    'Ritardi e Monitoraggio',
    '📊',
    'cu_statistics_tool',
    '[]',
    NULL,
    true,
    false,
    false,
    ARRAY['controlli eseguiti', 'controlli fatti', 'controlli totali', 'quanti controlli', 'numero controlli', 'controlli programmati'],
    ARRAY['anno', 'asl', 'macroarea', 'piano'],
    ARRAY['stabilimenti', 'ritardo', 'priorità', 'rischio', 'elenco', 'lista']
) ON CONFLICT (intent) DO NOTHING;

-- =============================================================================
-- 2. INSERT intent_examples (few-shot + disambiguation)
-- =============================================================================

INSERT INTO intent_examples (intent, text, example_type, expected_json, display_order) VALUES
('ask_cu_statistics', 'controlli eseguiti per il piano AO1', 'prompt_critical',
 '{"reasoning":"conteggio controlli eseguiti filtrato per piano","intent":"ask_cu_statistics","slots":{"piano_code":"AO1","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}', 1),
('ask_cu_statistics', 'controlli totali eseguiti quest''anno', 'prompt_critical',
 '{"reasoning":"conteggio totale controlli anno corrente","intent":"ask_cu_statistics","slots":{"tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}', 2),
('ask_cu_statistics', 'controlli eseguiti dalla mia ASL nel 2025 per il piano A22', 'prompt_critical',
 '{"reasoning":"conteggio controlli con filtro piano+ASL+anno","intent":"ask_cu_statistics","slots":{"piano_code":"A22","anno":2025,"tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.95}', 3),
('ask_cu_statistics', 'controlli eseguiti per il benessere animale', 'prompt_critical',
 '{"reasoning":"conteggio controlli filtrato per macroarea","intent":"ask_cu_statistics","slots":{"macroarea":"BENESSERE ANIMALE","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}', 4),
('ask_cu_statistics', 'controlli programmati per il 2026', 'prompt_critical',
 '{"reasoning":"somma controlli programmati per anno","intent":"ask_cu_statistics","slots":{"anno":2026,"tipo_conteggio":"programmati"},"needs_clarification":false,"confidence":0.90}', 5),
('ask_cu_statistics', 'quanti controlli sono stati eseguiti nell''ASL Benevento?', 'prompt_critical',
 '{"reasoning":"conteggio controlli per ASL","intent":"ask_cu_statistics","slots":{"asl":"BENEVENTO","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}', 6),
('ask_cu_statistics', 'quanti controlli ha fatto l''ASL Napoli nel 2025?', 'prompt_critical',
 '{"reasoning":"conteggio controlli ASL+anno","intent":"ask_cu_statistics","slots":{"asl":"NAPOLI","anno":2025,"tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}', 7)
ON CONFLICT (intent, text, example_type) DO NOTHING;

-- Esempi help (domande suggerite)
INSERT INTO intent_examples (intent, text, example_type, display_order) VALUES
('ask_cu_statistics', 'Quanti controlli sono stati eseguiti?', 'help', 1),
('ask_cu_statistics', 'Controlli programmati per il 2026', 'help', 2)
ON CONFLICT (intent, text, example_type) DO NOTHING;

-- Esempi disambiguation (vs query_data e ask_piano_statistics)
INSERT INTO intent_examples (intent, text, example_type, confused_with, display_order) VALUES
('ask_cu_statistics', 'quanti controlli nell''ASL Benevento', 'disambiguation', 'query_data', 1),
('ask_cu_statistics', 'quanti controlli per il piano A1', 'disambiguation', 'ask_piano_statistics', 2),
('query_data', 'distribuzione NC per macroarea', 'disambiguation', 'ask_cu_statistics', 10),
('ask_piano_statistics', 'statistiche dei piani di controllo', 'disambiguation', 'ask_cu_statistics', 10)
ON CONFLICT (intent, text, example_type) DO NOTHING;
