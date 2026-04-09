-- ============================================================================
-- FIX PERFORMANCE: REFRESH MATERIALIZED VIEW chatbot.vw_cu
-- ============================================================================
-- Problema: il REFRESH si bloccava a causa di:
--   1. regexp_replace nelle viste che impedivano l'uso degli indici
--   2. EXTRACT(year FROM ...) nel WHERE che impediva l'uso dell'indice su data
--   3. Assenza di indici sulle tabelle h_* piu' grandi
--   4. JIT compilation di 291 funzioni
--
-- Data: 2026-04-03
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Pulizia dati alla fonte (rimuove \r \n \t \v dalle tabelle h_*)
-- ============================================================================

-- h_dbi_get_all_stabilimenti_ (1.8M righe, 535 MB)
UPDATE "Analisi_dev".h_dbi_get_all_stabilimenti_
SET riferimento_id_nome_tab = regexp_replace(riferimento_id_nome_tab, E'[\r\n\t\v]', '', 'g'),
    ragione_sociale = regexp_replace(ragione_sociale, E'[\r\n\t\v]', '', 'g'),
    asl = regexp_replace(asl, E'[\r\n\t\v]', '', 'g'),
    codice_fiscale = regexp_replace(codice_fiscale, E'[\r\n\t\v]', '', 'g'),
    codice_fiscale_rappresentante = regexp_replace(codice_fiscale_rappresentante, E'[\r\n\t\v]', '', 'g'),
    partita_iva = regexp_replace(partita_iva, E'[\r\n\t\v]', '', 'g'),
    n_reg = regexp_replace(n_reg, E'[\r\n\t\v]', '', 'g'),
    nominativo_rappresentante = regexp_replace(nominativo_rappresentante, E'[\r\n\t\v]', '', 'g'),
    comune = regexp_replace(comune, E'[\r\n\t\v]', '', 'g'),
    provincia_stab = regexp_replace(provincia_stab, E'[\r\n\t\v]', '', 'g'),
    indirizzo = regexp_replace(indirizzo, E'[\r\n\t\v]', '', 'g'),
    cap_stab = regexp_replace(cap_stab, E'[\r\n\t\v]', '', 'g'),
    comune_leg = regexp_replace(comune_leg, E'[\r\n\t\v]', '', 'g'),
    provincia_leg = regexp_replace(provincia_leg, E'[\r\n\t\v]', '', 'g'),
    indirizzo_leg = regexp_replace(indirizzo_leg, E'[\r\n\t\v]', '', 'g'),
    cap_leg = regexp_replace(cap_leg, E'[\r\n\t\v]', '', 'g'),
    tipo_categorizzazione = regexp_replace(tipo_categorizzazione, E'[\r\n\t\v]', '', 'g'),
    livello_rischio = regexp_replace(livello_rischio, E'[\r\n\t\v]', '', 'g'),
    tipo_impresa = regexp_replace(tipo_impresa, E'[\r\n\t\v]', '', 'g')
WHERE riferimento_id_nome_tab ~ E'[\r\n\t\v]'
   OR ragione_sociale ~ E'[\r\n\t\v]'
   OR asl ~ E'[\r\n\t\v]'
   OR codice_fiscale ~ E'[\r\n\t\v]'
   OR codice_fiscale_rappresentante ~ E'[\r\n\t\v]'
   OR partita_iva ~ E'[\r\n\t\v]'
   OR n_reg ~ E'[\r\n\t\v]'
   OR nominativo_rappresentante ~ E'[\r\n\t\v]'
   OR comune ~ E'[\r\n\t\v]'
   OR provincia_stab ~ E'[\r\n\t\v]'
   OR indirizzo ~ E'[\r\n\t\v]'
   OR cap_stab ~ E'[\r\n\t\v]'
   OR comune_leg ~ E'[\r\n\t\v]'
   OR provincia_leg ~ E'[\r\n\t\v]'
   OR indirizzo_leg ~ E'[\r\n\t\v]'
   OR cap_leg ~ E'[\r\n\t\v]'
   OR tipo_categorizzazione ~ E'[\r\n\t\v]'
   OR livello_rischio ~ E'[\r\n\t\v]'
   OR tipo_impresa ~ E'[\r\n\t\v]';

-- h_dbi_get_all_linee (2.0M righe, 785 MB)
UPDATE "Analisi_dev".h_dbi_get_all_linee
SET riferimento_id_nome_tab = regexp_replace(riferimento_id_nome_tab, E'[\r\n\t\v]', '', 'g'),
    macroarea = regexp_replace(macroarea, E'[\r\n\t\v]', '', 'g'),
    aggregazione = regexp_replace(aggregazione, E'[\r\n\t\v]', '', 'g'),
    attivita = regexp_replace(attivita, E'[\r\n\t\v]', '', 'g'),
    path_attivita_completo = regexp_replace(path_attivita_completo, E'[\r\n\t\v]', '', 'g'),
    norma = regexp_replace(norma, E'[\r\n\t\v]', '', 'g'),
    codice_macroarea = regexp_replace(codice_macroarea, E'[\r\n\t\v]', '', 'g'),
    codice_aggregazione = regexp_replace(codice_aggregazione, E'[\r\n\t\v]', '', 'g'),
    codice_attivita = regexp_replace(codice_attivita, E'[\r\n\t\v]', '', 'g'),
    stato = regexp_replace(stato, E'[\r\n\t\v]', '', 'g'),
    codice_struttura_nazionale = regexp_replace(codice_struttura_nazionale, E'[\r\n\t\v]', '', 'g')
WHERE riferimento_id_nome_tab ~ E'[\r\n\t\v]'
   OR macroarea ~ E'[\r\n\t\v]'
   OR aggregazione ~ E'[\r\n\t\v]'
   OR attivita ~ E'[\r\n\t\v]'
   OR path_attivita_completo ~ E'[\r\n\t\v]'
   OR norma ~ E'[\r\n\t\v]'
   OR codice_macroarea ~ E'[\r\n\t\v]'
   OR codice_aggregazione ~ E'[\r\n\t\v]'
   OR codice_attivita ~ E'[\r\n\t\v]'
   OR stato ~ E'[\r\n\t\v]'
   OR codice_struttura_nazionale ~ E'[\r\n\t\v]';

-- h_dbi_get_stabilimenti_sintesis (76K righe, 55 MB)
UPDATE "Analisi_dev".h_dbi_get_stabilimenti_sintesis
SET tipo_impresa = regexp_replace(tipo_impresa, E'[\r\n\t\v]', '', 'g'),
    tipo_societa = regexp_replace(tipo_societa, E'[\r\n\t\v]', '', 'g'),
    ragione_sociale = regexp_replace(ragione_sociale, E'[\r\n\t\v]', '', 'g'),
    partita_iva = regexp_replace(partita_iva, E'[\r\n\t\v]', '', 'g'),
    approval_number = regexp_replace(approval_number, E'[\r\n\t\v]', '', 'g'),
    lat_stab = regexp_replace(lat_stab, E'[\r\n\t\v]', '', 'g'),
    long_stab = regexp_replace(long_stab, E'[\r\n\t\v]', '', 'g')
WHERE tipo_impresa ~ E'[\r\n\t\v]'
   OR tipo_societa ~ E'[\r\n\t\v]'
   OR ragione_sociale ~ E'[\r\n\t\v]'
   OR partita_iva ~ E'[\r\n\t\v]'
   OR approval_number ~ E'[\r\n\t\v]'
   OR lat_stab ~ E'[\r\n\t\v]'
   OR long_stab ~ E'[\r\n\t\v]';

-- h_get_campioni (2.7M righe, 1.28 GB)
UPDATE "Analisi_dev".h_get_campioni
SET asl = regexp_replace(asl::text, E'[\r\n\t\v]', '', 'g')::varchar,
    id_controllo_ufficiale = regexp_replace(id_controllo_ufficiale::text, E'[\r\n\t\v]', '', 'g')::varchar,
    analita_lev_1 = regexp_replace(analita_lev_1, E'[\r\n\t\v]', '', 'g'),
    analita_lev_2 = regexp_replace(analita_lev_2, E'[\r\n\t\v]', '', 'g'),
    analita_lev_3 = regexp_replace(analita_lev_3, E'[\r\n\t\v]', '', 'g'),
    analita_lev_4 = regexp_replace(analita_lev_4, E'[\r\n\t\v]', '', 'g'),
    matrice_lev_1 = regexp_replace(matrice_lev_1, E'[\r\n\t\v]', '', 'g'),
    matrice_lev_2 = regexp_replace(matrice_lev_2, E'[\r\n\t\v]', '', 'g'),
    matrice_lev_3 = regexp_replace(matrice_lev_3, E'[\r\n\t\v]', '', 'g')
WHERE asl::text ~ E'[\r\n\t\v]'
   OR id_controllo_ufficiale::text ~ E'[\r\n\t\v]'
   OR analita_lev_1 ~ E'[\r\n\t\v]'
   OR analita_lev_2 ~ E'[\r\n\t\v]'
   OR analita_lev_3 ~ E'[\r\n\t\v]'
   OR analita_lev_4 ~ E'[\r\n\t\v]'
   OR matrice_lev_1 ~ E'[\r\n\t\v]'
   OR matrice_lev_2 ~ E'[\r\n\t\v]'
   OR matrice_lev_3 ~ E'[\r\n\t\v]';

-- h_get_linee_attivita_controllo (5.7M righe, 638 MB)
UPDATE "Analisi_dev".h_get_linee_attivita_controllo
SET codice_linea = regexp_replace(codice_linea, E'[\r\n\t\v]', '', 'g'),
    attivita = regexp_replace(attivita, E'[\r\n\t\v]', '', 'g')
WHERE codice_linea ~ E'[\r\n\t\v]'
   OR attivita ~ E'[\r\n\t\v]';

COMMIT;


-- ============================================================================
-- STEP 2: Creazione indici sulle tabelle h_* (fuori transazione per sicurezza)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_h_stab_rif_id_tab
ON "Analisi_dev".h_dbi_get_all_stabilimenti_ (riferimento_id, riferimento_id_nome_tab)
WHERE upper_inf(rng) IS TRUE;

CREATE INDEX IF NOT EXISTS idx_h_linee_id_rif
ON "Analisi_dev".h_dbi_get_all_linee (id_linea, riferimento_id, riferimento_id_nome_tab)
WHERE upper_inf(rng) IS TRUE;


-- ============================================================================
-- STEP 3: Riscrittura viste senza regexp_replace
-- ============================================================================

CREATE OR REPLACE VIEW "Analisi_dev".vw_dbi_get_all_stabilimenti__validi AS
 SELECT riferimento_id,
    riferimento_id_nome_tab,
    ragione_sociale,
    asl_rif,
    asl,
    codice_fiscale,
    codice_fiscale_rappresentante,
    partita_iva,
    n_reg,
    nominativo_rappresentante,
    comune,
    provincia_stab,
    indirizzo,
    cap_stab,
    comune_leg,
    provincia_leg,
    indirizzo_leg,
    cap_leg,
    latitudine_stab,
    longitudine_stab,
    categoria_rischio,
    prossimo_controllo,
    id_controllo_ultima_categorizzazione,
    data_controllo_ultima_categorizzazione,
    tipo_categorizzazione,
    data_inserimento,
    livello_rischio,
    tipo_impresa
   FROM "Analisi_dev".h_dbi_get_all_stabilimenti_
  WHERE upper_inf(rng) IS TRUE;

CREATE OR REPLACE VIEW "Analisi_dev".vw_dbi_get_all_linee_validi AS
 SELECT id_linea,
    riferimento_id,
    riferimento_id_nome_tab,
    num_riconoscimento::text AS num_riconoscimento,
    n_linea::text AS n_linea,
    data_inizio_attivita,
    data_fine_attivita,
    macroarea,
    aggregazione,
    attivita,
    path_attivita_completo,
    norma,
    id_norma,
    codice_macroarea,
    codice_aggregazione,
    codice_attivita,
    stato,
    id_stato,
    miscela,
    tipo_attivita_descrizione::text AS tipo_attivita_descrizione,
    tipo_attivita,
    sintesis,
    codice_struttura_nazionale
   FROM "Analisi_dev".h_dbi_get_all_linee
  WHERE upper_inf(rng) IS TRUE;

CREATE OR REPLACE VIEW "Analisi_dev".vw_dbi_get_stabilimenti_sintesis_validi AS
 SELECT riferimento_id,
    tipo_impresa,
    tipo_societa,
    ragione_sociale,
    partita_iva,
    codice_fiscale_impresa,
    cf_rapp_sede_legale,
    nome_rapp_sede_legale,
    cognome_rapp_sede_legale,
    indirizzo_sede_legale,
    comune_sede_legale,
    cap_sede_legale,
    prov_sede_legale,
    comune_stab,
    indirizzo_stab,
    cap_stab,
    prov_stab,
    stab_descrizione_carattere,
    stab_descrizione_attivita,
    stab_asl,
    lat_stab,
    long_stab,
    approval_number,
    norma,
    codice_norma,
    macroarea,
    codice_macroarea,
    aggregazione,
    codice_aggregazione,
    attivita,
    codice_attivita,
    stato_linea,
    data_inizio_attivita,
    data_fine_attivita,
    categoria_rischio,
    id_controllo_ultima_categorizzazione,
    data_controllo_ultima_categorizzazione,
    tipo_categorizzazione,
    livello_rischio,
    categoria_rischio_qualitativa
   FROM "Analisi_dev".h_dbi_get_stabilimenti_sintesis
  WHERE upper_inf(rng) IS TRUE;

CREATE OR REPLACE VIEW "Analisi_dev".vw_get_campioni_validi AS
 SELECT id_asl,
    asl::text AS asl,
    motivazione_campione::text AS motivazione_campione,
    id_piano,
    id_attivita,
    id_campione,
    data_prelievo,
    identificativo_campione::text AS identificativo_campione,
    prelevatore_1_a4,
    prelevatore_2_a4,
    prelevatore_3_a4,
    strategia_campionamento_a1,
    capitoli_piani_a3,
    specie_alimento_b6::text AS specie_alimento_b6,
    metodo_produzione_b7,
    anno_campione,
    data_chiusura_campione,
    id_controllo_ufficiale::text AS id_controllo_ufficiale,
    esito,
    punteggio_campione,
    responsabilita_positiva::text AS responsabilita_positiva,
    data_esito_analita,
    esito_motivazione_respingimento,
    note_esito_campione,
    codice_accettazione,
    num_verbale::text AS num_verbale,
    barcode::text AS barcode,
    analita_lev_1,
    analita_lev_2,
    analita_lev_3,
    analita_lev_4,
    matrice_lev_1,
    matrice_lev_2,
    matrice_lev_3,
    note_campione,
    anno_controllo,
    codice_interno_piano,
    descrizione_esito_esame,
    motivazione_non_conformita,
    rendicontabile,
    codice_preaccettazione,
    laboratorio_destinazione
   FROM "Analisi_dev".h_get_campioni
  WHERE upper_inf(rng) IS TRUE;

CREATE OR REPLACE VIEW "Analisi_dev".vw_get_linee_attivita_controllo_validi AS
 SELECT id_controllo,
    codice_linea,
    attivita,
    id_linea
   FROM "Analisi_dev".h_get_linee_attivita_controllo
  WHERE upper_inf(rng) IS TRUE;


-- ============================================================================
-- STEP 4: Ricreazione materialized view chatbot.vw_cu con fix sulla data
--         (EXTRACT(year) -> confronto diretto per permettere uso indice)
-- ============================================================================

-- Drop con CASCADE (elimina anche le dipendenti)
DROP MATERIALIZED VIEW IF EXISTS chatbot.vw_cu CASCADE;

CREATE MATERIALIZED VIEW chatbot.vw_cu AS
 SELECT DISTINCT c.id_controllo,
    c.data_inizio_controllo,
    c.eseguiti,
    c.fonte AS tecnica_controllo,
    ll.macroarea AS macroarea_cu,
    ll.aggregazione AS aggregazione_cu,
    ll.attivita AS attivita_cu,
    p.id AS id_indicatore,
    ((p.alias || ' '::text) || p.descrizione) AS descrizione_indicatore,
    ppp.p_id AS id_piano,
    ((ppp.alias || ' '::text) || ppp.descrizione) AS descrizione_piano,
    pppp.id AS id_piano_o_attivita,
    pppp.descrizione AS piano_o_attivita,
    pppp.p_id AS id_sezione,
    pppp.p_descrizione AS sezione,
    a.id AS id_uos,
    a.descrizione AS descrizione_uos,
    aaa.id AS id_uoc,
    aaa.descrizione AS descrizione_uoc,
    aaaa.id AS id_asl,
    aaaa.descrizione AS descrizione_asl,
    s.riferimento_id,
    c.riferimento_nome_tab,
    s.ragione_sociale,
    n.norma,
    n.id_norma,
    s.n_reg AS num_registrazione,
    s.partita_iva,
    ss.approval_number,
    COALESCE((s.latitudine_stab)::text, ss.lat_stab) AS latitudine_stab,
    COALESCE((s.longitudine_stab)::text, ss.long_stab) AS longitudine_stab,
    camp.id_campione,
    camp.analita_lev_1,
    camp.analita_lev_2,
    camp.analita_lev_3,
    camp.analita_lev_4,
    camp.matrice_lev_1,
    camp.matrice_lev_2,
    camp.matrice_lev_3
   FROM ((((((((((((((ra.vw_gisa_controlli_ufficiali c
     JOIN matrix.struttura_piani p ON ((p.id_gisa = c.id_motivo)))
     JOIN matrix.vw_tree_nodes_piani_descr pp ON ((pp.id = p.id)))
     JOIN matrix.vw_tree_nodes_piani_descr ppp ON ((pp.p_id = ppp.id)))
     JOIN matrix.vw_tree_nodes_piani_descr pppp ON ((ppp.p_id = pppp.id)))
     JOIN matrix.struttura_asl a ON ((a.id_gisa = c.id_unita_operativa)))
     JOIN matrix.vw_tree_nodes_asl_descr aa ON ((aa.id = a.id)))
     JOIN matrix.vw_tree_nodes_asl_descr aaa ON ((aa.p_id = aaa.id)))
     JOIN matrix.vw_tree_nodes_asl_descr aaaa ON ((aaa.p_id = aaaa.id)))
     LEFT JOIN "Analisi_dev".vw_dbi_get_all_stabilimenti__validi s ON (((s.riferimento_id = c.riferimento_id) AND (s.riferimento_id_nome_tab = c.riferimento_nome_tab))))
     LEFT JOIN "Analisi_dev".vw_dbi_get_stabilimenti_sintesis_validi ss ON (((s.riferimento_id = ss.riferimento_id) AND (s.riferimento_id_nome_tab = 'sintesis_stabilimento'::text))))
     LEFT JOIN "Analisi_dev".vw_get_campioni_validi camp ON ((camp.id_controllo_ufficiale = (c.id_controllo)::text)))
     JOIN "Analisi_dev".lookup_norme n ON (((n.id_norma = c.id_norma) AND (n.id_norma = ANY (ARRAY[43, 49])))))
     JOIN "Analisi_dev".vw_get_linee_attivita_controllo_validi l ON ((l.id_controllo = c.id_controllo)))
     JOIN "Analisi_dev".vw_dbi_get_all_linee_validi ll ON (((ll.id_linea = l.id_linea) AND (ll.riferimento_id_nome_tab = s.riferimento_id_nome_tab) AND (ll.riferimento_id = s.riferimento_id))))
  WHERE (c.data_inizio_controllo >= date_trunc('year', CURRENT_DATE) - interval '10 years'
    AND ((s.riferimento_id_nome_tab <> 'sintesis_stabilimento'::text) OR (ss.riferimento_id IS NOT NULL))
    AND (NOT (p.id_gisa IN ( SELECT r.id_piano FROM "Analisi_dev".piani_no_rend r)))
    AND (c.fonte = ANY (ARRAY['camp'::text, 'isp semp'::text])))
WITH NO DATA;


-- ============================================================================
-- STEP 5: Ricreazione materialized views dipendenti
-- ============================================================================

CREATE MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti AS
 SELECT p.alias_indicatore AS indicatore,
    p.descrizione_indicatore,
    aa.p_descrizione AS descrizione_asl,
    aa.descrizione AS descrizione_uoc,
    p.descr_uos_uoc_asl AS descrizione_uos,
    p.programmato AS programmati,
    sum(COALESCE(c.eseguiti, (0)::double precision)) AS eseguiti,
    p.anno
   FROM (((chatbot.vw_programmazioni_matrix p
     LEFT JOIN chatbot.vw_cu c ON (((c.id_indicatore = p.id_indicatore) AND (c.id_uos = p.id_uos_uoc_asl))))
     JOIN matrix.vw_tree_nodes_asl_descr a ON ((a.id_node = p.id_uos_uoc_asl)))
     JOIN matrix.vw_tree_nodes_asl_descr aa ON ((a.p_id = aa.id)))
  WHERE (p.livello_struttura = 3)
  GROUP BY p.alias_indicatore, p.descrizione_indicatore, aa.p_descrizione, aa.descrizione, p.descr_uos_uoc_asl, p.programmato, p.anno
WITH NO DATA;

CREATE MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti_x AS
 SELECT p.alias_indicatore AS indicatore,
    p.descrizione_indicatore,
    aa.p_descrizione AS descrizione_asl,
    aa.descrizione AS descrizione_uoc,
    p.descr_uos_uoc_asl AS descrizione_uos,
    p.programmato AS programmati,
    sum(COALESCE(c.eseguiti, (0)::double precision)) AS eseguiti,
    p.anno
   FROM (((chatbot.vw_programmazioni_matrix p
     LEFT JOIN chatbot.vw_cu c ON (((c.id_indicatore = p.id_indicatore) AND (c.id_uos = p.id_uos_uoc_asl))))
     JOIN matrix.vw_tree_nodes_asl_descr a ON ((a.id_node = p.id_uos_uoc_asl)))
     JOIN matrix.vw_tree_nodes_asl_descr aa ON ((a.p_id = aa.id)))
  WHERE (p.livello_struttura = 3)
  GROUP BY p.alias_indicatore, p.descrizione_indicatore, aa.p_descrizione, aa.descrizione, p.descr_uos_uoc_asl, p.programmato, p.anno
UNION ALL
 SELECT sp.alias AS indicatore,
    c.descrizione_indicatore,
    c.descrizione_asl,
    c.descrizione_uoc,
    c.descrizione_uos,
    (0)::double precision AS programmati,
    sum(c.eseguiti) AS eseguiti,
    sp.anno
   FROM (chatbot.vw_cu c
     JOIN matrix.struttura_piani sp ON ((sp.id = c.id_indicatore)))
  WHERE (NOT (EXISTS ( SELECT 1
           FROM chatbot.vw_programmazioni_matrix p
          WHERE ((p.id_indicatore = c.id_indicatore) AND (p.id_uos_uoc_asl = c.id_uos) AND (p.livello_struttura = 3)))))
  GROUP BY sp.alias, c.descrizione_indicatore, c.descrizione_asl, c.descrizione_uoc, c.descrizione_uos, sp.anno
WITH NO DATA;


-- ============================================================================
-- STEP 6: Refresh delle materialized views (con JIT disabilitato)
-- ============================================================================

SET jit = off;

REFRESH MATERIALIZED VIEW chatbot.vw_cu;
REFRESH MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti;
REFRESH MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti_x;

RESET jit;
