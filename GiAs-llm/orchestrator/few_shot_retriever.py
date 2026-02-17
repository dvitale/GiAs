"""
FewShotRetriever - Recupero dinamico esempi simili per classificazione intent.

Architettura:
- Singleton con lazy init per minimizzare overhead a cold start
- Riusa storage Qdrant esistente (/data/qdrant_storage)
- Riusa embedding model sentence-transformers
- Cache FIFO LRU per evitare ricerche ripetute
- Graceful degradation: restituisce [] se Qdrant non disponibile
"""

import os
from typing import List, Dict, Any, Optional
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class FewShotRetriever:
    """
    Recupera esempi few-shot dinamici da Qdrant per migliorare classificazione LLM.

    Caratteristiche:
    - Singleton pattern per evitare ricaricamenti multipli del modello
    - Limita a max 2 esempi per intent (diversity)
    - Cache LRU per query frequenti
    - Graceful fallback a [] se errore
    """

    _instance: Optional['FewShotRetriever'] = None
    _initialized: bool = False

    # Config
    COLLECTION_NAME = "intent_examples"
    QDRANT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "qdrant_storage"
    )
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    CACHE_MAX_SIZE = 100

    def __new__(cls) -> 'FewShotRetriever':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Lazy init - non carica nulla finché non serve."""
        if FewShotRetriever._initialized:
            return

        self._qdrant_client = None
        self._embedding_model = None
        self._cache: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
        self._available = False  # Flag disponibilità

        FewShotRetriever._initialized = True

    def _ensure_initialized(self) -> bool:
        """
        Lazy loading di Qdrant client e embedding model.

        Returns:
            True se inizializzazione OK, False altrimenti
        """
        if self._qdrant_client is not None:
            return self._available

        try:
            from qdrant_client import QdrantClient
            from agents.embedding_singleton import get_embedding_model

            # Verifica esistenza storage
            if not os.path.exists(self.QDRANT_PATH):
                logger.warning(f"[FewShot] Qdrant storage non trovato: {self.QDRANT_PATH}")
                self._available = False
                return False

            # Init client
            self._qdrant_client = QdrantClient(path=self.QDRANT_PATH)

            # Verifica collection
            collections = self._qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            if self.COLLECTION_NAME not in collection_names:
                logger.warning(f"[FewShot] Collection '{self.COLLECTION_NAME}' non trovata. "
                              f"Esegui build_intent_examples_index.py")
                self._available = False
                return False

            # Init embedding model (singleton condiviso con DataRetriever)
            logger.info(f"[FewShot] Caricamento modello embedding (singleton)...")
            self._embedding_model = get_embedding_model()

            self._available = True
            logger.info(f"[FewShot] Inizializzato: collection={self.COLLECTION_NAME}, "
                       f"model_dim={self._embedding_model.get_sentence_embedding_dimension()}")
            return True

        except ImportError as e:
            logger.warning(f"[FewShot] Dipendenze mancanti: {e}")
            self._available = False
            return False
        except Exception as e:
            logger.warning(f"[FewShot] Errore inizializzazione: {e}")
            self._available = False
            return False

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        score_threshold: float = 0.40,
        max_per_intent: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Recupera esempi simili alla query.

        Args:
            query: Messaggio utente
            top_k: Numero max risultati da Qdrant (prima del filtraggio)
            score_threshold: Score minimo (0-1, cosine similarity)
            max_per_intent: Max esempi per stesso intent (diversity)

        Returns:
            Lista di dict con {text, intent, score}, max max_per_intent per intent.
            Restituisce [] in caso di errore (graceful degradation).
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Check cache
        cache_key = f"{query}:{top_k}:{score_threshold}"
        if cache_key in self._cache:
            # Move to end (LRU)
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        # Lazy init
        if not self._ensure_initialized():
            return []

        try:
            # Embed query
            query_vector = self._embedding_model.encode(query, show_progress_bar=False)

            # Search
            results = self._qdrant_client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_vector.tolist(),
                limit=top_k,
                score_threshold=score_threshold
            ).points

            # Filtra per diversity (max 2 per intent)
            examples = []
            intent_counts: Dict[str, int] = {}

            for hit in results:
                intent = hit.payload.get("intent", "unknown")

                # Skip se già raggiunto max per questo intent
                if intent_counts.get(intent, 0) >= max_per_intent:
                    continue

                examples.append({
                    "text": hit.payload.get("text", ""),
                    "intent": intent,
                    "score": round(hit.score, 3)
                })

                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            # Cache result (FIFO eviction)
            if len(self._cache) >= self.CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
            self._cache[cache_key] = examples

            logger.debug(f"[FewShot] Query: '{query[:50]}...' -> {len(examples)} esempi")
            return examples

        except Exception as e:
            logger.warning(f"[FewShot] Errore retrieve: {e}")
            return []

    def format_for_prompt(self, examples: List[Dict[str, Any]]) -> str:
        """
        Formatta esempi per injection nel prompt LLM.

        Args:
            examples: Lista da retrieve()

        Returns:
            Stringa formattata per il prompt
        """
        if not examples:
            return ""

        lines = ["ESEMPI SIMILI:"]
        for ex in examples:
            lines.append(f'"{ex["text"]}" → {ex["intent"]}')

        return "\n".join(lines)

    def is_available(self) -> bool:
        """Verifica se il retriever è disponibile."""
        return self._ensure_initialized()

    def clear_cache(self):
        """Svuota cache."""
        self._cache.clear()
        logger.info("[FewShot] Cache svuotata")

    def get_stats(self) -> Dict[str, Any]:
        """Statistiche retriever."""
        return {
            "available": self._available,
            "cache_size": len(self._cache),
            "cache_max_size": self.CACHE_MAX_SIZE,
            "collection": self.COLLECTION_NAME,
            "qdrant_path": self.QDRANT_PATH
        }


# Singleton accessor
def get_few_shot_retriever() -> FewShotRetriever:
    """Ottieni istanza singleton del FewShotRetriever."""
    return FewShotRetriever()
