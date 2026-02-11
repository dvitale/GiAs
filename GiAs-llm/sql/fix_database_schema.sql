-- Fix database schema to match actual CSV structures
\c gias_db;

-- Drop existing tables to recreate with correct schemas
DROP TABLE IF EXISTS piani_monitoraggio CASCADE;
DROP TABLE IF EXISTS attivita_master CASCADE;
DROP TABLE IF EXISTS vw_2025_eseguiti CASCADE;
DROP TABLE IF EXISTS osa_mai_controllati CASCADE;
DROP TABLE IF EXISTS ocse_isp_semp_2025 CASCADE;
DROP TABLE IF EXISTS vw_diff_programmati_eseguiti CASCADE;
DROP TABLE IF EXISTS personale CASCADE;

-- 1. piani_monitoraggio table (fix column name with hyphen)
CREATE TABLE piani_monitoraggio (
    id SERIAL PRIMARY KEY,
    sezione VARCHAR(50),
    alias VARCHAR(10),
    descrizione TEXT,
    alias_indicatore VARCHAR(20),
    "descrizione-2" TEXT,  -- Quoted column name for hyphen
    campionamento BOOLEAN
);

-- 2. attivita_master table (based on actual CSV columns)
CREATE TABLE attivita_master (
    id SERIAL PRIMARY KEY,
    norma VARCHAR(255),
    macroarea VARCHAR(255),
    aggregazione VARCHAR(255),
    "linea_di_attivita" VARCHAR(500),  -- Column name has spaces
    registrati CHAR(1),
    riconosciuti CHAR(1)
);

-- 3. vw_2025_eseguiti table (based on actual CSV columns from vw_cu.csv)
CREATE TABLE vw_2025_eseguiti (
    id SERIAL PRIMARY KEY,
    id_controllo BIGINT,
    data_inizio_controllo TIMESTAMP,
    eseguiti DECIMAL(10,2),
    tecnica_controllo VARCHAR(100),
    macroarea_cu TEXT,
    aggregazione_cu TEXT,
    attivita_cu TEXT,
    id_indicatore BIGINT,
    descrizione_indicatore TEXT,
    id_piano BIGINT,
    descrizione_piano TEXT,
    id_piano_o_attivita BIGINT,
    piano_o_attivita VARCHAR(100),
    id_sezione BIGINT,
    sezione VARCHAR(100),
    id_uos BIGINT,
    descrizione_uos TEXT,
    id_uoc BIGINT,
    descrizione_uoc TEXT,
    id_asl BIGINT,
    descrizione_asl TEXT,
    riferimento_id BIGINT,
    riferimento_nome_tab VARCHAR(100),
    ragione_sociale TEXT,
    norma VARCHAR(50),
    id_norma INTEGER,
    num_registrazione VARCHAR(100),
    partita_iva VARCHAR(20),
    approval_number VARCHAR(50),
    latitudine_stab DECIMAL(10,6),
    longitudine_stab DECIMAL(10,6),
    id_campione BIGINT,
    analita_lev_1 VARCHAR(100),
    analita_lev_2 VARCHAR(100),
    analita_lev_3 VARCHAR(100),
    analita_lev_4 VARCHAR(100),
    matrice_lev_1 VARCHAR(100),
    matrice_lev_2 VARCHAR(100),
    matrice_lev_3 VARCHAR(100)
);

-- 4. osa_mai_controllati table (based on actual CSV)
CREATE TABLE osa_mai_controllati (
    id SERIAL PRIMARY KEY,
    asl VARCHAR(100),
    codice_norma VARCHAR(20),
    codice_fiscale VARCHAR(20),
    n_reg VARCHAR(50),
    num_riconoscimento VARCHAR(100),
    partita_iva VARCHAR(20),
    comune VARCHAR(100),
    provincia_stab VARCHAR(100),
    indirizzo TEXT,
    latitudine_stab DECIMAL(10,6),
    longitudine_stab DECIMAL(10,6),
    codice_fiscale_rappresentante VARCHAR(20),
    nominativo_rappresentante VARCHAR(255),
    data_inizio_attivita DATE,
    data_fine_attivita DATE,
    macroarea TEXT,
    aggregazione TEXT,
    attivita TEXT,
    info_complete_attivita TEXT
);

-- 5. ocse_isp_semp_2025 table (based on actual isp CSV structure)
CREATE TABLE ocse_isp_semp_2025 (
    id SERIAL PRIMARY KEY,
    id_controllo_ufficiale BIGINT,
    id_asl INTEGER,
    asl VARCHAR(100),
    norma VARCHAR(50),
    numero_registrazione VARCHAR(100),
    numero_riconoscimento VARCHAR(100),
    macroarea_sottoposta_a_controllo TEXT,
    aggregazione_sottoposta_a_controllo TEXT,
    linea_attivita_sottoposta_a_controllo TEXT,
    tipo_controllo VARCHAR(100),
    anno_controllo INTEGER,
    ruoli_componente_nucleo VARCHAR(100),
    tipo_non_conformita VARCHAR(100),
    oggetto_non_conformita VARCHAR(100),
    provincia_stab VARCHAR(100),
    comune VARCHAR(100),
    numero_nc_non_gravi INTEGER DEFAULT 0,
    numero_nc_gravi INTEGER DEFAULT 0,
    data_inizio_attivita TIMESTAMP
);

-- 6. vw_diff_programmati_eseguiti table (based on actual CSV)
CREATE TABLE vw_diff_programmati_eseguiti (
    id SERIAL PRIMARY KEY,
    indicatore VARCHAR(20),
    descrizione_indicatore TEXT,
    descrizione_asl TEXT,
    descrizione_uoc TEXT,
    descrizione_uos TEXT,
    programmati DECIMAL(10,2) DEFAULT 0,
    eseguiti DECIMAL(10,2) DEFAULT 0,
    anno INTEGER
);

-- 7. personale table (based on actual CSV with pipe separator)
CREATE TABLE personale (
    id SERIAL PRIMARY KEY,
    asl VARCHAR(100),
    descrizione_asl TEXT,
    descrizione_uoc TEXT,
    descrizione_uos TEXT,
    namefirst VARCHAR(100),
    namelast VARCHAR(100),
    codice_fiscale VARCHAR(20),
    user_id VARCHAR(100)
);

-- Create indexes for better performance
CREATE INDEX idx_piani_alias ON piani_monitoraggio(alias);
CREATE INDEX idx_controlli_asl ON vw_2025_eseguiti(descrizione_asl);
CREATE INDEX idx_controlli_piano ON vw_2025_eseguiti(descrizione_piano);
CREATE INDEX idx_osa_asl ON osa_mai_controllati(asl);
CREATE INDEX idx_osa_norma ON osa_mai_controllati(codice_norma);
CREATE INDEX idx_ocse_asl ON ocse_isp_semp_2025(asl);
CREATE INDEX idx_diff_asl ON vw_diff_programmati_eseguiti(descrizione_asl);
CREATE INDEX idx_personale_user ON personale(user_id);
CREATE INDEX idx_personale_asl ON personale(asl);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;