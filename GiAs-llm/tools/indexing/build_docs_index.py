#!/usr/bin/env python3
"""
Indicizza documenti/manuali procedure in Qdrant per il sistema RAG.

Processa tutti i file in data/documents/ (PDF, DOCX, TXT),
li spezza in chunk e li indicizza nella collection 'procedure_documents'.

Usage:
    python3 tools/indexing/build_docs_index.py
    python3 tools/indexing/build_docs_index.py --docs-dir /path/to/docs
    python3 tools/indexing/build_docs_index.py --chunk-size 800 --chunk-overlap 150
"""

import os
import sys
import argparse

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.indexing.doc_chunker import DocumentChunker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")
QDRANT_PATH = os.path.join(BASE_DIR, "data", "qdrant_storage")
COLLECTION_NAME = "procedure_documents"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 50


def parse_args():
    parser = argparse.ArgumentParser(description="Indicizza documenti procedure in Qdrant")
    parser.add_argument("--docs-dir", default=DEFAULT_DOCS_DIR,
                        help=f"Directory documenti (default: {DEFAULT_DOCS_DIR})")
    parser.add_argument("--chunk-size", type=int, default=600,
                        help="Dimensione chunk in caratteri (default: 600)")
    parser.add_argument("--chunk-overlap", type=int, default=100,
                        help="Sovrapposizione chunk in caratteri (default: 100)")
    return parser.parse_args()


def load_and_chunk_documents(docs_dir, chunk_size, chunk_overlap):
    """Carica e chunka tutti i documenti dalla directory."""
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.process_directory(docs_dir)
    print(f"  Caricati {len(chunks)} chunk totali")
    return chunks


def initialize_qdrant():
    """Inizializza client Qdrant locale."""
    os.makedirs(QDRANT_PATH, exist_ok=True)
    client = QdrantClient(path=QDRANT_PATH)
    print(f"  Qdrant client inizializzato: {QDRANT_PATH}")
    return client


def initialize_embedding_model():
    """Inizializza modello sentence-transformers."""
    print("  Caricamento modello embedding (pazienta 10-30s la prima volta)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Modello caricato: {model.get_sentence_embedding_dimension()} dimensioni")
    return model


def create_collection(client, embedding_dim):
    """Crea collection Qdrant (elimina se esiste)."""
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"  Collection esistente eliminata: {COLLECTION_NAME}")
    except Exception:
        pass

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
    )
    print(f"  Collection creata: {COLLECTION_NAME} (dim={embedding_dim}, distance=COSINE)")


def index_chunks(client, model, chunks):
    """Indicizza tutti i chunk in Qdrant."""
    print(f"\n  Indicizzazione {len(chunks)} chunk...")

    points = []
    for idx, chunk in enumerate(chunks):
        embedding = model.encode(chunk["content"], show_progress_bar=False)

        point = PointStruct(
            id=idx,
            vector=embedding.tolist(),
            payload={
                "content": chunk["content"],
                "source_file": chunk["metadata"].get("source_file", ""),
                "title": chunk["metadata"].get("title", ""),
                "section": chunk["metadata"].get("section", ""),
                "chunk_index": chunk["metadata"].get("chunk_index", 0),
                "total_chunks": chunk["metadata"].get("total_chunks", 0),
                "page_num": chunk["metadata"].get("page_num"),
            }
        )
        points.append(point)

        if len(points) >= BATCH_SIZE:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"    Indicizzati {idx + 1}/{len(chunks)} chunk...", end="\r")
            points = []

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n  Indicizzazione completata: {len(chunks)} chunk")


def test_search(client, model):
    """Test rapido di ricerca semantica sulla nuova collection."""
    print("\n  Test ricerca semantica...")

    test_queries = [
        "procedura ispezione semplice",
        "controllo ufficiale",
        "come registrare una non conformita'",
    ]

    for query in test_queries:
        query_vector = model.encode(query, show_progress_bar=False)

        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            limit=3
        ).points

        print(f"\n  Query: '{query}'")
        if not results:
            print("    (nessun risultato)")
            continue

        for i, hit in enumerate(results, 1):
            score = hit.score
            source = hit.payload.get('source_file', '?')
            section = hit.payload.get('section', '')
            content_preview = hit.payload.get('content', '')[:80]
            print(f"    {i}. [{source}] {section} (score: {score:.3f})")
            print(f"       {content_preview}...")


def main():
    args = parse_args()

    print("=" * 60)
    print("QDRANT INDEXING - Documenti Procedure RAG")
    print("=" * 60)

    # Verifica directory documenti
    if not os.path.isdir(args.docs_dir):
        print(f"\n  Directory documenti non trovata: {args.docs_dir}")
        print(f"  Crea la directory e inserisci i manuali (PDF, DOCX, TXT).")
        sys.exit(1)

    doc_files = [f for f in os.listdir(args.docs_dir) if os.path.isfile(os.path.join(args.docs_dir, f))]
    supported = [f for f in doc_files if os.path.splitext(f)[1].lower() in DocumentChunker.SUPPORTED_EXTENSIONS]

    if not supported:
        print(f"\n  Nessun documento supportato trovato in: {args.docs_dir}")
        print(f"  Formati supportati: {', '.join(DocumentChunker.SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    print(f"\n  Directory: {args.docs_dir}")
    print(f"  Documenti trovati: {len(supported)}")
    for f in supported:
        print(f"    - {f}")

    # 1. Carica e chunka documenti
    print(f"\n[1/5] Caricamento e chunking documenti...")
    chunks = load_and_chunk_documents(args.docs_dir, args.chunk_size, args.chunk_overlap)

    if not chunks:
        print("\n  Nessun chunk generato. Verifica che i documenti contengano testo.")
        sys.exit(1)

    # 2. Inizializza embedding model
    print(f"\n[2/5] Inizializzazione modello embedding...")
    model = initialize_embedding_model()
    embedding_dim = model.get_sentence_embedding_dimension()

    # 3. Inizializza Qdrant
    print(f"\n[3/5] Inizializzazione Qdrant...")
    client = initialize_qdrant()

    # 4. Crea collection e indicizza
    print(f"\n[4/5] Creazione collection e indicizzazione...")
    create_collection(client, embedding_dim)
    index_chunks(client, model, chunks)

    # 5. Test di verifica
    print(f"\n[5/5] Test di verifica...")
    test_search(client, model)

    # Riepilogo
    print("\n" + "=" * 60)
    print("INDEXING COMPLETATO!")
    print("=" * 60)
    print(f"  Vector DB path: {QDRANT_PATH}")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Documenti processati: {len(supported)}")
    print(f"  Chunk indicizzati: {len(chunks)}")
    print(f"  Dimensioni vettori: {embedding_dim}")
    print(f"  Chunk size: {args.chunk_size} chars")
    print(f"  Chunk overlap: {args.chunk_overlap} chars")
    print("=" * 60)


if __name__ == "__main__":
    main()
