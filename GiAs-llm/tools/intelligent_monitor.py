"""
Intelligent Monitor per GIAS-AI

Sistema avanzato di analisi che va oltre il monitoring base per:
- Rilevare bug automaticamente (BugDetector)
- Analizzare cause root dei problemi (RootCauseAnalyzer)
- Generare suggerimenti actionable (ImprovementSuggester)
- Identificare trend e degradazioni (TrendAnalyzer)
- Scoprire nuovi use case utente (UserIntentMiner)

Usage:
  python -m tools.intelligent_monitor --days 7 --format summary
  python -m tools.intelligent_monitor --days 7 --use-llm --output report.json
  python -m tools.intelligent_monitor --suggestions --min-priority 3
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.conversation_monitor import (
    get_db_engine,
    ConversationAnalyzer,
    QualityDetector,
    LLMAnalyzer,
    Problem,
    Severity,
    MonitorReport,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

class SuggestionType(str, Enum):
    """Tipi di suggerimenti generati"""
    FIX_BUG = "fix_bug"              # Errore ricorrente da correggere
    ADD_PATTERN = "add_pattern"      # Pattern mancante nel router
    ADD_INTENT = "add_intent"        # Nuovo intent da implementare
    OPTIMIZE_TOOL = "optimize_tool"  # Tool con latenza alta
    UPDATE_TRAINING = "update_training"  # Esempi training da aggiornare
    INVESTIGATE = "investigate"      # Richiede investigazione manuale


@dataclass
class Suggestion:
    """Suggerimento di miglioramento generato dall'analisi"""
    type: SuggestionType
    priority: int  # 1-5, dove 5 è critico
    title: str
    description: str
    action: str  # Azione da intraprendere
    evidence: Dict[str, Any] = field(default_factory=dict)
    estimated_impact: str = "medium"  # low, medium, high
    implementation_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class TrendAlert:
    """Alert di degradazione performance"""
    metric: str
    current_value: float
    baseline_value: float
    delta_pct: float
    severity: str  # low, medium, high, critical
    intent: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HealthScore:
    """Score di salute complessivo del sistema"""
    overall_score: float  # 0-100
    components: Dict[str, float]  # Scores per componente
    alerts: List[TrendAlert]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["alerts"] = [a.to_dict() for a in self.alerts]
        return d


@dataclass
class IntelligentReport:
    """Report completo dell'Intelligent Monitor"""
    period_days: int
    generated_at: str
    health_score: HealthScore
    suggestions: List[Suggestion]
    bugs_detected: List[Dict[str, Any]]
    trend_analysis: Dict[str, Any]
    unmet_needs: List[Dict[str, Any]]
    root_causes: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_days": self.period_days,
            "generated_at": self.generated_at,
            "health_score": self.health_score.to_dict(),
            "suggestions": {
                "by_priority": {
                    "critical": [s.to_dict() for s in self.suggestions if s.priority == 5],
                    "high": [s.to_dict() for s in self.suggestions if s.priority == 4],
                    "medium": [s.to_dict() for s in self.suggestions if s.priority == 3],
                    "low": [s.to_dict() for s in self.suggestions if s.priority <= 2],
                },
                "by_type": {},
                "total": len(self.suggestions),
            },
            "bugs_detected": self.bugs_detected,
            "trend_analysis": self.trend_analysis,
            "unmet_needs": self.unmet_needs,
            "root_causes": self.root_causes,
        }


# =============================================================================
# BUG DETECTOR
# =============================================================================

class BugDetector:
    """
    Rileva bug automaticamente analizzando:
    - Errori ricorrenti con stessa signature
    - Intent che falliscono per specifici slot values
    - Correlazioni errori per ASL/fascia oraria
    """

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()

    def detect_recurring_errors(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """Rileva errori che si ripetono con la stessa signature"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        error_signature,
                        occurrence_count,
                        affected_sessions,
                        affected_asls,
                        related_intents,
                        asl_list,
                        first_occurrence,
                        last_occurrence,
                        span_days
                    FROM v_recurring_errors
                    WHERE occurrence_count >= :min_occurrences
                    ORDER BY occurrence_count DESC
                    LIMIT 20
                """), {"min_occurrences": min_occurrences}).fetchall()

            return [{
                "error_signature": row[0],
                "occurrence_count": row[1],
                "affected_sessions": row[2],
                "affected_asls": row[3],
                "related_intents": row[4] or [],
                "asl_list": row[5] or [],
                "first_occurrence": str(row[6]) if row[6] else None,
                "last_occurrence": str(row[7]) if row[7] else None,
                "span_days": row[8],
                "bug_type": "recurring_error",
            } for row in rows]
        except Exception as e:
            logger.error(f"[BugDetector] Error detecting recurring errors: {e}")
            return []

    def detect_slot_failures(self) -> List[Dict[str, Any]]:
        """Rileva intent che falliscono per specifiche combinazioni di slot"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        intent,
                        slot_piano,
                        slot_anno,
                        asl,
                        total_requests,
                        error_count,
                        short_response_count,
                        failure_rate_pct
                    FROM v_intent_slot_failures
                    WHERE failure_rate_pct > 20
                    ORDER BY failure_rate_pct DESC, error_count DESC
                    LIMIT 20
                """)).fetchall()

            return [{
                "intent": row[0],
                "slot_piano": row[1],
                "slot_anno": row[2],
                "asl": row[3],
                "total_requests": row[4],
                "error_count": row[5],
                "short_response_count": row[6],
                "failure_rate_pct": float(row[7]) if row[7] else 0,
                "bug_type": "slot_failure",
            } for row in rows]
        except Exception as e:
            logger.error(f"[BugDetector] Error detecting slot failures: {e}")
            return []

    def detect_asl_time_patterns(self) -> List[Dict[str, Any]]:
        """Rileva pattern problematici per ASL/fascia oraria"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        asl,
                        hour_of_day,
                        time_slot,
                        total_messages,
                        errors,
                        fallbacks,
                        problem_rate_pct,
                        avg_response_ms
                    FROM v_asl_time_correlation
                    WHERE problem_rate_pct > 15
                    ORDER BY problem_rate_pct DESC
                    LIMIT 20
                """)).fetchall()

            return [{
                "asl": row[0],
                "hour_of_day": int(row[1]) if row[1] else None,
                "time_slot": row[2],
                "total_messages": row[3],
                "errors": row[4],
                "fallbacks": row[5],
                "problem_rate_pct": float(row[6]) if row[6] else 0,
                "avg_response_ms": row[7],
                "pattern_type": "asl_time_correlation",
            } for row in rows]
        except Exception as e:
            logger.error(f"[BugDetector] Error detecting ASL time patterns: {e}")
            return []

    def detect_all(self) -> List[Dict[str, Any]]:
        """Esegue tutte le detection di bug"""
        bugs = []
        bugs.extend(self.detect_recurring_errors())
        bugs.extend(self.detect_slot_failures())
        bugs.extend(self.detect_asl_time_patterns())
        return bugs


# =============================================================================
# ROOT CAUSE ANALYZER
# =============================================================================

class RootCauseAnalyzer:
    """
    Analizza le cause root dei problemi:
    - Clustering domande fallback
    - Gap analysis copertura intent
    - Analisi semantica con LLM (opzionale)
    """

    def __init__(self, engine=None, llm_client=None):
        self.engine = engine or get_db_engine()
        self.llm = llm_client

    def analyze_fallback_clusters(self) -> List[Dict[str, Any]]:
        """Raggruppa i fallback per pattern ricorrenti"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        cluster_key,
                        cluster_size,
                        unique_sessions,
                        affected_asls,
                        example_questions,
                        first_seen,
                        last_seen
                    FROM v_fallback_clusters
                    ORDER BY cluster_size DESC
                    LIMIT 30
                """)).fetchall()

            return [{
                "cluster_key": row[0],
                "cluster_size": row[1],
                "unique_sessions": row[2],
                "affected_asls": row[3],
                "example_questions": row[4][:5] if row[4] else [],  # Max 5 esempi
                "first_seen": str(row[5]) if row[5] else None,
                "last_seen": str(row[6]) if row[6] else None,
            } for row in rows]
        except Exception as e:
            logger.error(f"[RootCauseAnalyzer] Error analyzing fallback clusters: {e}")
            return []

    def analyze_intent_gaps(self) -> List[Dict[str, Any]]:
        """Analizza i gap di copertura per categoria"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        category,
                        intent_count,
                        total_usage,
                        total_errors,
                        category_error_rate,
                        uncovered_questions,
                        gap_percentage
                    FROM v_intent_gap_analysis
                    ORDER BY gap_percentage DESC NULLS LAST
                """)).fetchall()

            return [{
                "category": row[0],
                "intent_count": row[1],
                "total_usage": row[2],
                "total_errors": row[3],
                "error_rate_pct": float(row[4]) if row[4] else 0,
                "uncovered_questions": row[5] or 0,
                "gap_percentage": float(row[6]) if row[6] else 0,
            } for row in rows]
        except Exception as e:
            logger.error(f"[RootCauseAnalyzer] Error analyzing intent gaps: {e}")
            return []

    def analyze_with_llm(self, fallback_samples: List[str], max_samples: int = 20) -> Optional[Dict[str, Any]]:
        """Usa LLM per analisi semantica dei fallback"""
        if not self.llm:
            try:
                from llm.client import LLMClient
                self.llm = LLMClient()
            except Exception as e:
                logger.warning(f"[RootCauseAnalyzer] Cannot initialize LLM: {e}")
                return None

        samples = fallback_samples[:max_samples]
        if not samples:
            return None

        prompt = f"""Analizza queste domande non riconosciute dal chatbot GIAS-AI (sistema veterinario):

{chr(10).join(f'- "{q}"' for q in samples)}

Identifica:
1. Pattern comuni (cosa cercano gli utenti?)
2. Possibili intent mancanti da implementare
3. Problemi di formulazione (domande ambigue?)
4. Suggerimenti per migliorare il riconoscimento

Rispondi SOLO con JSON valido:
{{
    "common_patterns": ["pattern1", "pattern2"],
    "suggested_intents": [
        {{"name": "intent_name", "description": "cosa fa", "examples": ["esempio1"]}}
    ],
    "ambiguous_questions": ["domanda1"],
    "recommendations": ["suggerimento1"]
}}"""

        try:
            response = self.llm.generate(prompt, temperature=0.2, json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.warning(f"[RootCauseAnalyzer] LLM analysis failed: {e}")
            return None

    def get_all_root_causes(self, use_llm: bool = False) -> List[Dict[str, Any]]:
        """Ottiene tutte le analisi root cause"""
        root_causes = []

        # Fallback clusters
        clusters = self.analyze_fallback_clusters()
        for cluster in clusters:
            root_causes.append({
                "type": "fallback_cluster",
                "severity": "high" if cluster["cluster_size"] >= 10 else "medium",
                **cluster
            })

        # Intent gaps
        gaps = self.analyze_intent_gaps()
        for gap in gaps:
            if gap["gap_percentage"] > 10:
                root_causes.append({
                    "type": "intent_gap",
                    "severity": "high" if gap["gap_percentage"] > 30 else "medium",
                    **gap
                })

        # LLM analysis (opzionale)
        if use_llm and clusters:
            # Estrai esempi dai cluster per analisi LLM
            all_examples = []
            for cluster in clusters[:10]:
                all_examples.extend(cluster.get("example_questions", [])[:2])
            llm_analysis = self.analyze_with_llm(all_examples)
            if llm_analysis:
                root_causes.append({
                    "type": "llm_analysis",
                    "severity": "info",
                    **llm_analysis
                })

        return root_causes


# =============================================================================
# TREND ANALYZER
# =============================================================================

class TrendAnalyzer:
    """
    Analizza trend e degradazioni:
    - Confronto settimana/settimana
    - Alert per degradazione performance
    """

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()

    def get_weekly_comparison(self) -> Dict[str, Any]:
        """Confronta metriche settimana corrente vs precedente"""
        if self.engine is None:
            return {}

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        period,
                        messages,
                        sessions,
                        fallbacks,
                        fallback_rate_pct,
                        errors,
                        error_rate_pct,
                        avg_response_ms,
                        p95_response_ms,
                        messages_delta_pct,
                        fallback_rate_delta,
                        error_rate_delta,
                        avg_response_ms_delta
                    FROM v_weekly_comparison
                    ORDER BY period = 'current' DESC
                """)).fetchall()

            result = {}
            for row in rows:
                period = row[0]
                result[period] = {
                    "messages": row[1],
                    "sessions": row[2],
                    "fallbacks": row[3],
                    "fallback_rate_pct": float(row[4]) if row[4] else 0,
                    "errors": row[5],
                    "error_rate_pct": float(row[6]) if row[6] else 0,
                    "avg_response_ms": row[7],
                    "p95_response_ms": row[8],
                }
                if period == "current":
                    result["deltas"] = {
                        "messages_pct": float(row[9]) if row[9] else 0,
                        "fallback_rate": float(row[10]) if row[10] else 0,
                        "error_rate": float(row[11]) if row[11] else 0,
                        "avg_response_ms": row[12],
                    }

            return result
        except Exception as e:
            logger.error(f"[TrendAnalyzer] Error getting weekly comparison: {e}")
            return {}

    def get_degradation_alerts(self) -> List[TrendAlert]:
        """Ottiene alert per degradazioni performance"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        intent,
                        recent_requests,
                        baseline_error_rate,
                        recent_error_rate,
                        error_rate_delta,
                        baseline_avg_ms,
                        recent_avg_ms,
                        latency_delta_ms,
                        alert_type,
                        severity
                    FROM v_degradation_alerts
                    WHERE alert_type IS NOT NULL
                    ORDER BY
                        CASE severity
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            ELSE 4
                        END,
                        recent_requests DESC
                    LIMIT 20
                """)).fetchall()

            alerts = []
            for row in rows:
                alert_type = row[8]
                if "error" in alert_type:
                    metric = "error_rate"
                    current = float(row[3]) if row[3] else 0
                    baseline = float(row[2]) if row[2] else 0
                    delta = float(row[4]) if row[4] else 0
                else:
                    metric = "latency_ms"
                    current = row[6] or 0
                    baseline = row[5] or 0
                    delta = row[7] or 0

                delta_pct = (delta / baseline * 100) if baseline else 0

                alerts.append(TrendAlert(
                    metric=metric,
                    current_value=current,
                    baseline_value=baseline,
                    delta_pct=delta_pct,
                    severity=row[9] or "medium",
                    intent=row[0],
                    recommendation=self._get_recommendation(alert_type, row[0])
                ))

            return alerts
        except Exception as e:
            logger.error(f"[TrendAnalyzer] Error getting degradation alerts: {e}")
            return []

    def _get_recommendation(self, alert_type: str, intent: str) -> str:
        """Genera raccomandazione basata sul tipo di alert"""
        recommendations = {
            "error_spike": f"Verifica urgente: error rate raddoppiato per '{intent}'. Controllare logs e tool correlati.",
            "latency_spike": f"Performance critica: latenza alta per '{intent}'. Verificare query DB o chiamate LLM.",
            "error_increase": f"Monitorare: incremento errori per '{intent}'. Potrebbe indicare bug emergente.",
            "latency_increase": f"Ottimizzare: latenza aumentata per '{intent}'. Considerare caching o query optimization.",
        }
        return recommendations.get(alert_type, f"Investigare comportamento anomalo per '{intent}'")

    def calculate_health_score(self) -> HealthScore:
        """Calcola score di salute complessivo"""
        weekly = self.get_weekly_comparison()
        alerts = self.get_degradation_alerts()

        current = weekly.get("current", {})
        deltas = weekly.get("deltas", {})

        # Componenti dello score (0-100)
        components = {}

        # 1. Error rate score (inverse - lower is better)
        error_rate = current.get("error_rate_pct", 0)
        components["error_rate"] = max(0, 100 - error_rate * 10)

        # 2. Fallback rate score
        fallback_rate = current.get("fallback_rate_pct", 0)
        components["fallback_rate"] = max(0, 100 - fallback_rate * 2)

        # 3. Latency score
        avg_latency = current.get("avg_response_ms", 0) or 0
        if avg_latency < 500:
            components["latency"] = 100
        elif avg_latency < 1000:
            components["latency"] = 80
        elif avg_latency < 2000:
            components["latency"] = 60
        elif avg_latency < 5000:
            components["latency"] = 40
        else:
            components["latency"] = 20

        # 4. Trend score (based on deltas)
        trend_score = 50  # Neutral
        if deltas:
            # Positive if error rate decreased
            error_delta = deltas.get("error_rate", 0)
            fallback_delta = deltas.get("fallback_rate", 0)
            trend_score = 50 - (error_delta * 5) - (fallback_delta * 2)
            trend_score = max(0, min(100, trend_score))
        components["trend"] = trend_score

        # 5. Alert severity score
        alert_penalty = 0
        for alert in alerts:
            if alert.severity == "critical":
                alert_penalty += 20
            elif alert.severity == "high":
                alert_penalty += 10
            elif alert.severity == "medium":
                alert_penalty += 5
        components["stability"] = max(0, 100 - alert_penalty)

        # Overall score (weighted average)
        weights = {
            "error_rate": 0.25,
            "fallback_rate": 0.25,
            "latency": 0.20,
            "trend": 0.15,
            "stability": 0.15,
        }
        overall = sum(components[k] * weights[k] for k in weights)

        return HealthScore(
            overall_score=round(overall, 1),
            components={k: round(v, 1) for k, v in components.items()},
            alerts=alerts,
            generated_at=datetime.now().isoformat()
        )


# =============================================================================
# USER INTENT MINER
# =============================================================================

class UserIntentMiner:
    """
    Scopre bisogni utente non soddisfatti analizzando:
    - Pattern nelle domande fallback
    - Tipi di richieste non coperte
    - Azioni richieste dagli utenti
    """

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()

    def mine_unmet_needs(self) -> List[Dict[str, Any]]:
        """Identifica bisogni utente non soddisfatti"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        request_type,
                        action_type,
                        frequency,
                        unique_sessions,
                        affected_asls,
                        sample_questions,
                        priority_score
                    FROM v_unmet_user_needs
                    ORDER BY priority_score DESC, frequency DESC
                    LIMIT 20
                """)).fetchall()

            return [{
                "request_type": row[0],
                "action_type": row[1],
                "frequency": row[2],
                "unique_sessions": row[3],
                "affected_asls": row[4],
                "sample_questions": row[5][:5] if row[5] else [],
                "priority_score": float(row[6]) if row[6] else 0,
            } for row in rows]
        except Exception as e:
            logger.error(f"[UserIntentMiner] Error mining unmet needs: {e}")
            return []


# =============================================================================
# IMPROVEMENT SUGGESTER
# =============================================================================

class ImprovementSuggester:
    """
    Genera suggerimenti actionable con priorita':
    - FIX_BUG: errori ricorrenti da correggere (priority 5)
    - ADD_PATTERN: pattern mancante nel router (priority 4)
    - ADD_INTENT: nuovo intent da implementare (priority 4-5)
    - OPTIMIZE_TOOL: tool con latenza alta (priority 3)
    - UPDATE_TRAINING: esempi training da aggiornare (priority 2)

    IMPORTANTE: L'output deve essere direttamente utilizzabile per
    progettare e realizzare bugfix e miglioramenti. Ogni suggerimento
    include codice pronto, query SQL, e istruzioni step-by-step.
    """

    def __init__(self):
        pass

    def _generate_regex_from_examples(self, examples: List[str], cluster_key: str) -> str:
        """Genera una regex suggerita basata sugli esempi"""
        # Estrae parole chiave comuni
        keywords = cluster_key.split()
        if not keywords:
            return ""

        # Pattern base: parole chiave in sequenza con spazi flessibili
        pattern_parts = [rf"(?i)\b{kw}\b" for kw in keywords if len(kw) > 2]
        if pattern_parts:
            return r".*".join(pattern_parts)
        return ""

    def _generate_investigation_sql(self, bug: Dict[str, Any]) -> str:
        """Genera query SQL per investigare un bug"""
        bug_type = bug.get("bug_type")

        if bug_type == "recurring_error":
            return f"""-- Query per investigare errore ricorrente
SELECT
    id, session_id, asl, intent, ask, error, "when"
FROM chat_log
WHERE error ILIKE '%{bug.get("error_signature", "")[:30]}%'
ORDER BY "when" DESC
LIMIT 20;"""

        elif bug_type == "slot_failure":
            intent = bug.get("intent", "")
            piano = bug.get("slot_piano", "")
            return f"""-- Query per investigare slot failure
SELECT
    id, session_id, asl, intent, ask, answer, slots::text, error
FROM chat_log
WHERE intent = '{intent}'
  AND (slots::text ILIKE '%{piano}%' OR slots IS NULL)
  AND (error IS NOT NULL OR LENGTH(answer) < 50)
ORDER BY "when" DESC
LIMIT 20;"""

        elif bug_type == "asl_time_correlation":
            asl = bug.get("asl", "")
            hour = bug.get("hour_of_day", 0)
            return f"""-- Query per investigare pattern ASL/orario
SELECT
    intent, COUNT(*) as cnt,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as errors,
    COUNT(*) FILTER (WHERE intent = 'fallback') as fallbacks
FROM chat_log
WHERE asl = '{asl}'
  AND EXTRACT(HOUR FROM "when"::timestamp) = {hour}
  AND "when"::timestamp >= NOW() - INTERVAL '14 days'
GROUP BY intent
ORDER BY cnt DESC;"""

        return ""

    def _suggest_intent_for_cluster(self, cluster_key: str, examples: List[str]) -> Dict[str, str]:
        """Suggerisce intent esistente o nuovo basato sul contenuto del cluster"""
        key_lower = cluster_key.lower()
        example_text = " ".join(examples).lower() if examples else ""

        # Mapping keyword -> intent esistente
        intent_mappings = {
            ("piano", "piani", "monitoraggio"): "ask_piano_description",
            ("controllo", "controlli", "ispezione"): "ask_controlli_stabilimento",
            ("stabilimento", "azienda", "attivita"): "ask_stabilimento_info",
            ("rischio", "priorita", "score"): "ask_risk_analysis",
            ("ritardo", "scadenza", "deadline"): "piani_in_ritardo",
            ("procedure", "documento", "come si fa"): "ask_procedure",
            ("osa", "operatore", "mai controllat"): "ask_osa_mai_controllati",
        }

        for keywords, intent in intent_mappings.items():
            if any(kw in key_lower or kw in example_text for kw in keywords):
                return {
                    "intent": intent,
                    "new_intent": f"ask_{cluster_key.replace(' ', '_').lower()}",
                    "match_reason": f"Keyword match: {keywords}"
                }

        # Default: suggerisci nuovo intent
        safe_name = "".join(c if c.isalnum() else "_" for c in cluster_key.lower())
        return {
            "intent": None,
            "new_intent": f"ask_{safe_name}",
            "match_reason": "No existing intent match - suggest new"
        }

    def _category_to_pattern(self, category: str) -> str:
        """Converte categoria in pattern regex per query SQL"""
        category_patterns = {
            "piani": "piano|piani|monitoraggio",
            "controlli": "controll|ispezion|verific",
            "stabilimenti": "stabiliment|aziend|attivita|osa",
            "rischio": "rischio|priorit|score|punteggio",
            "procedure": "procedur|document|come|manuale",
            "altro": ".*",  # Catch-all
        }
        return category_patterns.get(category, category)

    def generate_from_bugs(self, bugs: List[Dict[str, Any]]) -> List[Suggestion]:
        """Genera suggerimenti da bug rilevati"""
        suggestions = []

        for bug in bugs:
            bug_type = bug.get("bug_type")

            if bug_type == "recurring_error":
                sql_query = self._generate_investigation_sql(bug)
                intents = bug.get("related_intents", [])
                intent_str = intents[0] if intents else "unknown"

                suggestions.append(Suggestion(
                    type=SuggestionType.FIX_BUG,
                    priority=5,
                    title=f"Correggi errore ricorrente: {bug['error_signature'][:50]}...",
                    description=f"Errore ripetuto {bug['occurrence_count']} volte su {bug['affected_sessions']} sessioni",
                    action="Investigare e correggere la causa root dell'errore",
                    evidence={
                        "error_signature": bug["error_signature"],
                        "occurrence_count": bug["occurrence_count"],
                        "related_intents": bug.get("related_intents", []),
                        "asl_list": bug.get("asl_list", []),
                        "investigation_sql": sql_query,
                        "first_occurrence": bug.get("first_occurrence"),
                        "last_occurrence": bug.get("last_occurrence"),
                    },
                    estimated_impact="high",
                    implementation_hint=f"""STEP 1: Esegui query SQL per ottenere dettagli:
{sql_query}

STEP 2: Cerca nei log per stack trace:
  grep -r "{bug['error_signature'][:30]}" runtime/logs/

STEP 3: Identifica il file sorgente dell'errore:
  - Se intent = '{intent_str}': verificare orchestrator/tool_nodes.py
  - Se errore DB: verificare data_sources/postgresql_source.py
  - Se errore LLM: verificare llm/client.py

STEP 4: Implementa fix e aggiungi test case"""
                ))

            elif bug_type == "slot_failure":
                sql_query = self._generate_investigation_sql(bug)
                intent = bug.get("intent", "")

                suggestions.append(Suggestion(
                    type=SuggestionType.FIX_BUG,
                    priority=4,
                    title=f"Slot failure per intent '{intent}'",
                    description=f"Failure rate {bug['failure_rate_pct']}% per piano={bug.get('slot_piano')}, ASL={bug.get('asl')}",
                    action="Verificare gestione slot e query correlate",
                    evidence={
                        "intent": intent,
                        "slot_piano": bug.get("slot_piano"),
                        "slot_anno": bug.get("slot_anno"),
                        "failure_rate_pct": bug["failure_rate_pct"],
                        "total_requests": bug.get("total_requests"),
                        "investigation_sql": sql_query,
                    },
                    estimated_impact="medium",
                    implementation_hint=f"""STEP 1: Esegui query SQL per vedere i casi falliti:
{sql_query}

STEP 2: Verifica il tool handler per '{intent}':
  File: orchestrator/tool_nodes.py
  Cerca: def {intent.replace('ask_', '')}( o TOOL_REGISTRY['{intent}']

STEP 3: Verifica DataRetriever per slot '{bug.get("slot_piano")}':
  File: agents/data_retriever.py
  Verifica: gestione caso piano=None o piano non trovato

STEP 4: Aggiungi test case in tests/test_tools.py:
  def test_{intent}_with_invalid_slot(self):
      # Test con piano='{bug.get("slot_piano")}'"""
                ))

            elif bug_type == "asl_time_correlation":
                if bug.get("problem_rate_pct", 0) > 30:
                    sql_query = self._generate_investigation_sql(bug)

                    suggestions.append(Suggestion(
                        type=SuggestionType.INVESTIGATE,
                        priority=3,
                        title=f"Pattern problematico: {bug['asl']} ore {bug['hour_of_day']}",
                        description=f"Problem rate {bug['problem_rate_pct']}% nella fascia {bug['time_slot']}",
                        action="Investigare correlazione temporale/infrastrutturale",
                        evidence={
                            "asl": bug["asl"],
                            "hour_of_day": bug["hour_of_day"],
                            "time_slot": bug["time_slot"],
                            "problem_rate_pct": bug["problem_rate_pct"],
                            "total_messages": bug.get("total_messages"),
                            "investigation_sql": sql_query,
                        },
                        estimated_impact="medium",
                        implementation_hint=f"""STEP 1: Analizza distribuzione errori:
{sql_query}

STEP 2: Verifica logs di sistema per quell'orario:
  grep "$(date -d 'yesterday' +%Y-%m-%d) {bug['hour_of_day']:02d}:" runtime/logs/api.log

STEP 3: Controlla se e' problema di:
  - Carico sistema (troppe richieste contemporanee)
  - Connettivita' ASL {bug['asl']}
  - Timeout LLM/DB in orario di punta

STEP 4: Se pattern confermato, considera:
  - Rate limiting per ASL
  - Caching aggressivo per quell'orario
  - Alert monitoring per soglia {bug['problem_rate_pct']}%"""
                    ))

        return suggestions

    def generate_from_root_causes(self, root_causes: List[Dict[str, Any]]) -> List[Suggestion]:
        """Genera suggerimenti da analisi root cause"""
        suggestions = []

        for cause in root_causes:
            cause_type = cause.get("type")

            if cause_type == "fallback_cluster":
                cluster_size = cause.get("cluster_size", 0)
                cluster_key = cause.get("cluster_key", "")
                examples = cause.get("example_questions", [])
                priority = 5 if cluster_size >= 15 else (4 if cluster_size >= 8 else 3)

                # Genera regex suggerita
                suggested_regex = self._generate_regex_from_examples(examples, cluster_key)

                # Determina intent target basato sul contenuto
                intent_suggestion = self._suggest_intent_for_cluster(cluster_key, examples)

                suggestions.append(Suggestion(
                    type=SuggestionType.ADD_PATTERN,
                    priority=priority,
                    title=f"Aggiungi pattern per: '{cluster_key}'",
                    description=f"Domanda ripetuta {cluster_size} volte senza riconoscimento",
                    action="Aggiungere pattern nel Router o creare nuovo intent",
                    evidence={
                        "cluster_key": cluster_key,
                        "cluster_size": cluster_size,
                        "examples": examples[:5],
                        "suggested_regex": suggested_regex,
                        "suggested_intent": intent_suggestion.get("intent"),
                    },
                    estimated_impact="high" if cluster_size >= 10 else "medium",
                    implementation_hint=f"""OPZIONE A - Aggiungi pattern a intent esistente:
----------------------------------------
File: orchestrator/router.py

# Aggiungi a HEURISTICS (riga ~50):
HEURISTICS = {{
    ...
    "{intent_suggestion.get('intent', 'INTENT_DA_SCEGLIERE')}": [
        r"{suggested_regex}",  # Pattern per: {cluster_key}
    ],
    ...
}}

OPZIONE B - Crea nuovo intent:
----------------------------------------
# 1. Aggiungi a VALID_INTENTS (orchestrator/router.py):
VALID_INTENTS = {{
    ...
    "{intent_suggestion.get('new_intent', 'ask_' + cluster_key.replace(' ', '_'))}",
}}

# 2. Aggiungi handler in orchestrator/tool_nodes.py:
def {intent_suggestion.get('new_intent', 'nuovo_intent').replace('ask_', '')}(state: ConversationState) -> ConversationState:
    \"\"\"Handler per: {examples[0] if examples else cluster_key}\"\"\"
    # TODO: implementare logica
    pass

# 3. Registra in TOOL_REGISTRY:
TOOL_REGISTRY["{intent_suggestion.get('new_intent', 'nuovo_intent')}"] = {intent_suggestion.get('new_intent', 'nuovo_intent').replace('ask_', '')}

ESEMPI DA GESTIRE:
{chr(10).join(f'  - "{ex}"' for ex in examples[:3])}"""
                ))

            elif cause_type == "intent_gap":
                gap_pct = cause.get("gap_percentage", 0)
                if gap_pct > 20:
                    category = cause.get("category", "")

                    suggestions.append(Suggestion(
                        type=SuggestionType.ADD_INTENT,
                        priority=4,
                        title=f"Gap copertura categoria '{category}'",
                        description=f"{cause['uncovered_questions']} domande non coperte ({gap_pct}% del totale)",
                        action=f"Espandere copertura intent per categoria {category}",
                        evidence={
                            "category": category,
                            "current_intents": cause.get("intent_count", 0),
                            "uncovered_questions": cause["uncovered_questions"],
                            "gap_percentage": gap_pct,
                            "analysis_sql": f"""-- Query per vedere domande non coperte in '{category}'
SELECT ask, COUNT(*) as cnt
FROM chat_log
WHERE intent = 'fallback'
  AND "when"::timestamp >= NOW() - INTERVAL '30 days'
  AND LOWER(ask) ~ '{self._category_to_pattern(category)}'
GROUP BY ask
ORDER BY cnt DESC
LIMIT 20;""",
                        },
                        estimated_impact="high" if gap_pct > 40 else "medium",
                        implementation_hint=f"""STEP 1: Analizza le domande non coperte:
  Esegui la query in evidence.analysis_sql

STEP 2: Identifica pattern comuni e raggruppa per intent potenziali

STEP 3: Per ogni nuovo intent, crea:
  a) Entry in VALID_INTENTS (router.py)
  b) Pattern in HEURISTICS (router.py)
  c) Handler in tool_nodes.py
  d) Test in tests/test_tools.py

STEP 4: Aggiorna documentazione:
  - GiAs-llm/docs/CLAUDE.md (lista intent)
  - Tabella 'intents' nel database

CATEGORIA: {category}
INTENT ESISTENTI: {cause.get('intent_count', 0)}
GAP: {gap_pct}%"""
                    ))

            elif cause_type == "llm_analysis":
                # Suggerimenti da analisi LLM
                suggested_intents = cause.get("suggested_intents", [])
                for intent_suggestion in suggested_intents[:3]:
                    suggestions.append(Suggestion(
                        type=SuggestionType.ADD_INTENT,
                        priority=4,
                        title=f"Nuovo intent suggerito: {intent_suggestion.get('name', 'unknown')}",
                        description=intent_suggestion.get("description", ""),
                        action="Implementare nuovo intent con esempi forniti",
                        evidence={
                            "suggested_name": intent_suggestion.get("name"),
                            "examples": intent_suggestion.get("examples", []),
                        },
                        estimated_impact="medium",
                        implementation_hint="Aggiungere a VALID_INTENTS e implementare tool/handler"
                    ))

        return suggestions

    def generate_from_alerts(self, alerts: List[TrendAlert]) -> List[Suggestion]:
        """Genera suggerimenti da alert degradazione"""
        suggestions = []

        for alert in alerts:
            if alert.severity in ("critical", "high"):
                intent = alert.intent or "unknown"

                if alert.metric == "latency_ms":
                    suggestions.append(Suggestion(
                        type=SuggestionType.OPTIMIZE_TOOL,
                        priority=4 if alert.severity == "critical" else 3,
                        title=f"Ottimizza latenza per '{intent}'",
                        description=f"Latenza aumentata da {alert.baseline_value:.0f}ms a {alert.current_value:.0f}ms ({alert.delta_pct:.1f}%)",
                        action=alert.recommendation or "Ottimizzare query e cache",
                        evidence={
                            "intent": intent,
                            "current_latency_ms": alert.current_value,
                            "baseline_latency_ms": alert.baseline_value,
                            "delta_pct": alert.delta_pct,
                            "profiling_sql": f"""-- Query per profilare latenza intent '{intent}'
SELECT
    DATE("when"::timestamp) as day,
    COUNT(*) as requests,
    ROUND(AVG(response_time_ms)) as avg_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)) as p95_ms,
    MAX(response_time_ms) as max_ms
FROM chat_log
WHERE intent = '{intent}'
  AND "when"::timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE("when"::timestamp)
ORDER BY day DESC;""",
                        },
                        estimated_impact="medium",
                        implementation_hint=f"""STEP 1: Profila la latenza per identificare il collo di bottiglia:
  Esegui la query in evidence.profiling_sql

STEP 2: Identifica componente lento:
  a) DataRetriever - agents/data_retriever.py
     Cerca il metodo usato da '{intent}'
  b) Query SQL - verifica se ci sono query lente
  c) Chiamate LLM - llm/client.py

STEP 3: Ottimizzazioni possibili:
  a) Aggiungere caching in agents/data_retriever.py:
     @lru_cache(maxsize=100)
     def get_{intent.replace('ask_', '')}(...):
  b) Ottimizzare query SQL con indici appropriati
  c) Ridurre dimensione prompt LLM

STEP 4: Benchmark dopo fix:
  python -c "from agents.data_retriever import *; import time; t=time.time(); {intent.replace('ask_', '')}(...); print(time.time()-t)"

SOGLIA ATTUALE: {alert.current_value:.0f}ms (baseline: {alert.baseline_value:.0f}ms)"""
                    ))
                else:  # error_rate
                    suggestions.append(Suggestion(
                        type=SuggestionType.FIX_BUG,
                        priority=5 if alert.severity == "critical" else 4,
                        title=f"Error rate spike per '{intent}'",
                        description=f"Error rate aumentato da {alert.baseline_value:.1f}% a {alert.current_value:.1f}%",
                        action=alert.recommendation or "Investigare causa errori",
                        evidence={
                            "intent": intent,
                            "current_error_rate": alert.current_value,
                            "baseline_error_rate": alert.baseline_value,
                            "error_analysis_sql": f"""-- Query per analizzare errori intent '{intent}'
SELECT
    error,
    COUNT(*) as cnt,
    ARRAY_AGG(DISTINCT asl) as affected_asls,
    MIN("when"::timestamp) as first_seen,
    MAX("when"::timestamp) as last_seen
FROM chat_log
WHERE intent = '{intent}'
  AND error IS NOT NULL
  AND "when"::timestamp >= NOW() - INTERVAL '3 days'
GROUP BY error
ORDER BY cnt DESC
LIMIT 10;""",
                        },
                        estimated_impact="high",
                        implementation_hint=f"""STEP 1: Analizza tipi di errore:
  Esegui la query in evidence.error_analysis_sql

STEP 2: Cerca stack trace nei log:
  grep -A 10 "{intent}" runtime/logs/api.log | grep -i error

STEP 3: Verifica handler dell'intent:
  File: orchestrator/tool_nodes.py
  Cerca: TOOL_REGISTRY['{intent}'] o def {intent.replace('ask_', '')}

STEP 4: Verifica dipendenze:
  - Database connectivity: data_sources/postgresql_source.py
  - LLM availability: llm/client.py
  - Data retriever: agents/data_retriever.py

STEP 5: Aggiungi test di regressione:
  File: tests/test_tools.py
  def test_{intent}_error_handling(self):
      # Testa scenari di errore

ERROR RATE: {alert.current_value:.1f}% (baseline: {alert.baseline_value:.1f}%)"""
                    ))

        return suggestions

    def generate_from_unmet_needs(self, unmet_needs: List[Dict[str, Any]]) -> List[Suggestion]:
        """Genera suggerimenti da bisogni utente non soddisfatti"""
        suggestions = []

        for need in unmet_needs:
            if need.get("priority_score", 0) >= 2:
                action_type = need.get("action_type", "unknown")
                request_type = need.get("request_type", "other")
                samples = need.get("sample_questions", [])

                # Determina tipo suggerimento
                if action_type in ("view_data", "search"):
                    sug_type = SuggestionType.ADD_INTENT
                elif action_type == "help":
                    sug_type = SuggestionType.UPDATE_TRAINING
                else:
                    sug_type = SuggestionType.INVESTIGATE

                priority = 4 if need["frequency"] >= 10 else 3

                # Genera nome intent suggerito
                suggested_intent = f"ask_{action_type}_{request_type}".replace(" ", "_")

                suggestions.append(Suggestion(
                    type=sug_type,
                    priority=priority,
                    title=f"Bisogno utente: {request_type}/{action_type}",
                    description=f"{need['frequency']} richieste ({need['unique_sessions']} sessioni) per azione '{action_type}'",
                    action="Analizzare domande e valutare implementazione",
                    evidence={
                        "request_type": request_type,
                        "action_type": action_type,
                        "frequency": need["frequency"],
                        "unique_sessions": need["unique_sessions"],
                        "sample_questions": samples[:5],
                        "suggested_intent": suggested_intent,
                    },
                    estimated_impact="high" if need["frequency"] >= 15 else "medium",
                    implementation_hint=f"""ANALISI BISOGNO UTENTE: {request_type}/{action_type}
{'='*50}

DOMANDE ESEMPIO:
{chr(10).join(f'  - "{q}"' for q in samples[:5])}

OPZIONE A - Estendi intent esistente:
----------------------------------------
Se il bisogno e' coperto parzialmente da un intent esistente,
aggiungi pattern per coprire questi casi.

OPZIONE B - Crea nuovo intent '{suggested_intent}':
----------------------------------------
# 1. Aggiungi a VALID_INTENTS (orchestrator/router.py):
"{suggested_intent}",

# 2. Aggiungi pattern in HEURISTICS:
"{suggested_intent}": [
    r"(?i).*({action_type}).*",
],

# 3. Crea handler in orchestrator/tool_nodes.py:
def {suggested_intent.replace('ask_', '')}(state: ConversationState) -> ConversationState:
    \"\"\"
    Gestisce richieste di tipo: {request_type}/{action_type}
    Esempi: {samples[0] if samples else 'N/A'}
    \"\"\"
    # TODO: implementare logica
    metadata = state.get("metadata", {{}})
    asl = metadata.get("asl", "")

    # Recupera dati
    # result = data_retriever.get_...()

    state["response"] = "Risposta da implementare"
    return state

# 4. Registra in TOOL_REGISTRY:
TOOL_REGISTRY["{suggested_intent}"] = {suggested_intent.replace('ask_', '')}

# 5. Aggiungi test:
def test_{suggested_intent}(self):
    state = {{"message": "{samples[0] if samples else 'test'}", "metadata": {{"asl": "TEST"}}}}
    result = {suggested_intent.replace('ask_', '')}(state)
    assert result.get("response")

FREQUENZA: {need['frequency']} richieste in {need['unique_sessions']} sessioni"""
                ))

        return suggestions


# =============================================================================
# INTELLIGENT MONITOR (Orchestrator)
# =============================================================================

class IntelligentMonitor:
    """
    Orchestratore principale che coordina:
    - BugDetector
    - RootCauseAnalyzer
    - TrendAnalyzer
    - UserIntentMiner
    - ImprovementSuggester
    """

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()
        self.bug_detector = BugDetector(self.engine)
        self.root_cause_analyzer = RootCauseAnalyzer(self.engine)
        self.trend_analyzer = TrendAnalyzer(self.engine)
        self.intent_miner = UserIntentMiner(self.engine)
        self.suggester = ImprovementSuggester()

    def run_analysis(
        self,
        days: int = 7,
        use_llm: bool = False,
        min_priority: int = 1
    ) -> IntelligentReport:
        """Esegue analisi completa e genera report"""

        logger.info(f"[IntelligentMonitor] Starting analysis: days={days}, use_llm={use_llm}")

        # 1. Bug detection
        bugs = self.bug_detector.detect_all()
        logger.info(f"[IntelligentMonitor] Bugs detected: {len(bugs)}")

        # 2. Root cause analysis
        root_causes = self.root_cause_analyzer.get_all_root_causes(use_llm=use_llm)
        logger.info(f"[IntelligentMonitor] Root causes identified: {len(root_causes)}")

        # 3. Trend analysis
        weekly_comparison = self.trend_analyzer.get_weekly_comparison()
        health_score = self.trend_analyzer.calculate_health_score()
        logger.info(f"[IntelligentMonitor] Health score: {health_score.overall_score}")

        # 4. User intent mining
        unmet_needs = self.intent_miner.mine_unmet_needs()
        logger.info(f"[IntelligentMonitor] Unmet needs found: {len(unmet_needs)}")

        # 5. Generate suggestions
        all_suggestions = []
        all_suggestions.extend(self.suggester.generate_from_bugs(bugs))
        all_suggestions.extend(self.suggester.generate_from_root_causes(root_causes))
        all_suggestions.extend(self.suggester.generate_from_alerts(health_score.alerts))
        all_suggestions.extend(self.suggester.generate_from_unmet_needs(unmet_needs))

        # Filter by priority
        filtered_suggestions = [s for s in all_suggestions if s.priority >= min_priority]

        # Sort by priority (descending)
        filtered_suggestions.sort(key=lambda s: (-s.priority, s.title))

        logger.info(f"[IntelligentMonitor] Suggestions generated: {len(filtered_suggestions)}")

        return IntelligentReport(
            period_days=days,
            generated_at=datetime.now().isoformat(),
            health_score=health_score,
            suggestions=filtered_suggestions,
            bugs_detected=bugs,
            trend_analysis={
                "weekly_comparison": weekly_comparison,
                "alerts_count": len(health_score.alerts),
            },
            unmet_needs=unmet_needs,
            root_causes=root_causes,
        )

    def get_suggestions(self, min_priority: int = 1, limit: int = 20) -> List[Suggestion]:
        """Ottiene solo i suggerimenti (senza report completo)"""
        report = self.run_analysis(days=14, use_llm=False, min_priority=min_priority)
        return report.suggestions[:limit]

    def get_health(self) -> HealthScore:
        """Ottiene solo lo health score"""
        return self.trend_analyzer.calculate_health_score()


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class IntelligentReportGenerator:
    """Genera report in vari formati"""

    def generate_json(self, report: IntelligentReport) -> str:
        """Genera report JSON"""
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str)

    def generate_summary(self, report: IntelligentReport) -> str:
        """Genera summary testuale"""
        lines = [
            "=" * 70,
            "INTELLIGENT MONITOR REPORT - GIAS-AI",
            "=" * 70,
            f"Periodo: ultimi {report.period_days} giorni",
            f"Generato: {report.generated_at}",
            "",
            "HEALTH SCORE",
            "-" * 40,
            f"Score complessivo: {report.health_score.overall_score}/100",
            "",
            "Componenti:",
        ]

        for comp, score in report.health_score.components.items():
            status = "OK" if score >= 70 else ("WARN" if score >= 40 else "CRIT")
            lines.append(f"  - {comp}: {score}/100 [{status}]")

        # Alerts
        if report.health_score.alerts:
            lines.append("")
            lines.append(f"ALERT ATTIVI: {len(report.health_score.alerts)}")
            lines.append("-" * 40)
            for alert in report.health_score.alerts[:5]:
                lines.append(f"  [{alert.severity.upper()}] {alert.intent}: {alert.metric} = {alert.current_value:.1f} (baseline: {alert.baseline_value:.1f})")

        # Suggestions
        lines.append("")
        lines.append(f"SUGGERIMENTI: {len(report.suggestions)}")
        lines.append("-" * 40)

        by_priority = {}
        for s in report.suggestions:
            by_priority.setdefault(s.priority, []).append(s)

        for priority in sorted(by_priority.keys(), reverse=True):
            prio_name = {5: "CRITICO", 4: "ALTO", 3: "MEDIO", 2: "BASSO"}.get(priority, "INFO")
            lines.append(f"\n[{prio_name}] ({len(by_priority[priority])} suggerimenti)")
            for s in by_priority[priority][:3]:  # Max 3 per priorita'
                lines.append(f"  * {s.title}")
                lines.append(f"    Azione: {s.action}")

        # Bugs detected
        if report.bugs_detected:
            lines.append("")
            lines.append(f"BUG RILEVATI: {len(report.bugs_detected)}")
            lines.append("-" * 40)
            for bug in report.bugs_detected[:5]:
                bug_type = bug.get("bug_type", "unknown")
                if bug_type == "recurring_error":
                    lines.append(f"  - Errore ricorrente ({bug['occurrence_count']}x): {bug['error_signature'][:60]}...")
                elif bug_type == "slot_failure":
                    lines.append(f"  - Slot failure: {bug['intent']} (piano={bug.get('slot_piano')}, rate={bug['failure_rate_pct']}%)")

        # Unmet needs
        if report.unmet_needs:
            lines.append("")
            lines.append(f"BISOGNI UTENTE NON SODDISFATTI: {len(report.unmet_needs)}")
            lines.append("-" * 40)
            for need in report.unmet_needs[:5]:
                lines.append(f"  - {need['request_type']}/{need['action_type']}: {need['frequency']} richieste")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Monitor per GIAS-AI - Analisi avanzata conversazioni",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python -m tools.intelligent_monitor --days 7 --format summary
  python -m tools.intelligent_monitor --days 14 --use-llm --output report.json
  python -m tools.intelligent_monitor --suggestions --min-priority 3
  python -m tools.intelligent_monitor --health
"""
    )

    parser.add_argument("--days", type=int, default=7, help="Numero di giorni da analizzare (default: 7)")
    parser.add_argument("--output", "-o", type=str, help="File di output (default: stdout)")
    parser.add_argument("--format", "-f", choices=["json", "summary"], default="summary",
                        help="Formato output (default: summary)")
    parser.add_argument("--min-priority", type=int, default=1, choices=[1, 2, 3, 4, 5],
                        help="Priorita' minima suggerimenti (default: 1)")
    parser.add_argument("--use-llm", action="store_true",
                        help="Abilita analisi semantica con LLM (piu' lento)")
    parser.add_argument("--suggestions", action="store_true",
                        help="Mostra solo suggerimenti")
    parser.add_argument("--health", action="store_true",
                        help="Mostra solo health score")

    args = parser.parse_args()

    monitor = IntelligentMonitor()

    if args.health:
        # Solo health score
        health = monitor.get_health()
        if args.format == "json":
            output = json.dumps(health.to_dict(), indent=2, ensure_ascii=False)
        else:
            output = f"Health Score: {health.overall_score}/100\n"
            for comp, score in health.components.items():
                output += f"  - {comp}: {score}/100\n"
            if health.alerts:
                output += f"\nAlerts: {len(health.alerts)}\n"
                for alert in health.alerts[:5]:
                    output += f"  [{alert.severity}] {alert.intent}: {alert.metric}\n"
    elif args.suggestions:
        # Solo suggerimenti
        suggestions = monitor.get_suggestions(min_priority=args.min_priority)
        if args.format == "json":
            output = json.dumps([s.to_dict() for s in suggestions], indent=2, ensure_ascii=False)
        else:
            output = f"Suggerimenti ({len(suggestions)}):\n"
            for s in suggestions:
                output += f"\n[P{s.priority}] {s.type.value.upper()}: {s.title}\n"
                output += f"  Azione: {s.action}\n"
                if s.implementation_hint:
                    output += f"  Hint: {s.implementation_hint}\n"
    else:
        # Report completo
        report = monitor.run_analysis(
            days=args.days,
            use_llm=args.use_llm,
            min_priority=args.min_priority
        )

        generator = IntelligentReportGenerator()
        if args.format == "json":
            output = generator.generate_json(report)
        else:
            output = generator.generate_summary(report)

    # Scrivi output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report salvato in: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
