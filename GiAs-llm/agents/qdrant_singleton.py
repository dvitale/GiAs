"""
Singleton per QdrantClient condiviso.

Qdrant in modalita' locale (file-based) usa un lock esclusivo sulla directory
di storage. Un solo QdrantClient puo' accedere alla directory in un dato momento.
Questo singleton garantisce che DataRetriever e FewShotRetriever condividano
la stessa istanza, evitando errori "already accessed by another instance".
"""

import os
import logging

logger = logging.getLogger(__name__)

_shared_client = None
_initialized = False

QDRANT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "qdrant_storage"
)


def get_qdrant_client():
    """
    Restituisce l'istanza singleton del QdrantClient locale.

    Lazy loading: il client viene creato solo al primo utilizzo.
    Tutte le chiamate successive restituiscono la stessa istanza.

    Returns:
        QdrantClient o None se storage non disponibile.
    """
    global _shared_client, _initialized
    if _initialized:
        return _shared_client

    try:
        from qdrant_client import QdrantClient

        if not os.path.exists(QDRANT_PATH):
            logger.warning(f"[QdrantSingleton] Storage non trovato: {QDRANT_PATH}")
            _initialized = True
            return None

        _shared_client = QdrantClient(path=QDRANT_PATH)
        _initialized = True
        logger.info(f"[QdrantSingleton] Client inizializzato: {QDRANT_PATH}")
        return _shared_client

    except ImportError as e:
        logger.warning(f"[QdrantSingleton] qdrant_client non installato: {e}")
        _initialized = True
        return None
    except Exception as e:
        logger.warning(f"[QdrantSingleton] Errore inizializzazione: {e}")
        _initialized = True
        return None
