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
    parser.add_argument("--parent-chunk-size", type=int, default=1800,
                        help="Dimensione parent chunk in caratteri (default: 1800)")
    parser.add_argument("--parent-chunk-overlap", type=int, default=200,
                        help="Sovrapposizione parent chunk in caratteri (default: 200)")
    return parser.parse_args()


def load_and_chunk_documents(docs_dir, chunk_size, chunk_overlap,
                             parent_chunk_size=1800, parent_chunk_overlap=200):
    """Carica e chunka tutti i documenti con parent-child chunking."""
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    loaders = {
        '.pdf': chunker._load_pdf,
        '.docx': chunker._load_docx,
        '.txt': chunker._load_txt,
        '.md': chunker._load_txt,
    }

    all_chunks = []
    files = sorted(os.listdir(docs_dir))
    for filename in files:
        filepath = os.path.join(docs_dir, filename)
        if not os.path.isfile(filepath):
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in DocumentChunker.SUPPORTED_EXTENSIONS:
            continue
        try:
            loader = loaders.get(ext)
            text, page_map = loader(filepath)
            if not text or not text.strip():
                print(f"  File vuoto: {filename}")
                continue

            base_metadata = {
                "source_file": filename,
                "title": chunker._extract_title_from_filename(filename),
            }
            chunks = chunker.chunk_text_with_parents(
                text, base_metadata, page_map=page_map,
                parent_chunk_size=parent_chunk_size,
                parent_chunk_overlap=parent_chunk_overlap
            )
            all_chunks.extend(chunks)
            print(f"  Processato {filename}: {len(chunks)} chunk (parent-child)")
        except Exception as e:
            # Fallback: chunking standard senza parent
            try:
                chunks = chunker.load_file(filepath)
                all_chunks.extend(chunks)
                print(f"  Processato {filename} (senza parent): {len(chunks)} chunk")
            except Exception as e2:
                print(f"  Errore processando {filename}: {e2}")

    print(f"  Caricati {len(all_chunks)} chunk totali")
    return all_chunks


def initialize_qdrant(use_singleton=False):
    """Inizializza client Qdrant locale.

    Args:
        use_singleton: se True, usa il singleton condiviso (quando chiamato dal server).
                       Se False, crea un client dedicato (per esecuzione standalone).
    """
    if use_singleton:
        try:
            from agents.qdrant_singleton import get_qdrant_client
            client = get_qdrant_client()
            if client is not None:
                print(f"  Qdrant client singleton riutilizzato")
                return client
        except ImportError:
            pass
        print(f"  Singleton non disponibile, creo client dedicato")

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
                "parent_content": chunk.get("parent_content", chunk["content"]),
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
    chunks = load_and_chunk_documents(
        args.docs_dir, args.chunk_size, args.chunk_overlap,
        parent_chunk_size=args.parent_chunk_size,
        parent_chunk_overlap=args.parent_chunk_overlap
    )

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


def run_indexing(docs_dir=None, chunk_size=600, chunk_overlap=100,
                 parent_chunk_size=1800, parent_chunk_overlap=200):
    """
    Esegue l'indicizzazione programmaticamente (senza argparse).

    Returns:
        Dict con risultati: documents_count, chunks_count, status, error (se presente)
    """
    if docs_dir is None:
        docs_dir = DEFAULT_DOCS_DIR

    if not os.path.isdir(docs_dir):
        return {"status": "error", "error": f"Directory non trovata: {docs_dir}",
                "documents_count": 0, "chunks_count": 0}

    doc_files = [f for f in os.listdir(docs_dir) if os.path.isfile(os.path.join(docs_dir, f))]
    supported = [f for f in doc_files
                 if os.path.splitext(f)[1].lower() in DocumentChunker.SUPPORTED_EXTENSIONS]

    if not supported:
        return {"status": "error", "error": "Nessun documento supportato trovato",
                "documents_count": 0, "chunks_count": 0}

    try:
        chunks = load_and_chunk_documents(
            docs_dir, chunk_size, chunk_overlap,
            parent_chunk_size=parent_chunk_size,
            parent_chunk_overlap=parent_chunk_overlap
        )
        if not chunks:
            return {"status": "error", "error": "Nessun chunk generato",
                    "documents_count": len(supported), "chunks_count": 0}

        model = initialize_embedding_model()
        embedding_dim = model.get_sentence_embedding_dimension()
        client = initialize_qdrant(use_singleton=True)
        create_collection(client, embedding_dim)
        index_chunks(client, model, chunks)

        return {
            "status": "completed",
            "documents_count": len(supported),
            "chunks_count": len(chunks),
            "documents": supported,
        }
    except Exception as e:
        return {"status": "error", "error": str(e),
                "documents_count": len(supported), "chunks_count": 0}


if __name__ == "__main__":
    main()
