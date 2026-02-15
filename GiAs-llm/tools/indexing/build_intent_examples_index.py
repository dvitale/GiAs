#!/usr/bin/env python3
"""
Costruisce l'indice Qdrant per esempi intent (few-shot retrieval).

Fonti:
1. INTENT_REGISTRY.examples da intent_metadata.py
2. Tabella `intents` dal database (se disponibile)
3. Coppie di disambiguazione hardcoded
4. Variazioni generate

Usage:
    python3 build_intent_examples_index.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Tuple

# Config
QDRANT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "qdrant_storage"
)
COLLECTION_NAME = "intent_examples"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_from_registry() -> List[Tuple[str, str]]:
    """Carica esempi da INTENT_REGISTRY."""
    from orchestrator.intent_metadata import INTENT_REGISTRY

    examples = []
    for intent_id, metadata in INTENT_REGISTRY.items():
        if intent_id == "fallback":
            continue
        for ex in metadata.examples:
            if ex and ex.strip():
                examples.append((ex.strip(), intent_id))

    print(f"✅ Caricati {len(examples)} esempi da INTENT_REGISTRY")
    return examples


def load_from_database() -> List[Tuple[str, str]]:
    """Carica esempi dalla tabella `intents` nel database."""
    examples = []
    try:
        from data_retrieval.db_connect import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT intent, example_question
            FROM intents
            WHERE example_question IS NOT NULL AND example_question != ''
        """)

        for row in cursor.fetchall():
            intent, example = row
            if example and example.strip():
                examples.append((example.strip(), intent))

        cursor.close()
        conn.close()
        print(f"✅ Caricati {len(examples)} esempi da database")

    except Exception as e:
        print(f"⚠️  Database non disponibile o errore: {e}")

    return examples


def get_disambiguation_pairs() -> List[Tuple[str, str]]:
    """
    Coppie di esempi per intent frequentemente confusi.
    Queste sono critiche per la disambiguazione.
    """
    pairs = [
        # ask_risk_based_priority vs ask_top_risk_activities
        ("stabilimenti a rischio", "ask_risk_based_priority"),
        ("stabilimenti più rischiosi", "ask_risk_based_priority"),
        ("OSA a maggior rischio", "ask_risk_based_priority"),
        ("attività più rischiose", "ask_top_risk_activities"),
        ("classifica attività per rischio", "ask_top_risk_activities"),
        ("top attività pericolose", "ask_top_risk_activities"),
        ("tipologie di attività rischiose", "ask_top_risk_activities"),

        # ask_delayed_plans vs check_if_plan_delayed
        ("piani in ritardo", "ask_delayed_plans"),
        ("quali piani sono in ritardo", "ask_delayed_plans"),
        ("lista piani scaduti", "ask_delayed_plans"),
        ("il piano A1 è in ritardo", "check_if_plan_delayed"),
        ("piano B2 è scaduto?", "check_if_plan_delayed"),
        ("verifica ritardo piano C3", "check_if_plan_delayed"),

        # ask_piano_description vs ask_piano_stabilimenti
        ("di cosa tratta il piano A1", "ask_piano_description"),
        ("descrizione piano B2", "ask_piano_description"),
        ("cosa prevede il piano C3", "ask_piano_description"),
        ("stabilimenti del piano A1", "ask_piano_stabilimenti"),
        ("dove si applica il piano B2", "ask_piano_stabilimenti"),
        ("OSA controllati dal piano C3", "ask_piano_stabilimenti"),

        # ask_priority_establishment vs ask_suggest_controls
        ("chi devo controllare oggi", "ask_priority_establishment"),
        ("priorità controlli", "ask_priority_establishment"),
        ("cosa fare per primo", "ask_priority_establishment"),
        ("stabilimenti mai controllati", "ask_suggest_controls"),
        ("OSA da ispezionare per prima volta", "ask_suggest_controls"),
        ("suggerisci controlli", "ask_suggest_controls"),

        # greet vs ask_help
        ("ciao", "greet"),
        ("buongiorno", "greet"),
        ("salve", "greet"),
        ("ciao cosa puoi fare", "ask_help"),
        ("buongiorno aiutami", "ask_help"),
        ("cosa sai fare", "ask_help"),

        # search_piani_by_topic variations
        ("piani su latte", "search_piani_by_topic"),
        ("piani che trattano di igiene", "search_piani_by_topic"),
        ("cerca piani sulla sicurezza alimentare", "search_piani_by_topic"),
        ("piani riguardanti bovini", "search_piani_by_topic"),

        # info_procedure
        ("procedura ispezione semplice", "info_procedure"),
        ("come si fa un controllo", "info_procedure"),
        ("passi per registrare NC", "info_procedure"),
        ("guida ispezione", "info_procedure"),

        # ask_nearby_priority
        ("stabilimenti vicino a Napoli", "ask_nearby_priority"),
        ("controlli nelle vicinanze", "ask_nearby_priority"),
        ("entro 5 km da Via Roma", "ask_nearby_priority"),
        ("OSA nei dintorni", "ask_nearby_priority"),

        # analyze_nc_by_category
        ("NC per categoria HACCP", "analyze_nc_by_category"),
        ("analisi non conformità igiene", "analyze_nc_by_category"),
        ("distribuzione NC", "analyze_nc_by_category"),

        # ask_establishment_history
        ("storico stabilimento IT 2287", "ask_establishment_history"),
        ("controlli passati OSA", "ask_establishment_history"),
        ("storia NC per partita iva", "ask_establishment_history"),

        # confirm/decline
        ("sì mostrami", "confirm_show_details"),
        ("ok vediamo tutto", "confirm_show_details"),
        ("procedi", "confirm_show_details"),
        ("no grazie", "decline_show_details"),
        ("basta così", "decline_show_details"),
        ("va bene così", "decline_show_details"),
    ]

    print(f"✅ Generate {len(pairs)} coppie di disambiguazione")
    return pairs


def get_variations() -> List[Tuple[str, str]]:
    """Variazioni linguistiche per aumentare coverage."""
    variations = [
        # Variazioni rischio
        ("quali sono gli stabilimenti più pericolosi", "ask_risk_based_priority"),
        ("osa con più non conformità", "ask_risk_based_priority"),
        ("attività ad alto rischio", "ask_top_risk_activities"),

        # Variazioni ritardo
        ("abbiamo piani scaduti?", "ask_delayed_plans"),
        ("controllo se piano A1 è scaduto", "check_if_plan_delayed"),

        # Variazioni piano
        ("info sul piano B2", "ask_piano_description"),
        ("dimmi del piano A1", "ask_piano_stabilimenti"),
        ("piano C3", "ask_piano_stabilimenti"),

        # Variazioni priorità
        ("da chi inizio oggi", "ask_priority_establishment"),
        ("dove vado a controllare", "ask_priority_establishment"),

        # Variazioni geografiche
        ("controlli zona centro Napoli", "ask_nearby_priority"),
        ("stabilimenti a 3 km da qui", "ask_nearby_priority"),

        # Variazioni statistiche
        ("quanti piani abbiamo", "ask_piano_statistics"),
        ("piani più frequenti", "ask_piano_statistics"),
    ]

    print(f"✅ Generate {len(variations)} variazioni aggiuntive")
    return variations


def main():
    print("=" * 60)
    print("BUILD INTENT EXAMPLES INDEX - Few-Shot Retriever")
    print("=" * 60)

    # Raccogli tutti gli esempi
    all_examples: List[Tuple[str, str]] = []

    all_examples.extend(load_from_registry())
    all_examples.extend(load_from_database())
    all_examples.extend(get_disambiguation_pairs())
    all_examples.extend(get_variations())

    # Deduplica (stesso testo)
    seen_texts = set()
    unique_examples = []
    for text, intent in all_examples:
        text_lower = text.lower().strip()
        if text_lower not in seen_texts:
            seen_texts.add(text_lower)
            unique_examples.append((text, intent))

    print(f"\n📊 Totale esempi unici: {len(unique_examples)}")

    # Init embedding model
    print("\n📦 Caricamento modello embedding...")
    model = SentenceTransformer(MODEL_NAME)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"✅ Modello caricato: {embedding_dim} dimensioni")

    # Init Qdrant
    print("\n🗄️  Inizializzazione Qdrant...")
    os.makedirs(QDRANT_PATH, exist_ok=True)
    client = QdrantClient(path=QDRANT_PATH)

    # Ricrea collection
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"🗑️  Collection esistente eliminata: {COLLECTION_NAME}")
    except Exception:
        pass

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )
    print(f"✅ Collection creata: {COLLECTION_NAME}")

    # Indicizza
    print(f"\n📊 Indicizzazione {len(unique_examples)} esempi...")
    points = []

    for idx, (text, intent) in enumerate(unique_examples):
        embedding = model.encode(text, show_progress_bar=False)

        points.append(PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload={
                "text": text,
                "intent": intent
            }
        ))

        if len(points) >= 50:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  → Indicizzati {idx + 1}/{len(unique_examples)}...", end="\r")
            points = []

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n✅ Indicizzazione completata: {len(unique_examples)} esempi")

    # Test
    print("\n🧪 Test semantic search...")
    test_queries = [
        "stabilimenti a rischio",
        "attività rischiose",
        "piani in ritardo",
        "il piano B2 è in ritardo?",
        "ciao",
    ]

    for query in test_queries:
        query_vector = model.encode(query, show_progress_bar=False)
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=3,
            score_threshold=0.40
        ).points

        print(f"\n📝 Query: '{query}'")
        for hit in results:
            print(f"  • {hit.payload['text']} → {hit.payload['intent']} (score: {hit.score:.3f})")

    # Summary
    print("\n" + "=" * 60)
    print("✅ INDEXING COMPLETATO!")
    print("=" * 60)
    print(f"📂 Vector DB path: {QDRANT_PATH}")
    print(f"📦 Collection: {COLLECTION_NAME}")
    print(f"📊 Esempi indicizzati: {len(unique_examples)}")
    print(f"🔢 Dimensioni vettori: {embedding_dim}")
    print("=" * 60)


if __name__ == "__main__":
    main()
