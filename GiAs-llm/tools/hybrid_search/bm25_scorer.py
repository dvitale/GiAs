"""
BM25 Scorer on-the-fly per Reciprocal Rank Fusion (RRF).

Calcola score BM25 sui chunk gia' recuperati da Qdrant (8-15 chunk, < 1ms).
Non serve un indice BM25 globale persistente.
"""

from typing import List, Optional
import re


class BM25Scorer:
    """Score BM25 on-the-fly su una lista di testi."""

    @staticmethod
    def score_chunks(query: str, contents: List[str]) -> List[float]:
        """
        Calcola score BM25 per ogni contenuto rispetto alla query.

        Fallback silenzioso: se rank-bm25 non disponibile, usa TF-IDF semplificato.

        Args:
            query: Query dell'utente
            contents: Lista di testi dei chunk

        Returns:
            Lista di score (stesso ordine di contents)
        """
        if not contents or not query.strip():
            return [0.0] * len(contents)

        try:
            return BM25Scorer._score_with_rank_bm25(query, contents)
        except ImportError:
            return BM25Scorer._score_tf_fallback(query, contents)
        except Exception:
            return [0.0] * len(contents)

    @staticmethod
    def _score_with_rank_bm25(query: str, contents: List[str]) -> List[float]:
        """Score via libreria rank-bm25."""
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [BM25Scorer._tokenize(c) for c in contents]
        tokenized_query = BM25Scorer._tokenize(query)

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)
        return scores.tolist()

    @staticmethod
    def _score_tf_fallback(query: str, contents: List[str]) -> List[float]:
        """Fallback TF semplificato se rank-bm25 non installato."""
        query_tokens = set(BM25Scorer._tokenize(query))
        scores = []
        for content in contents:
            tokens = BM25Scorer._tokenize(content)
            if not tokens:
                scores.append(0.0)
                continue
            match_count = sum(1 for t in tokens if t in query_tokens)
            scores.append(match_count / len(tokens))
        return scores

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenizzazione semplice: lowercase, split su non-alfanumerici, rimuovi stop words corte."""
        text = text.lower()
        tokens = re.findall(r'\b\w{2,}\b', text)
        return tokens


def rrf_combine(vector_scores: List[float], bm25_scores: List[float],
                k: int = 60) -> List[float]:
    """
    Reciprocal Rank Fusion: combina due ranking in uno.

    RRF(d) = 1/(k + rank_vector(d)) + 1/(k + rank_bm25(d))

    Args:
        vector_scores: Score dal retrieval vettoriale
        bm25_scores: Score BM25
        k: Parametro di smoothing (default 60, standard)

    Returns:
        Lista di score RRF combinati (stesso ordine degli input)
    """
    n = len(vector_scores)
    if n == 0:
        return []

    # Calcola rank per ogni lista di score (rank 1 = migliore)
    def _ranks(scores):
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        ranks = [0] * len(scores)
        for rank, (idx, _) in enumerate(indexed, 1):
            ranks[idx] = rank
        return ranks

    v_ranks = _ranks(vector_scores)
    b_ranks = _ranks(bm25_scores)

    # RRF score
    return [1.0 / (k + v_ranks[i]) + 1.0 / (k + b_ranks[i]) for i in range(n)]
