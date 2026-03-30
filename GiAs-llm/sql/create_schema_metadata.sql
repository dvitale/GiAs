-- Schema Metadata per Schema-Aware LLM
-- Rende accessibili all'LLM i significati dei campi e le relazioni delle 7 tabelle applicative.

CREATE TABLE IF NOT EXISTS schema_metadata (
    table_key VARCHAR(60) PRIMARY KEY,       -- chiave logica (piani, masterlist, controlli, ...)
    table_name VARCHAR(100) NOT NULL,        -- nome tabella reale nel DB / DataFrame
    df_variable VARCHAR(60),                 -- nome variabile DataFrame in Python (piani_df, controlli_df, ...)
    description_it TEXT NOT NULL,            -- descrizione in italiano per il prompt LLM
    columns JSONB NOT NULL DEFAULT '[]',     -- [{name, type, description_it, filterable, sample_values}]
    relationships JSONB DEFAULT '[]',        -- [{target_table, source_col, target_col, description}]
    valid_values JSONB DEFAULT '{}',         -- {col_name: ["val1","val2",...]} per valori enumerabili
    pii_columns TEXT[] DEFAULT '{}',         -- colonne da escludere da query_data
    row_count_approx INTEGER,               -- cardinalità approssimativa
    is_active BOOLEAN DEFAULT TRUE,          -- flag per disabilitare senza cancellare
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════
-- POPOLAZIONE DATI - 7 tabelle applicative
-- ═══════════════════════════════════════════════════════════════════

-- 1. piani_monitoraggio (~730 righe)
INSERT INTO schema_metadata VALUES (
  'piani', 'piani_monitoraggio', 'piani_df',
  'Piani di controllo veterinario organizzati per sezione PRISCAV. Ogni piano ha un alias (codice) e indicatori specifici.',
  '[
    {"name":"sezione","type":"varchar","description_it":"Sezione PRISCAV (A-G)","filterable":true,"sample_values":["SEZIONE A","SEZIONE B","SEZIONE C"]},
    {"name":"alias_piano_attivita","type":"varchar","description_it":"Codice piano (A1, B2, C3, D1)","filterable":true,"sample_values":["A1","A22","B2","C3"]},
    {"name":"alias_indicatore","type":"varchar","description_it":"Codice indicatore specifico del piano","filterable":true,"sample_values":["A1_A","A22_B","B2_A"]},
    {"name":"descrizione_piano","type":"text","description_it":"Descrizione del piano di controllo","filterable":false},
    {"name":"descrizione_indicatore","type":"text","description_it":"Descrizione del sotto-piano/indicatore","filterable":false},
    {"name":"campionamento","type":"boolean","description_it":"True = prelievo campioni, False = controllo ufficiale","filterable":true},
    {"name":"tipo_piano_attivita","type":"varchar","description_it":"Tipo: piano o attivita","filterable":true,"sample_values":["piano","attivita"]}
  ]'::jsonb,
  '[{"target_table":"cu_eseguiti","source_col":"alias_indicatore","target_col":"alias_indicatore","description":"Indicatore nei controlli eseguiti"}]'::jsonb,
  '{"sezione":["SEZIONE A=Sicurezza Alimentare","SEZIONE B=Sanità Animale","SEZIONE C=Igiene Allevamenti","SEZIONE D=Alimentazione Animale","SEZIONE E=Farmacosorveglianza","SEZIONE F=Benessere Animale","SEZIONE G=Sottoprodotti"]}'::jsonb,
  '{}', 730, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name,
  df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it,
  columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships,
  valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns,
  row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();

-- 2. masterlist (~105K righe)
INSERT INTO schema_metadata VALUES (
  'masterlist', 'masterlist', 'attivita_df',
  'Tassonomia completa delle attività soggette a controllo veterinario. Ogni stabilimento è classificato per norma, macroarea, aggregazione e linea di attività.',
  '[
    {"name":"NORMA","type":"varchar","description_it":"Normativa di riferimento (Reg. CE 852, 853, etc.)","filterable":true},
    {"name":"MACROAREA","type":"varchar","description_it":"Macroarea di attività (es. Produzione alimenti, Allevamenti)","filterable":true},
    {"name":"AGGREGAZIONE","type":"varchar","description_it":"Aggregazione di attività (sottocategoria della macroarea)","filterable":true},
    {"name":"linea_di_attivita","type":"varchar","description_it":"Linea di attività specifica","filterable":true},
    {"name":"registrati","type":"integer","description_it":"Numero stabilimenti registrati","filterable":false},
    {"name":"riconosciuti","type":"integer","description_it":"Numero stabilimenti riconosciuti","filterable":false}
  ]'::jsonb,
  '[]'::jsonb,
  '{}'::jsonb,
  '{}', 105000, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name, df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it, columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships, valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns, row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();

-- 3. cu_eseguiti_nc (~3.2M righe)
INSERT INTO schema_metadata VALUES (
  'controlli', 'cu_eseguiti_nc', 'controlli_df',
  'Controlli ufficiali eseguiti nel 2025 con esito non conformità. Contiene dettagli su ASL, UOC, piano, macroarea, stabilimento, tipo e numero di non conformità rilevate, comune e coordinate. Alias piano/indicatore estratti in colonne dedicate.',
  '[
    {"name":"descrizione_asl","type":"varchar","description_it":"Nome ASL (es. NAPOLI 1 CENTRO, BENEVENTO)","filterable":true},
    {"name":"descrizione_uoc","type":"varchar","description_it":"Unità Operativa Complessa","filterable":true},
    {"name":"alias_piano_attivita","type":"varchar","description_it":"Sigla piano (es. A11, B2, C44)","filterable":true},
    {"name":"descrizione_piano","type":"varchar","description_it":"Descrizione del piano di controllo (senza sigla)","filterable":true},
    {"name":"alias_indicatore","type":"varchar","description_it":"Sigla indicatore (es. A11_A, ATT AO5_A)","filterable":true},
    {"name":"descrizione_indicatore","type":"varchar","description_it":"Descrizione indicatore piano (senza sigla)","filterable":true},
    {"name":"campionamento","type":"boolean","description_it":"True = prelievo campioni, False = controllo ufficiale","filterable":true},
    {"name":"tipo_piano_attivita","type":"varchar","description_it":"Tipo: piano o attivita","filterable":true},
    {"name":"macroarea_cu","type":"varchar","description_it":"Macroarea del controllo","filterable":true},
    {"name":"aggregazione_cu","type":"varchar","description_it":"Aggregazione del controllo","filterable":true},
    {"name":"attivita_cu","type":"varchar","description_it":"Linea di attività controllata","filterable":true},
    {"name":"sezione","type":"varchar","description_it":"Sezione PRISCAV del controllo","filterable":true},
    {"name":"data_inizio_controllo","type":"date","description_it":"Data inizio controllo","filterable":true},
    {"name":"id_controllo","type":"varchar","description_it":"Identificativo univoco del controllo ufficiale","filterable":true},
    {"name":"tipo_non_conformita","type":"varchar","description_it":"Tipo di non conformità rilevata (es. GRAVE, NON GRAVE, NESSUNA NC RILEVATA)","filterable":true},
    {"name":"numero_nc_gravi","type":"integer","description_it":"Numero di non conformità gravi rilevate nel controllo","filterable":false},
    {"name":"numero_nc_non_gravi","type":"integer","description_it":"Numero di non conformità non gravi rilevate nel controllo","filterable":false},
    {"name":"oggetto_non_conformita","type":"varchar","description_it":"Oggetto o categoria della non conformità rilevata","filterable":true},
    {"name":"comune","type":"varchar","description_it":"Comune dello stabilimento controllato","filterable":true},
    {"name":"num_riconoscimento","type":"varchar","description_it":"Numero riconoscimento stabilimento","filterable":true},
    {"name":"num_registrazione","type":"varchar","description_it":"Numero registrazione stabilimento (IT...)","filterable":false},
    {"name":"ragione_sociale","type":"varchar","description_it":"Ragione sociale dello stabilimento","filterable":false},
    {"name":"partita_iva","type":"varchar","description_it":"Partita IVA stabilimento","filterable":false},
    {"name":"latitudine_stab","type":"float","description_it":"Coordinata latitudine stabilimento","filterable":false},
    {"name":"longitudine_stab","type":"float","description_it":"Coordinata longitudine stabilimento","filterable":false}
  ]'::jsonb,
  '[
    {"target_table":"piani_monitoraggio","source_col":"alias_indicatore","target_col":"alias_indicatore","description":"Piano monitoraggio di riferimento"},
    {"target_table":"masterlist","source_col":"macroarea_cu","target_col":"macroarea","description":"Classificazione attività"}
  ]'::jsonb,
  '{}'::jsonb,
  '{"partita_iva","ragione_sociale","num_registrazione","codice_fiscale","nominativo_rappresentante"}',
  3200000, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name, df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it, columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships, valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns, row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();

-- 4. osa_mai_controllati (~643K righe)
INSERT INTO schema_metadata VALUES (
  'mai_controllati', 'osa_mai_controllati', 'osa_mai_controllati_df',
  'Stabilimenti (OSA) che non hanno mai ricevuto un controllo ufficiale. Utile per identificare priorità di ispezione.',
  '[
    {"name":"asl","type":"varchar","description_it":"Nome ASL","filterable":true},
    {"name":"comune","type":"varchar","description_it":"Comune dello stabilimento","filterable":true},
    {"name":"indirizzo","type":"varchar","description_it":"Indirizzo stabilimento","filterable":false},
    {"name":"macroarea","type":"varchar","description_it":"Macroarea di attività","filterable":true},
    {"name":"aggregazione","type":"varchar","description_it":"Aggregazione di attività","filterable":true},
    {"name":"attivita","type":"varchar","description_it":"Linea di attività","filterable":true},
    {"name":"num_riconoscimento","type":"varchar","description_it":"Numero riconoscimento stabilimento","filterable":true},
    {"name":"provincia_stab","type":"varchar","description_it":"Provincia stabilimento","filterable":true},
    {"name":"latitudine_stab","type":"float","description_it":"Coordinata latitudine stabilimento","filterable":false},
    {"name":"longitudine_stab","type":"float","description_it":"Coordinata longitudine stabilimento","filterable":false}
  ]'::jsonb,
  '[{"target_table":"masterlist","source_col":"macroarea","target_col":"macroarea","description":"Classificazione attività"}]'::jsonb,
  '{}'::jsonb,
  '{"partita_iva","codice_fiscale","codice_fiscale_rappresentante","nominativo_rappresentante","num_riconoscimento"}',
  643000, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name, df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it, columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships, valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns, row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();

-- 5. ocse_isp_semp (rimosso: sostituito da cu_eseguiti_nc che include le colonne NC)
-- INSERT INTO schema_metadata VALUES (
--   'nc_storiche', 'ocse_isp_semp', 'ocse_df', ...
-- ) -- RIMOSSO: tabella ocse_isp_semp non più utilizzata.
-- Le informazioni sulle non conformità sono ora in cu_eseguiti_nc
-- (colonne: tipo_non_conformita, numero_nc_gravi, numero_nc_non_gravi, oggetto_non_conformita).

-- 6. cu_diff_programmati_eseguiti (indicatori programmati vs eseguiti)
INSERT INTO schema_metadata VALUES (
  'programmazione', 'cu_diff_programmati_eseguiti', 'diff_prog_eseg_df',
  'Confronto tra controlli programmati e controlli eseguiti per indicatore, ASL, UOC e UOS. Base per calcolo ritardi.',
  '[
    {"name":"descrizione_asl","type":"varchar","description_it":"Nome ASL","filterable":true},
    {"name":"descrizione_uoc","type":"varchar","description_it":"Unità Operativa Complessa","filterable":true},
    {"name":"descrizione_uos","type":"varchar","description_it":"Unità Operativa Semplice","filterable":true},
    {"name":"alias_indicatore","type":"varchar","description_it":"Codice indicatore piano (es. A1_A)","filterable":true},
    {"name":"programmati","type":"integer","description_it":"Numero controlli programmati","filterable":false},
    {"name":"eseguiti","type":"integer","description_it":"Numero controlli eseguiti","filterable":false},
    {"name":"anno","type":"integer","description_it":"Anno di riferimento","filterable":true}
  ]'::jsonb,
  '[{"target_table":"piani_monitoraggio","source_col":"alias_indicatore","target_col":"alias_indicatore","description":"Piano monitoraggio di riferimento"}]'::jsonb,
  '{}'::jsonb,
  '{}', 10000, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name, df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it, columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships, valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns, row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();

-- 7. personale (~100K righe)
INSERT INTO schema_metadata VALUES (
  'personale', 'personale', 'personale_df',
  'Struttura organizzativa del personale ASL. Mappa utenti a ASL, UOC e UOS.',
  '[
    {"name":"user_id","type":"integer","description_it":"ID utente","filterable":true},
    {"name":"asl","type":"varchar","description_it":"Nome ASL di appartenenza","filterable":true},
    {"name":"descrizione_area_struttura_complessa","type":"varchar","description_it":"UOC di appartenenza","filterable":true},
    {"name":"descrizione","type":"varchar","description_it":"Gerarchia organizzativa completa","filterable":false}
  ]'::jsonb,
  '[]'::jsonb,
  '{}'::jsonb,
  '{"codice_fiscale","namefirst","namelast"}',
  100000, TRUE, NOW()
) ON CONFLICT (table_key) DO UPDATE SET
  table_name = EXCLUDED.table_name, df_variable = EXCLUDED.df_variable,
  description_it = EXCLUDED.description_it, columns = EXCLUDED.columns,
  relationships = EXCLUDED.relationships, valid_values = EXCLUDED.valid_values,
  pii_columns = EXCLUDED.pii_columns, row_count_approx = EXCLUDED.row_count_approx,
  updated_at = NOW();
