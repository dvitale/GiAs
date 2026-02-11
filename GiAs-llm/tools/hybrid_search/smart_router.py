"""
Smart Router for Hybrid Search

Intelligently selects the optimal search strategy based on query analysis.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time
from .query_analyzer import QueryAnalyzer, QueryAnalysis

class SearchStrategy(Enum):
    """Available search strategies"""
    VECTOR_ONLY = "vector_only"
    LLM_ONLY = "llm_only"
    HYBRID = "hybrid"

@dataclass
class RoutingConfig:
    """Configuration for smart routing decisions"""

    # Complexity thresholds
    complexity_threshold_high: float = 0.7  # Above = LLM only
    complexity_threshold_low: float = 0.3   # Below = Vector only

    # Performance constraints
    max_latency_ms: int = 3000
    max_tokens_per_query: int = 800

    # Quality constraints
    min_confidence_vector: float = 0.6
    min_confidence_llm: float = 0.8

    # System load thresholds
    high_load_threshold: float = 0.8  # Above = prefer vector

    # Domain-specific rules
    enable_domain_boosting: bool = True
    semantic_indicator_weight: float = 0.3

class SmartRouter:
    """
    Intelligent router that selects optimal search strategy based on:
    - Query complexity analysis
    - Current system performance
    - Historical success rates
    - User preferences and constraints
    """

    def __init__(self, config: RoutingConfig = None):
        self.config = config or RoutingConfig()
        self._cpu_mode = None  # Lazy loaded from config.json
        self.query_analyzer = QueryAnalyzer()
        self.performance_history = {}
        self.routing_stats = {
            "total_requests": 0,
            "strategy_counts": {
                SearchStrategy.VECTOR_ONLY.value: 0,
                SearchStrategy.LLM_ONLY.value: 0,
                SearchStrategy.HYBRID.value: 0
            }
        }

    def select_strategy(self, query: str, metadata: Dict[str, Any] = None) -> SearchStrategy:
        """
        Select optimal search strategy for the given query.

        Args:
            query: User query string
            metadata: Additional context (user preferences, system state, etc.)

        Returns:
            SearchStrategy enum indicating optimal approach
        """
        if not query or not query.strip():
            return SearchStrategy.VECTOR_ONLY  # Default for empty queries

        # CPU-mode: forza vector_only per risparmiare LLM calls
        if self._is_cpu_mode():
            analysis = self.query_analyzer.analyze(query)
            self._track_routing_decision(query, analysis, SearchStrategy.VECTOR_ONLY)
            return SearchStrategy.VECTOR_ONLY

        # Analyze query characteristics
        analysis = self.query_analyzer.analyze(query)

        # Apply routing logic
        strategy = self._apply_routing_rules(analysis, metadata or {})

        # System-level adjustments
        strategy = self._adjust_for_system_state(strategy, metadata or {})

        # Track routing decision
        self._track_routing_decision(query, analysis, strategy)

        return strategy

    def _apply_routing_rules(self, analysis: QueryAnalysis, metadata: Dict) -> SearchStrategy:
        """
        Core routing logic based on query analysis.

        Rules are applied in priority order - first match wins.
        """

        # Rule 1: Exact code queries → Vector (fast exact match)
        if analysis.query_type == "exact_code":
            return SearchStrategy.VECTOR_ONLY

        # Rule 2: Very high complexity → Hybrid (always ground with retrieval)
        if analysis.complexity_score > self.config.complexity_threshold_high:
            return SearchStrategy.HYBRID

        # Rule 3: Low complexity + no semantic indicators → Vector only (simple keyword)
        if (analysis.complexity_score < self.config.complexity_threshold_low
            and len(analysis.semantic_indicators) == 0):
            return SearchStrategy.VECTOR_ONLY

        # Rule 4: High domain entity count + semantic indicators → Hybrid (ground with retrieval)
        if (analysis.entity_count > 2
            and len(analysis.semantic_indicators) > 1):
            return SearchStrategy.HYBRID

        # Rule 5: Question queries with domain terms → Hybrid (recall + precision)
        if (analysis.query_type == "question"
            and analysis.entity_count > 0):
            return SearchStrategy.HYBRID

        # Rule 6: Semantic relationship queries → always Hybrid (ground with retrieval)
        if analysis.query_type == "semantic_relationship":
            return SearchStrategy.HYBRID

        # Rule 7: Multi-domain queries → Hybrid (comprehensive coverage)
        if analysis.entity_count > 1:
            return SearchStrategy.HYBRID

        # Rule 8: Medium complexity queries → Hybrid (balanced approach)
        if 0.3 <= analysis.complexity_score <= 0.7:
            return SearchStrategy.HYBRID

        # Default: Vector (conservative, fast choice)
        return SearchStrategy.VECTOR_ONLY

    def _adjust_for_system_state(self, strategy: SearchStrategy, metadata: Dict) -> SearchStrategy:
        """
        Adjust strategy based on current system state and constraints.
        """

        # User preference overrides
        user_preference = metadata.get("preferred_strategy")
        if user_preference and user_preference in [s.value for s in SearchStrategy]:
            try:
                return SearchStrategy(user_preference)
            except ValueError:
                pass  # Invalid preference, ignore

        # Fast response requirement
        if metadata.get("require_fast_response", False):
            if strategy == SearchStrategy.HYBRID:
                return SearchStrategy.VECTOR_ONLY

        # System load considerations (would be implemented with actual monitoring)
        current_load = metadata.get("system_load", 0.0)
        if current_load > self.config.high_load_threshold:
            # Under high load, prefer lighter strategies
            if strategy == SearchStrategy.HYBRID:
                # Only downgrade if load is very high
                if current_load > 0.9:
                    return SearchStrategy.VECTOR_ONLY

        # Token budget constraints (for LLM strategies)
        max_tokens = metadata.get("max_tokens", self.config.max_tokens_per_query)
        if max_tokens < 200:  # Very limited token budget
            if strategy == SearchStrategy.HYBRID:
                return SearchStrategy.VECTOR_ONLY

        return strategy

    def _is_cpu_mode(self) -> bool:
        """Verifica se la configurazione richiede modalità CPU-only (no LLM reranking)."""
        if self._cpu_mode is not None:
            return self._cpu_mode
        try:
            import json, os
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "configs", "config.json"
            )
            with open(config_path, 'r') as f:
                config = json.load(f)
            self._cpu_mode = config.get("hybrid_search", {}).get("cpu_mode", False)
        except Exception:
            self._cpu_mode = False
        return self._cpu_mode

    def _track_routing_decision(self, query: str, analysis: QueryAnalysis,
                              strategy: SearchStrategy) -> None:
        """Track routing decisions for analytics and optimization"""

        self.routing_stats["total_requests"] += 1
        self.routing_stats["strategy_counts"][strategy.value] += 1

        # Store recent decisions for analysis (keep last 100)
        if not hasattr(self, '_recent_decisions'):
            self._recent_decisions = []

        decision_record = {
            "timestamp": time.time(),
            "query": query[:50],  # Truncate for privacy
            "complexity_score": analysis.complexity_score,
            "entity_count": analysis.entity_count,
            "semantic_indicators": len(analysis.semantic_indicators),
            "query_type": analysis.query_type,
            "strategy": strategy.value
        }

        self._recent_decisions.append(decision_record)

        # Keep only recent decisions
        if len(self._recent_decisions) > 100:
            self._recent_decisions = self._recent_decisions[-100:]

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics for monitoring and optimization"""

        total = self.routing_stats["total_requests"]
        if total == 0:
            return {"error": "No routing decisions recorded"}

        strategy_percentages = {}
        for strategy, count in self.routing_stats["strategy_counts"].items():
            strategy_percentages[f"{strategy}_percentage"] = round((count / total) * 100, 1)

        recent_decisions = getattr(self, '_recent_decisions', [])

        return {
            "total_requests": total,
            "strategy_distribution": self.routing_stats["strategy_counts"],
            "strategy_percentages": strategy_percentages,
            "recent_decision_count": len(recent_decisions),
            "avg_complexity": self._calculate_avg_complexity(recent_decisions),
            "common_query_types": self._get_common_query_types(recent_decisions)
        }

    def _calculate_avg_complexity(self, decisions: List[Dict]) -> float:
        """Calculate average complexity score from recent decisions"""
        if not decisions:
            return 0.0

        total_complexity = sum(d["complexity_score"] for d in decisions)
        return round(total_complexity / len(decisions), 3)

    def _get_common_query_types(self, decisions: List[Dict]) -> Dict[str, int]:
        """Get distribution of query types from recent decisions"""
        type_counts = {}

        for decision in decisions:
            query_type = decision["query_type"]
            type_counts[query_type] = type_counts.get(query_type, 0) + 1

        # Sort by frequency
        return dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True))

    def explain_decision(self, query: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Explain why a particular strategy was chosen for educational/debugging purposes.

        Args:
            query: The query to analyze
            metadata: Context metadata

        Returns:
            Dictionary with decision explanation
        """
        analysis = self.query_analyzer.analyze(query)
        strategy = self.select_strategy(query, metadata)

        explanation = {
            "query": query,
            "selected_strategy": strategy.value,
            "query_analysis": {
                "complexity_score": analysis.complexity_score,
                "query_type": analysis.query_type,
                "entity_count": analysis.entity_count,
                "semantic_indicators": analysis.semantic_indicators,
                "domain_terms": analysis.domain_terms
            },
            "decision_factors": self._get_decision_factors(analysis),
            "alternative_strategies": self._get_alternative_explanations(analysis)
        }

        return explanation

    def _get_decision_factors(self, analysis: QueryAnalysis) -> List[str]:
        """Get human-readable decision factors"""
        factors = []

        if analysis.query_type == "exact_code":
            factors.append("Query is exact code (piano ID) - use vector for fast lookup")

        if analysis.complexity_score > 0.7:
            factors.append("High complexity score - requires LLM reasoning")

        if analysis.complexity_score < 0.3:
            factors.append("Low complexity score - simple vector search sufficient")

        if len(analysis.semantic_indicators) > 0:
            factors.append(f"Semantic indicators found: {analysis.semantic_indicators}")

        if analysis.entity_count > 1:
            factors.append(f"Multiple domain entities: {analysis.domain_terms}")

        if analysis.query_type == "question":
            factors.append("Question query - benefits from comprehensive search")

        return factors

    def _get_alternative_explanations(self, analysis: QueryAnalysis) -> Dict[str, str]:
        """Explain why other strategies weren't chosen"""
        alternatives = {}

        # This would contain explanations for why each strategy wasn't optimal
        alternatives["vector_only"] = "Fast but may miss semantic relationships"
        alternatives["llm_only"] = "Best understanding but slower"
        alternatives["hybrid"] = "Balanced approach with vector recall + LLM precision"

        return alternatives