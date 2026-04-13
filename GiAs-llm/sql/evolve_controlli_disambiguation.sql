-- Evoluzione: disambiguazione "controlli fatti per [codice]"
-- Aggiorna prompt_critical examples per riflettere l'ambiguità
-- tra ask_piano_stabilimenti e ask_piano_statistics

-- Aggiorna l'esempio "controlli eseguiti per attività B47" per includere alternatives
UPDATE intent_examples
SET expected_json = '{"reasoning":"controlli per attività specifica B47 - ambiguo tra stabilimenti e statistiche","intent":"ask_piano_stabilimenti","slots":{"piano_code":"ATT B47"},"needs_clarification":false,"confidence":0.65,"alternatives":[{"intent":"ask_piano_statistics","confidence":0.55}]}'
WHERE intent = 'ask_piano_stabilimenti'
  AND text = 'controlli eseguiti per l''attività B47'
  AND example_type = 'prompt_critical';

-- Aggiorna "controlli per il piano A1" → disambiguazione
UPDATE intent_examples
SET expected_json = '{"reasoning":"controlli per piano specifico A1 - ambiguo tra stabilimenti e statistiche","intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.65,"alternatives":[{"intent":"ask_piano_statistics","confidence":0.55}]}'
WHERE intent = 'ask_piano_stabilimenti'
  AND text = 'controlli per il piano A1'
  AND example_type = 'prompt_critical';

-- Aggiungi esempi espliciti NON ambigui (per training LLM)
INSERT INTO intent_examples (intent, text, example_type, expected_json, display_order)
VALUES
('ask_piano_stabilimenti',
 'quali stabilimenti sono stati controllati per il piano A1',
 'prompt_critical',
 '{"reasoning":"chiede esplicitamente stabilimenti controllati","intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.90}',
 5),
('ask_piano_statistics',
 'quanti controlli sono stati fatti per AO1',
 'prompt_critical',
 '{"reasoning":"chiede conteggio/statistiche controlli","intent":"ask_piano_statistics","slots":{"piano_code":"AO1"},"needs_clarification":false,"confidence":0.90}',
 5)
ON CONFLICT (intent, text, example_type) DO NOTHING;

-- Aggiungi esempio disambiguation per training
INSERT INTO intent_examples (intent, text, example_type, confused_with, display_order)
VALUES
('ask_piano_stabilimenti',
 'controlli fatti per AO1',
 'disambiguation',
 'ask_piano_statistics',
 1),
('ask_piano_statistics',
 'controlli fatti per AO1',
 'disambiguation',
 'ask_piano_stabilimenti',
 1)
ON CONFLICT (intent, text, example_type) DO NOTHING;
