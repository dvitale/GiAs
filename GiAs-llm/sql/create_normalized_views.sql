-- Normalizzazione schema piani/indicatori
-- Le tabelle originali sono in schema "old". Le nuove tabelle in "public"
-- hanno colonne canoniche e campi arricchiti da piani_monitoraggio.
--
-- Schema canonico:
--   anno | sezione | alias_piano_attivita | descrizione_piano_attivita | alias_indicatore
--   descrizione_indicatore | tipo_piano_attivita | campionamento | tipo_item_dpat

-- Prerequisito: CREATE SCHEMA IF NOT EXISTS old;
-- Prerequisito: CREATE EXTENSION IF NOT EXISTS dblink;

-- 1. piani_monitoraggio — MATERIALIZED VIEW via dblink da gisa.chatbot.dpat
CREATE MATERIALIZED VIEW piani_monitoraggio AS
SELECT
    anno,
    sezione,
    alias_piano_attivita,
    descrizione_piano_attivita,
    alias_indicatore,
    descrizione_indicatore,
    tipo_piano_attivita,
    campionamento,
    tipo_item_dpat
FROM dblink(
    'host=172.16.3.248 port=5432 dbname=gisa user=postgres password=postgres',
    'SELECT anno, sezione, alias_piano_attivita, descrizione_piano_attivita,
            alias_indicatore, descrizione_indicatore, tipo_piano_attivita,
            campionamento, tipo_item_dpat
     FROM chatbot.dpat'
) AS t(
    anno integer,
    sezione text,
    alias_piano_attivita text,
    descrizione_piano_attivita text,
    alias_indicatore text,
    descrizione_indicatore text,
    tipo_piano_attivita text,
    campionamento boolean,
    tipo_item_dpat varchar
)
WITH DATA;

CREATE UNIQUE INDEX idx_piani_unique ON piani_monitoraggio (anno, sezione, alias_piano_attivita, alias_indicatore);
CREATE INDEX idx_piani_anno ON piani_monitoraggio (anno);
CREATE INDEX idx_piani_alias_piano ON piani_monitoraggio (alias_piano_attivita);
CREATE INDEX idx_piani_alias_indicatore ON piani_monitoraggio (alias_indicatore);

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
