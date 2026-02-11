"""
Performance Tracker for Hybrid Search

Tracks and analyzes performance metrics across different search strategies.
"""

import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

@dataclass
class SearchMetrics:
    """Individual search operation metrics"""
    query: str
    strategy: str
    latency_ms: float
    result_count: int
    accuracy_estimate: float = 0.0
    user_satisfaction: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class MetricType(Enum):
    """Types of metrics we track"""
    LATENCY = "latency"
    ACCURACY = "accuracy"
    RESULT_COUNT = "result_count"
    USER_SATISFACTION = "user_satisfaction"

class PerformanceTracker:
    """
    Tracks performance metrics across search strategies with:
    - Real-time monitoring
    - Historical analysis
    - Performance alerting
    - Strategy comparison
    """

    def __init__(self, window_minutes: int = 30, max_history: int = 1000):
        """
        Initialize performance tracker.

        Args:
            window_minutes: Sliding window for current performance calculation
            max_history: Maximum number of metrics to keep in memory
        """
        self.window_minutes = window_minutes
        self.max_history = max_history

        # Storage
        self.metrics_history = deque(maxlen=max_history)
        self.strategy_stats = defaultdict(list)

        # Real-time monitoring
        self._current_load = 0.0
        self._last_load_update = time.time()

        # Alert thresholds
        self.alert_thresholds = {
            "latency_p95_ms": 5000,
            "accuracy_min": 0.7,
            "error_rate_max": 0.05
        }

    def track_search(self, query: str, strategy: str, result: Dict[str, Any],
                    latency_ms: float, metadata: Dict[str, Any] = None) -> None:
        """
        Track a search operation.

        Args:
            query: User query
            strategy: Strategy used (vector_only, llm_only, hybrid)
            result: Search result dictionary
            latency_ms: Time taken for the search
            metadata: Additional context
        """
        metrics = SearchMetrics(
            query=query[:100],  # Truncate for privacy/storage
            strategy=strategy,
            latency_ms=latency_ms,
            result_count=len(result.get('matches', [])),
            accuracy_estimate=self._estimate_accuracy(result),
            metadata=metadata or {},
            timestamp=datetime.now()
        )

        # Add to history with automatic cleanup
        self.metrics_history.append(metrics)
        self._cleanup_old_metrics()

        # Update strategy-specific stats
        self.strategy_stats[strategy].append(metrics)
        self._cleanup_strategy_stats()

        # Update real-time load estimate
        self._update_load_estimate()

    def get_current_load(self) -> float:
        """
        Get current system load estimate (0-1).

        Returns:
            Load estimate where 1.0 = very high load
        """
        # Update load if it's been a while
        if time.time() - self._last_load_update > 30:  # 30 seconds
            self._update_load_estimate()

        return self._current_load

    def get_strategy_performance(self, strategy: str, window_minutes: int = None) -> Dict[str, Any]:
        """
        Get performance statistics for a specific strategy.

        Args:
            strategy: Strategy name (vector_only, llm_only, hybrid)
            window_minutes: Time window for analysis (default: instance window)

        Returns:
            Performance statistics dictionary
        """
        window = window_minutes or self.window_minutes
        cutoff = datetime.now() - timedelta(minutes=window)

        # Get recent metrics for this strategy
        recent_metrics = [
            m for m in self.strategy_stats.get(strategy, [])
            if m.timestamp > cutoff
        ]

        if not recent_metrics:
            return {
                "strategy": strategy,
                "sample_count": 0,
                "error": "No recent data available"
            }

        # Calculate statistics
        latencies = [m.latency_ms for m in recent_metrics]
        accuracies = [m.accuracy_estimate for m in recent_metrics]
        result_counts = [m.result_count for m in recent_metrics]

        # Percentile calculations
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        return {
            "strategy": strategy,
            "sample_count": n,
            "window_minutes": window,
            "latency": {
                "avg_ms": round(sum(latencies) / n, 2),
                "p50_ms": latencies_sorted[n // 2],
                "p95_ms": latencies_sorted[int(0.95 * n)] if n > 5 else latencies_sorted[-1],
                "p99_ms": latencies_sorted[int(0.99 * n)] if n > 10 else latencies_sorted[-1],
                "min_ms": min(latencies),
                "max_ms": max(latencies)
            },
            "accuracy": {
                "avg": round(sum(accuracies) / n, 3),
                "min": min(accuracies),
                "max": max(accuracies)
            },
            "results": {
                "avg_count": round(sum(result_counts) / n, 1),
                "zero_results_rate": sum(1 for c in result_counts if c == 0) / n
            }
        }

    def compare_strategies(self, strategies: List[str] = None,
                          window_minutes: int = None) -> Dict[str, Any]:
        """
        Compare performance across strategies.

        Args:
            strategies: List of strategies to compare (default: all available)
            window_minutes: Time window for analysis

        Returns:
            Comparison results with rankings and insights
        """
        if strategies is None:
            strategies = list(self.strategy_stats.keys())

        if not strategies:
            return {"error": "No strategies available for comparison"}

        # Get performance for each strategy
        strategy_performance = {}
        for strategy in strategies:
            perf = self.get_strategy_performance(strategy, window_minutes)
            if perf.get("sample_count", 0) > 0:
                strategy_performance[strategy] = perf

        if not strategy_performance:
            return {"error": "No recent data available for any strategy"}

        # Calculate rankings
        rankings = self._calculate_strategy_rankings(strategy_performance)

        # Generate insights
        insights = self._generate_comparison_insights(strategy_performance, rankings)

        return {
            "comparison_time": datetime.now().isoformat(),
            "strategies_compared": list(strategy_performance.keys()),
            "performance_details": strategy_performance,
            "rankings": rankings,
            "insights": insights,
            "recommendation": self._get_strategy_recommendation(rankings, insights)
        }

    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for performance alerts based on thresholds.

        Returns:
            List of active alerts
        """
        alerts = []

        for strategy in self.strategy_stats.keys():
            perf = self.get_strategy_performance(strategy, window_minutes=10)

            if perf.get("sample_count", 0) < 5:
                continue  # Not enough data

            # Latency alerts
            p95_latency = perf["latency"]["p95_ms"]
            if p95_latency > self.alert_thresholds["latency_p95_ms"]:
                alerts.append({
                    "type": "performance_degradation",
                    "strategy": strategy,
                    "metric": "latency_p95",
                    "value": p95_latency,
                    "threshold": self.alert_thresholds["latency_p95_ms"],
                    "severity": "high" if p95_latency > 2 * self.alert_thresholds["latency_p95_ms"] else "medium"
                })

            # Accuracy alerts
            avg_accuracy = perf["accuracy"]["avg"]
            if avg_accuracy < self.alert_thresholds["accuracy_min"]:
                alerts.append({
                    "type": "accuracy_degradation",
                    "strategy": strategy,
                    "metric": "accuracy_avg",
                    "value": avg_accuracy,
                    "threshold": self.alert_thresholds["accuracy_min"],
                    "severity": "high" if avg_accuracy < 0.5 else "medium"
                })

            # Zero results rate alert
            zero_results_rate = perf["results"]["zero_results_rate"]
            if zero_results_rate > self.alert_thresholds["error_rate_max"]:
                alerts.append({
                    "type": "high_error_rate",
                    "strategy": strategy,
                    "metric": "zero_results_rate",
                    "value": zero_results_rate,
                    "threshold": self.alert_thresholds["error_rate_max"],
                    "severity": "high" if zero_results_rate > 0.2 else "medium"
                })

        return alerts

    def _estimate_accuracy(self, result: Dict[str, Any]) -> float:
        """
        Estimate accuracy based on result characteristics.

        This is a heuristic until we have user feedback mechanisms.
        """
        matches = result.get('matches', [])

        if not matches:
            return 0.0

        # Use average similarity score as proxy for accuracy
        similarities = [m.get('similarity', 0) for m in matches]
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            # Convert similarity to accuracy estimate with some adjustment
            return min(avg_similarity * 1.1, 1.0)

        # Fallback: estimate based on result count
        result_count = len(matches)
        if result_count > 5:
            return 0.8  # Assume good if multiple results
        elif result_count > 0:
            return 0.6  # Moderate if some results
        else:
            return 0.0

    def _update_load_estimate(self) -> None:
        """Update real-time system load estimate"""
        current_time = time.time()
        self._last_load_update = current_time

        # Get metrics from last 2 minutes
        recent_cutoff = datetime.now() - timedelta(minutes=2)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > recent_cutoff]

        if not recent_metrics:
            self._current_load = 0.0
            return

        # Calculate load factors
        request_rate = len(recent_metrics) / 2.0  # requests per minute
        avg_latency = sum(m.latency_ms for m in recent_metrics) / len(recent_metrics)

        # Load estimation formula
        # High request rate + high latency = high load
        load_score = min((request_rate * avg_latency) / 5000.0, 1.0)

        # Smooth the load estimate (exponential moving average)
        alpha = 0.3  # Smoothing factor
        self._current_load = alpha * load_score + (1 - alpha) * self._current_load

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics outside the maximum history window"""
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes * 2)

        # Clean main history (deque handles max size automatically)
        # But we might want to clean by time too
        while (self.metrics_history
               and self.metrics_history[0].timestamp < cutoff):
            self.metrics_history.popleft()

    def _cleanup_strategy_stats(self) -> None:
        """Clean strategy-specific stats to prevent memory bloat"""
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes * 2)

        for strategy in self.strategy_stats:
            self.strategy_stats[strategy] = [
                m for m in self.strategy_stats[strategy]
                if m.timestamp > cutoff
            ]

    def _calculate_strategy_rankings(self, performance: Dict[str, Dict]) -> Dict[str, Any]:
        """Calculate rankings for strategies across different metrics"""
        if len(performance) < 2:
            return {"error": "Need at least 2 strategies for ranking"}

        strategies = list(performance.keys())

        # Rank by different metrics (lower is better for latency, higher for accuracy)
        latency_ranking = sorted(strategies, key=lambda s: performance[s]["latency"]["avg_ms"])
        accuracy_ranking = sorted(strategies, key=lambda s: performance[s]["accuracy"]["avg"], reverse=True)

        # Calculate combined score (simple weighted average)
        combined_scores = {}
        for strategy in strategies:
            perf = performance[strategy]

            # Normalize metrics (0-1 scale)
            latency_score = 1 - min(perf["latency"]["avg_ms"] / 5000.0, 1.0)  # Lower is better
            accuracy_score = perf["accuracy"]["avg"]  # Higher is better

            # Weighted combination (accuracy weighted more heavily)
            combined_scores[strategy] = 0.3 * latency_score + 0.7 * accuracy_score

        overall_ranking = sorted(strategies, key=lambda s: combined_scores[s], reverse=True)

        return {
            "latency_ranking": latency_ranking,
            "accuracy_ranking": accuracy_ranking,
            "overall_ranking": overall_ranking,
            "combined_scores": combined_scores
        }

    def _generate_comparison_insights(self, performance: Dict, rankings: Dict) -> List[str]:
        """Generate human-readable insights from performance comparison"""
        insights = []

        if "error" in rankings:
            return ["Insufficient data for meaningful insights"]

        # Best overall strategy
        best_overall = rankings["overall_ranking"][0]
        insights.append(f"Overall best performer: {best_overall}")

        # Speed vs accuracy tradeoffs
        fastest = rankings["latency_ranking"][0]
        most_accurate = rankings["accuracy_ranking"][0]

        if fastest != most_accurate:
            insights.append(f"Speed-accuracy tradeoff: {fastest} is fastest, {most_accurate} is most accurate")

        # Performance gaps
        strategies = list(performance.keys())
        if len(strategies) >= 2:
            best_latency = performance[fastest]["latency"]["avg_ms"]
            worst_latency = performance[rankings["latency_ranking"][-1]]["latency"]["avg_ms"]

            if worst_latency > best_latency * 2:
                insights.append(f"Significant latency gap: {worst_latency/best_latency:.1f}x difference")

        return insights

    def _get_strategy_recommendation(self, rankings: Dict, insights: List[str]) -> str:
        """Get recommendation for optimal strategy selection"""
        if "error" in rankings:
            return "Insufficient data for recommendation"

        best_overall = rankings["overall_ranking"][0]
        return f"Recommend {best_overall} as primary strategy based on combined performance"