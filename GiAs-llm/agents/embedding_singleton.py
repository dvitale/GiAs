"""
Singleton per modello embedding condiviso.

Evita il caricamento duplicato di SentenceTransformer (~300MB RAM ciascuno)
tra DataRetriever e FewShotRetriever.
"""

import logging

logger = logging.getLogger(__name__)

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
