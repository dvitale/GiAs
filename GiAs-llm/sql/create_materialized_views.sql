-- =====================================================================
-- GiAs-llm — Materialized Views per migrazione Hybrid SQL-first (Fase 1)
-- =====================================================================
--
-- Nota importante: la tabella `piani_monitoraggio` è GIÀ una MATERIALIZED
-- VIEW, creata da `sql/create_normalized_views.sql` via dblink dalla
-- sorgente remota `gisa.chatbot.dpat`. Non serve crearne un'altra —
-- il SqlPianoRepository (data_sources/repositories/sql_piano_repository.py)
-- la interroga direttamente.
--
-- Questo file serve a:
--   1. Documentare la procedura di REFRESH della MV esistente
--   2. Garantire gli INDICI necessari per le query del repository
--   3. Preparare il terreno per MV future (Fase 2/3: controlli, risk)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Indici su piani_monitoraggio (idempotenti)
--
-- Verifica: gli indici base sono già presenti, vedi create_normalized_views.sql
--   - idx_piani_unique (anno, sezione, alias_piano_attivita, alias_indicatore)
--   - idx_piani_anno
--   - idx_piani_alias_piano
--   - idx_piani_alias_indicatore
--
-- Aggiungiamo indici mirati per le query del SqlPianoRepository:
-- ---------------------------------------------------------------------

-- Indice per ricerca full-text su descrizione (usato da search_piani_by_db).
-- PostgreSQL trigram per ILIKE efficiente.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_piani_descrizione_piano_trgm
    ON piani_monitoraggio USING gin (descrizione_piano_attivita gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_piani_descrizione_indicatore_trgm
    ON piani_monitoraggio USING gin (descrizione_indicatore gin_trgm_ops);

-- Indice per UPPER(alias_*) usato dai 3 fallback di find_by_alias.
-- Permette al planner di usare index scan invece di seq scan sul regex.
CREATE INDEX IF NOT EXISTS idx_piani_alias_piano_upper
    ON piani_monitoraggio (UPPER(alias_piano_attivita));

CREATE INDEX IF NOT EXISTS idx_piani_alias_indicatore_upper
    ON piani_monitoraggio (UPPER(alias_indicatore));

-- ---------------------------------------------------------------------
-- 2. Procedura di REFRESH
--
-- Manuale:
--   REFRESH MATERIALIZED VIEW CONCURRENTLY piani_monitoraggio;
--
-- CONCURRENTLY richiede l'indice UNIQUE, già presente (idx_piani_unique).
-- Durante il refresh le query di lettura continuano a funzionare sulla
-- versione precedente della MV.
--
-- Da automatizzare in Fase 2/3: cron job o pg_cron per refresh schedulato
-- (proposta: nightly alle 03:00 quando i dati gisa sono stabilizzati).
-- ---------------------------------------------------------------------

-- Esempio di refresh: scommentare per eseguire manualmente
-- REFRESH MATERIALIZED VIEW CONCURRENTLY piani_monitoraggio;

-- ---------------------------------------------------------------------
-- 3. Verifica post-esecuzione
--
-- Le query di sotto servono a convalidare che gli indici siano attivi.
-- Sono solo output informativi, non bloccanti.
-- ---------------------------------------------------------------------

\echo 'Indici su piani_monitoraggio dopo questo script:'
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'piani_monitoraggio'
ORDER BY indexname;

\echo ''
\echo 'Statistiche MV piani_monitoraggio:'
SELECT
    schemaname,
    matviewname,
    hasindexes,
    ispopulated,
    pg_size_pretty(pg_relation_size(schemaname || '.' || matviewname)) AS size
FROM pg_matviews
WHERE matviewname = 'piani_monitoraggio';
