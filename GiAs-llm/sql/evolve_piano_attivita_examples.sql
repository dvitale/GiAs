-- Migration: aggiunge esempi classificazione per disambiguare piano/attivita
-- Risolve: "controlli per l'attività B47" classificato come query_data invece di ask_piano_stabilimenti

INSERT INTO intent_examples (intent, text, example_type, expected_json, display_order) VALUES
('ask_piano_stabilimenti', 'controlli eseguiti per l''attività B47', 'prompt_critical',
 '{"reasoning":"controlli per attività specifica B47","intent":"ask_piano_stabilimenti","slots":{"piano_code":"ATT B47"},"needs_clarification":false,"confidence":0.90}',
 3),
('ask_piano_stabilimenti', 'controlli per il piano A1', 'prompt_critical',
 '{"reasoning":"controlli per piano specifico A1","intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.90}',
 4),
('ask_piano_stabilimenti', 'controlli per l''attività B5', 'few_shot', NULL, 5),
('ask_piano_stabilimenti', 'controlli eseguiti per attività AO5', 'few_shot', NULL, 6)
ON CONFLICT DO NOTHING;
