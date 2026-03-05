#!/usr/bin/env python3
"""
Migrazione dati intent: popola intent_examples e aggiorna intents da tutte le fonti Python.

Fonti:
1. INTENT_REGISTRY (intent_metadata.py) -> colonne intents + esempi few_shot
2. CLASSIFICATION_SYSTEM_PROMPT (router.py) -> esempi prompt_critical con expected_json
3. get_disambiguation_pairs() (build_intent_examples_index.py) -> esempi disambiguation
4. get_variations() (build_intent_examples_index.py) -> variazioni
5. help_tool() (tool_nodes.py) -> esempi help con display_order

Idempotente: usa INSERT ... ON CONFLICT DO NOTHING.

Usage:
    cd GiAs-llm && python scripts/migrate_intent_examples.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db_engine():
    """Ottiene engine SQLAlchemy dal singleton PostgreSQLDataSource."""
    from data_sources.postgresql_source import PostgreSQLDataSource
    engine = PostgreSQLDataSource._engine
    if engine is not None:
        return engine

    # Engine non inizializzato, lo creiamo
    from configs.config_loader import get_config
    config = get_config()
    pg_config = config.config.get("data_source", {}).get("postgresql", {})
    PostgreSQLDataSource(pg_config)
    return PostgreSQLDataSource._engine


def update_intents_from_registry(engine):
    """Fase 1: UPDATE intents con category, emoji, keywords, is_direct_response da INTENT_REGISTRY."""
    from orchestrator.intent_metadata import INTENT_REGISTRY
    from orchestrator.response_node import DIRECT_RESPONSE_INTENTS
    from sqlalchemy import text

    count = 0
    with engine.connect() as conn:
        for intent_id, meta in INTENT_REGISTRY.items():
            result = conn.execute(text("""
                UPDATE intents SET
                    category = :category,
                    emoji = :emoji,
                    keywords = :keywords,
                    context_keywords = :context_keywords,
                    negative_keywords = :negative_keywords,
                    is_direct_response = :is_direct_response,
                    updated_at = NOW()
                WHERE intent = :intent
            """), {
                "intent": intent_id,
                "category": meta.category,
                "emoji": meta.emoji,
                "keywords": meta.keywords,
                "context_keywords": meta.context_keywords,
                "negative_keywords": meta.negative_keywords,
                "is_direct_response": intent_id in DIRECT_RESPONSE_INTENTS,
            })
            if result.rowcount > 0:
                count += 1
        conn.commit()

    print(f"  Aggiornati {count} intent con metadati da INTENT_REGISTRY")
    return count


def insert_few_shot_examples(engine):
    """Fase 2: INSERT esempi few_shot da INTENT_REGISTRY.examples."""
    from orchestrator.intent_metadata import INTENT_REGISTRY
    from sqlalchemy import text

    count = 0
    with engine.connect() as conn:
        for intent_id, meta in INTENT_REGISTRY.items():
            if intent_id == "fallback":
                continue
            for ex in meta.examples:
                if not ex or not ex.strip():
                    continue
                result = conn.execute(text("""
                    INSERT INTO intent_examples (intent, text, example_type)
                    VALUES (:intent, :text, 'few_shot')
                    ON CONFLICT (intent, text, example_type) DO NOTHING
                """), {"intent": intent_id, "text": ex.strip()})
                count += result.rowcount
        conn.commit()

    print(f"  Inseriti {count} esempi few_shot da INTENT_REGISTRY")
    return count


def insert_prompt_critical_examples(engine):
    """Fase 3: INSERT esempi prompt_critical dal CLASSIFICATION_SYSTEM_PROMPT."""
    from sqlalchemy import text

    # Esempi critici estratti dal prompt V2 (router.py righe 124-150)
    critical_examples = [
        ("stabilimenti a rischio", {"reasoning": "chiede stabilimenti con alto rischio", "intent": "ask_risk_based_priority", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("attività più rischiose", {"reasoning": "chiede classifica attività per rischio", "intent": "ask_top_risk_activities", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("piani in ritardo", {"reasoning": "lista piani ritardo generico", "intent": "ask_delayed_plans", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("il piano B2 è in ritardo?", {"reasoning": "verifica ritardo piano specifico B2", "intent": "check_if_plan_delayed", "slots": {"piano_code": "B2"}, "needs_clarification": False, "confidence": 0.95}),
        ("voglio verificare se un piano è in ritardo", {"reasoning": "manca piano_code", "intent": "check_if_plan_delayed", "slots": {}, "needs_clarification": True, "confidence": 0.85}),
        ("piano A1", {"reasoning": "info piano A1", "intent": "ask_piano_stabilimenti", "slots": {"piano_code": "A1"}, "needs_clarification": False, "confidence": 0.90}),
        ("di cosa si occupa il piano A1", {"reasoning": "descrizione piano", "intent": "ask_piano_description", "slots": {"piano_code": "A1"}, "needs_clarification": False, "confidence": 0.95}),
        ("piani su latte", {"reasoning": "cerca piani tema latte", "intent": "search_piani_by_topic", "slots": {"topic": "latte"}, "needs_clarification": False, "confidence": 0.95}),
        ("chi devo controllare", {"reasoning": "priorità generica", "intent": "ask_priority_establishment", "slots": {}, "needs_clarification": False, "confidence": 0.90}),
        ("chi devo controllare secondo la programmazione", {"reasoning": "priorità per programmazione", "intent": "ask_priority_establishment", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("quali piani devo controllare per primi", {"reasoning": "priorità PIANI, non stabilimenti", "intent": "ask_delayed_plans", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("quali stabilimenti devo controllare per primi", {"reasoning": "priorità STABILIMENTI", "intent": "ask_priority_establishment", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("mai controllati", {"reasoning": "stabilimenti mai controllati", "intent": "ask_suggest_controls", "slots": {}, "needs_clarification": False, "confidence": 0.90}),
        ("vicino a Napoli", {"reasoning": "controlli vicino indirizzo", "intent": "ask_nearby_priority", "slots": {"location": "Napoli"}, "needs_clarification": False, "confidence": 0.90}),
        ("entro 5 km da Via Roma", {"reasoning": "raggio specifico", "intent": "ask_nearby_priority", "slots": {"location": "Via Roma", "radius_km": 5}, "needs_clarification": False, "confidence": 0.95}),
        ("NC categoria HACCP", {"reasoning": "analisi NC HACCP", "intent": "analyze_nc_by_category", "slots": {"categoria": "HACCP"}, "needs_clarification": False, "confidence": 0.95}),
        ("procedura ispezione", {"reasoning": "come si fa ispezione", "intent": "info_procedure", "slots": {}, "needs_clarification": False, "confidence": 0.90}),
        ("storico IT 2287", {"reasoning": "storico stabilimento", "intent": "ask_establishment_history", "slots": {"num_registrazione": "IT 2287"}, "needs_clarification": False, "confidence": 0.95}),
        ("ciao", {"reasoning": "saluto", "intent": "greet", "slots": {}, "needs_clarification": False, "confidence": 0.99}),
        ("buonanotte", {"reasoning": "saluto serale", "intent": "greet", "slots": {}, "needs_clarification": False, "confidence": 0.99}),
        ("come stai", {"reasoning": "convenevole", "intent": "greet", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("tanti saluti", {"reasoning": "commiato", "intent": "goodbye", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("alla prossima", {"reasoning": "commiato", "intent": "goodbye", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("ciao cosa puoi fare", {"reasoning": "non solo saluto, chiede help", "intent": "ask_help", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("sì mostrami", {"reasoning": "conferma offerta dettagli", "intent": "confirm_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("no grazie", {"reasoning": "rifiuto dettagli", "intent": "decline_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.95}),
        ("pizza?", {"reasoning": "fuori dominio", "intent": "fallback", "slots": {}, "needs_clarification": False, "confidence": 0.99}),
        # Esempi con alternatives
        ("come funziona il rischio", {"reasoning": "potrebbe essere procedura o analisi rischio", "intent": "info_procedure", "slots": {}, "needs_clarification": False, "confidence": 0.60, "alternatives": [{"intent": "ask_risk_based_priority", "confidence": 0.55, "reasoning": "potrebbe chiedere stabilimenti a rischio"}]}),
        ("controlli recenti", {"reasoning": "potrebbe essere storico o priorità", "intent": "ask_establishment_history", "slots": {}, "needs_clarification": True, "confidence": 0.55, "alternatives": [{"intent": "ask_priority_establishment", "confidence": 0.50, "reasoning": "potrebbe chiedere chi controllare"}]}),
    ]

    count = 0
    with engine.connect() as conn:
        for text_val, expected in critical_examples:
            intent = expected["intent"]
            result = conn.execute(text("""
                INSERT INTO intent_examples (intent, text, example_type, expected_json)
                VALUES (:intent, :text, 'prompt_critical', CAST(:expected_json AS jsonb))
                ON CONFLICT (intent, text, example_type) DO NOTHING
            """), {
                "intent": intent,
                "text": text_val,
                "expected_json": json.dumps(expected, ensure_ascii=False),
            })
            count += result.rowcount
        conn.commit()

    print(f"  Inseriti {count} esempi prompt_critical")
    return count


def insert_disambiguation_examples(engine):
    """Fase 4: INSERT esempi disambiguation da get_disambiguation_pairs()."""
    from sqlalchemy import text

    # Coppie di disambiguazione (da build_intent_examples_index.py)
    pairs = [
        # ask_risk_based_priority vs ask_top_risk_activities
        ("stabilimenti a rischio", "ask_risk_based_priority", "ask_top_risk_activities"),
        ("stabilimenti più rischiosi", "ask_risk_based_priority", "ask_top_risk_activities"),
        ("OSA a maggior rischio", "ask_risk_based_priority", "ask_top_risk_activities"),
        ("attività più rischiose", "ask_top_risk_activities", "ask_risk_based_priority"),
        ("classifica attività per rischio", "ask_top_risk_activities", "ask_risk_based_priority"),
        ("top attività pericolose", "ask_top_risk_activities", "ask_risk_based_priority"),
        ("tipologie di attività rischiose", "ask_top_risk_activities", "ask_risk_based_priority"),

        # ask_delayed_plans vs check_if_plan_delayed
        ("piani in ritardo", "ask_delayed_plans", "check_if_plan_delayed"),
        ("quali piani sono in ritardo", "ask_delayed_plans", "check_if_plan_delayed"),
        ("lista piani scaduti", "ask_delayed_plans", "check_if_plan_delayed"),
        ("il piano A1 è in ritardo", "check_if_plan_delayed", "ask_delayed_plans"),
        ("piano B2 è scaduto?", "check_if_plan_delayed", "ask_delayed_plans"),
        ("verifica ritardo piano C3", "check_if_plan_delayed", "ask_delayed_plans"),

        # ask_piano_description vs ask_piano_stabilimenti
        ("di cosa tratta il piano A1", "ask_piano_description", "ask_piano_stabilimenti"),
        ("descrizione piano B2", "ask_piano_description", "ask_piano_stabilimenti"),
        ("cosa prevede il piano C3", "ask_piano_description", "ask_piano_stabilimenti"),
        ("stabilimenti del piano A1", "ask_piano_stabilimenti", "ask_piano_description"),
        ("dove si applica il piano B2", "ask_piano_stabilimenti", "ask_piano_description"),
        ("OSA controllati dal piano C3", "ask_piano_stabilimenti", "ask_piano_description"),

        # ask_priority_establishment vs ask_suggest_controls
        ("chi devo controllare oggi", "ask_priority_establishment", "ask_suggest_controls"),
        ("priorità controlli", "ask_priority_establishment", "ask_suggest_controls"),
        ("cosa fare per primo", "ask_priority_establishment", "ask_suggest_controls"),
        ("stabilimenti mai controllati", "ask_suggest_controls", "ask_priority_establishment"),
        ("OSA da ispezionare per prima volta", "ask_suggest_controls", "ask_priority_establishment"),
        ("suggerisci controlli", "ask_suggest_controls", "ask_priority_establishment"),

        # greet vs ask_help
        ("ciao", "greet", "ask_help"),
        ("buongiorno", "greet", "ask_help"),
        ("salve", "greet", "ask_help"),
        ("ciao cosa puoi fare", "ask_help", "greet"),
        ("buongiorno aiutami", "ask_help", "greet"),
        ("cosa sai fare", "ask_help", "greet"),

        # search_piani_by_topic
        ("piani su latte", "search_piani_by_topic", None),
        ("piani che trattano di igiene", "search_piani_by_topic", None),
        ("cerca piani sulla sicurezza alimentare", "search_piani_by_topic", None),
        ("piani riguardanti bovini", "search_piani_by_topic", None),

        # info_procedure
        ("procedura ispezione semplice", "info_procedure", None),
        ("come si fa un controllo", "info_procedure", None),
        ("passi per registrare NC", "info_procedure", None),
        ("guida ispezione", "info_procedure", None),

        # ask_nearby_priority
        ("stabilimenti vicino a Napoli", "ask_nearby_priority", None),
        ("controlli nelle vicinanze", "ask_nearby_priority", None),
        ("entro 5 km da Via Roma", "ask_nearby_priority", None),
        ("OSA nei dintorni", "ask_nearby_priority", None),

        # analyze_nc_by_category
        ("NC per categoria HACCP", "analyze_nc_by_category", None),
        ("analisi non conformità igiene", "analyze_nc_by_category", None),
        ("distribuzione NC", "analyze_nc_by_category", None),

        # ask_establishment_history
        ("storico stabilimento IT 2287", "ask_establishment_history", None),
        ("controlli passati OSA", "ask_establishment_history", None),
        ("storia NC per partita iva", "ask_establishment_history", None),

        # confirm/decline
        ("sì mostrami", "confirm_show_details", "decline_show_details"),
        ("ok vediamo tutto", "confirm_show_details", "decline_show_details"),
        ("procedi", "confirm_show_details", "decline_show_details"),
        ("no grazie", "decline_show_details", "confirm_show_details"),
        ("basta così", "decline_show_details", "confirm_show_details"),
        ("va bene così", "decline_show_details", "confirm_show_details"),
    ]

    count = 0
    with engine.connect() as conn:
        for item in pairs:
            text_val, intent, confused = item
            result = conn.execute(text("""
                INSERT INTO intent_examples (intent, text, example_type, confused_with)
                VALUES (:intent, :text, 'disambiguation', :confused_with)
                ON CONFLICT (intent, text, example_type) DO NOTHING
            """), {
                "intent": intent,
                "text": text_val,
                "confused_with": confused,
            })
            count += result.rowcount
        conn.commit()

    print(f"  Inseriti {count} esempi disambiguation")
    return count


def insert_variation_examples(engine):
    """Fase 5: INSERT variazioni linguistiche."""
    from sqlalchemy import text

    variations = [
        ("quali sono gli stabilimenti più pericolosi", "ask_risk_based_priority"),
        ("osa con più non conformità", "ask_risk_based_priority"),
        ("attività ad alto rischio", "ask_top_risk_activities"),
        ("abbiamo piani scaduti?", "ask_delayed_plans"),
        ("controllo se piano A1 è scaduto", "check_if_plan_delayed"),
        ("info sul piano B2", "ask_piano_description"),
        ("dimmi del piano A1", "ask_piano_stabilimenti"),
        ("piano C3", "ask_piano_stabilimenti"),
        ("da chi inizio oggi", "ask_priority_establishment"),
        ("dove vado a controllare", "ask_priority_establishment"),
        ("controlli zona centro Napoli", "ask_nearby_priority"),
        ("stabilimenti a 3 km da qui", "ask_nearby_priority"),
        ("quanti piani abbiamo", "ask_piano_statistics"),
        ("piani più frequenti", "ask_piano_statistics"),
    ]

    count = 0
    with engine.connect() as conn:
        for text_val, intent in variations:
            result = conn.execute(text("""
                INSERT INTO intent_examples (intent, text, example_type)
                VALUES (:intent, :text, 'variation')
                ON CONFLICT (intent, text, example_type) DO NOTHING
            """), {"intent": intent, "text": text_val})
            count += result.rowcount
        conn.commit()

    print(f"  Inseriti {count} variazioni")
    return count


def insert_help_examples(engine):
    """Fase 6: INSERT domande help da help_tool() con display_order."""
    from sqlalchemy import text

    # Domande mostrate in help_tool (tool_nodes.py righe 74-100)
    help_questions = [
        # (text, intent, display_order)
        ("Di cosa tratta il piano A1?", "ask_piano_description", 1),
        ("Quali stabilimenti per piano A1?", "ask_piano_stabilimenti", 2),
        ("Statistiche piano A1", "ask_piano_statistics", 3),
        ("Cerca piani sulla sicurezza alimentare", "search_piani_by_topic", 4),
        ("Piani sul benessere animale", "search_piani_by_topic", 5),
        ("Piani in ritardo", "ask_delayed_plans", 6),
        ("Il piano A1 è in ritardo?", "check_if_plan_delayed", 7),
        ("Stabilimenti prioritari", "ask_priority_establishment", 8),
        ("Stabilimenti a rischio", "ask_risk_based_priority", 9),
        ("Stabilimenti mai controllati", "ask_suggest_controls", 10),
        ("Attività più rischiose", "ask_top_risk_activities", 11),
        ("Stabilimenti vicino a Piazza Risorgimento, Benevento", "ask_nearby_priority", 12),
        ("Controlli nei dintorni di Via Roma 15, Napoli entro 3 km", "ask_nearby_priority", 13),
        ("Storico controlli stabilimento", "ask_establishment_history", 14),
        ("Analisi NC per categoria", "analyze_nc_by_category", 15),
        ("Qual e' la procedura per ispezione semplice?", "info_procedure", 16),
        ("Come si esegue un controllo ufficiale?", "info_procedure", 17),
    ]

    count = 0
    with engine.connect() as conn:
        for text_val, intent, order in help_questions:
            result = conn.execute(text("""
                INSERT INTO intent_examples (intent, text, example_type, display_order)
                VALUES (:intent, :text, 'help', :display_order)
                ON CONFLICT (intent, text, example_type) DO NOTHING
            """), {"intent": intent, "text": text_val, "display_order": order})
            count += result.rowcount
        conn.commit()

    print(f"  Inseriti {count} esempi help")
    return count


def verify_migration(engine):
    """Verifica conteggi finali."""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Conteggio totale
        total = conn.execute(text("SELECT COUNT(*) FROM intent_examples")).scalar()
        print(f"\n  Totale esempi in intent_examples: {total}")

        # Per tipo
        rows = conn.execute(text("""
            SELECT example_type, COUNT(*) as cnt
            FROM intent_examples
            GROUP BY example_type
            ORDER BY example_type
        """)).fetchall()
        for row in rows:
            print(f"    {row[0]}: {row[1]}")

        # Verifica vista
        view_rows = conn.execute(text("""
            SELECT intent, total_examples, few_shot_count, prompt_critical_count,
                   disambiguation_count, variation_count, help_count
            FROM v_intent_example_counts
            ORDER BY intent
        """)).fetchall()
        print(f"\n  Vista v_intent_example_counts ({len(view_rows)} intent):")
        for row in view_rows:
            print(f"    {row[0]}: tot={row[1]} fs={row[2]} pc={row[3]} dis={row[4]} var={row[5]} help={row[6]}")


def main():
    print("=" * 60)
    print("MIGRAZIONE INTENT EXAMPLES - Popola DB da fonti Python")
    print("=" * 60)

    engine = get_db_engine()
    if engine is None:
        print("ERRORE: impossibile ottenere engine DB")
        sys.exit(1)

    print("\n[1/6] UPDATE intents con metadati da INTENT_REGISTRY...")
    update_intents_from_registry(engine)

    print("\n[2/6] INSERT esempi few_shot da INTENT_REGISTRY.examples...")
    insert_few_shot_examples(engine)

    print("\n[3/6] INSERT esempi prompt_critical da CLASSIFICATION_SYSTEM_PROMPT...")
    insert_prompt_critical_examples(engine)

    print("\n[4/6] INSERT esempi disambiguation da coppie confuse...")
    insert_disambiguation_examples(engine)

    print("\n[5/6] INSERT variazioni linguistiche...")
    insert_variation_examples(engine)

    print("\n[6/6] INSERT domande help da help_tool()...")
    insert_help_examples(engine)

    print("\n" + "=" * 60)
    print("VERIFICA MIGRAZIONE")
    print("=" * 60)
    verify_migration(engine)

    print("\n" + "=" * 60)
    print("MIGRAZIONE COMPLETATA!")
    print("=" * 60)


if __name__ == "__main__":
    main()
