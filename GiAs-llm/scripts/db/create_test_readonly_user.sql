-- =====================================================================
-- GiAs-llm — User PostgreSQL readonly per test suite
-- =====================================================================
--
-- Scopo: creare un ruolo "gias_test_readonly" con solo GRANT SELECT sulle
-- tabelle di gias_db. Questo user viene usato dai test unit/integration
-- che leggono direttamente dal DB (marker @pytest.mark.db) come rete di
-- sicurezza: se qualcuno scrive per errore un DELETE/UPDATE in un tool,
-- la connection fallisce con permission denied invece di corrompere i
-- dati condivisi del DB di sviluppo.
--
-- Eseguire come superuser (postgres o gisa_owner) una sola volta:
--   psql -U postgres -d gias_db -f scripts/db/create_test_readonly_user.sql
--
-- Lo script è idempotente: può essere rieseguito senza effetti collaterali
-- (aggiorna la password e riapplica i grant).
--
-- Dopo l'esecuzione, impostare la password come env var nei test:
--   export GIAS_TEST_DB_PASSWORD='<valore>'
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gias_test_readonly') THEN
        CREATE ROLE gias_test_readonly
            WITH LOGIN
            PASSWORD 'gias_test_ro_2026'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            CONNECTION LIMIT 20;
        RAISE NOTICE 'Creato ruolo gias_test_readonly';
    ELSE
        ALTER ROLE gias_test_readonly WITH PASSWORD 'gias_test_ro_2026';
        RAISE NOTICE 'Password gias_test_readonly aggiornata';
    END IF;
END
$$;

-- Grant di base
GRANT CONNECT ON DATABASE gias_db TO gias_test_readonly;
GRANT USAGE ON SCHEMA public TO gias_test_readonly;

-- Schema old (tabelle archiviate dopo normalizzazione) — accesso read per test
-- che verificano backward compatibility.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'old') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA old TO gias_test_readonly';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA old TO gias_test_readonly';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA old GRANT SELECT ON TABLES TO gias_test_readonly';
    END IF;
END
$$;

-- SELECT su tutte le tabelle correnti di public
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gias_test_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO gias_test_readonly;

-- Default per tabelle future (create dopo questo script)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO gias_test_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO gias_test_readonly;

-- Verifica finale: elencare i privilegi ottenuti
-- (output informativo, non blocca lo script)
\echo 'Grants per gias_test_readonly:'
SELECT table_schema, COUNT(*) AS tables_with_select
FROM information_schema.table_privileges
WHERE grantee = 'gias_test_readonly' AND privilege_type = 'SELECT'
GROUP BY table_schema
ORDER BY table_schema;
