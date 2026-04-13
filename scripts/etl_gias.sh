#!/bin/bash
# =============================================================================
# ETL Script: Popola gias_db da gisa e mdgm
#
# Modalita':
#   etl_gias.sh [full]                  Esegue export + import (default, come prima)
#   etl_gias.sh export [BUNDLE_DIR]     Solo export CSV da gisa/mdgm + manifest
#   etl_gias.sh import <BUNDLE_DIR>     Solo import CSV in gias_db da bundle
#   etl_gias.sh serve [PORT]            Export + avvia server HTTP per download bundle
#   etl_gias.sh pull <HOST:PORT|URL>     Scarica bundle da server remoto + import
#
# Eseguire con: bash /opt/lang-env/scripts/etl_gias.sh [full|export|import|serve|pull] [args]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Parsing modalita'
# ---------------------------------------------------------------------------
MODE="${1:-full}"
case "$MODE" in
    full|export|import|serve|pull) shift ;;
    -h|--help)
        sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    *)
        echo "Uso: $0 [full|export|import|serve|pull] [args]" >&2
        exit 1
        ;;
esac

# ---------------------------------------------------------------------------
# Credenziali DB
# ---------------------------------------------------------------------------
PGHOST=localhost
PGUSER=gisa_owner
PGPASSWORD=5XRe4g8Q5QSg
export PGHOST PGUSER PGPASSWORD

GISA=gisa
MDGM=mdgm
GIAS=gias_db

psql_gisa()  { psql -d "$GISA" -v ON_ERROR_STOP=1 "$@"; }
psql_mdgm()  { psql -d "$MDGM" -v ON_ERROR_STOP=1 "$@"; }
psql_gias()  { psql -d "$GIAS" -v ON_ERROR_STOP=1 "$@"; }

# ---------------------------------------------------------------------------
# Bundle directory
# ---------------------------------------------------------------------------
if [ "$MODE" = "full" ]; then
    BUNDLE_DIR=$(mktemp -d)
    trap 'rm -rf "$BUNDLE_DIR"' EXIT
elif [ "$MODE" = "export" ]; then
    BUNDLE_DIR="${1:-./etl_bundle_$(date +%Y%m%d_%H%M%S)}"
    mkdir -p "$BUNDLE_DIR"
elif [ "$MODE" = "import" ]; then
    BUNDLE_DIR="${1:?Errore: specificare il percorso del bundle. Uso: $0 import <BUNDLE_DIR>}"
    if [ ! -d "$BUNDLE_DIR" ]; then
        echo "ERRORE: directory bundle non trovata: $BUNDLE_DIR" >&2
        exit 1
    fi
elif [ "$MODE" = "serve" ]; then
    ETL_SERVE_PORT="${1:-9000}"
    BUNDLE_DIR=$(mktemp -d)
    trap 'rm -rf "$BUNDLE_DIR"' EXIT
elif [ "$MODE" = "pull" ]; then
    ETL_REMOTE="${1:?Errore: specificare HOST:PORT del server. Uso: $0 pull <HOST:PORT>}"
    BUNDLE_DIR=$(mktemp -d)
    trap 'rm -rf "$BUNDLE_DIR"' EXIT
fi

# ---------------------------------------------------------------------------
# Manifest: scrittura e lettura
# ---------------------------------------------------------------------------
write_manifest() {
    local manifest="$BUNDLE_DIR/manifest.txt"
    echo "# ETL export manifest - $(date -Iseconds)" > "$manifest"
    for csv in "$BUNDLE_DIR"/*.csv; do
        [ -f "$csv" ] || continue
        local name count
        name=$(basename "$csv")
        count=$(wc -l < "$csv")
        echo "${name}=${count}" >> "$manifest"
    done
    echo "   Manifest scritto: $manifest"
}

manifest_count() {
    local csv_name="$1"
    local manifest="$BUNDLE_DIR/manifest.txt"
    grep "^${csv_name}=" "$manifest" | cut -d= -f2
}

validate_bundle() {
    local manifest="$BUNDLE_DIR/manifest.txt"
    if [ ! -f "$manifest" ]; then
        echo "ERRORE: manifest.txt non trovato in $BUNDLE_DIR" >&2
        exit 1
    fi
    local missing=0
    while IFS='=' read -r name count; do
        [[ "$name" =~ ^#.*$ ]] && continue
        [ -z "$name" ] && continue
        if [ ! -f "$BUNDLE_DIR/$name" ]; then
            echo "   ERRORE: file mancante nel bundle: $name" >&2
            missing=1
        fi
    done < "$manifest"
    if [ "$missing" -eq 1 ]; then
        echo "ERRORE: bundle incompleto, impossibile procedere" >&2
        exit 1
    fi
    echo "   Bundle validato: tutti i file presenti"
}

# ---------------------------------------------------------------------------
# check_count: verifica righe sorgente vs destinazione
#   Modalita' full  -> query DB sorgente
#   Modalita' import -> conteggio da manifest
# ---------------------------------------------------------------------------
check_count() {
    local label="$1" src_cmd="$2" src_query="$3" dst_query="$4" mode="${5:-exact}"
    local src_count dst_count

    if [ "$MODE" = "import" ]; then
        # In import il src_cmd contiene il nome del CSV, src_query e' ignorata
        src_count=$(manifest_count "$src_cmd")
    else
        src_count=$($src_cmd -tAc "$src_query")
    fi

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

# ===========================================================================
# EXPORT functions (richiedono accesso a gisa/mdgm)
# ===========================================================================

export_masterlist() {
    echo ">>> 1. masterlist [export]"
    psql_gisa -c "\copy (
        SELECT
            norma, macroarea, aggregazione, linea_attivita,
            CASE WHEN registrati  THEN 'S' ELSE 'N' END,
            CASE WHEN riconosciuti THEN 'S' ELSE 'N' END
        FROM chatbot.masterlist
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/masterlist.csv"
    echo "   masterlist: $(wc -l < "$BUNDLE_DIR/masterlist.csv") righe"
}

export_personale() {
    echo ">>> 2. personale [export]"
    psql_gisa -c "\copy (
        SELECT descrizione_asl, descrizione_uoc, descrizione_uos,
               namefirst, namelast, codice_fiscale, user_id::text, anno
        FROM chatbot.personale
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/personale.csv"
    echo "   personale: $(wc -l < "$BUNDLE_DIR/personale.csv") righe"
}

export_osa_mai_controllati() {
    echo ">>> 3. osa_mai_controllati [export]"
    psql_mdgm -c "\copy (
        SELECT asl, codice_norma, codice_fiscale, n_reg, num_riconoscimento,
               partita_iva, comune, provincia_stab, indirizzo,
               latitudine_stab::text, longitudine_stab::text,
               codice_fiscale_rappresentante, nominativo_rappresentante,
               data_inizio_attivita, data_fine_attivita,
               macroarea, aggregazione, attivita, ragione_sociale
        FROM chatbot.osa_mai_controllati
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/osa_mai_controllati.csv"
    echo "   osa_mai_controllati: $(wc -l < "$BUNDLE_DIR/osa_mai_controllati.csv") righe"
}

export_piani_monitoraggio() {
    echo ">>> 4. piani_monitoraggio [export]"
    psql_gisa -c "\copy (
        SELECT anno, sezione, alias_piano_attivita, descrizione_piano_attivita,
               alias_indicatore, descrizione_indicatore, tipo_piano_attivita,
               campionamento, tipo_item_dpat
        FROM chatbot.dpat
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/dpat.csv"
    echo "   piani_monitoraggio: $(wc -l < "$BUNDLE_DIR/dpat.csv") righe"
}

export_cu_diff() {
    echo ">>> 5. cu_diff_programmati_eseguiti [export]"
    psql_mdgm -c "\copy (
        SELECT indicatore, descrizione_indicatore, descrizione_asl,
               descrizione_uoc, descrizione_uos, programmati, eseguiti, anno
        FROM chatbot.vw_diff_programmati_eseguiti_x
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/diff.csv"
    echo "   cu_diff: $(wc -l < "$BUNDLE_DIR/diff.csv") righe"
}

export_cu_eseguiti_nc() {
    echo ">>> 6. cu_eseguiti_nc [export]"

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
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/cu.csv"

    echo "   6b. export vw_nc da mdgm..."
    psql_mdgm -c "\copy (
        SELECT id_controllo, tipo_non_conformita,
               numero_nc_non_gravi, numero_nc_gravi, oggetto_non_conformita
        FROM chatbot.vw_nc
    ) TO STDOUT WITH CSV" > "$BUNDLE_DIR/nc.csv"

    echo "   cu_eseguiti_nc: $(wc -l < "$BUNDLE_DIR/cu.csv") righe CU, $(wc -l < "$BUNDLE_DIR/nc.csv") righe NC"
}

# ===========================================================================
# IMPORT functions (richiedono accesso a gias_db)
# ===========================================================================

import_masterlist() {
    echo ">>> 1. masterlist [import]"
    psql_gias -c "TRUNCATE TABLE public.masterlist;"
    psql_gias -c "\copy public.masterlist(norma,macroarea,aggregazione,linea_di_attivita,registrati,riconosciuti) FROM STDIN WITH CSV" < "$BUNDLE_DIR/masterlist.csv"
    echo "   masterlist: $(wc -l < "$BUNDLE_DIR/masterlist.csv") righe"
}

import_personale() {
    echo ">>> 2. personale [import]"
    psql_gias -c "TRUNCATE TABLE public.personale;"
    psql_gias -c "\copy public.personale(descrizione_asl,descrizione_uoc,descrizione_uos,namefirst,namelast,codice_fiscale,user_id,anno) FROM STDIN WITH CSV" < "$BUNDLE_DIR/personale.csv"
    echo "   personale: $(wc -l < "$BUNDLE_DIR/personale.csv") righe"
}

import_osa_mai_controllati() {
    echo ">>> 3. osa_mai_controllati [import]"
    psql_gias -c "TRUNCATE TABLE public.osa_mai_controllati;"
    psql_gias -c "\copy public.osa_mai_controllati(asl,codice_norma,codice_fiscale,n_reg,num_riconoscimento,partita_iva,comune,provincia_stab,indirizzo,latitudine_stab,longitudine_stab,codice_fiscale_rappresentante,nominativo_rappresentante,data_inizio_attivita,data_fine_attivita,macroarea,aggregazione,attivita,ragione_sociale) FROM STDIN WITH CSV" < "$BUNDLE_DIR/osa_mai_controllati.csv"
    echo "   osa_mai_controllati: $(wc -l < "$BUNDLE_DIR/osa_mai_controllati.csv") righe"
}

import_piani_monitoraggio() {
    echo ">>> 4. piani_monitoraggio [import]"
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
    psql_gias -c "\copy public.piani_monitoraggio FROM STDIN WITH CSV" < "$BUNDLE_DIR/dpat.csv"
    echo "   piani_monitoraggio: $(wc -l < "$BUNDLE_DIR/dpat.csv") righe"
}

import_cu_diff() {
    echo ">>> 5. cu_diff_programmati_eseguiti [import]"

    psql_gias <<'SQL'
DROP TABLE IF EXISTS public._tmp_diff;
CREATE TABLE public._tmp_diff (
    indicatore text, descrizione_indicatore text,
    descrizione_asl text, descrizione_uoc text, descrizione_uos text,
    programmati double precision, eseguiti double precision, anno integer
);
SQL

    psql_gias -c "\copy public._tmp_diff FROM STDIN WITH CSV" < "$BUNDLE_DIR/diff.csv"

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

    echo "   cu_diff_programmati_eseguiti: $(wc -l < "$BUNDLE_DIR/diff.csv") righe sorgente"
}

import_cu_eseguiti_nc() {
    echo ">>> 6. cu_eseguiti_nc [import]"

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

    psql_gias -c "\copy public._tmp_cu FROM STDIN WITH CSV" < "$BUNDLE_DIR/cu.csv"
    psql_gias -c "\copy public._tmp_nc FROM STDIN WITH CSV" < "$BUNDLE_DIR/nc.csv"

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

    echo "   cu_eseguiti_nc: $(wc -l < "$BUNDLE_DIR/cu.csv") righe CU, $(wc -l < "$BUNDLE_DIR/nc.csv") righe NC"
}

import_indicatori_non_catalogati() {
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
}

# ===========================================================================
# Funzioni serve/pull
# ===========================================================================

# Crea archivio tar.gz del bundle
create_bundle_tar() {
    tar -czf "$BUNDLE_DIR/etl_bundle.tar.gz" -C "$BUNDLE_DIR" \
        --exclude=etl_bundle.tar.gz .
    echo "   Archivio creato: $BUNDLE_DIR/etl_bundle.tar.gz"
}

# Avvia micro-server HTTP Python per servire il bundle
start_etl_server() {
    local port="$1" bundle_dir="$2" etl_script="$3"
    python3 - "$port" "$bundle_dir" "$etl_script" <<'PYSERVER'
import sys, os, json, subprocess, tarfile, io, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = int(sys.argv[1])
BUNDLE_DIR = sys.argv[2]
ETL_SCRIPT = sys.argv[3]
TAR_PATH = os.path.join(BUNDLE_DIR, "etl_bundle.tar.gz")
MANIFEST_PATH = os.path.join(BUNDLE_DIR, "manifest.txt")

def read_manifest():
    info = {}
    if not os.path.exists(MANIFEST_PATH):
        return info
    with open(MANIFEST_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                if line.startswith("# ETL export manifest - "):
                    info["generated"] = line.split(" - ", 1)[1]
                continue
            k, v = line.split("=", 1)
            info[k] = int(v)
    return info

def run_export():
    result = subprocess.run(
        ["bash", ETL_SCRIPT, "export", BUNDLE_DIR],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        subprocess.run(
            ["tar", "-czf", TAR_PATH, "-C", BUNDLE_DIR,
             "--exclude=etl_bundle.tar.gz", "."]
        )
    return result

class ETLHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now():%H:%M:%S}] {fmt % args}")

    def _json(self, code, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            manifest = read_manifest()
            tar_size = os.path.getsize(TAR_PATH) if os.path.exists(TAR_PATH) else 0
            self._json(200, {
                "status": "ready" if os.path.exists(TAR_PATH) else "no_bundle",
                "manifest": manifest,
                "bundle_size_bytes": tar_size,
                "server_time": datetime.now().isoformat()
            })

        elif self.path == "/export":
            self.log_message("Avvio export...")
            t0 = time.time()
            result = run_export()
            elapsed = round(time.time() - t0, 1)
            if result.returncode == 0:
                manifest = read_manifest()
                tar_size = os.path.getsize(TAR_PATH)
                self._json(200, {
                    "status": "ok",
                    "elapsed_seconds": elapsed,
                    "manifest": manifest,
                    "bundle_size_bytes": tar_size
                })
            else:
                self._json(500, {
                    "status": "error",
                    "elapsed_seconds": elapsed,
                    "stderr": result.stderr[-2000:] if result.stderr else ""
                })

        elif self.path == "/download":
            if not os.path.exists(TAR_PATH):
                self._json(404, {"error": "Nessun bundle disponibile. Chiama /export prima."})
                return
            size = os.path.getsize(TAR_PATH)
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Disposition", "attachment; filename=etl_bundle.tar.gz")
            self.send_header("Content-Length", size)
            self.end_headers()
            with open(TAR_PATH, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)

        else:
            self._json(404, {
                "error": "Endpoint non trovato",
                "endpoints": ["/status", "/export", "/download"]
            })

print(f"ETL Server avviato su porta {PORT}")
print(f"  GET /status   - stato del bundle")
print(f"  GET /export   - rigenera export dai DB sorgente")
print(f"  GET /download - scarica bundle tar.gz")
print(f"Ctrl+C per terminare")
HTTPServer(("0.0.0.0", PORT), ETLHandler).serve_forever()
PYSERVER
}

# Scarica bundle da server remoto e lo estrae in BUNDLE_DIR
pull_bundle() {
    local remote="$1"
    local tar_path="$BUNDLE_DIR/etl_bundle.tar.gz"

    # Supporta URL completi (https://proxy.example.com/etl) o shorthand (host:port)
    local base_url
    if [[ "$remote" =~ ^https?:// ]]; then
        base_url="${remote%/}"
    else
        base_url="http://${remote}"
    fi

    echo ">>> Verifica server remoto..."
    local status
    if ! status=$(curl -sf "${base_url}/status"); then
        echo "ERRORE: impossibile contattare il server su ${base_url}/status" >&2
        exit 1
    fi
    echo "   Server raggiungibile: $status"

    echo ">>> Download bundle da ${base_url}/download ..."
    if ! curl -f -o "$tar_path" "${base_url}/download"; then
        echo "ERRORE: download fallito. Potrebbe servire /export prima." >&2
        echo "   Prova: curl ${base_url}/export" >&2
        exit 1
    fi

    local size
    size=$(wc -c < "$tar_path")
    echo "   Scaricato: ${size} bytes"

    echo ">>> Estrazione bundle..."
    tar -xzf "$tar_path" -C "$BUNDLE_DIR"
    rm -f "$tar_path"
    echo "   Estratto in: $BUNDLE_DIR"
}

# ===========================================================================
# DISPATCH
# ===========================================================================

echo "=== ETL gias_db ($MODE) - inizio: $(date) ==="
echo ">>> Bundle dir: $BUNDLE_DIR"

case "$MODE" in
    # -------------------------------------------------------------------
    export)
        export_masterlist
        export_personale
        export_osa_mai_controllati
        export_piani_monitoraggio
        export_cu_diff
        export_cu_eseguiti_nc
        write_manifest

        echo ""
        echo "=== Export completato: $(date) ==="
        echo ">>> Bundle pronto in: $BUNDLE_DIR"

        # Suggerimento trasferimento
        if [ -f "${SCRIPT_DIR}/.remote_config" ]; then
            # shellcheck source=.remote_config
            source "${SCRIPT_DIR}/.remote_config"
            echo ">>> Trasferisci con:"
            echo "    scp -r -P ${REMOTE_SSH_PORT:-22} $BUNDLE_DIR ${REMOTE_USER:-root}@${REMOTE_HOST}:/tmp/"
            echo ">>> Poi sul server remoto:"
            echo "    bash $0 import /tmp/$(basename "$BUNDLE_DIR")"
        fi
        ;;

    # -------------------------------------------------------------------
    import)
        validate_bundle

        import_masterlist
        check_count "masterlist" "masterlist.csv" "" \
            "SELECT count(*) FROM public.masterlist"

        import_personale
        check_count "personale" "personale.csv" "" \
            "SELECT count(*) FROM public.personale"

        import_osa_mai_controllati
        check_count "osa_mai_controllati" "osa_mai_controllati.csv" "" \
            "SELECT count(*) FROM public.osa_mai_controllati"

        import_piani_monitoraggio
        check_count "piani_monitoraggio" "dpat.csv" "" \
            "SELECT count(*) FROM public.piani_monitoraggio"

        import_cu_diff
        check_count "cu_diff_programmati_eseguiti" "diff.csv" "" \
            "SELECT count(*) FROM public.cu_diff_programmati_eseguiti" \
            gte

        import_cu_eseguiti_nc
        check_count "cu_eseguiti_nc" "cu.csv" "" \
            "SELECT count(*) FROM public.cu_eseguiti_nc" \
            gte

        import_indicatori_non_catalogati

        echo "=== Import completato con successo: $(date) ==="
        ;;

    # -------------------------------------------------------------------
    full)
        export_masterlist
        import_masterlist
        check_count "masterlist" psql_gisa \
            "SELECT count(*) FROM chatbot.masterlist" \
            "SELECT count(*) FROM public.masterlist"

        export_personale
        import_personale
        check_count "personale" psql_gisa \
            "SELECT count(*) FROM chatbot.personale" \
            "SELECT count(*) FROM public.personale"

        export_osa_mai_controllati
        import_osa_mai_controllati
        check_count "osa_mai_controllati" psql_mdgm \
            "SELECT count(*) FROM chatbot.osa_mai_controllati" \
            "SELECT count(*) FROM public.osa_mai_controllati"

        export_piani_monitoraggio
        import_piani_monitoraggio
        check_count "piani_monitoraggio" psql_gisa \
            "SELECT count(*) FROM chatbot.dpat" \
            "SELECT count(*) FROM public.piani_monitoraggio"

        export_cu_diff
        import_cu_diff
        check_count "cu_diff_programmati_eseguiti" psql_mdgm \
            "SELECT count(*) FROM chatbot.vw_diff_programmati_eseguiti_x" \
            "SELECT count(*) FROM public.cu_diff_programmati_eseguiti" \
            gte

        export_cu_eseguiti_nc
        import_cu_eseguiti_nc
        check_count "cu_eseguiti_nc" psql_mdgm \
            "SELECT count(*) FROM chatbot.vw_cu_xx" \
            "SELECT count(*) FROM public.cu_eseguiti_nc" \
            gte

        import_indicatori_non_catalogati

        echo "=== ETL completato con successo: $(date) ==="
        ;;

    # -------------------------------------------------------------------
    serve)
        export_masterlist
        export_personale
        export_osa_mai_controllati
        export_piani_monitoraggio
        export_cu_diff
        export_cu_eseguiti_nc
        write_manifest
        create_bundle_tar

        echo ""
        echo "=== Export completato, avvio server HTTP sulla porta ${ETL_SERVE_PORT} ==="
        start_etl_server "$ETL_SERVE_PORT" "$BUNDLE_DIR" "$(readlink -f "$0")"
        ;;

    # -------------------------------------------------------------------
    pull)
        pull_bundle "$ETL_REMOTE"

        # Da qui in poi e' equivalente a 'import'
        MODE=import
        validate_bundle

        import_masterlist
        check_count "masterlist" "masterlist.csv" "" \
            "SELECT count(*) FROM public.masterlist"

        import_personale
        check_count "personale" "personale.csv" "" \
            "SELECT count(*) FROM public.personale"

        import_osa_mai_controllati
        check_count "osa_mai_controllati" "osa_mai_controllati.csv" "" \
            "SELECT count(*) FROM public.osa_mai_controllati"

        import_piani_monitoraggio
        check_count "piani_monitoraggio" "dpat.csv" "" \
            "SELECT count(*) FROM public.piani_monitoraggio"

        import_cu_diff
        check_count "cu_diff_programmati_eseguiti" "diff.csv" "" \
            "SELECT count(*) FROM public.cu_diff_programmati_eseguiti" \
            gte

        import_cu_eseguiti_nc
        check_count "cu_eseguiti_nc" "cu.csv" "" \
            "SELECT count(*) FROM public.cu_eseguiti_nc" \
            gte

        import_indicatori_non_catalogati

        echo "=== Pull + Import completato con successo: $(date) ==="
        ;;
esac
