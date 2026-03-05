#!/usr/bin/env python3
"""
Costruisce l'indice Qdrant per esempi intent (few-shot retrieval).

Fonte unica: IntentMetadataService (DB-first, Python-fallback).
Se il servizio non e' disponibile, fallback diretto a INTENT_REGISTRY + hardcoded.

Usage:
    python3 build_intent_examples_index.py
    python3 build_intent_examples_index.py --incremental
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Tuple

# Config
QDRANT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "qdrant_storage"
)
COLLECTION_NAME = "intent_examples"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_examples_from_service() -> List[Tuple[str, str]]:
    """Carica tutti gli esempi da IntentMetadataService (DB-first, Python-fallback)."""
    try:
        from orchestrator.intent_metadata_service import get_intent_metadata_service
        service = get_intent_metadata_service()
        examples = service.get_all_examples_for_indexing()
        print(f"✅ Caricati {len(examples)} esempi da IntentMetadataService (source: {service.source})")
        return examples
    except Exception as e:
        print(f"⚠️  IntentMetadataService non disponibile: {e}")
        print("   Fallback a fonti hardcoded...")
        return _load_hardcoded_fallback()


def _load_hardcoded_fallback() -> List[Tuple[str, str]]:
    """Fallback diretto se il servizio non e' disponibile."""
    from orchestrator.intent_metadata import INTENT_REGISTRY

    examples = []

    # 1. Esempi da INTENT_REGISTRY
    for intent_id, metadata in INTENT_REGISTRY.items():
        if intent_id == "fallback":
            continue
        for ex in metadata.examples:
            if ex and ex.strip():
                examples.append((ex.strip(), intent_id))
    print(f"  → {len(examples)} da INTENT_REGISTRY")

    # 2. Coppie disambiguazione
    disambiguation = [
        ("stabilimenti a rischio", "ask_risk_based_priority"),
        ("stabilimenti più rischiosi", "ask_risk_based_priority"),
        ("OSA a maggior rischio", "ask_risk_based_priority"),
        ("attività più rischiose", "ask_top_risk_activities"),
        ("classifica attività per rischio", "ask_top_risk_activities"),
        ("top attività pericolose", "ask_top_risk_activities"),
        ("tipologie di attività rischiose", "ask_top_risk_activities"),
        ("piani in ritardo", "ask_delayed_plans"),
        ("quali piani sono in ritardo", "ask_delayed_plans"),
        ("lista piani scaduti", "ask_delayed_plans"),
        ("il piano A1 è in ritardo", "check_if_plan_delayed"),
        ("piano B2 è scaduto?", "check_if_plan_delayed"),
        ("verifica ritardo piano C3", "check_if_plan_delayed"),
        ("di cosa tratta il piano A1", "ask_piano_description"),
        ("descrizione piano B2", "ask_piano_description"),
        ("cosa prevede il piano C3", "ask_piano_description"),
        ("stabilimenti del piano A1", "ask_piano_stabilimenti"),
        ("dove si applica il piano B2", "ask_piano_stabilimenti"),
        ("OSA controllati dal piano C3", "ask_piano_stabilimenti"),
        ("chi devo controllare oggi", "ask_priority_establishment"),
        ("priorità controlli", "ask_priority_establishment"),
        ("cosa fare per primo", "ask_priority_establishment"),
        ("stabilimenti mai controllati", "ask_suggest_controls"),
        ("OSA da ispezionare per prima volta", "ask_suggest_controls"),
        ("suggerisci controlli", "ask_suggest_controls"),
        ("ciao", "greet"),
        ("buongiorno", "greet"),
        ("salve", "greet"),
        ("ciao cosa puoi fare", "ask_help"),
        ("buongiorno aiutami", "ask_help"),
        ("cosa sai fare", "ask_help"),
        ("piani su latte", "search_piani_by_topic"),
        ("piani che trattano di igiene", "search_piani_by_topic"),
        ("cerca piani sulla sicurezza alimentare", "search_piani_by_topic"),
        ("piani riguardanti bovini", "search_piani_by_topic"),
        ("procedura ispezione semplice", "info_procedure"),
        ("come si fa un controllo", "info_procedure"),
        ("passi per registrare NC", "info_procedure"),
        ("guida ispezione", "info_procedure"),
        ("stabilimenti vicino a Napoli", "ask_nearby_priority"),
        ("controlli nelle vicinanze", "ask_nearby_priority"),
        ("entro 5 km da Via Roma", "ask_nearby_priority"),
        ("OSA nei dintorni", "ask_nearby_priority"),
        ("NC per categoria HACCP", "analyze_nc_by_category"),
        ("analisi non conformità igiene", "analyze_nc_by_category"),
        ("distribuzione NC", "analyze_nc_by_category"),
        ("storico stabilimento IT 2287", "ask_establishment_history"),
        ("controlli passati OSA", "ask_establishment_history"),
        ("storia NC per partita iva", "ask_establishment_history"),
        ("sì mostrami", "confirm_show_details"),
        ("ok vediamo tutto", "confirm_show_details"),
        ("procedi", "confirm_show_details"),
        ("no grazie", "decline_show_details"),
        ("basta così", "decline_show_details"),
        ("va bene così", "decline_show_details"),
    ]
    examples.extend(disambiguation)
    print(f"  → {len(disambiguation)} disambiguazione")

    # 3. Variazioni
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
    examples.extend(variations)
    print(f"  → {len(variations)} variazioni")

    return examples


def _deterministic_id(text: str, intent: str) -> int:
    """Calcola ID deterministico per un punto Qdrant."""
    key = f"{text.lower().strip()}:{intent}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:15], 16)


def incremental_upsert(new_examples: List[Tuple[str, str]]):
    """Upsert incrementale: aggiunge/aggiorna solo i nuovi esempi senza delete+recreate."""
    if not new_examples:
        print("Nessun esempio da indicizzare incrementalmente.")
        return

    print(f"\n📦 Caricamento modello embedding...")
    model = SentenceTransformer(MODEL_NAME)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"✅ Modello caricato: {embedding_dim} dimensioni")

    os.makedirs(QDRANT_PATH, exist_ok=True)
    client = QdrantClient(path=QDRANT_PATH)

    # Crea collection se non esiste
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
        )
        print(f"✅ Collection creata: {COLLECTION_NAME}")

    # Deduplica
    seen = set()
    unique = []
    for text, intent in new_examples:
        key = text.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append((text, intent))

    print(f"📊 Upsert incrementale: {len(unique)} esempi...")
    points = []
    for text, intent in unique:
        embedding = model.encode(text, show_progress_bar=False)
        points.append(PointStruct(
            id=_deterministic_id(text, intent),
            vector=embedding.tolist(),
            payload={"text": text, "intent": intent}
        ))
        if len(points) >= 50:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            points = []

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"✅ Upsert incrementale completato: {len(unique)} esempi")


def main(incremental: bool = False):
    print("=" * 60)
    print("BUILD INTENT EXAMPLES INDEX - Few-Shot Retriever")
    print("=" * 60)

    # Raccogli tutti gli esempi (via servizio o fallback)
    all_examples = load_examples_from_service()

    # Deduplica (stesso testo)
    seen_texts = set()
    unique_examples = []
    for text, intent in all_examples:
        text_lower = text.lower().strip()
        if text_lower not in seen_texts:
            seen_texts.add(text_lower)
            unique_examples.append((text, intent))

    print(f"\n📊 Totale esempi unici: {len(unique_examples)}")

    if incremental:
        incremental_upsert(unique_examples)
        return

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

    # Indicizza con ID deterministici
    print(f"\n📊 Indicizzazione {len(unique_examples)} esempi...")
    points = []

    for idx, (text, intent) in enumerate(unique_examples):
        embedding = model.encode(text, show_progress_bar=False)

        points.append(PointStruct(
            id=_deterministic_id(text, intent),
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
    parser = argparse.ArgumentParser(description="Build intent examples Qdrant index")
    parser.add_argument("--incremental", action="store_true",
                        help="Upsert incrementale senza delete+recreate")
    args = parser.parse_args()
    main(incremental=args.incremental)
