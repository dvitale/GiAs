"""
Singleton per modello embedding condiviso.

Evita il caricamento duplicato di SentenceTransformer (~300MB RAM ciascuno)
tra DataRetriever e FewShotRetriever.

Offline mode: abilitiamo HF_HUB_OFFLINE per evitare HEAD request verso
huggingface.co ad ogni caricamento (se la rete e' lenta/bloccata,
queste request vanno in timeout 10s e sommate bloccano il grafo). Il
modello e' gia' nella cache locale (downloadato al primo boot / via
indexing scripts), quindi l'offline mode e' sicuro.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Disabilita HEAD/network calls verso HuggingFace Hub: il modello e'
# cachato in locale, non serve verificare online.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_shared_model = None
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_embedding_model():
    """
    Restituisce l'istanza singleton del modello embedding.

    Lazy loading: il modello viene caricato solo al primo utilizzo.
    Tutte le chiamate successive restituiscono la stessa istanza.
    """
    global _shared_model
    if _shared_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"[EmbeddingSingleton] Caricamento modello {MODEL_NAME}...")
        _shared_model = SentenceTransformer(MODEL_NAME)
        logger.info(f"[EmbeddingSingleton] Modello caricato (dim={_shared_model.get_sentence_embedding_dimension()})")
    return _shared_model
