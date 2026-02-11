#!/usr/bin/env python3
"""
Indicizza i piani di monitoraggio in Qdrant usando sentence-transformers.

Usage:
    python3 build_qdrant_index.py
"""

import os
import sys
import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dataset.10")
QDRANT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "qdrant_storage")
COLLECTION_NAME = "piani_monitoraggio"


def load_piani_data():
    """Carica dati piani da CSV"""
    piani_file = os.path.join(DATASET_DIR, "piani_monitoraggio.csv")

    if not os.path.exists(piani_file):
        raise FileNotFoundError(f"File piani non trovato: {piani_file}")

    piani_df = pd.read_csv(piani_file)
    print(f"✅ Caricati {len(piani_df)} piani da CSV")

    return piani_df


def initialize_qdrant():
    """Inizializza client Qdrant locale"""
    os.makedirs(QDRANT_PATH, exist_ok=True)

    client = QdrantClient(path=QDRANT_PATH)
    print(f"✅ Qdrant client inizializzato: {QDRANT_PATH}")

    return client


def initialize_embedding_model():
    """Inizializza modello sentence-transformers (multilingual)"""
    print("📦 Caricamento modello embedding (pazienta 10-30s la prima volta)...")

    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    print(f"✅ Modello caricato: {model.get_sentence_embedding_dimension()} dimensioni")

    return model


def create_collection(client, embedding_dim):
    """Crea collection Qdrant (elimina se esiste)"""
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"🗑️  Collection esistente eliminata: {COLLECTION_NAME}")
    except:
        pass

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )

    print(f"✅ Collection creata: {COLLECTION_NAME} (dim={embedding_dim}, distance=COSINE)")


def index_piani(client, model, piani_df):
    """Indicizza tutti i piani in Qdrant"""
    print(f"\n📊 Indicizzazione {len(piani_df)} piani...")

    points = []
    batch_size = 50

    for idx, row in piani_df.iterrows():
        desc_parts = []

        if pd.notna(row.get("sezione")):
            desc_parts.append(f"SEZIONE {row['sezione']}")

        if pd.notna(row.get("descrizione")):
            desc_parts.append(str(row["descrizione"]))

        if pd.notna(row.get("descrizione-2")):
            desc_parts.append(str(row["descrizione-2"]))

        full_text = " ".join(desc_parts).strip()

        if not full_text:
            full_text = f"Piano {row['alias']}"

        embedding = model.encode(full_text, show_progress_bar=False)

        point = PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload={
                "alias": row["alias"],
                "alias_indicatore": row.get("alias_indicatore", "") or "",
                "sezione": row.get("sezione", "") or "",
                "descrizione": row.get("descrizione", "") or "",
                "descrizione_2": row.get("descrizione-2", "") or "",
                "full_text": full_text
            }
        )

        points.append(point)

        if len(points) >= batch_size:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  → Indicizzati {idx + 1}/{len(piani_df)} piani...", end="\r")
            points = []

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n✅ Indicizzazione completata: {len(piani_df)} piani")


def test_search(client, model):
    """Test rapido semantic search"""
    print("\n🧪 Test semantic search...")

    test_queries = [
        "piani sul benessere animale",
        "attività zootecniche",
        "controlli latte"
    ]

    for query in test_queries:
        query_vector = model.encode(query, show_progress_bar=False)

        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=3
        ).points

        print(f"\n📝 Query: '{query}'")
        for i, hit in enumerate(results, 1):
            score = hit.score
            alias = hit.payload['alias']
            desc = hit.payload['descrizione'][:80]
            print(f"  {i}. {alias} (score: {score:.3f}) - {desc}...")


def main():
    print("="*60)
    print("QDRANT INDEXING - GiAs-llm Piani Monitoraggio")
    print("="*60)

    piani_df = load_piani_data()

    model = initialize_embedding_model()

    embedding_dim = model.get_sentence_embedding_dimension()

    client = initialize_qdrant()

    create_collection(client, embedding_dim)

    index_piani(client, model, piani_df)

    test_search(client, model)

    print("\n" + "="*60)
    print("✅ INDEXING COMPLETATO!")
    print("="*60)
    print(f"📂 Vector DB path: {QDRANT_PATH}")
    print(f"📦 Collection: {COLLECTION_NAME}")
    print(f"📊 Piani indicizzati: {len(piani_df)}")
    print(f"🔢 Dimensioni vettori: {embedding_dim}")
    print("="*60)


if __name__ == "__main__":
    main()
