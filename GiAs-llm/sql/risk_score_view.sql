-- ============================================================================
-- VIEW: v_risk_score_per_attivita
-- ============================================================================
-- Calcola il risk score per tipologia di attivita' basato su dati storici NC.
--
-- Formula: risk_score = P(NC) × Impatto × 100
--   - P(NC) = (NC gravi + NC non gravi) / controlli
--   - Impatto = NC gravi / controlli
--
-- Soglie calibrate su distribuzione reale (P90=6.6, P75=3.0, P50=0.66):
--   - ALTO RISCHIO: > 7 (top 10%)
--   - MEDIO RISCHIO: 3-7 (top 25%)
--   - BASSO RISCHIO: 1-3 (25-50%)
--   - RISCHIO MINIMO: < 1 (bottom 50%)
--
-- Fix applicati:
--   - COALESCE per gestire NULL nei campi NC (90% del dataset ha NULL)
--   - NULLS LAST per evitare NULL in cima alla classifica
--   - Filtro risk_score > 0 per escludere attivita' senza NC
-- ============================================================================

DROP VIEW IF EXISTS v_risk_score_per_attivita;

CREATE VIEW v_risk_score_per_attivita AS
WITH aggregated AS (
    SELECT
        macroarea_sottoposta_a_controllo AS macroarea,
        aggregazione_sottoposta_a_controllo AS aggregazione,
        linea_attivita_sottoposta_a_controllo AS linea_attivita,
        COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) AS tot_nc_gravi,
        COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0) AS tot_nc_non_gravi,
        COUNT(*) AS numero_controlli_totali
    FROM ocse_isp_semp
    GROUP BY 1, 2, 3
),
with_metrics AS (
    SELECT
        macroarea,
        aggregazione,
        linea_attivita,
        tot_nc_gravi,
        tot_nc_non_gravi,
        (tot_nc_gravi + tot_nc_non_gravi) AS tot_nc_totali,
        numero_controlli_totali,
        -- Probabilita' NC = (NC totali) / controlli
        CASE
            WHEN numero_controlli_totali > 0
            THEN (tot_nc_gravi + tot_nc_non_gravi)::FLOAT / numero_controlli_totali
            ELSE 0
        END AS prob_nc,
        -- Impatto = NC gravi / controlli
        CASE
            WHEN numero_controlli_totali > 0
            THEN tot_nc_gravi::FLOAT / numero_controlli_totali
            ELSE 0
        END AS impatto
    FROM aggregated
),
with_risk AS (
    SELECT
        *,
        -- Risk Score = P(NC) × Impatto × 100
        ROUND((prob_nc * impatto * 100)::NUMERIC, 3) AS risk_score,
        -- Classificazione rischio (soglie calibrate)
        CASE
            WHEN (prob_nc * impatto * 100) > 7 THEN 'ALTO'
            WHEN (prob_nc * impatto * 100) > 3 THEN 'MEDIO'
            WHEN (prob_nc * impatto * 100) > 1 THEN 'BASSO'
            ELSE 'MINIMO'
        END AS risk_category
    FROM with_metrics
)
SELECT *
FROM with_risk
WHERE risk_score > 0  -- Escludi attivita' senza NC
ORDER BY risk_score DESC NULLS LAST;

-- ============================================================================
-- Query di esempio per report
-- ============================================================================

-- Top 10 attivita' a rischio
-- SELECT * FROM v_risk_score_per_attivita LIMIT 10;

-- Conteggio per categoria rischio
-- SELECT
--     risk_category,
--     COUNT(*) AS num_attivita,
--     ROUND(AVG(risk_score)::NUMERIC, 2) AS avg_score,
--     MAX(risk_score) AS max_score
-- FROM v_risk_score_per_attivita
-- GROUP BY risk_category
-- ORDER BY
--     CASE risk_category
--         WHEN 'ALTO' THEN 1
--         WHEN 'MEDIO' THEN 2
--         WHEN 'BASSO' THEN 3
--         ELSE 4
--     END;

-- ============================================================================
-- Query diretta (alternativa senza VIEW)
-- ============================================================================
-- Usa questa se non puoi creare VIEW nel database:

/*
SELECT
    macroarea_sottoposta_a_controllo AS macroarea,
    aggregazione_sottoposta_a_controllo AS aggregazione,
    linea_attivita_sottoposta_a_controllo AS linea_attivita,
    COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) AS tot_nc_gravi,
    COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0) AS tot_nc_non_gravi,
    COUNT(*) AS numero_controlli,
    -- Risk Score = P(NC) × Impatto × 100
    ROUND(
        (
            (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
             COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * (
            COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * 100
    , 3) AS risk_score,
    -- Categoria
    CASE
        WHEN (
            (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
             COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * (
            COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * 100 > 7 THEN 'ALTO'
        WHEN (
            (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
             COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * (
            COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * 100 > 3 THEN 'MEDIO'
        WHEN (
            (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
             COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * (
            COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::FLOAT /
            NULLIF(COUNT(*), 0)
        ) * 100 > 1 THEN 'BASSO'
        ELSE 'MINIMO'
    END AS risk_category
FROM ocse_isp_semp
GROUP BY 1, 2, 3
HAVING (
    (COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0) +
     COALESCE(SUM(CAST(numero_nc_non_gravi AS INTEGER)), 0))::FLOAT /
    NULLIF(COUNT(*), 0)
) * (
    COALESCE(SUM(CAST(numero_nc_gravi AS INTEGER)), 0)::FLOAT /
    NULLIF(COUNT(*), 0)
) * 100 > 0
ORDER BY risk_score DESC NULLS LAST;
*/
