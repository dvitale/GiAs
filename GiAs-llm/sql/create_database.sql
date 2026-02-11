-- Create GiAs-llm PostgreSQL database and tables
-- Based on config.json table definitions and CSV structure

-- Create database (run as superuser)
CREATE DATABASE IF NOT EXISTS gias_db;

-- Connect to the database
\c gias_db;

-- Create tables based on config.json mappings

-- 1. piani_monitoraggio table
CREATE TABLE IF NOT EXISTS piani_monitoraggio (
    id SERIAL PRIMARY KEY,
    sezione VARCHAR(50),
    alias VARCHAR(10),
    descrizione TEXT,
    alias_indicatore VARCHAR(20),
    descrizione_2 TEXT,
    campionamento BOOLEAN
);

-- 2. attivita_master table (Master list rev 11_filtered.csv)
CREATE TABLE IF NOT EXISTS attivita_master (
    id SERIAL PRIMARY KEY,
    macroarea VARCHAR(255),
    aggregazione VARCHAR(255),
    attivita VARCHAR(255),
    sezione_categoria VARCHAR(100),
    piano VARCHAR(10),
    descrizione_piano TEXT
);

-- 3. vw_2025_eseguiti table (vw_cu.csv)
CREATE TABLE IF NOT EXISTS vw_2025_eseguiti (
    id SERIAL PRIMARY KEY,
    asl VARCHAR(50),
    uoc VARCHAR(100),
    descrizione_piano TEXT,
    macroarea_cu VARCHAR(255),
    aggregazione_cu VARCHAR(255),
    attivita_cu VARCHAR(255),
    data_controllo DATE,
    comune VARCHAR(100),
    indirizzo TEXT,
    num_riconoscimento VARCHAR(100),
    esito VARCHAR(50)
);

-- 4. osa_mai_controllati table
CREATE TABLE IF NOT EXISTS osa_mai_controllati (
    id SERIAL PRIMARY KEY,
    asl VARCHAR(50),
    comune VARCHAR(100),
    indirizzo TEXT,
    macroarea VARCHAR(255),
    aggregazione VARCHAR(255),
    attivita VARCHAR(255),
    num_riconoscimento VARCHAR(100),
    piano VARCHAR(10),
    descrizione_piano TEXT
);

-- 5. ocse_isp_semp_2025 table (isp_sempl_in_chiaro_2016_2025.csv)
CREATE TABLE IF NOT EXISTS ocse_isp_semp_2025 (
    id SERIAL PRIMARY KEY,
    anno INTEGER,
    asl VARCHAR(50),
    uoc VARCHAR(100),
    comune VARCHAR(100),
    macroarea_sottoposta_a_controllo VARCHAR(255),
    aggregazione_sottoposta_a_controllo VARCHAR(255),
    attivita_sottoposta_a_controllo VARCHAR(255),
    numero_nc_gravi INTEGER DEFAULT 0,
    numero_nc_non_gravi INTEGER DEFAULT 0,
    numero_controlli INTEGER DEFAULT 0
);

-- 6. vw_diff_programmati_eseguiti table
CREATE TABLE IF NOT EXISTS vw_diff_programmati_eseguiti (
    id SERIAL PRIMARY KEY,
    asl VARCHAR(50),
    descrizione_uoc VARCHAR(100),
    piano VARCHAR(10),
    descrizione_piano TEXT,
    programmati INTEGER DEFAULT 0,
    eseguiti INTEGER DEFAULT 0,
    differenza INTEGER DEFAULT 0,
    percentuale_esecuzione DECIMAL(5,2) DEFAULT 0.0
);

-- 7. personale table
CREATE TABLE IF NOT EXISTS personale (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    asl VARCHAR(50),
    descrizione VARCHAR(255),
    descrizione_area_struttura_complessa TEXT
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_piani_alias ON piani_monitoraggio(alias);
CREATE INDEX IF NOT EXISTS idx_controlli_asl ON vw_2025_eseguiti(asl);
CREATE INDEX IF NOT EXISTS idx_controlli_piano ON vw_2025_eseguiti(descrizione_piano);
CREATE INDEX IF NOT EXISTS idx_osa_asl ON osa_mai_controllati(asl);
CREATE INDEX IF NOT EXISTS idx_osa_piano ON osa_mai_controllati(piano);
CREATE INDEX IF NOT EXISTS idx_ocse_asl ON ocse_isp_semp_2025(asl);
CREATE INDEX IF NOT EXISTS idx_ocse_anno ON ocse_isp_semp_2025(anno);
CREATE INDEX IF NOT EXISTS idx_diff_asl ON vw_diff_programmati_eseguiti(asl);
CREATE INDEX IF NOT EXISTS idx_diff_piano ON vw_diff_programmati_eseguiti(piano);
CREATE INDEX IF NOT EXISTS idx_personale_user ON personale(user_id);
CREATE INDEX IF NOT EXISTS idx_personale_asl ON personale(asl);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;