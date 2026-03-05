"""
RAG Response Cache per GiAs-llm

Cache delle risposte RAG per evitare retrieval e generazione ripetuti.
Pattern singleton come IntentCache.
"""

import hashlib
import threading
from typing import Dict, Optional, Any
from datetime import datetime, timedelta


class RAGCache:
    """
    Cache TTL per risposte RAG (procedure_tools).

    - Key: MD5 di query normalizzata (lowercase, strip)
    - Value: result dict completo + timestamp
    - Thread-safe via lock
    """

    def __init__(self, ttl_seconds: int = 1800, max_size: int = 200):
        self._cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_size = max_size
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Ritorna risultato cached se presente e non scaduto."""
        key = self._hash_query(query)
        with self._lock:
            if key in self._cache:
                entry, timestamp = self._cache[key]
                if datetime.now() - timestamp < self._ttl:
                    self._stats["hits"] += 1
                    return entry
                del self._cache[key]
                self._stats["evictions"] += 1
            self._stats["misses"] += 1
            return None

    def set(self, query: str, result: Dict[str, Any]) -> None:
        """Inserisce un risultato in cache."""
        key = self._hash_query(query)
        with self._lock:
            self._cache[key] = (result, datetime.now())
            if len(self._cache) > self._max_size:
                self._cleanup_oldest()

    def clear_all(self) -> int:
        """Svuota tutta la cache. Ritorna numero di entry rimosse."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats["evictions"] += count
            return count

    def get_stats(self) -> Dict[str, Any]:
        """Statistiche cache."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "total_requests": total,
                "hit_rate_percent": round(hit_rate, 2),
                "cache_size": len(self._cache),
                "max_size": self._max_size,
                "evictions": self._stats["evictions"],
                "ttl_seconds": int(self._ttl.total_seconds()),
            }

    def _hash_query(self, query: str) -> str:
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def _cleanup_oldest(self) -> None:
        target = int(self._max_size * 0.8)
        sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
        to_remove = len(self._cache) - target
        for key, _ in sorted_items[:to_remove]:
            del self._cache[key]
        self._stats["evictions"] += to_remove


# Singleton
_rag_cache: Optional[RAGCache] = None
_rag_cache_lock = threading.Lock()


def get_rag_cache() -> RAGCache:
    """Accessor singleton per la RAG cache."""
    global _rag_cache
    if _rag_cache is None:
        with _rag_cache_lock:
            if _rag_cache is None:
                try:
                    from configs.config_loader import get_config
                    config = get_config()
                    rag_cfg = config._config.get("rag_documents", {})
                    ttl = rag_cfg.get("cache_ttl_seconds", 1800)
                    max_size = rag_cfg.get("cache_max_size", 200)
                except Exception:
                    ttl, max_size = 1800, 200
                _rag_cache = RAGCache(ttl_seconds=ttl, max_size=max_size)
    return _rag_cache
