-- =============================================================================
-- Fix: vw_diff_programmati_eseguiti e vw_diff_programmati_eseguiti_x
-- Sostituisce chatbot.vw_cu con chatbot.vw_cu_x come sorgente dati.
--
-- Motivo: vw_cu filtra per id_norma IN (43,49) e fonte IN ('camp','isp semp'),
-- escludendo ~55% dei controlli ufficiali. Questo causava discrepanze tra
-- count_from_cu_eseguiti e count_from_cu_diff.
--
-- Dipendenze da ricreare:
--   count_from_cu_diff → cu_diff_programmati_eseguiti → vw_diff_programmati_eseguiti_x
--
-- Eseguire con: psql -d mdgm -f fix_vw_diff_use_vw_cu_x.sql
-- =============================================================================

BEGIN;

-- -------------------------------------------------------------------------
-- 1. Drop catena dipendente (ordine inverso)
-- -------------------------------------------------------------------------
DROP VIEW IF EXISTS chatbot.count_from_cu_diff;
DROP VIEW IF EXISTS chatbot.cu_diff_programmati_eseguiti;
DROP MATERIALIZED VIEW IF EXISTS chatbot.vw_diff_programmati_eseguiti_x;
DROP MATERIALIZED VIEW IF EXISTS chatbot.vw_diff_programmati_eseguiti;

-- -------------------------------------------------------------------------
-- 2. Ricrea vw_diff_programmati_eseguiti (senza UNION, solo programmati)
--    Cambiamento: chatbot.vw_cu → chatbot.vw_cu_x
-- -------------------------------------------------------------------------
CREATE MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti AS
SELECT p.alias_indicatore AS indicatore,
    p.descrizione_indicatore,
    aa.p_descrizione AS descrizione_asl,
    aa.descrizione AS descrizione_uoc,
    p.descr_uos_uoc_asl AS descrizione_uos,
    p.programmato AS programmati,
    sum(COALESCE(c.eseguiti, 0::double precision)) AS eseguiti,
    p.anno
FROM chatbot.vw_programmazioni_matrix p
    LEFT JOIN chatbot.vw_cu_x c ON c.id_indicatore = p.id_indicatore AND c.id_uos = p.id_uos_uoc_asl
    JOIN matrix.vw_tree_nodes_asl_descr a ON a.id_node = p.id_uos_uoc_asl
    JOIN matrix.vw_tree_nodes_asl_descr aa ON a.p_id = aa.id
WHERE p.livello_struttura = 3
GROUP BY p.alias_indicatore, p.descrizione_indicatore, aa.p_descrizione,
         aa.descrizione, p.descr_uos_uoc_asl, p.programmato, p.anno
WITH DATA;

-- -------------------------------------------------------------------------
-- 3. Ricrea vw_diff_programmati_eseguiti_x (con UNION ALL non programmati)
--    Cambiamento: chatbot.vw_cu → chatbot.vw_cu_x (in entrambe le parti)
-- -------------------------------------------------------------------------
CREATE MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti_x AS
SELECT p.alias_indicatore AS indicatore,
    p.descrizione_indicatore,
    aa.p_descrizione AS descrizione_asl,
    aa.descrizione AS descrizione_uoc,
    p.descr_uos_uoc_asl AS descrizione_uos,
    p.programmato AS programmati,
    sum(COALESCE(c.eseguiti, 0::double precision)) AS eseguiti,
    p.anno
FROM chatbot.vw_programmazioni_matrix p
    LEFT JOIN chatbot.vw_cu_x c ON c.id_indicatore = p.id_indicatore AND c.id_uos = p.id_uos_uoc_asl
    JOIN matrix.vw_tree_nodes_asl_descr a ON a.id_node = p.id_uos_uoc_asl
    JOIN matrix.vw_tree_nodes_asl_descr aa ON a.p_id = aa.id
WHERE p.livello_struttura = 3
GROUP BY p.alias_indicatore, p.descrizione_indicatore, aa.p_descrizione,
         aa.descrizione, p.descr_uos_uoc_asl, p.programmato, p.anno
UNION ALL
SELECT sp.alias AS indicatore,
    c.descrizione_indicatore,
    c.descrizione_asl,
    c.descrizione_uoc,
    c.descrizione_uos,
    0::double precision AS programmati,
    sum(c.eseguiti) AS eseguiti,
    sp.anno
FROM chatbot.vw_cu_x c
    JOIN matrix.struttura_piani sp ON sp.id = c.id_indicatore
WHERE NOT EXISTS (
    SELECT 1 FROM chatbot.vw_programmazioni_matrix p
    WHERE p.id_indicatore = c.id_indicatore
      AND p.id_uos_uoc_asl = c.id_uos
      AND p.livello_struttura = 3
)
GROUP BY sp.alias, c.descrizione_indicatore, c.descrizione_asl,
         c.descrizione_uoc, c.descrizione_uos, sp.anno
WITH DATA;

-- -------------------------------------------------------------------------
-- 4. Ricrea view cu_diff_programmati_eseguiti (invariata, dipende da _x)
-- -------------------------------------------------------------------------
CREATE VIEW chatbot.cu_diff_programmati_eseguiti AS
SELECT row_number() OVER ()::integer AS id,
    d.indicatore AS alias_indicatore,
    d.descrizione_indicatore,
    d.descrizione_asl,
    d.descrizione_uoc,
    d.descrizione_uos,
    d.programmati::numeric AS programmati,
    d.eseguiti::numeric AS eseguiti,
    d.anno,
    pm.sezione::character varying AS sezione,
    pm.alias_piano_attivita::character varying AS alias_piano_attivita,
    pm.descrizione_piano_attivita AS descrizione_piano,
    pm.tipo_piano_attivita,
    pm.campionamento
FROM chatbot.vw_diff_programmati_eseguiti_x d
    LEFT JOIN chatbot.piani_monitoraggio pm
        ON TRIM(BOTH FROM pm.alias_indicatore) = TRIM(BOTH FROM d.indicatore)
       AND pm.anno = d.anno;

-- -------------------------------------------------------------------------
-- 5. Ricrea view count_from_cu_diff (invariata, dipende da cu_diff)
-- -------------------------------------------------------------------------
CREATE VIEW chatbot.count_from_cu_diff AS
SELECT upper(TRIM(BOTH FROM descrizione_asl)) AS asl,
    upper(TRIM(BOTH FROM descrizione_uos)) AS uos,
    upper(TRIM(BOTH FROM alias_indicatore)) AS indicatore,
    sum(eseguiti) AS num_controlli
FROM chatbot.cu_diff_programmati_eseguiti
WHERE anno = 2026 AND eseguiti > 0::numeric
GROUP BY (upper(TRIM(BOTH FROM alias_indicatore))),
         (upper(TRIM(BOTH FROM descrizione_uos))),
         (upper(TRIM(BOTH FROM descrizione_asl)))
ORDER BY (upper(TRIM(BOTH FROM descrizione_asl))),
         (upper(TRIM(BOTH FROM descrizione_uos))),
         (upper(TRIM(BOTH FROM alias_indicatore)));

COMMIT;

-- -------------------------------------------------------------------------
-- 6. Verifica post-deploy
-- -------------------------------------------------------------------------
-- Deve restituire 0 righe in entrambe le direzioni:
-- SELECT * FROM chatbot.count_from_cu_eseguiti WHERE uos='UOV IAPZ 1'
-- EXCEPT
-- SELECT * FROM chatbot.count_from_cu_diff WHERE uos ILIKE 'UOV IAPZ 1';
