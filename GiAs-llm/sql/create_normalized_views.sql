-- Normalizzazione schema piani/indicatori
-- Le tabelle originali sono in schema "old". Le nuove tabelle in "public"
-- hanno colonne canoniche e campi arricchiti da piani_monitoraggio.
--
-- Schema canonico:
--   sezione | alias_piano_attivita | descrizione_piano | alias_indicatore
--   descrizione_indicatore | tipo_piano_attivita | campionamento

-- Prerequisito: CREATE SCHEMA IF NOT EXISTS old;
-- Le tabelle originali devono essere gia' in old.

-- 1. piani_monitoraggio — colonne rinominate
CREATE TABLE piani_monitoraggio AS
SELECT
    id,
    sezione,
    alias AS alias_piano_attivita,
    descrizione AS descrizione_piano,
    alias_indicatore,
    descrizione_2 AS descrizione_indicatore,
    campionamento,
    CASE WHEN is_attivita THEN 'attivita' ELSE 'piano' END AS tipo_piano_attivita
FROM old.piani_monitoraggio;

-- 2. cu_eseguiti_nc — arricchita con campionamento e tipo da piani
CREATE TABLE cu_eseguiti_nc AS
SELECT
    c.*,
    p.campionamento,
    p.tipo_piano_attivita
FROM old.cu_eseguiti_nc c
LEFT JOIN (
    SELECT DISTINCT ON (alias_indicatore)
        alias_indicatore, campionamento,
        CASE WHEN is_attivita THEN 'attivita' ELSE 'piano' END AS tipo_piano_attivita
    FROM old.piani_monitoraggio
    ORDER BY alias_indicatore, id
) p ON p.alias_indicatore = c.alias_indicatore;

-- 3. cu_diff_programmati_eseguiti — indicatore rinominato + campi arricchiti
CREATE TABLE cu_diff_programmati_eseguiti AS
SELECT
    d.id,
    d.indicatore AS alias_indicatore,
    d.descrizione_indicatore,
    d.descrizione_asl,
    d.descrizione_uoc,
    d.descrizione_uos,
    d.programmati,
    d.eseguiti,
    d.anno,
    p.sezione,
    p.alias_piano_attivita,
    p.descrizione_piano,
    p.tipo_piano_attivita,
    p.campionamento
FROM old.cu_diff_programmati_eseguiti d
LEFT JOIN (
    SELECT DISTINCT ON (alias_indicatore)
        alias_indicatore, sezione,
        alias AS alias_piano_attivita,
        descrizione AS descrizione_piano,
        campionamento,
        CASE WHEN is_attivita THEN 'attivita' ELSE 'piano' END AS tipo_piano_attivita
    FROM old.piani_monitoraggio
    ORDER BY alias_indicatore, id
) p ON p.alias_indicatore = d.indicatore;

-- 4. Tabella per indicatori orfani (non presenti in piani_monitoraggio)
CREATE TABLE IF NOT EXISTS indicatori_non_catalogati (
    alias_indicatore VARCHAR PRIMARY KEY,
    descrizione_indicatore TEXT,
    fonte VARCHAR NOT NULL,
    data_rilevamento TIMESTAMP DEFAULT NOW()
);
