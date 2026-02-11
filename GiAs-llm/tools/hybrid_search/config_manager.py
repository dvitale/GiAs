"""
Configuration Manager for Hybrid Search

Manages routing rules, performance thresholds, and strategy selection logic.
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class RoutingRule:
    """Single routing rule configuration"""
    name: str
    description: str
    conditions: Dict[str, Any]
    target_strategy: str
    priority: int = 0
    enabled: bool = True

@dataclass
class PerformanceThresholds:
    """Performance thresholds for strategy selection"""
    max_latency_ms: int = 3000
    min_accuracy: float = 0.7
    max_system_load: float = 0.8
    min_confidence: float = 0.6

@dataclass
class HybridConfig:
    """Complete hybrid search configuration"""
    enabled: bool = True
    default_strategy: str = "hybrid"
    routing_rules: List[RoutingRule] = None
    performance_thresholds: PerformanceThresholds = None
    vector_settings: Dict[str, Any] = None
    llm_settings: Dict[str, Any] = None

    def __post_init__(self):
        if self.routing_rules is None:
            self.routing_rules = []
        if self.performance_thresholds is None:
            self.performance_thresholds = PerformanceThresholds()
        if self.vector_settings is None:
            self.vector_settings = {
                "top_k": 20,
                "threshold": 0.3,
                "timeout_ms": 1000
            }
        if self.llm_settings is None:
            self.llm_settings = {
                "rerank_top_k": 10,
                "max_tokens": 500,
                "temperature": 0.1,
                "timeout_ms": 5000
            }

class HybridConfigManager:
    """
    Manages configuration for hybrid search system with:
    - Dynamic routing rules
    - Performance thresholds
    - Strategy selection logic
    - Runtime configuration updates
    """

    def __init__(self, config_path: str = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file (default: auto-detect)
        """
        self.config_path = config_path or self._detect_config_path()
        self.config = self._load_configuration()
        self._last_modified = None

    def get_routing_rules(self) -> List[RoutingRule]:
        """Get all enabled routing rules, sorted by priority"""
        enabled_rules = [rule for rule in self.config.routing_rules if rule.enabled]
        return sorted(enabled_rules, key=lambda r: r.priority, reverse=True)

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Add new routing rule"""
        # Check for duplicate names
        existing_names = {r.name for r in self.config.routing_rules}
        if rule.name in existing_names:
            raise ValueError(f"Routing rule '{rule.name}' already exists")

        self.config.routing_rules.append(rule)
        self._save_configuration()

    def update_routing_rule(self, rule_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update existing routing rule.

        Args:
            rule_name: Name of rule to update
            updates: Dictionary of fields to update

        Returns:
            True if rule was found and updated
        """
        for i, rule in enumerate(self.config.routing_rules):
            if rule.name == rule_name:
                # Update fields
                for field, value in updates.items():
                    if hasattr(rule, field):
                        setattr(rule, field, value)

                self._save_configuration()
                return True
        return False

    def remove_routing_rule(self, rule_name: str) -> bool:
        """Remove routing rule by name"""
        original_count = len(self.config.routing_rules)
        self.config.routing_rules = [
            rule for rule in self.config.routing_rules
            if rule.name != rule_name
        ]

        if len(self.config.routing_rules) < original_count:
            self._save_configuration()
            return True
        return False

    def evaluate_routing_rules(self, query_analysis: Dict[str, Any],
                              metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Evaluate routing rules against query analysis and return target strategy.

        Args:
            query_analysis: Results from QueryAnalyzer
            metadata: Additional context

        Returns:
            Target strategy name or None if no rules match
        """
        metadata = metadata or {}

        # Get enabled rules sorted by priority
        rules = self.get_routing_rules()

        for rule in rules:
            if self._evaluate_rule_conditions(rule.conditions, query_analysis, metadata):
                return rule.target_strategy

        return None

    def _evaluate_rule_conditions(self, conditions: Dict[str, Any],
                                 analysis: Dict[str, Any],
                                 metadata: Dict[str, Any]) -> bool:
        """Evaluate whether rule conditions are met"""

        for condition_key, condition_value in conditions.items():

            # Handle complexity score conditions
            if condition_key == "complexity_score":
                score = analysis.get("complexity_score", 0.0)
                if not self._check_numeric_condition(score, condition_value):
                    return False

            # Handle entity count conditions
            elif condition_key == "entity_count":
                count = analysis.get("entity_count", 0)
                if not self._check_numeric_condition(count, condition_value):
                    return False

            # Handle semantic indicators
            elif condition_key == "has_semantic_indicators":
                has_indicators = len(analysis.get("semantic_indicators", [])) > 0
                if has_indicators != condition_value:
                    return False

            # Handle query type
            elif condition_key == "query_type":
                query_type = analysis.get("query_type", "")
                if isinstance(condition_value, list):
                    if query_type not in condition_value:
                        return False
                else:
                    if query_type != condition_value:
                        return False

            # Handle system load (from metadata)
            elif condition_key == "system_load":
                load = metadata.get("system_load", 0.0)
                if not self._check_numeric_condition(load, condition_value):
                    return False

            # Handle user preferences
            elif condition_key == "user_preference":
                user_pref = metadata.get("user_preference", "")
                if user_pref != condition_value:
                    return False

            # Handle time-based conditions
            elif condition_key == "time_of_day":
                current_hour = datetime.now().hour
                if not self._check_time_condition(current_hour, condition_value):
                    return False

        return True

    def _check_numeric_condition(self, value: float, condition: Any) -> bool:
        """Check numeric condition (supports min, max, exact)"""

        if isinstance(condition, (int, float)):
            return value == condition

        if isinstance(condition, dict):
            if "min" in condition and value < condition["min"]:
                return False
            if "max" in condition and value > condition["max"]:
                return False
            if "exact" in condition and value != condition["exact"]:
                return False

        return True

    def _check_time_condition(self, hour: int, condition: Dict[str, Any]) -> bool:
        """Check time-based condition"""

        if "between" in condition:
            start, end = condition["between"]
            if start <= end:
                return start <= hour <= end
            else:  # Overnight range (e.g., 22-6)
                return hour >= start or hour <= end

        return True

    def get_performance_thresholds(self) -> PerformanceThresholds:
        """Get current performance thresholds"""
        return self.config.performance_thresholds

    def update_performance_thresholds(self, **kwargs) -> None:
        """Update performance thresholds"""
        thresholds = self.config.performance_thresholds

        for field, value in kwargs.items():
            if hasattr(thresholds, field):
                setattr(thresholds, field, value)

        self._save_configuration()

    def get_strategy_config(self, strategy: str) -> Dict[str, Any]:
        """Get configuration for specific strategy"""

        if strategy == "vector_only":
            return self.config.vector_settings.copy()
        elif strategy in ["llm_only", "hybrid"]:
            return self.config.llm_settings.copy()
        else:
            return {}

    def is_enabled(self) -> bool:
        """Check if hybrid search is enabled"""
        return self.config.enabled

    def enable_hybrid_search(self) -> None:
        """Enable hybrid search"""
        self.config.enabled = True
        self._save_configuration()

    def disable_hybrid_search(self) -> None:
        """Disable hybrid search"""
        self.config.enabled = False
        self._save_configuration()

    def reload_configuration(self) -> bool:
        """
        Reload configuration from file if it was modified.

        Returns:
            True if configuration was reloaded
        """
        if not os.path.exists(self.config_path):
            return False

        current_modified = os.path.getmtime(self.config_path)

        if self._last_modified is None or current_modified > self._last_modified:
            self.config = self._load_configuration()
            self._last_modified = current_modified
            return True

        return False

    def export_configuration(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            "enabled": self.config.enabled,
            "default_strategy": self.config.default_strategy,
            "routing_rules": [
                {
                    "name": rule.name,
                    "description": rule.description,
                    "conditions": rule.conditions,
                    "target_strategy": rule.target_strategy,
                    "priority": rule.priority,
                    "enabled": rule.enabled
                }
                for rule in self.config.routing_rules
            ],
            "performance_thresholds": asdict(self.config.performance_thresholds),
            "vector_settings": self.config.vector_settings,
            "llm_settings": self.config.llm_settings
        }

    def import_configuration(self, config_dict: Dict[str, Any]) -> None:
        """Import configuration from dictionary"""

        # Create routing rules
        routing_rules = []
        for rule_data in config_dict.get("routing_rules", []):
            rule = RoutingRule(
                name=rule_data["name"],
                description=rule_data["description"],
                conditions=rule_data["conditions"],
                target_strategy=rule_data["target_strategy"],
                priority=rule_data.get("priority", 0),
                enabled=rule_data.get("enabled", True)
            )
            routing_rules.append(rule)

        # Create performance thresholds
        perf_data = config_dict.get("performance_thresholds", {})
        performance_thresholds = PerformanceThresholds(**perf_data)

        # Update configuration
        self.config = HybridConfig(
            enabled=config_dict.get("enabled", True),
            default_strategy=config_dict.get("default_strategy", "hybrid"),
            routing_rules=routing_rules,
            performance_thresholds=performance_thresholds,
            vector_settings=config_dict.get("vector_settings", {}),
            llm_settings=config_dict.get("llm_settings", {})
        )

        self._save_configuration()

    def _load_configuration(self) -> HybridConfig:
        """Load configuration from file or create default"""

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)

                # Parse hybrid search specific config
                hybrid_config = config_dict.get("hybrid_search", {})

                if hybrid_config:
                    self.import_configuration(hybrid_config)
                    return self.config

            except Exception as e:
                print(f"⚠️  Failed to load hybrid config: {e}, using defaults")

        # Return default configuration
        return self._create_default_config()

    def _create_default_config(self) -> HybridConfig:
        """Create default configuration with sensible routing rules"""

        default_rules = [
            RoutingRule(
                name="exact_code_queries",
                description="Route exact piano codes to vector search",
                conditions={"query_type": "exact_code"},
                target_strategy="vector_only",
                priority=10
            ),
            RoutingRule(
                name="high_complexity_semantic",
                description="Route complex semantic queries to LLM",
                conditions={"complexity_score": {"min": 0.7}},
                target_strategy="llm_only",
                priority=8
            ),
            RoutingRule(
                name="simple_keywords",
                description="Route simple keyword queries to vector search",
                conditions={
                    "complexity_score": {"max": 0.3},
                    "has_semantic_indicators": False
                },
                target_strategy="vector_only",
                priority=6
            ),
            RoutingRule(
                name="high_load_fallback",
                description="Use vector search under high system load",
                conditions={"system_load": {"min": 0.8}},
                target_strategy="vector_only",
                priority=9
            ),
            RoutingRule(
                name="question_queries",
                description="Use hybrid approach for question queries",
                conditions={
                    "query_type": "question",
                    "entity_count": {"min": 1}
                },
                target_strategy="hybrid",
                priority=5
            )
        ]

        return HybridConfig(
            enabled=True,
            default_strategy="hybrid",
            routing_rules=default_rules,
            performance_thresholds=PerformanceThresholds(),
            vector_settings={
                "top_k": 20,
                "threshold": 0.3,
                "timeout_ms": 1000
            },
            llm_settings={
                "rerank_top_k": 10,
                "max_tokens": 500,
                "temperature": 0.1,
                "timeout_ms": 5000
            }
        )

    def _save_configuration(self) -> None:
        """Save configuration to file"""

        try:
            # Load existing config file to preserve other settings
            config_data = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

            # Update hybrid search section
            config_data["hybrid_search"] = self.export_configuration()

            # Save back to file
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self._last_modified = os.path.getmtime(self.config_path)

        except Exception as e:
            print(f"❌ Failed to save hybrid configuration: {e}")

    def _detect_config_path(self) -> str:
        """Auto-detect configuration file path"""

        # Try to find config.json in project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        config_path = os.path.join(project_root, "config.json")

        return config_path

    def get_stats(self) -> Dict[str, Any]:
        """Get configuration statistics"""

        enabled_rules = sum(1 for rule in self.config.routing_rules if rule.enabled)

        return {
            "enabled": self.config.enabled,
            "default_strategy": self.config.default_strategy,
            "total_rules": len(self.config.routing_rules),
            "enabled_rules": enabled_rules,
            "config_file": self.config_path,
            "last_modified": self._last_modified
        }