#!/usr/bin/env python3
"""
Sincronizzazione osa_mai_controllati: mdgm (sorgente) → gias (destinazione)

Copia tutti i record dalla vista chatbot.osa_mai_controllati su mdgm
alla tabella public.osa_mai_controllati su gias_db.

Procedura:
  1. Svuota la tabella destinazione (TRUNCATE)
  2. Estrae dati dalla sorgente in batch
  3. Inserisce nella destinazione con executemany
  4. Verifica conteggio finale

Uso:
  python scripts/sync_osa_mai_controllati.py [--dry-run] [--batch-size N]

Ripetibile: puo' essere rieseguito in qualsiasi momento.
"""

import argparse
import sys
import time

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERRORE: psycopg2 non installato. Eseguire: pip install psycopg2-binary")
    sys.exit(1)

# --- Configurazione connessioni ---
MDGM_DSN = {
    "host": "172.16.3.248",
    "port": 5432,
    "dbname": "mdgm",
    "user": "postgres",
    "password": "postgres",
}

GIAS_DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gias_db",
    "user": "gisa_owner",
    "password": "5XRe4g8Q5QSg",
}

# Colonne comuni (ordine usato per SELECT e INSERT)
COLUMNS = [
    "ragione_sociale",
    "asl",
    "codice_norma",
    "codice_fiscale",
    "n_reg",
    "num_riconoscimento",
    "partita_iva",
    "comune",
    "provincia_stab",
    "indirizzo",
    "latitudine_stab",
    "longitudine_stab",
    "codice_fiscale_rappresentante",
    "nominativo_rappresentante",
    "data_inizio_attivita",
    "data_fine_attivita",
    "macroarea",
    "aggregazione",
    "attivita",
]

SOURCE_QUERY = f"""
    SELECT {', '.join(COLUMNS)}
    FROM chatbot.osa_mai_controllati
    ORDER BY asl, comune, ragione_sociale
"""

INSERT_QUERY = f"""
    INSERT INTO public.osa_mai_controllati ({', '.join(COLUMNS)})
    VALUES ({', '.join(['%s'] * len(COLUMNS))})
"""


def sync(batch_size: int = 5000, dry_run: bool = False):
    print(f"=== Sync osa_mai_controllati: mdgm → gias ===")
    print(f"Batch size: {batch_size} | Dry run: {dry_run}")
    print()

    # Connessione sorgente (mdgm)
    print(f"Connessione a mdgm ({MDGM_DSN['host']})...")
    src = psycopg2.connect(**MDGM_DSN)
    src_cur = src.cursor("fetch_osa", cursor_factory=psycopg2.extras.DictCursor)

    # Connessione destinazione (gias)
    print(f"Connessione a gias ({GIAS_DSN['host']})...")
    dst = psycopg2.connect(**GIAS_DSN)
    dst_cur = dst.cursor()

    try:
        # Conteggio sorgente
        with src.cursor() as cnt_cur:
            cnt_cur.execute("SELECT count(*) FROM chatbot.osa_mai_controllati")
            source_count = cnt_cur.fetchone()[0]
        print(f"Righe sorgente (mdgm): {source_count:,}")

        # Conteggio destinazione pre-sync
        dst_cur.execute("SELECT count(*) FROM public.osa_mai_controllati")
        dest_count_before = dst_cur.fetchone()[0]
        print(f"Righe destinazione (gias) prima: {dest_count_before:,}")

        if dry_run:
            print("\n[DRY RUN] Nessuna modifica applicata.")
            return

        # Truncate destinazione
        print("\nTRUNCATE public.osa_mai_controllati...")
        dst_cur.execute("TRUNCATE TABLE public.osa_mai_controllati")

        # Estrai e inserisci in batch
        print(f"Estrazione e inserimento in batch da {batch_size}...")
        src_cur.execute(SOURCE_QUERY)

        total_inserted = 0
        t_start = time.time()

        while True:
            rows = src_cur.fetchmany(batch_size)
            if not rows:
                break

            # Converti DictRow in tuple
            values = [tuple(row) for row in rows]
            psycopg2.extras.execute_batch(dst_cur, INSERT_QUERY, values, page_size=batch_size)

            total_inserted += len(values)
            elapsed = time.time() - t_start
            rate = total_inserted / elapsed if elapsed > 0 else 0
            print(f"  Inserite {total_inserted:>7,} / {source_count:,}  ({rate:,.0f} righe/s)", end="\r")

        dst.commit()
        elapsed = time.time() - t_start
        print(f"\n\nInserimento completato in {elapsed:.1f}s ({total_inserted:,} righe)")

        # Verifica finale
        dst_cur.execute("SELECT count(*) FROM public.osa_mai_controllati")
        dest_count_after = dst_cur.fetchone()[0]
        print(f"\nVerifica finale:")
        print(f"  Sorgente (mdgm):       {source_count:,}")
        print(f"  Destinazione (gias):   {dest_count_after:,}")

        if dest_count_after == source_count:
            print(f"  ✓ Conteggio corretto")
        else:
            print(f"  ✗ MISMATCH! Differenza: {source_count - dest_count_after:,}")
            sys.exit(1)

        # Campione di verifica
        dst_cur.execute("""
            SELECT asl, count(*) as n
            FROM public.osa_mai_controllati
            GROUP BY asl ORDER BY asl
        """)
        print(f"\nDistribuzione per ASL (gias):")
        for row in dst_cur.fetchall():
            print(f"  {row[0]:<20} {row[1]:>7,}")

    finally:
        src_cur.close()
        src.close()
        dst_cur.close()
        dst.close()
        print("\nConnessioni chiuse.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync osa_mai_controllati: mdgm → gias")
    parser.add_argument("--dry-run", action="store_true", help="Solo verifica, nessuna modifica")
    parser.add_argument("--batch-size", type=int, default=5000, help="Righe per batch (default: 5000)")
    args = parser.parse_args()

    sync(batch_size=args.batch_size, dry_run=args.dry_run)
