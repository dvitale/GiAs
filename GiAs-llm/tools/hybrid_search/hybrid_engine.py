"""
Hybrid Search Engine

Main orchestrator that combines vector search + LLM reranking with intelligent routing.
"""

from typing import Dict, Any, List, Optional
import time
from dataclasses import dataclass
from enum import Enum

# Import hybrid components
from .smart_router import SmartRouter, SearchStrategy, RoutingConfig
from .llm_reranker import LLMReranker
from .performance_tracker import PerformanceTracker
from .query_analyzer import QueryAnalyzer

# Import existing system components
try:
    from agents.data_agent import DataRetriever
    from agents.response_agent import ResponseFormatter
    COMPONENTS_AVAILABLE = True
except ImportError:
    print("⚠️  Core components not available, hybrid search will operate in limited mode")
    COMPONENTS_AVAILABLE = False

@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search engine"""

    # Strategy routing
    routing_config: RoutingConfig = None

    # Vector search parameters
    vector_top_k: int = 20
    vector_threshold: float = 0.3

    # LLM reranking parameters
    llm_rerank_top_k: int = 10
    llm_timeout_ms: int = 5000

    # Performance constraints
    max_hybrid_latency_ms: int = 3000
    fallback_to_vector_threshold: float = 0.8  # System load threshold

    # Quality settings
    min_candidates_for_reranking: int = 5
    enable_fallbacks: bool = True

class SearchMode(Enum):
    """Search execution modes"""
    PERFORMANCE = "performance"  # Prioritize speed
    QUALITY = "quality"         # Prioritize accuracy
    BALANCED = "balanced"       # Balance speed/accuracy

class HybridSearchEngine:
    """
    Main hybrid search engine that intelligently combines:
    - Vector search for fast, high-recall candidate retrieval
    - LLM reranking for semantic precision and domain understanding
    - Smart routing based on query complexity and system state
    """

    def __init__(self, config: HybridSearchConfig = None, llm_client=None):
        """
        Initialize hybrid search engine.

        Args:
            config: Configuration for search behavior
            llm_client: LLM client for semantic operations
        """
        self.config = config or HybridSearchConfig()
        if self.config.routing_config is None:
            self.config.routing_config = RoutingConfig()

        # Initialize core components
        self.smart_router = SmartRouter(self.config.routing_config)
        self.llm_reranker = LLMReranker(llm_client, timeout_ms=self.config.llm_timeout_ms)
        self.performance_tracker = PerformanceTracker()
        self.query_analyzer = QueryAnalyzer()

        # Initialize LLM client
        self.llm_client = llm_client

        # Internal state
        self._search_stats = {
            "total_searches": 0,
            "strategy_usage": {strategy.value: 0 for strategy in SearchStrategy}
        }

    def search(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main search interface with intelligent strategy selection.

        Args:
            query: User search query
            metadata: Additional context (ASL, preferences, etc.)

        Returns:
            Search results with strategy information and performance metrics
        """
        start_time = time.time()
        search_metadata = metadata or {}

        try:
            # Input validation
            if not query or not query.strip():
                return self._create_error_result("Query vuota o non specificata", start_time)

            # Update search statistics
            self._search_stats["total_searches"] += 1

            # Analyze query and select strategy
            strategy = self.smart_router.select_strategy(query, search_metadata)
            self._search_stats["strategy_usage"][strategy.value] += 1

            # Execute search based on selected strategy
            # Note: LLM_ONLY is no longer routed to; always use retrieval-grounded strategies
            if strategy == SearchStrategy.VECTOR_ONLY:
                result = self._execute_vector_only_search(query, search_metadata)
            else:  # HYBRID (or any other strategy)
                result = self._execute_hybrid_search(query, search_metadata)

            # Validate plan aliases in results to filter out hallucinated ones
            result = self._validate_plan_aliases(result)

            # Add search metadata
            latency_ms = (time.time() - start_time) * 1000
            result = self._enhance_result_metadata(result, strategy, latency_ms, search_metadata)

            # Track performance
            self.performance_tracker.track_search(
                query=query,
                strategy=strategy.value,
                result=result,
                latency_ms=latency_ms,
                metadata=search_metadata
            )

            return result

        except Exception as e:
            # Ultimate fallback to ensure system always responds
            print(f"❌ Hybrid search critical failure: {e}")
            return self._execute_emergency_fallback(query, start_time)

    def _execute_vector_only_search(self, query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Execute vector-only search strategy"""

        try:
            if not COMPONENTS_AVAILABLE:
                return {"error": "Vector search components not available"}

            # Use existing vector search with optimized parameters
            similarity_threshold = metadata.get("similarity_threshold", self.config.vector_threshold)

            matches = DataRetriever.search_piani_semantic(
                query=query,
                top_k=self.config.vector_top_k,
                score_threshold=similarity_threshold
            )

            # Fallback to keyword search if no semantic results
            if not matches:
                matches = DataRetriever.search_piani_by_keyword(
                    keyword=query,
                    similarity_threshold=similarity_threshold
                )

            # Format response
            formatted_response = ResponseFormatter.format_search_results(
                search_term=query,
                matches=matches[:15],  # Limit display
                max_display=15
            ) if matches else f"Nessun piano trovato per '{query}'"

            return {
                "search_term": query,
                "total_found": len(matches),
                "matches": matches,
                "formatted_response": formatted_response,
                "search_strategy": "vector_only",
                "confidence": self._estimate_vector_confidence(matches)
            }

        except Exception as e:
            print(f"⚠️  Vector search failed: {e}")
            return {"error": f"Vector search failed: {str(e)}", "matches": []}

    def _execute_llm_only_search(self, query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LLM-only semantic search strategy"""

        try:
            if not self.llm_client:
                return self._execute_vector_only_search(query, metadata)  # Fallback

            # Build LLM semantic search prompt
            search_prompt = self._build_llm_search_prompt(query, metadata)

            # Call LLM for semantic search
            llm_response = self.llm_client.query(
                prompt=search_prompt,
                temperature=0.2,
                max_tokens=800
            )

            # Parse LLM response
            search_results = self._parse_llm_search_response(llm_response, query)

            return search_results

        except Exception as e:
            print(f"⚠️  LLM search failed: {e}, falling back to vector")
            return self._execute_vector_only_search(query, metadata)

    def _execute_hybrid_search(self, query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hybrid search: vector retrieval + LLM reranking"""

        try:
            # Stage 1: Vector retrieval for high recall
            vector_result = self._execute_vector_retrieval_stage(query, metadata)
            candidates = vector_result.get("matches", [])

            if not candidates:
                return vector_result  # Return vector result if no candidates

            # Stage 2: Check if reranking is beneficial
            if len(candidates) < self.config.min_candidates_for_reranking:
                # Too few candidates for meaningful reranking
                return self._finalize_hybrid_result(vector_result, skip_reranking=True)

            # Stage 3: LLM reranking for high precision
            reranking_result = self.llm_reranker.rerank_candidates(
                query=query,
                candidates=candidates,
                top_k=self.config.llm_rerank_top_k,
                context=metadata
            )

            # Stage 4: Combine results
            final_result = self._combine_hybrid_results(
                query=query,
                vector_result=vector_result,
                reranking_result=reranking_result,
                metadata=metadata
            )

            return final_result

        except Exception as e:
            print(f"⚠️  Hybrid search failed: {e}, falling back to vector")
            return self._execute_vector_only_search(query, metadata)

    def _execute_vector_retrieval_stage(self, query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized vector search for candidate retrieval (first stage of hybrid)"""

        try:
            # Use broader parameters for higher recall in first stage
            broad_threshold = max(self.config.vector_threshold - 0.1, 0.1)

            matches = DataRetriever.search_piani_semantic(
                query=query,
                top_k=self.config.vector_top_k,
                score_threshold=broad_threshold
            )

            # Include keyword fallback in candidate pool
            if len(matches) < 10:  # If few semantic results, supplement with keyword
                keyword_matches = DataRetriever.search_piani_by_keyword(
                    keyword=query,
                    similarity_threshold=broad_threshold
                )

                # Merge and deduplicate
                matches = self._merge_candidate_lists(matches, keyword_matches)

            return {
                "search_term": query,
                "total_found": len(matches),
                "matches": matches,
                "stage": "vector_retrieval"
            }

        except Exception as e:
            print(f"⚠️  Vector retrieval stage failed: {e}")
            return {"matches": [], "error": str(e)}

    def _combine_hybrid_results(self, query: str, vector_result: Dict,
                               reranking_result, metadata: Dict) -> Dict[str, Any]:
        """Combine vector and LLM results into final hybrid response"""

        try:
            reranked_matches = reranking_result.reranked_items

            # Format final response
            if COMPONENTS_AVAILABLE and reranked_matches:
                formatted_response = ResponseFormatter.format_search_results(
                    search_term=query,
                    matches=reranked_matches,
                    max_display=self.config.llm_rerank_top_k
                )
            else:
                formatted_response = f"Trovati {len(reranked_matches)} piani per '{query}'"

            return {
                "search_term": query,
                "total_found": len(reranked_matches),
                "matches": reranked_matches,
                "formatted_response": formatted_response,
                "search_strategy": "hybrid",
                "hybrid_metadata": {
                    "vector_candidates": len(vector_result.get("matches", [])),
                    "llm_reranked": len(reranked_matches),
                    "reranking_confidence": reranking_result.confidence_score,
                    "reranking_reasoning": reranking_result.reasoning,
                    "reranking_time_ms": reranking_result.processing_time_ms,
                    "fallback_used": reranking_result.fallback_used
                }
            }

        except Exception as e:
            print(f"⚠️  Failed to combine hybrid results: {e}")
            # Fallback to vector results
            return self._finalize_hybrid_result(vector_result, skip_reranking=True)

    def _build_llm_search_prompt(self, query: str, metadata: Dict[str, Any]) -> str:
        """Build prompt for LLM-only semantic search"""

        # Get all available plans (would be optimized with context management)
        context_info = []
        if metadata.get("asl"):
            context_info.append(f"ASL: {metadata['asl']}")
        if metadata.get("uoc"):
            context_info.append(f"UOC: {metadata['uoc']}")

        context_str = f"\nCONTESTO: {', '.join(context_info)}" if context_info else ""

        return f"""Sei un esperto del sistema di monitoraggio veterinario della Regione Campania.

QUERY OPERATORE: "{query}"{context_str}

Analizza semanticamente la query e identifica i piani di monitoraggio più rilevanti.

CRITERI:
- Comprensione semantica profonda (non solo keyword matching)
- Conoscenza dominio veterinario
- Sinonimi e correlazioni concettuali
- Rilevanza operativa per ASL

RISPOSTA (JSON):
{{
    "reasoning": "analisi semantica della query",
    "selected_plans": [
        {{"alias": "A1", "relevance": 0.95, "rationale": "motivo"}},
        {{"alias": "B2", "relevance": 0.87, "rationale": "motivo"}}
    ],
    "confidence": 0.9
}}

Massimo 10 piani più rilevanti."""

    def _parse_llm_search_response(self, response: str, query: str) -> Dict[str, Any]:
        """Parse LLM search response into standardized format"""

        try:
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in LLM response")

            parsed = json.loads(json_match.group())

            # Convert to standard search result format
            selected_plans = parsed.get("selected_plans", [])

            # Transform to match expected structure
            matches = []
            for plan in selected_plans:
                matches.append({
                    "alias": plan.get("alias", ""),
                    "similarity": plan.get("relevance", 0.7),
                    "llm_rationale": plan.get("rationale", ""),
                    "descrizione": f"Piano {plan.get('alias', '')} - {plan.get('rationale', '')}"
                })

            formatted_response = f"LLM search per '{query}': {parsed.get('reasoning', '')}"

            return {
                "search_term": query,
                "total_found": len(matches),
                "matches": matches,
                "formatted_response": formatted_response,
                "search_strategy": "llm_only",
                "confidence": parsed.get("confidence", 0.8),
                "llm_reasoning": parsed.get("reasoning", "")
            }

        except Exception as e:
            print(f"⚠️  Failed to parse LLM search response: {e}")
            return {
                "error": f"Failed to parse LLM response: {str(e)}",
                "matches": [],
                "search_strategy": "llm_only"
            }

    def _merge_candidate_lists(self, semantic_matches: List[Dict],
                              keyword_matches: List[Dict]) -> List[Dict]:
        """Merge semantic and keyword results, removing duplicates"""

        # Create combined list with deduplication by alias
        seen_aliases = set()
        merged = []

        # Add semantic matches first (higher priority)
        for match in semantic_matches:
            alias = match.get("alias", "")
            if alias and alias not in seen_aliases:
                merged.append(match)
                seen_aliases.add(alias)

        # Add keyword matches that aren't already included
        for match in keyword_matches:
            alias = match.get("alias", "")
            if alias and alias not in seen_aliases:
                merged.append(match)
                seen_aliases.add(alias)

        return merged

    def _enhance_result_metadata(self, result: Dict[str, Any], strategy: SearchStrategy,
                                latency_ms: float, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add search metadata to results"""

        result["search_metadata"] = {
            "strategy_used": strategy.value,
            "latency_ms": round(latency_ms, 2),
            "timestamp": time.time(),
            "engine_version": "1.0.0",
            "request_id": f"hybrid_{int(time.time() * 1000)}_{hash(result.get('search_term', '')) % 1000}"
        }

        # Add strategy-specific metadata
        if strategy == SearchStrategy.HYBRID and "hybrid_metadata" in result:
            result["search_metadata"]["hybrid_stats"] = result["hybrid_metadata"]

        return result

    def _estimate_vector_confidence(self, matches: List[Dict]) -> float:
        """Estimate confidence for vector-only results"""

        if not matches:
            return 0.0

        # Use average similarity as confidence proxy
        similarities = [m.get("similarity", 0) for m in matches]
        avg_similarity = sum(similarities) / len(similarities)

        # Boost confidence if multiple good matches
        if len(matches) > 3 and avg_similarity > 0.6:
            return min(avg_similarity * 1.1, 1.0)

        return avg_similarity

    def _finalize_hybrid_result(self, vector_result: Dict, skip_reranking: bool = False) -> Dict[str, Any]:
        """Finalize hybrid result when reranking is skipped"""

        vector_result["search_strategy"] = "hybrid"
        vector_result["hybrid_metadata"] = {
            "vector_candidates": len(vector_result.get("matches", [])),
            "reranking_skipped": skip_reranking,
            "reason": "Too few candidates for reranking" if skip_reranking else "Reranking failed"
        }

        return vector_result

    def _create_error_result(self, error_msg: str, start_time: float) -> Dict[str, Any]:
        """Create standardized error result"""

        return {
            "error": error_msg,
            "matches": [],
            "total_found": 0,
            "formatted_response": f"Errore: {error_msg}",
            "search_metadata": {
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "strategy_used": "error_fallback"
            }
        }

    def _execute_emergency_fallback(self, query: str, start_time: float) -> Dict[str, Any]:
        """Emergency fallback when all strategies fail"""

        try:
            # Try basic vector search with minimal parameters
            if COMPONENTS_AVAILABLE:
                matches = DataRetriever.search_piani_by_keyword(query, similarity_threshold=0.2)
                if matches:
                    return {
                        "search_term": query,
                        "matches": matches[:5],
                        "total_found": len(matches),
                        "formatted_response": f"Risultati di emergenza per '{query}'",
                        "search_strategy": "emergency_fallback",
                        "search_metadata": {
                            "latency_ms": round((time.time() - start_time) * 1000, 2)
                        }
                    }

        except Exception as e:
            print(f"❌ Emergency fallback also failed: {e}")

        # Absolute last resort
        return self._create_error_result(
            "Sistema di ricerca temporaneamente non disponibile",
            start_time
        )

    def _validate_plan_aliases(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate plan aliases in search results by checking they exist in the database.
        Filters out hallucinated aliases that don't correspond to real plans.
        """
        if not COMPONENTS_AVAILABLE:
            return result

        matches = result.get("matches", [])
        if not matches:
            return result

        validated_matches = []
        for match in matches:
            alias = match.get("alias", "")
            if not alias:
                validated_matches.append(match)
                continue
            # Verify alias exists via DataRetriever
            try:
                piano_data = DataRetriever.get_piano_by_id(alias)
                if piano_data is not None:
                    validated_matches.append(match)
                else:
                    print(f"⚠️  Filtered out non-existent plan alias: {alias}")
            except Exception:
                # On error, keep the match (fail-open)
                validated_matches.append(match)

        if len(validated_matches) != len(matches):
            result["matches"] = validated_matches
            result["total_found"] = len(validated_matches)
            # Re-format response if needed
            if COMPONENTS_AVAILABLE and validated_matches:
                result["formatted_response"] = ResponseFormatter.format_search_results(
                    search_term=result.get("search_term", ""),
                    matches=validated_matches[:15],
                    max_display=15
                )

        return result

    def get_engine_stats(self) -> Dict[str, Any]:
        """Get engine performance and usage statistics"""

        router_stats = self.smart_router.get_routing_stats()
        tracker_stats = self.performance_tracker.compare_strategies()

        return {
            "engine_stats": self._search_stats,
            "routing_stats": router_stats,
            "performance_stats": tracker_stats,
            "configuration": {
                "vector_top_k": self.config.vector_top_k,
                "llm_rerank_top_k": self.config.llm_rerank_top_k,
                "max_latency_ms": self.config.max_hybrid_latency_ms
            }
        }

    def set_llm_client(self, llm_client):
        """Set LLM client for dependency injection"""
        self.llm_client = llm_client
        self.llm_reranker.set_llm_client(llm_client)