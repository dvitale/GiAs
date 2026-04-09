-- =============================================================================
-- ETL Script: Popola gias_db da gisa e mdgm
-- Eseguire con: psql -h localhost -U gisa_owner -d gias_db -f etl_gias.sql
-- =============================================================================

\set ON_ERROR_STOP on
\timing on

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Prerequisiti: dblink + funzione di verifica row count
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS dblink;

CREATE OR REPLACE FUNCTION pg_temp.check_count(
    p_label text,
    p_conn text,
    p_src_query text,
    p_dst_query text,
    p_mode text DEFAULT 'exact'  -- 'exact' oppure 'gte' (dest >= sorgente)
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_src bigint;
    v_dst bigint;
BEGIN
    EXECUTE format('SELECT val FROM dblink(%L, %L) AS t(val bigint)', p_conn, p_src_query)
        INTO v_src;
    EXECUTE p_dst_query INTO v_dst;

    IF p_mode = 'exact' AND v_src <> v_dst THEN
        RAISE EXCEPTION 'CHECK % FALLITO: sorgente=% destinazione=% (atteso uguale)',
            p_label, v_src, v_dst;
    ELSIF p_mode = 'gte' AND v_dst < v_src THEN
        RAISE EXCEPTION 'CHECK % FALLITO: sorgente=% destinazione=% (atteso dest >= sorgente)',
            p_label, v_src, v_dst;
    END IF;

    RAISE NOTICE 'CHECK %: sorgente=% destinazione=% OK', p_label, v_src, v_dst;
END;
$$;

-- ---------------------------------------------------------------------------
-- Connessioni dblink ai DB sorgente
-- ---------------------------------------------------------------------------
SELECT dblink_connect('gisa_conn',
    'dbname=gisa host=localhost user=gisa_owner password=5XRe4g8Q5QSg');
SELECT dblink_connect('mdgm_conn',
    'dbname=mdgm host=localhost user=gisa_owner password=5XRe4g8Q5QSg');

-- ===========================================================================
-- 1. masterlist  (sorgente: gisa.chatbot.masterlist)
-- ===========================================================================
\echo '>>> 1. masterlist'

TRUNCATE TABLE public.masterlist;

INSERT INTO public.masterlist (id, norma, macroarea, aggregazione, linea_di_attivita, registrati, riconosciuti)
SELECT
    row_number() OVER ()::integer AS id,
    norma::varchar,
    macroarea::varchar,
    aggregazione::varchar,
    linea_attivita::varchar        AS linea_di_attivita,
    CASE WHEN registrati  THEN 'S' ELSE 'N' END::char(1) AS registrati,
    CASE WHEN riconosciuti THEN 'S' ELSE 'N' END::char(1) AS riconosciuti
FROM dblink('gisa_conn', $$
    SELECT norma, macroarea, aggregazione, linea_attivita, registrati, riconosciuti
    FROM chatbot.masterlist
$$) AS t(
    norma text, macroarea text, aggregazione text,
    linea_attivita text, registrati boolean, riconosciuti boolean
);

\echo '   masterlist: ' :ROW_COUNT ' righe inserite'

SELECT pg_temp.check_count('masterlist', 'gisa_conn',
    'SELECT count(*) FROM chatbot.masterlist',
    'SELECT count(*) FROM public.masterlist');

-- ===========================================================================
-- 2. personale  (sorgente: gisa.chatbot.personale)
-- ===========================================================================
\echo '>>> 2. personale'

TRUNCATE TABLE public.personale;

INSERT INTO public.personale (id, descrizione_asl, descrizione_uoc, descrizione_uos,
                              namefirst, namelast, codice_fiscale, user_id, anno)
SELECT
    row_number() OVER ()::integer AS id,
    descrizione_asl,
    descrizione_uoc,
    descrizione_uos,
    namefirst,
    namelast,
    codice_fiscale,
    user_id::text,
    anno::numeric
FROM dblink('gisa_conn', $$
    SELECT descrizione_asl, descrizione_uoc, descrizione_uos,
           namefirst, namelast, codice_fiscale, user_id, anno
    FROM chatbot.personale
$$) AS t(
    descrizione_asl text, descrizione_uoc text, descrizione_uos text,
    namefirst text, namelast text, codice_fiscale text,
    user_id integer, anno integer
);

\echo '   personale: ' :ROW_COUNT ' righe inserite'

SELECT pg_temp.check_count('personale', 'gisa_conn',
    'SELECT count(*) FROM chatbot.personale',
    'SELECT count(*) FROM public.personale');

-- ===========================================================================
-- 3. osa_mai_controllati  (sorgente: mdgm.chatbot.osa_mai_controllati)
-- ===========================================================================
\echo '>>> 3. osa_mai_controllati'

TRUNCATE TABLE public.osa_mai_controllati;

INSERT INTO public.osa_mai_controllati (
    asl, codice_norma, codice_fiscale, n_reg, num_riconoscimento,
    partita_iva, comune, provincia_stab, indirizzo,
    latitudine_stab, longitudine_stab,
    codice_fiscale_rappresentante, nominativo_rappresentante,
    data_inizio_attivita, data_fine_attivita,
    macroarea, aggregazione, attivita, ragione_sociale
)
SELECT
    asl::varchar,
    codice_norma::varchar,
    codice_fiscale,
    n_reg::varchar,
    num_riconoscimento::varchar,
    partita_iva,
    comune::varchar,
    provincia_stab::varchar,
    indirizzo,
    latitudine_stab::text,
    longitudine_stab::text,
    codice_fiscale_rappresentante::text,
    nominativo_rappresentante::varchar,
    data_inizio_attivita::date,
    data_fine_attivita::date,
    macroarea,
    aggregazione,
    attivita,
    ragione_sociale
FROM dblink('mdgm_conn', $$
    SELECT asl, codice_norma, codice_fiscale, n_reg, num_riconoscimento,
           partita_iva, comune, provincia_stab, indirizzo,
           latitudine_stab, longitudine_stab,
           codice_fiscale_rappresentante, nominativo_rappresentante,
           data_inizio_attivita, data_fine_attivita,
           macroarea, aggregazione, attivita, ragione_sociale
    FROM chatbot.osa_mai_controllati
$$) AS t(
    asl text, codice_norma text, codice_fiscale text,
    n_reg text, num_riconoscimento text,
    partita_iva text, comune text, provincia_stab text,
    indirizzo text, latitudine_stab double precision,
    longitudine_stab double precision,
    codice_fiscale_rappresentante text, nominativo_rappresentante text,
    data_inizio_attivita date, data_fine_attivita date,
    macroarea text, aggregazione text, attivita text, ragione_sociale text
);

\echo '   osa_mai_controllati: ' :ROW_COUNT ' righe inserite'

SELECT pg_temp.check_count('osa_mai_controllati', 'mdgm_conn',
    'SELECT count(*) FROM chatbot.osa_mai_controllati',
    'SELECT count(*) FROM public.osa_mai_controllati');

-- ===========================================================================
-- 4. piani_monitoraggio (MATVIEW)  (sorgente: gisa.chatbot.dpat)
-- ===========================================================================
\echo '>>> 4. piani_monitoraggio'

DROP MATERIALIZED VIEW IF EXISTS public.piani_monitoraggio;

CREATE MATERIALIZED VIEW public.piani_monitoraggio AS
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
FROM dblink('gisa_conn', $$
    SELECT anno, sezione, alias_piano_attivita, descrizione_piano_attivita,
           alias_indicatore, descrizione_indicatore, tipo_piano_attivita,
           campionamento, tipo_item_dpat
    FROM chatbot.dpat
$$) AS t(
    anno integer, sezione text, alias_piano_attivita text,
    descrizione_piano_attivita text, alias_indicatore text,
    descrizione_indicatore text, tipo_piano_attivita text,
    campionamento boolean, tipo_item_dpat varchar
)
WITH DATA;

\echo '   piani_monitoraggio: matview creata'

SELECT pg_temp.check_count('piani_monitoraggio', 'gisa_conn',
    'SELECT count(*) FROM chatbot.dpat',
    'SELECT count(*) FROM public.piani_monitoraggio');

-- ===========================================================================
-- 5. cu_diff_programmati_eseguiti
--    (sorgente: mdgm.chatbot.vw_diff_programmati_eseguiti_x
--             + gisa.chatbot.dpat per sezione, alias_piano, tipo, campionamento)
-- ===========================================================================
\echo '>>> 5. cu_diff_programmati_eseguiti'

TRUNCATE TABLE public.cu_diff_programmati_eseguiti;

-- Passo 5a: tabella temporanea con dati mdgm
CREATE TEMP TABLE _tmp_diff AS
SELECT
    indicatore,
    descrizione_indicatore,
    descrizione_asl,
    descrizione_uoc,
    descrizione_uos,
    programmati,
    eseguiti,
    anno
FROM dblink('mdgm_conn', $$
    SELECT indicatore, descrizione_indicatore, descrizione_asl,
           descrizione_uoc, descrizione_uos, programmati, eseguiti, anno
    FROM chatbot.vw_diff_programmati_eseguiti_x
$$) AS t(
    indicatore text, descrizione_indicatore text,
    descrizione_asl text, descrizione_uoc text, descrizione_uos text,
    programmati double precision, eseguiti double precision, anno integer
);

-- Passo 5b: insert con join a piani_monitoraggio (dpat)
INSERT INTO public.cu_diff_programmati_eseguiti (
    id, alias_indicatore, descrizione_indicatore,
    descrizione_asl, descrizione_uoc, descrizione_uos,
    programmati, eseguiti, anno,
    sezione, alias_piano_attivita, descrizione_piano, tipo_piano_attivita, campionamento
)
SELECT
    row_number() OVER ()::integer AS id,
    d.indicatore                  AS alias_indicatore,
    d.descrizione_indicatore,
    d.descrizione_asl,
    d.descrizione_uoc,
    d.descrizione_uos,
    d.programmati::numeric,
    d.eseguiti::numeric,
    d.anno,
    pm.sezione::varchar,
    pm.alias_piano_attivita::varchar,
    pm.descrizione_piano_attivita  AS descrizione_piano,
    pm.tipo_piano_attivita,
    pm.campionamento
FROM _tmp_diff d
LEFT JOIN public.piani_monitoraggio pm
    ON trim(pm.alias_indicatore) = trim(d.indicatore)
   AND pm.anno = d.anno;

DROP TABLE _tmp_diff;

\echo '   cu_diff_programmati_eseguiti: ' :ROW_COUNT ' righe inserite'

SELECT pg_temp.check_count('cu_diff_programmati_eseguiti', 'mdgm_conn',
    'SELECT count(*) FROM chatbot.vw_diff_programmati_eseguiti_x',
    'SELECT count(*) FROM public.cu_diff_programmati_eseguiti',
    'gte');

-- ===========================================================================
-- 6. cu_eseguiti_nc
--    (sorgente: mdgm.chatbot.vw_cu_xx + mdgm.chatbot.vw_nc
--             + gisa.chatbot.dpat per campionamento, tipo_piano_attivita
--             + stabilimenti per comune)
-- ===========================================================================
\echo '>>> 6. cu_eseguiti_nc'

-- Rimuovo la colonna id_campione se esiste
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='cu_eseguiti_nc' AND column_name='id_campione'
    ) THEN
        ALTER TABLE public.cu_eseguiti_nc DROP COLUMN id_campione;
    END IF;
END $$;

TRUNCATE TABLE public.cu_eseguiti_nc;

-- Passo 6a: dati CU da mdgm (vw_cu_xx) con comune dagli stabilimenti
CREATE TEMP TABLE _tmp_cu AS
SELECT
    id_controllo, data_inizio_controllo, eseguiti, tecnica_controllo,
    macroarea_cu, aggregazione_cu, attivita_cu,
    id_indicatore, alias_indicatore, descrizione_indicatore,
    id_piano, alias_piano, descrizione_piano,
    id_piano_o_attivita, piano_o_attivita,
    id_sezione, sezione,
    id_uos, descrizione_uos, id_uoc, descrizione_uoc,
    id_asl, descrizione_asl,
    riferimento_id, riferimento_nome_tab, ragione_sociale,
    norma, id_norma, num_registrazione, partita_iva,
    approval_number, latitudine_stab, longitudine_stab,
    comune
FROM dblink('mdgm_conn', $$
    SELECT
        cu.id_controllo, cu.data_inizio_controllo, cu.eseguiti, cu.tecnica_controllo,
        cu.macroarea_cu, cu.aggregazione_cu, cu.attivita_cu,
        cu.id_indicatore, cu.alias_indicatore, cu.descrizione_indicatore,
        cu.id_piano, cu.alias_piano, cu.descrizione_piano,
        cu.id_piano_o_attivita, cu.piano_o_attivita,
        cu.id_sezione, cu.sezione,
        cu.id_uos, cu.descrizione_uos, cu.id_uoc, cu.descrizione_uoc,
        cu.id_asl, cu.descrizione_asl,
        cu.riferimento_id, cu.riferimento_nome_tab, cu.ragione_sociale,
        cu.norma, cu.id_norma, cu.num_registrazione, cu.partita_iva,
        cu.approval_number, cu.latitudine_stab, cu.longitudine_stab,
        s.comune
    FROM chatbot.vw_cu_xx cu
    LEFT JOIN "Analisi_dev".vw_dbi_get_all_stabilimenti__validi s
        ON s.riferimento_id = cu.riferimento_id
       AND s.riferimento_id_nome_tab = cu.riferimento_nome_tab
$$) AS t(
    id_controllo integer, data_inizio_controllo timestamp,
    eseguiti double precision, tecnica_controllo text,
    macroarea_cu text, aggregazione_cu text, attivita_cu text,
    id_indicatore bigint, alias_indicatore text, descrizione_indicatore text,
    id_piano bigint, alias_piano text, descrizione_piano text,
    id_piano_o_attivita bigint, piano_o_attivita text,
    id_sezione bigint, sezione text,
    id_uos bigint, descrizione_uos text, id_uoc bigint, descrizione_uoc text,
    id_asl bigint, descrizione_asl text,
    riferimento_id integer, riferimento_nome_tab text, ragione_sociale text,
    norma text, id_norma integer, num_registrazione text, partita_iva text,
    approval_number text, latitudine_stab text, longitudine_stab text,
    comune text
);

-- Passo 6b: dati NC da mdgm (vw_nc)
CREATE TEMP TABLE _tmp_nc AS
SELECT
    id_controllo,
    tipo_non_conformita,
    numero_nc_non_gravi,
    numero_nc_gravi,
    oggetto_non_conformita
FROM dblink('mdgm_conn', $$
    SELECT id_controllo, tipo_non_conformita,
           numero_nc_non_gravi, numero_nc_gravi, oggetto_non_conformita
    FROM chatbot.vw_nc
$$) AS t(
    id_controllo integer, tipo_non_conformita text,
    numero_nc_non_gravi bigint, numero_nc_gravi bigint,
    oggetto_non_conformita text
);

-- Passo 6c: insert finale con join NC + dpat
INSERT INTO public.cu_eseguiti_nc (
    id,
    id_controllo, data_inizio_controllo, eseguiti, tecnica_controllo,
    macroarea_cu, aggregazione_cu, attivita_cu,
    id_indicatore, alias_indicatore, descrizione_indicatore,
    id_piano, alias_piano_attivita, descrizione_piano,
    id_piano_o_attivita, piano_o_attivita,
    id_sezione, sezione,
    id_uos, descrizione_uos, id_uoc, descrizione_uoc,
    id_asl, descrizione_asl,
    riferimento_id, riferimento_nome_tab, ragione_sociale,
    norma, id_norma, num_registrazione, partita_iva,
    num_riconoscimento, latitudine_stab, longitudine_stab,
    tipo_non_conformita, numero_nc_non_gravi, numero_nc_gravi,
    oggetto_non_conformita, comune, campionamento, tipo_piano_attivita
)
SELECT
    row_number() OVER ()::integer AS id,
    cu.id_controllo::text,
    cu.data_inizio_controllo,
    cu.eseguiti::numeric,
    cu.tecnica_controllo,
    cu.macroarea_cu,
    cu.aggregazione_cu,
    cu.attivita_cu,
    cu.id_indicatore::text,
    cu.alias_indicatore,
    cu.descrizione_indicatore,
    cu.id_piano::text,
    cu.alias_piano              AS alias_piano_attivita,
    cu.descrizione_piano,
    cu.id_piano_o_attivita::text,
    cu.piano_o_attivita,
    cu.id_sezione::text,
    cu.sezione,
    cu.id_uos::text,
    cu.descrizione_uos,
    cu.id_uoc::text,
    cu.descrizione_uoc,
    cu.id_asl::text,
    cu.descrizione_asl,
    cu.riferimento_id::text,
    cu.riferimento_nome_tab,
    cu.ragione_sociale,
    cu.norma,
    cu.id_norma::text,
    cu.num_registrazione,
    cu.partita_iva,
    cu.approval_number          AS num_riconoscimento,
    cu.latitudine_stab,
    cu.longitudine_stab,
    nc.tipo_non_conformita,
    nc.numero_nc_non_gravi,
    nc.numero_nc_gravi,
    nc.oggetto_non_conformita,
    cu.comune,
    pm.campionamento,
    pm.tipo_piano_attivita
FROM _tmp_cu cu
LEFT JOIN _tmp_nc nc ON nc.id_controllo = cu.id_controllo
LEFT JOIN public.piani_monitoraggio pm
    ON trim(pm.alias_indicatore) = trim(cu.alias_indicatore);

DROP TABLE _tmp_cu;
DROP TABLE _tmp_nc;

\echo '   cu_eseguiti_nc: ' :ROW_COUNT ' righe inserite'

SELECT pg_temp.check_count('cu_eseguiti_nc', 'mdgm_conn',
    'SELECT count(*) FROM chatbot.vw_cu_xx',
    'SELECT count(*) FROM public.cu_eseguiti_nc',
    'gte');

-- ===========================================================================
-- 7. indicatori_non_catalogati (derivata)
--    indicatori presenti in cu_eseguiti_nc ma assenti in piani_monitoraggio
-- ===========================================================================
\echo '>>> 7. indicatori_non_catalogati'

TRUNCATE TABLE public.indicatori_non_catalogati;

INSERT INTO public.indicatori_non_catalogati (
    alias_indicatore, descrizione_indicatore, fonte, data_rilevamento
)
SELECT DISTINCT
    cu.alias_indicatore::varchar,
    cu.descrizione_indicatore,
    'cu_eseguiti_x'::varchar     AS fonte,
    now()                        AS data_rilevamento
FROM public.cu_eseguiti_nc cu
WHERE cu.alias_indicatore IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.piani_monitoraggio pm
    WHERE trim(pm.alias_indicatore) = trim(cu.alias_indicatore)
);

\echo '   indicatori_non_catalogati: ' :ROW_COUNT ' righe inserite'

-- ---------------------------------------------------------------------------
-- Chiusura connessioni
-- ---------------------------------------------------------------------------
SELECT dblink_disconnect('gisa_conn');
SELECT dblink_disconnect('mdgm_conn');

COMMIT;

\echo '>>> ETL completato con successo.'
