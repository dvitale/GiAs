-- Migration: aggiunge colonne UX conversazionale alla tabella intents
-- llm_description: descrizione intent per prompt LLM (ex INTENT_DESCRIPTIONS)
-- anaphora_context: contesto breve per risoluzione anaforica (ex intent_context)
-- intro_phrases: frasi intro randomizzate per framing conversazionale (ex _INTROS)

ALTER TABLE intents ADD COLUMN IF NOT EXISTS llm_description VARCHAR(200);
ALTER TABLE intents ADD COLUMN IF NOT EXISTS anaphora_context VARCHAR(60);
ALTER TABLE intents ADD COLUMN IF NOT EXISTS intro_phrases TEXT[] DEFAULT '{}';

-- Popola llm_description (da INTENT_DESCRIPTIONS in response_node.py)
UPDATE intents SET llm_description = 'descrizione di un piano di controllo veterinario' WHERE intent = 'ask_piano_description';
UPDATE intents SET llm_description = 'analisi degli stabilimenti controllati per un piano' WHERE intent = 'ask_piano_stabilimenti';
UPDATE intents SET llm_description = 'statistiche aggregate sui piani di controllo eseguiti' WHERE intent = 'ask_piano_statistics';
UPDATE intents SET llm_description = 'ricerca di piani per argomento' WHERE intent = 'search_piani_by_topic';
UPDATE intents SET llm_description = 'stabilimenti prioritari da controllare secondo programmazione' WHERE intent = 'ask_priority_establishment';
UPDATE intents SET llm_description = 'stabilimenti prioritari basati sul rischio storico' WHERE intent = 'ask_risk_based_priority';
UPDATE intents SET llm_description = 'suggerimenti per controlli di stabilimenti mai ispezionati' WHERE intent = 'ask_suggest_controls';
UPDATE intents SET llm_description = 'analisi dei piani in ritardo' WHERE intent = 'ask_delayed_plans';
UPDATE intents SET llm_description = 'verifica se un piano specifico e'' in ritardo' WHERE intent = 'check_if_plan_delayed';
UPDATE intents SET llm_description = 'storico controlli e NC per stabilimento' WHERE intent = 'ask_establishment_history';
UPDATE intents SET llm_description = 'top attivita'' con risk score piu'' elevato' WHERE intent = 'ask_top_risk_activities';
UPDATE intents SET llm_description = 'informazioni sulle funzionalita'' disponibili' WHERE intent = 'ask_help';
UPDATE intents SET llm_description = 'informazioni su procedure operative da documentazione' WHERE intent = 'info_procedure';
UPDATE intents SET llm_description = 'interrogazione dati su misura' WHERE intent = 'query_data';

-- Popola anaphora_context (da intent_context in response_node.py)
UPDATE intents SET anaphora_context = 'descrizione piano' WHERE intent = 'ask_piano_description';
UPDATE intents SET anaphora_context = 'stabilimenti piano' WHERE intent = 'ask_piano_stabilimenti';
UPDATE intents SET anaphora_context = 'statistiche piani' WHERE intent = 'ask_piano_statistics';
UPDATE intents SET anaphora_context = 'ricerca piani' WHERE intent = 'search_piani_by_topic';
UPDATE intents SET anaphora_context = 'piani in ritardo' WHERE intent = 'ask_delayed_plans';
UPDATE intents SET anaphora_context = 'verifica ritardo piano' WHERE intent = 'check_if_plan_delayed';
UPDATE intents SET anaphora_context = 'stabilimenti prioritari' WHERE intent = 'ask_priority_establishment';
UPDATE intents SET anaphora_context = 'priorita'' rischio' WHERE intent = 'ask_risk_based_priority';
UPDATE intents SET anaphora_context = 'suggerimenti controlli' WHERE intent = 'ask_suggest_controls';
UPDATE intents SET anaphora_context = 'storico stabilimento' WHERE intent = 'ask_establishment_history';
UPDATE intents SET anaphora_context = 'top rischio' WHERE intent = 'ask_top_risk_activities';

-- Popola intro_phrases (da _INTROS in conversational_framing.py)
UPDATE intents SET intro_phrases = ARRAY['Ecco le informazioni sul piano che cerchi.', 'Ho recuperato i dettagli del piano.'] WHERE intent = 'ask_piano_description';
UPDATE intents SET intro_phrases = ARRAY['Ecco gli stabilimenti coinvolti.', 'Ho trovato gli stabilimenti associati al piano.'] WHERE intent = 'ask_piano_stabilimenti';
UPDATE intents SET intro_phrases = ARRAY['Ecco le statistiche che hai richiesto.', 'Ho elaborato i dati statistici.'] WHERE intent = 'ask_piano_statistics';
UPDATE intents SET intro_phrases = ARRAY['Ecco i piani che ho trovato.', 'Ho cercato nei piani di monitoraggio.'] WHERE intent = 'search_piani_by_topic';
UPDATE intents SET intro_phrases = ARRAY['Ho analizzato la situazione dei ritardi.', 'Ecco il quadro dei piani in ritardo.'] WHERE intent = 'ask_delayed_plans';
UPDATE intents SET intro_phrases = ARRAY['Ho verificato lo stato del piano.', 'Ecco cosa risulta per questo piano.'] WHERE intent = 'check_if_plan_delayed';
UPDATE intents SET intro_phrases = ARRAY['Ho calcolato le priorita'' di controllo.', 'Ecco gli stabilimenti su cui concentrare l''attenzione.'] WHERE intent = 'ask_priority_establishment';
UPDATE intents SET intro_phrases = ARRAY['Ho analizzato il rischio storico.', 'Ecco la classifica basata sul rischio.'] WHERE intent = 'ask_risk_based_priority';
UPDATE intents SET intro_phrases = ARRAY['Ecco i controlli che ti suggerisco.', 'Ho elaborato dei suggerimenti per te.'] WHERE intent = 'ask_suggest_controls';
UPDATE intents SET intro_phrases = ARRAY['Ho cercato gli stabilimenti nelle vicinanze.', 'Ecco cosa c''e'' nella tua zona.'] WHERE intent = 'ask_nearby_priority';
UPDATE intents SET intro_phrases = ARRAY['Ho recuperato lo storico dello stabilimento.', 'Ecco il quadro dei controlli per questo stabilimento.'] WHERE intent = 'ask_establishment_history';
UPDATE intents SET intro_phrases = ARRAY['Ho analizzato le attivita'' a rischio.', 'Ecco le linee di attivita'' piu'' critiche.'] WHERE intent = 'ask_top_risk_activities';
UPDATE intents SET intro_phrases = ARRAY['Ho trovato le informazioni sulla procedura.', 'Ecco cosa prevede la procedura.'] WHERE intent = 'info_procedure';
UPDATE intents SET intro_phrases = ARRAY['Ecco il risultato della tua ricerca.', 'Ho interrogato i dati.'] WHERE intent = 'query_data';
