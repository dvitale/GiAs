#!/bin/bash
# =============================================================================
# ETL Script: Popola gias_db da gisa e mdgm
# Eseguire con: bash /opt/lang-env/scripts/etl_gias.sh
# =============================================================================
set -euo pipefail

PGHOST=localhost
PGUSER=gisa_owner
PGPASSWORD=5XRe4g8Q5QSg
export PGHOST PGUSER PGPASSWORD

GISA=gisa
MDGM=mdgm
GIAS=gias_db
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

psql_gisa()  { psql -d "$GISA" -v ON_ERROR_STOP=1 "$@"; }
psql_mdgm()  { psql -d "$MDGM" -v ON_ERROR_STOP=1 "$@"; }
psql_gias()  { psql -d "$GIAS" -v ON_ERROR_STOP=1 "$@"; }

# ---------------------------------------------------------------------------
# Funzione di verifica row count sorgente vs destinazione
#   $1 = label (nome step)
#   $2 = comando psql sorgente (psql_gisa o psql_mdgm)
#   $3 = query sorgente (SELECT count(*) FROM ...)
#   $4 = query destinazione (SELECT count(*) FROM ...)
#   $5 = modalita': "exact" (default) oppure "gte" (dest >= sorgente, per LEFT JOIN)
# ---------------------------------------------------------------------------
check_count() {
    local label="$1" src_cmd="$2" src_query="$3" dst_query="$4" mode="${5:-exact}"
    local src_count dst_count
    src_count=$($src_cmd -tAc "$src_query")
    dst_count=$(psql_gias -tAc "$dst_query")
    if [ "$mode" = "exact" ] && [ "$src_count" -ne "$dst_count" ]; then
        echo "   ERRORE $label: sorgente=$src_count destinazione=$dst_count (atteso uguale)" >&2
        exit 1
    elif [ "$mode" = "gte" ] && [ "$dst_count" -lt "$src_count" ]; then
        echo "   ERRORE $label: sorgente=$src_count destinazione=$dst_count (atteso dest >= sorgente)" >&2
        exit 1
    fi
    echo "   CHECK $label: sorgente=$src_count destinazione=$dst_count OK"
}

echo "=== ETL gias_db - inizio: $(date) ==="
echo ">>> Temp dir: $TMPDIR"

# ===========================================================================
# 1. masterlist  (gisa.chatbot.masterlist)
# ===========================================================================
echo ">>> 1. masterlist"

psql_gisa -c "\copy (
    SELECT
        norma, macroarea, aggregazione, linea_attivita,
        CASE WHEN registrati  THEN 'S' ELSE 'N' END,
        CASE WHEN riconosciuti THEN 'S' ELSE 'N' END
    FROM chatbot.masterlist
) TO STDOUT WITH CSV" > "$TMPDIR/masterlist.csv"

psql_gias -c "TRUNCATE TABLE public.masterlist;"
psql_gias -c "\copy public.masterlist(norma,macroarea,aggregazione,linea_di_attivita,registrati,riconosciuti) FROM STDIN WITH CSV" < "$TMPDIR/masterlist.csv"

echo "   masterlist: $(wc -l < "$TMPDIR/masterlist.csv") righe"
check_count "masterlist" psql_gisa \
    "SELECT count(*) FROM chatbot.masterlist" \
    "SELECT count(*) FROM public.masterlist"

# ===========================================================================
# 2. personale  (gisa.chatbot.personale)
# ===========================================================================
echo ">>> 2. personale"

psql_gisa -c "\copy (
    SELECT descrizione_asl, descrizione_uoc, descrizione_uos,
           namefirst, namelast, codice_fiscale, user_id::text, anno
    FROM chatbot.personale
) TO STDOUT WITH CSV" > "$TMPDIR/personale.csv"

psql_gias -c "TRUNCATE TABLE public.personale;"
psql_gias -c "\copy public.personale(descrizione_asl,descrizione_uoc,descrizione_uos,namefirst,namelast,codice_fiscale,user_id,anno) FROM STDIN WITH CSV" < "$TMPDIR/personale.csv"

echo "   personale: $(wc -l < "$TMPDIR/personale.csv") righe"
check_count "personale" psql_gisa \
    "SELECT count(*) FROM chatbot.personale" \
    "SELECT count(*) FROM public.personale"

# ===========================================================================
# 3. osa_mai_controllati  (mdgm.chatbot.osa_mai_controllati)
# ===========================================================================
echo ">>> 3. osa_mai_controllati"

psql_mdgm -c "\copy (
    SELECT asl, codice_norma, codice_fiscale, n_reg, num_riconoscimento,
           partita_iva, comune, provincia_stab, indirizzo,
           latitudine_stab::text, longitudine_stab::text,
           codice_fiscale_rappresentante, nominativo_rappresentante,
           data_inizio_attivita, data_fine_attivita,
           macroarea, aggregazione, attivita, ragione_sociale
    FROM chatbot.osa_mai_controllati
) TO STDOUT WITH CSV" > "$TMPDIR/osa_mai_controllati.csv"

psql_gias -c "TRUNCATE TABLE public.osa_mai_controllati;"
psql_gias -c "\copy public.osa_mai_controllati(asl,codice_norma,codice_fiscale,n_reg,num_riconoscimento,partita_iva,comune,provincia_stab,indirizzo,latitudine_stab,longitudine_stab,codice_fiscale_rappresentante,nominativo_rappresentante,data_inizio_attivita,data_fine_attivita,macroarea,aggregazione,attivita,ragione_sociale) FROM STDIN WITH CSV" < "$TMPDIR/osa_mai_controllati.csv"

echo "   osa_mai_controllati: $(wc -l < "$TMPDIR/osa_mai_controllati.csv") righe"
check_count "osa_mai_controllati" psql_mdgm \
    "SELECT count(*) FROM chatbot.osa_mai_controllati" \
    "SELECT count(*) FROM public.osa_mai_controllati"

# ===========================================================================
# 4. piani_monitoraggio (MATVIEW)  (gisa.chatbot.dpat)
# ===========================================================================
echo ">>> 4. piani_monitoraggio"

psql_gisa -c "\copy (
    SELECT anno, sezione, alias_piano_attivita, descrizione_piano_attivita,
           alias_indicatore, descrizione_indicatore, tipo_piano_attivita,
           campionamento, tipo_item_dpat
    FROM chatbot.dpat
) TO STDOUT WITH CSV" > "$TMPDIR/dpat.csv"

psql_gias <<'SQL'
DROP TABLE IF EXISTS public.piani_monitoraggio CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.piani_monitoraggio;
CREATE TABLE public.piani_monitoraggio (
    anno integer,
    sezione text,
    alias_piano_attivita text,
    descrizione_piano_attivita text,
    alias_indicatore text,
    descrizione_indicatore text,
    tipo_piano_attivita text,
    campionamento boolean,
    tipo_item_dpat varchar
);
TRUNCATE public.piani_monitoraggio;
SQL

psql_gias -c "\copy public.piani_monitoraggio FROM STDIN WITH CSV" < "$TMPDIR/dpat.csv"

echo "   piani_monitoraggio: $(wc -l < "$TMPDIR/dpat.csv") righe"
check_count "piani_monitoraggio" psql_gisa \
    "SELECT count(*) FROM chatbot.dpat" \
    "SELECT count(*) FROM public.piani_monitoraggio"

# ===========================================================================
# 5. cu_diff_programmati_eseguiti
#    (mdgm.chatbot.vw_diff_programmati_eseguiti_x + dpat)
# ===========================================================================
echo ">>> 5. cu_diff_programmati_eseguiti"

psql_mdgm -c "\copy (
    SELECT indicatore, descrizione_indicatore, descrizione_asl,
           descrizione_uoc, descrizione_uos, programmati, eseguiti, anno
    FROM chatbot.vw_diff_programmati_eseguiti_x
) TO STDOUT WITH CSV" > "$TMPDIR/diff.csv"

psql_gias <<'SQL'
DROP TABLE IF EXISTS public._tmp_diff;
CREATE TABLE public._tmp_diff (
    indicatore text, descrizione_indicatore text,
    descrizione_asl text, descrizione_uoc text, descrizione_uos text,
    programmati double precision, eseguiti double precision, anno integer
);
SQL

psql_gias -c "\copy public._tmp_diff FROM STDIN WITH CSV" < "$TMPDIR/diff.csv"

psql_gias <<'SQL'
TRUNCATE TABLE public.cu_diff_programmati_eseguiti;

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
FROM public._tmp_diff d
LEFT JOIN public.piani_monitoraggio pm
    ON trim(pm.alias_indicatore) = trim(d.indicatore)
   AND pm.anno = d.anno;

DROP TABLE public._tmp_diff;
SQL

echo "   cu_diff_programmati_eseguiti: $(wc -l < "$TMPDIR/diff.csv") righe sorgente"
check_count "cu_diff_programmati_eseguiti" psql_mdgm \
    "SELECT count(*) FROM chatbot.vw_diff_programmati_eseguiti_x" \
    "SELECT count(*) FROM public.cu_diff_programmati_eseguiti" \
    gte

# ===========================================================================
# 6. cu_eseguiti_nc
#    (mdgm.chatbot.vw_cu_xx + vw_nc + dpat + stabilimenti.comune)
# ===========================================================================
echo ">>> 6. cu_eseguiti_nc"

# Rimuovo id_campione se esiste
psql_gias -c "
DO \$\$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='cu_eseguiti_nc' AND column_name='id_campione'
    ) THEN
        ALTER TABLE public.cu_eseguiti_nc DROP COLUMN id_campione;
    END IF;
END \$\$;
"

echo "   6a. export vw_cu_xx + comune da mdgm..."
psql_mdgm -c "\copy (
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
    LEFT JOIN \"Analisi_dev\".vw_dbi_get_all_stabilimenti__validi s
        ON s.riferimento_id = cu.riferimento_id
       AND s.riferimento_id_nome_tab = cu.riferimento_nome_tab
) TO STDOUT WITH CSV" > "$TMPDIR/cu.csv"

echo "   6b. export vw_nc da mdgm..."
psql_mdgm -c "\copy (
    SELECT id_controllo, tipo_non_conformita,
           numero_nc_non_gravi, numero_nc_gravi, oggetto_non_conformita
    FROM chatbot.vw_nc
) TO STDOUT WITH CSV" > "$TMPDIR/nc.csv"

echo "   6c. import e join in gias..."

psql_gias <<'SQL'
DROP TABLE IF EXISTS public._tmp_cu;
CREATE TABLE public._tmp_cu (
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
DROP TABLE IF EXISTS public._tmp_nc;
CREATE TABLE public._tmp_nc (
    id_controllo integer, tipo_non_conformita text,
    numero_nc_non_gravi bigint, numero_nc_gravi bigint,
    oggetto_non_conformita text
);
SQL

psql_gias -c "\copy public._tmp_cu FROM STDIN WITH CSV" < "$TMPDIR/cu.csv"
psql_gias -c "\copy public._tmp_nc FROM STDIN WITH CSV" < "$TMPDIR/nc.csv"

psql_gias <<'SQL'
TRUNCATE TABLE public.cu_eseguiti_nc;

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
FROM public._tmp_cu cu
LEFT JOIN public._tmp_nc nc ON nc.id_controllo = cu.id_controllo
LEFT JOIN public.piani_monitoraggio pm
    ON trim(pm.alias_indicatore) = trim(cu.alias_indicatore);

DROP TABLE public._tmp_cu;
DROP TABLE public._tmp_nc;
SQL

echo "   cu_eseguiti_nc: $(wc -l < "$TMPDIR/cu.csv") righe CU, $(wc -l < "$TMPDIR/nc.csv") righe NC"
check_count "cu_eseguiti_nc" psql_mdgm \
    "SELECT count(*) FROM chatbot.vw_cu_xx" \
    "SELECT count(*) FROM public.cu_eseguiti_nc" \
    gte

# ===========================================================================
# 7. indicatori_non_catalogati (derivata)
# ===========================================================================
echo ">>> 7. indicatori_non_catalogati"

psql_gias <<'SQL'
TRUNCATE TABLE public.indicatori_non_catalogati;

INSERT INTO public.indicatori_non_catalogati (
    alias_indicatore, descrizione_indicatore, fonte, data_rilevamento
)
SELECT DISTINCT ON (trim(cu.alias_indicatore))
    trim(cu.alias_indicatore)::varchar AS alias_indicatore,
    cu.descrizione_indicatore,
    'cu_eseguiti_x'::varchar     AS fonte,
    now()                        AS data_rilevamento
FROM public.cu_eseguiti_nc cu
WHERE cu.alias_indicatore IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.piani_monitoraggio pm
    WHERE trim(pm.alias_indicatore) = trim(cu.alias_indicatore)
)
ORDER BY trim(cu.alias_indicatore);
SQL

echo "=== ETL completato con successo: $(date) ==="
