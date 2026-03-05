#!/usr/bin/env python3
"""
Sincronizza domande_risposte -> intent_examples -> Qdrant.

Fasi:
  1. Legge da domande_risposte WHERE active = TRUE, valida intent
  2. INSERT in intent_examples con ON CONFLICT DO NOTHING
  3. Ricostruisce indice Qdrant (opzionale)

Usage:
    cd GiAs-llm && python scripts/sync_domande_risposte.py
    cd GiAs-llm && python scripts/sync_domande_risposte.py --dry-run
    cd GiAs-llm && python scripts/sync_domande_risposte.py --skip-qdrant
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db_engine():
    """Ottiene engine SQLAlchemy dal singleton PostgreSQLDataSource."""
    from data_sources.postgresql_source import PostgreSQLDataSource
    engine = PostgreSQLDataSource._engine
    if engine is not None:
        return engine

    from configs.config_loader import get_config
    config = get_config()
    pg_config = config.config.get("data_source", {}).get("postgresql", {})
    PostgreSQLDataSource(pg_config)
    return PostgreSQLDataSource._engine


def phase1_read_and_validate(engine):
    """Fase 1: Legge domande attive e valida intent."""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Leggi domande attive
        rows = conn.execute(text("""
            SELECT id, domanda, intent, example_type, confused_with
            FROM domande_risposte
            WHERE active = TRUE
            ORDER BY id
        """)).fetchall()

        if not rows:
            print("  Nessuna domanda attiva trovata in domande_risposte.")
            return []

        # Leggi intent validi dal DB
        valid_intents = {r[0] for r in conn.execute(text(
            "SELECT intent FROM intents"
        )).fetchall()}

    valid = []
    skipped = 0
    for row in rows:
        row_id, domanda, intent, example_type, confused_with = row
        if intent not in valid_intents:
            print(f"  ⚠️  Riga id={row_id}: intent '{intent}' non esiste in tabella intents — SKIPPED")
            skipped += 1
            continue
        valid.append({
            "id": row_id,
            "domanda": domanda,
            "intent": intent,
            "example_type": example_type,
            "confused_with": confused_with,
        })

    print(f"  Lette {len(rows)} domande attive, {len(valid)} valide, {skipped} skipped")
    return valid


def phase2_sync_to_intent_examples(engine, records, dry_run=False):
    """Fase 2: INSERT in intent_examples con ON CONFLICT DO NOTHING."""
    from sqlalchemy import text

    if dry_run:
        print("  [DRY-RUN] Domande che verrebbero sincronizzate:")
        for r in records:
            print(f"    → [{r['intent']}] {r['domanda']} (type={r['example_type']}, confused={r['confused_with']})")
        return 0

    inserted = 0
    errors = 0
    with engine.connect() as conn:
        for r in records:
            try:
                result = conn.execute(text("""
                    INSERT INTO intent_examples (intent, text, example_type, confused_with)
                    VALUES (:intent, :text, :example_type, :confused_with)
                    ON CONFLICT (intent, text, example_type) DO NOTHING
                """), {
                    "intent": r["intent"],
                    "text": r["domanda"],
                    "example_type": r["example_type"],
                    "confused_with": r["confused_with"],
                })
                inserted += result.rowcount
            except Exception as e:
                print(f"  ✗ Errore riga id={r['id']} intent='{r['intent']}': {e}")
                errors += 1
        conn.commit()

    print(f"  Inserite {inserted} nuove righe in intent_examples ({errors} errori)")
    return inserted


def phase3_rebuild_qdrant(incremental: bool = False):
    """Fase 3: Ricostruisce indice Qdrant."""
    from tools.indexing.build_intent_examples_index import main as build_index
    build_index(incremental=incremental)


def main():
    parser = argparse.ArgumentParser(
        description="Sincronizza domande_risposte -> intent_examples -> Qdrant"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo lettura, mostra cosa verrebbe sincronizzato"
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Sincronizza DB ma salta rebuild indice Qdrant"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("SYNC DOMANDE_RISPOSTE -> INTENT_EXAMPLES -> QDRANT")
    print("=" * 60)

    if args.dry_run:
        print("  Modalita' DRY-RUN attiva\n")

    engine = get_db_engine()
    if engine is None:
        print("ERRORE: impossibile ottenere engine DB")
        sys.exit(1)

    # Fase 1
    print("\n[1/3] Lettura e validazione domande_risposte...")
    records = phase1_read_and_validate(engine)
    if not records:
        print("\nNessuna domanda da sincronizzare. Uscita.")
        return

    # Fase 2
    print(f"\n[2/3] Sync verso intent_examples ({len(records)} record)...")
    inserted = phase2_sync_to_intent_examples(engine, records, dry_run=args.dry_run)

    # Fase 3
    if args.dry_run:
        print("\n[3/3] [DRY-RUN] Rebuild Qdrant skipped")
    elif args.skip_qdrant:
        print("\n[3/3] Rebuild Qdrant skipped (--skip-qdrant)")
    else:
        # Upsert incrementale se pochi inserimenti, rebuild completo altrimenti
        use_incremental = 0 < inserted <= 20
        mode_label = "incrementale" if use_incremental else "completo"
        print(f"\n[3/3] Rebuild indice Qdrant ({mode_label})...")
        phase3_rebuild_qdrant(incremental=use_incremental)

    print("\n" + "=" * 60)
    print("SYNC COMPLETATO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
