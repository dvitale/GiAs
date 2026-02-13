"""
Monitoraggio qualita' conversazioni GIAS-AI

Analizza la tabella chat_log per rilevare:
1. Fallback espliciti
2. Cattive interpretazioni dell'intent
3. Problemi di flusso conversazionale

Usage:
  python -m tools.conversation_monitor --days 7 --output report.json
  python -m tools.conversation_monitor --days 7 --use-llm --output report.json
  python -m tools.conversation_monitor --days 1 --format summary
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Problem:
    """Rappresenta un problema rilevato nella conversazione"""
    type: str
    severity: Severity
    session_id: str
    asl: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class SessionAnalysis:
    """Analisi di una singola sessione"""
    session_id: str
    asl: Optional[str]
    msg_count: int
    fallback_count: int
    intent_sequence: List[str]
    duration_seconds: float
    has_errors: bool
    problems: List[Problem] = field(default_factory=list)


@dataclass
class MonitorReport:
    """Report completo del monitoraggio"""
    period_days: int
    generated_at: str
    total_sessions: int
    total_messages: int
    fallback_rate: float
    avg_session_length: float
    problems: List[Problem]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_days": self.period_days,
            "generated_at": self.generated_at,
            "total_sessions": self.total_sessions,
            "total_messages": self.total_messages,
            "fallback_rate": self.fallback_rate,
            "avg_session_length": self.avg_session_length,
            "problems": {
                "critical": [p.to_dict() for p in self.problems if p.severity == Severity.CRITICAL],
                "high": [p.to_dict() for p in self.problems if p.severity == Severity.HIGH],
                "medium": [p.to_dict() for p in self.problems if p.severity == Severity.MEDIUM],
                "low": [p.to_dict() for p in self.problems if p.severity == Severity.LOW],
            },
            "problem_counts": {
                "critical": len([p for p in self.problems if p.severity == Severity.CRITICAL]),
                "high": len([p for p in self.problems if p.severity == Severity.HIGH]),
                "medium": len([p for p in self.problems if p.severity == Severity.MEDIUM]),
                "low": len([p for p in self.problems if p.severity == Severity.LOW]),
            },
            "summary": self.summary,
        }


def get_db_engine():
    """Ottiene l'engine SQLAlchemy dal PostgreSQLDataSource."""
    try:
        from data_sources.postgresql_source import PostgreSQLDataSource
        # Initialize the data source if not already done
        if PostgreSQLDataSource._engine is None:
            from configs.config_loader import get_config
            config = get_config()
            db_config = config.get("database", {})
            PostgreSQLDataSource(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 5432),
                database=db_config.get("database", "gias_db"),
                user=db_config.get("user", "gias_user"),
                password=db_config.get("password", ""),
            )
        return PostgreSQLDataSource._engine
    except Exception as e:
        logger.error(f"[Monitor] Errore connessione DB: {e}")
        return None


class ConversationAnalyzer:
    """Analizza sessioni da chat_log"""

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()

    def get_sessions(self, days: int, asl_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera le sessioni dal chat_log raggruppate per session_id"""
        if self.engine is None:
            logger.error("[Monitor] No DB engine available")
            return []

        from sqlalchemy import text

        query = """
        SELECT
            session_id,
            asl,
            COUNT(*) as msg_count,
            COUNT(*) FILTER (WHERE intent = 'fallback') as fallback_count,
            COUNT(DISTINCT intent) as intent_variety,
            MIN("when"::timestamp) as session_start,
            MAX("when"::timestamp) as session_end,
            EXTRACT(EPOCH FROM (MAX("when"::timestamp) - MIN("when"::timestamp))) as duration_seconds,
            ARRAY_AGG(intent ORDER BY "when"::timestamp) as intent_sequence,
            ARRAY_AGG(ask ORDER BY "when"::timestamp) as questions,
            ARRAY_AGG(answer ORDER BY "when"::timestamp) as answers,
            ARRAY_AGG(slots::text ORDER BY "when"::timestamp) as slots_list,
            ARRAY_AGG(two_phase_resp ORDER BY "when"::timestamp) as two_phase_list,
            ARRAY_AGG(response_time_ms ORDER BY "when"::timestamp) as response_times,
            BOOL_OR(error IS NOT NULL) as has_errors
        FROM chat_log
        WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
        """

        params = {"days": days}
        if asl_filter:
            query += " AND asl = :asl"
            params["asl"] = asl_filter

        query += """
        GROUP BY session_id, asl
        ORDER BY MIN("when"::timestamp) DESC
        """

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(query), params).fetchall()

            sessions = []
            for row in rows:
                sessions.append({
                    "session_id": row[0] or "unknown",
                    "asl": row[1],
                    "msg_count": row[2],
                    "fallback_count": row[3],
                    "intent_variety": row[4],
                    "session_start": row[5],
                    "session_end": row[6],
                    "duration_seconds": float(row[7]) if row[7] else 0,
                    "intent_sequence": row[8] or [],
                    "questions": row[9] or [],
                    "answers": row[10] or [],
                    "slots_list": row[11] or [],
                    "two_phase_list": row[12] or [],
                    "response_times": row[13] or [],
                    "has_errors": row[14],
                })
            return sessions
        except Exception as e:
            logger.error(f"[Monitor] Errore query sessioni: {e}")
            return []

    def get_raw_messages(self, days: int, asl_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera i singoli messaggi dal chat_log"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        query = """
        SELECT
            id, session_id, asl, "when", ask, intent, answer,
            slots::text, two_phase_resp, response_time_ms, error
        FROM chat_log
        WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
        """

        params = {"days": days}
        if asl_filter:
            query += " AND asl = :asl"
            params["asl"] = asl_filter

        query += " ORDER BY session_id, \"when\"::timestamp"

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(query), params).fetchall()

            return [{
                "id": row[0],
                "session_id": row[1] or "unknown",
                "asl": row[2],
                "timestamp": str(row[3]) if row[3] else None,
                "ask": row[4],
                "intent": row[5],
                "answer": row[6],
                "slots": row[7],
                "two_phase_resp": row[8],
                "response_time_ms": row[9],
                "error": row[10],
            } for row in rows]
        except Exception as e:
            logger.error(f"[Monitor] Errore query messaggi: {e}")
            return []

    def analyze_session(self, session: Dict[str, Any]) -> List[Problem]:
        """Analizza una singola sessione e rileva problemi"""
        problems = []

        session_id = session["session_id"]
        asl = session.get("asl")
        intent_seq = session.get("intent_sequence", [])
        questions = session.get("questions", [])

        # 1. Fallback loop (3+ fallback consecutivi)
        problems.extend(self._detect_fallback_loops(session_id, asl, intent_seq))

        # 2. Intent ping-pong
        problems.extend(self._detect_intent_pingpong(session_id, asl, intent_seq))

        # 3. Domande ripetute
        problems.extend(self._detect_repeated_questions(session_id, asl, questions, intent_seq))

        # 4. Sessione lunga anomala
        if session.get("msg_count", 0) > 10:
            problems.append(Problem(
                type="long_session",
                severity=Severity.MEDIUM,
                session_id=session_id,
                asl=asl,
                description=f"Sessione con {session['msg_count']} messaggi senza risoluzione",
                details={"msg_count": session["msg_count"], "duration_seconds": session.get("duration_seconds", 0)}
            ))

        # 5. Fallback dopo intent valido
        problems.extend(self._detect_post_intent_fallback(session_id, asl, intent_seq))

        return problems

    def _detect_fallback_loops(self, session_id: str, asl: Optional[str], intent_seq: List[str]) -> List[Problem]:
        """Rileva 3+ fallback consecutivi"""
        problems = []
        consecutive = 0
        max_consecutive = 0

        for intent in intent_seq:
            if intent == "fallback":
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0

        if max_consecutive >= 3:
            problems.append(Problem(
                type="fallback_loop",
                severity=Severity.CRITICAL,
                session_id=session_id,
                asl=asl,
                description=f"Loop di {max_consecutive} fallback consecutivi",
                details={"consecutive_fallbacks": max_consecutive, "intent_sequence": intent_seq}
            ))

        return problems

    def _detect_intent_pingpong(self, session_id: str, asl: Optional[str], intent_seq: List[str]) -> List[Problem]:
        """Rileva intent che cambiano avanti/indietro"""
        problems = []

        if len(intent_seq) < 4:
            return problems

        # Pattern: A -> B -> A (ping-pong)
        for i in range(len(intent_seq) - 2):
            if intent_seq[i] == intent_seq[i + 2] and intent_seq[i] != intent_seq[i + 1]:
                if intent_seq[i] not in ("fallback", "greet", "goodbye"):
                    problems.append(Problem(
                        type="intent_pingpong",
                        severity=Severity.MEDIUM,
                        session_id=session_id,
                        asl=asl,
                        description=f"Intent oscillante: {intent_seq[i]} -> {intent_seq[i+1]} -> {intent_seq[i]}",
                        details={"pattern": intent_seq[i:i+3], "position": i}
                    ))
                    break  # Solo uno per sessione

        return problems

    def _detect_repeated_questions(
        self, session_id: str, asl: Optional[str], questions: List[str], intent_seq: List[str]
    ) -> List[Problem]:
        """Rileva domande ripetute nella stessa sessione"""
        problems = []

        if not questions:
            return problems

        # Normalizza le domande
        normalized = [q.lower().strip() if q else "" for q in questions]

        seen = {}
        for i, q in enumerate(normalized):
            if not q or len(q) < 5:
                continue
            if q in seen:
                # Domanda ripetuta
                first_idx = seen[q]
                problems.append(Problem(
                    type="repeated_question",
                    severity=Severity.HIGH,
                    session_id=session_id,
                    asl=asl,
                    description=f"Domanda ripetuta: '{questions[i][:50]}...'",
                    details={
                        "question": questions[i],
                        "first_intent": intent_seq[first_idx] if first_idx < len(intent_seq) else None,
                        "second_intent": intent_seq[i] if i < len(intent_seq) else None,
                        "positions": [first_idx, i]
                    }
                ))
            else:
                seen[q] = i

        return problems

    def _detect_post_intent_fallback(self, session_id: str, asl: Optional[str], intent_seq: List[str]) -> List[Problem]:
        """Rileva fallback subito dopo un intent valido (utente non soddisfatto)"""
        problems = []

        for i in range(len(intent_seq) - 1):
            current = intent_seq[i]
            next_intent = intent_seq[i + 1]

            # Intent valido seguito da fallback
            if current not in ("fallback", "greet", "goodbye", "ask_help") and next_intent == "fallback":
                problems.append(Problem(
                    type="post_intent_fallback",
                    severity=Severity.HIGH,
                    session_id=session_id,
                    asl=asl,
                    description=f"Fallback subito dopo '{current}' - possibile risposta insoddisfacente",
                    details={"previous_intent": current, "position": i}
                ))

        return problems


class QualityDetector:
    """Rileva problemi specifici di qualita'"""

    def __init__(self, engine=None):
        self.engine = engine or get_db_engine()

    def detect_short_responses(self, days: int, min_length: int = 50) -> List[Problem]:
        """Rileva risposte troppo brevi per intent non-fallback"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        query = text("""
        SELECT id, session_id, asl, intent, ask, answer, "when"
        FROM chat_log
        WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
          AND intent NOT IN ('fallback', 'greet', 'goodbye')
          AND LENGTH(answer) < :min_length
          AND answer IS NOT NULL
        ORDER BY "when"::timestamp DESC
        LIMIT 100
        """)

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, {"days": days, "min_length": min_length}).fetchall()

            return [Problem(
                type="short_response",
                severity=Severity.MEDIUM,
                session_id=row[1] or "unknown",
                asl=row[2],
                description=f"Risposta breve ({len(row[5]) if row[5] else 0} char) per intent '{row[3]}'",
                details={
                    "id": row[0],
                    "intent": row[3],
                    "ask": row[4][:100] if row[4] else None,
                    "answer": row[5][:100] if row[5] else None,
                    "answer_length": len(row[5]) if row[5] else 0
                },
                timestamp=str(row[6]) if row[6] else None
            ) for row in rows]
        except Exception as e:
            logger.error(f"[Monitor] Errore detect_short_responses: {e}")
            return []

    def detect_ignored_slots(self, days: int) -> List[Problem]:
        """Rileva casi in cui gli slot sono stati estratti ma la risposta e' generica"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        query = text("""
        SELECT id, session_id, asl, intent, ask, answer, slots::text, "when"
        FROM chat_log
        WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
          AND slots IS NOT NULL
          AND slots::text != '{}'
          AND slots::text != 'null'
          AND LENGTH(answer) < 100
          AND intent NOT IN ('fallback', 'greet', 'goodbye', 'confirm_show_details', 'decline_show_details')
        ORDER BY "when"::timestamp DESC
        LIMIT 100
        """)

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, {"days": days}).fetchall()

            return [Problem(
                type="ignored_slots",
                severity=Severity.HIGH,
                session_id=row[1] or "unknown",
                asl=row[2],
                description=f"Slot estratti ma risposta generica per intent '{row[3]}'",
                details={
                    "id": row[0],
                    "intent": row[3],
                    "ask": row[4][:100] if row[4] else None,
                    "answer": row[5][:100] if row[5] else None,
                    "slots": row[6]
                },
                timestamp=str(row[7]) if row[7] else None
            ) for row in rows]
        except Exception as e:
            logger.error(f"[Monitor] Errore detect_ignored_slots: {e}")
            return []

    def detect_twophase_abandoned(self, days: int) -> List[Problem]:
        """Rileva two-phase iniziati ma non completati"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        # Cerca sessioni con two_phase=true senza confirm/decline successivo
        query = text("""
        WITH twophase_sessions AS (
            SELECT DISTINCT session_id
            FROM chat_log
            WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
              AND two_phase_resp = true
        ),
        confirmed_sessions AS (
            SELECT DISTINCT session_id
            FROM chat_log
            WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
              AND intent IN ('confirm_show_details', 'decline_show_details')
        )
        SELECT t.session_id, c.asl, c.intent, c.ask, c."when"
        FROM twophase_sessions t
        LEFT JOIN confirmed_sessions cs ON t.session_id = cs.session_id
        JOIN chat_log c ON c.session_id = t.session_id AND c.two_phase_resp = true
        WHERE cs.session_id IS NULL
        ORDER BY c."when"::timestamp DESC
        LIMIT 50
        """)

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, {"days": days}).fetchall()

            return [Problem(
                type="twophase_abandoned",
                severity=Severity.MEDIUM,
                session_id=row[0] or "unknown",
                asl=row[1],
                description=f"Two-phase avviato per '{row[2]}' ma non completato",
                details={
                    "intent": row[2],
                    "ask": row[3][:100] if row[3] else None
                },
                timestamp=str(row[4]) if row[4] else None
            ) for row in rows]
        except Exception as e:
            logger.error(f"[Monitor] Errore detect_twophase_abandoned: {e}")
            return []

    def detect_timeouts(self, days: int) -> List[Problem]:
        """Rileva errori di timeout"""
        if self.engine is None:
            return []

        from sqlalchemy import text

        query = text("""
        SELECT id, session_id, asl, intent, ask, error, "when"
        FROM chat_log
        WHERE "when"::timestamp >= NOW() - INTERVAL '1 day' * :days
          AND error ILIKE '%timeout%'
        ORDER BY "when"::timestamp DESC
        LIMIT 50
        """)

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, {"days": days}).fetchall()

            return [Problem(
                type="timeout",
                severity=Severity.HIGH,
                session_id=row[1] or "unknown",
                asl=row[2],
                description=f"Timeout per intent '{row[3]}'",
                details={
                    "id": row[0],
                    "intent": row[3],
                    "ask": row[4][:100] if row[4] else None,
                    "error": row[5]
                },
                timestamp=str(row[6]) if row[6] else None
            ) for row in rows]
        except Exception as e:
            logger.error(f"[Monitor] Errore detect_timeouts: {e}")
            return []

    def detect_all(self, days: int) -> List[Problem]:
        """Esegue tutte le detection"""
        problems = []
        problems.extend(self.detect_short_responses(days))
        problems.extend(self.detect_ignored_slots(days))
        problems.extend(self.detect_twophase_abandoned(days))
        problems.extend(self.detect_timeouts(days))
        return problems


class LLMAnalyzer:
    """Analisi semantica con LLM (opzionale)"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def _get_llm_client(self):
        """Lazy load del client LLM"""
        if self.llm is None:
            try:
                from llm.client import LLMClient
                self.llm = LLMClient()
            except Exception as e:
                logger.error(f"[Monitor] Impossibile inizializzare LLM client: {e}")
                return None
        return self.llm

    def analyze_coherence(self, ask: str, answer: str, intent: str) -> Optional[Dict[str, Any]]:
        """Verifica se la risposta e' coerente con la domanda e l'intent"""
        client = self._get_llm_client()
        if client is None:
            return None

        prompt = f"""Analizza questa conversazione di un assistente veterinario:

Domanda utente: {ask}
Intent classificato: {intent}
Risposta del sistema: {answer[:500]}

Valuta:
1. La risposta e' pertinente alla domanda?
2. L'intent classificato sembra corretto?
3. Ci sono problemi evidenti?

Rispondi SOLO con JSON valido:
{{"coherent": true/false, "confidence": 0.0-1.0, "issue": "descrizione problema o null"}}"""

        try:
            response = client.generate(prompt, temperature=0.1, json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.warning(f"[LLMAnalyzer] Errore analisi: {e}")
            return None

    def batch_analyze(self, messages: List[Dict[str, Any]], sample_size: int = 50) -> List[Problem]:
        """Analizza un campione di conversazioni"""
        problems = []

        # Campiona solo messaggi con intent non-fallback e risposta sostanziale
        candidates = [
            m for m in messages
            if m.get("intent") not in ("fallback", "greet", "goodbye")
            and m.get("answer") and len(m["answer"]) > 50
            and m.get("ask")
        ]

        # Campiona casualmente
        import random
        sample = random.sample(candidates, min(sample_size, len(candidates)))

        logger.info(f"[LLMAnalyzer] Analizzando {len(sample)} conversazioni...")

        for msg in sample:
            result = self.analyze_coherence(msg["ask"], msg["answer"], msg["intent"])
            if result and not result.get("coherent", True):
                problems.append(Problem(
                    type="llm_incoherence",
                    severity=Severity.MEDIUM,
                    session_id=msg.get("session_id", "unknown"),
                    asl=msg.get("asl"),
                    description=f"LLM rileva incoerenza: {result.get('issue', 'non specificato')}",
                    details={
                        "ask": msg["ask"][:100],
                        "intent": msg["intent"],
                        "answer_preview": msg["answer"][:100],
                        "llm_confidence": result.get("confidence", 0),
                        "llm_issue": result.get("issue")
                    },
                    timestamp=msg.get("timestamp")
                ))

        return problems


class ReportGenerator:
    """Genera report in vari formati"""

    def generate_json(self, report: MonitorReport) -> str:
        """Genera report JSON"""
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str)

    def generate_summary(self, report: MonitorReport) -> str:
        """Genera summary testuale"""
        lines = [
            "=" * 60,
            "REPORT MONITORAGGIO CONVERSAZIONI GIAS-AI",
            "=" * 60,
            f"Periodo: ultimi {report.period_days} giorni",
            f"Generato: {report.generated_at}",
            "",
            "STATISTICHE GENERALI",
            "-" * 40,
            f"Sessioni totali: {report.total_sessions}",
            f"Messaggi totali: {report.total_messages}",
            f"Tasso fallback: {report.fallback_rate:.1f}%",
            f"Media messaggi/sessione: {report.avg_session_length:.1f}",
            "",
            "PROBLEMI RILEVATI",
            "-" * 40,
        ]

        counts = report.to_dict()["problem_counts"]
        lines.append(f"Critici: {counts['critical']}")
        lines.append(f"Alti: {counts['high']}")
        lines.append(f"Medi: {counts['medium']}")
        lines.append(f"Bassi: {counts['low']}")

        # Dettagli problemi critici e alti
        critical_high = [p for p in report.problems if p.severity in (Severity.CRITICAL, Severity.HIGH)]
        if critical_high:
            lines.append("")
            lines.append("DETTAGLI PROBLEMI CRITICI/ALTI (max 10)")
            lines.append("-" * 40)
            for p in critical_high[:10]:
                lines.append(f"[{p.severity.value.upper()}] {p.type}")
                lines.append(f"  Sessione: {p.session_id}")
                lines.append(f"  {p.description}")
                lines.append("")

        # Raccomandazioni
        if report.summary.get("recommendations"):
            lines.append("RACCOMANDAZIONI")
            lines.append("-" * 40)
            for rec in report.summary["recommendations"]:
                lines.append(f"- {rec}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_html(self, report: MonitorReport) -> str:
        """Genera report HTML"""
        data = report.to_dict()
        counts = data["problem_counts"]

        html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Report Monitoraggio GIAS-AI</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; background: #1e293b; color: #f1f5f9; }}
        h1, h2 {{ color: #38bdf8; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }}
        .stat {{ background: #334155; padding: 1rem; border-radius: 8px; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #4ade80; }}
        .stat-label {{ color: #94a3b8; }}
        .problems {{ margin-top: 2rem; }}
        .problem {{ background: #334155; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid; }}
        .problem.critical {{ border-color: #ef4444; }}
        .problem.high {{ border-color: #f97316; }}
        .problem.medium {{ border-color: #eab308; }}
        .problem.low {{ border-color: #3b82f6; }}
        .badge {{ display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
        .badge.critical {{ background: #ef4444; }}
        .badge.high {{ background: #f97316; }}
        .badge.medium {{ background: #eab308; color: #1e293b; }}
        .badge.low {{ background: #3b82f6; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #475569; }}
        th {{ color: #94a3b8; }}
    </style>
</head>
<body>
    <h1>Report Monitoraggio Conversazioni GIAS-AI</h1>
    <p>Periodo: ultimi {report.period_days} giorni | Generato: {report.generated_at}</p>

    <h2>Statistiche Generali</h2>
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{report.total_sessions}</div>
            <div class="stat-label">Sessioni</div>
        </div>
        <div class="stat">
            <div class="stat-value">{report.total_messages}</div>
            <div class="stat-label">Messaggi</div>
        </div>
        <div class="stat">
            <div class="stat-value">{report.fallback_rate:.1f}%</div>
            <div class="stat-label">Tasso Fallback</div>
        </div>
        <div class="stat">
            <div class="stat-value">{report.avg_session_length:.1f}</div>
            <div class="stat-label">Media msg/sessione</div>
        </div>
    </div>

    <h2>Problemi Rilevati</h2>
    <div class="stats">
        <div class="stat">
            <div class="stat-value" style="color: #ef4444;">{counts['critical']}</div>
            <div class="stat-label">Critici</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #f97316;">{counts['high']}</div>
            <div class="stat-label">Alti</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #eab308;">{counts['medium']}</div>
            <div class="stat-label">Medi</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #3b82f6;">{counts['low']}</div>
            <div class="stat-label">Bassi</div>
        </div>
    </div>

    <div class="problems">
        <h3>Problemi Critici e Alti</h3>
"""

        for severity in ["critical", "high"]:
            for p in data["problems"][severity][:20]:
                html += f"""
        <div class="problem {severity}">
            <span class="badge {severity}">{severity.upper()}</span>
            <strong>{p['type']}</strong> - {p['description']}
            <br><small>Sessione: {p['session_id']} | ASL: {p.get('asl', 'N/A')}</small>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""
        return html


def run_monitor(
    days: int = 7,
    asl_filter: Optional[str] = None,
    use_llm: bool = False,
    llm_sample: int = 50,
    min_severity: Optional[str] = None
) -> MonitorReport:
    """Esegue il monitoraggio completo e ritorna il report"""

    logger.info(f"[Monitor] Avvio monitoraggio: days={days}, asl={asl_filter}, use_llm={use_llm}")

    engine = get_db_engine()
    analyzer = ConversationAnalyzer(engine)
    detector = QualityDetector(engine)

    # Recupera sessioni
    sessions = analyzer.get_sessions(days, asl_filter)
    logger.info(f"[Monitor] Trovate {len(sessions)} sessioni")

    # Analizza sessioni
    all_problems = []
    total_messages = 0
    total_fallbacks = 0

    for session in sessions:
        problems = analyzer.analyze_session(session)
        all_problems.extend(problems)
        total_messages += session.get("msg_count", 0)
        total_fallbacks += session.get("fallback_count", 0)

    # Rilevamento qualita'
    quality_problems = detector.detect_all(days)
    all_problems.extend(quality_problems)

    # Analisi LLM opzionale
    if use_llm:
        llm_analyzer = LLMAnalyzer()
        messages = analyzer.get_raw_messages(days, asl_filter)
        llm_problems = llm_analyzer.batch_analyze(messages, llm_sample)
        all_problems.extend(llm_problems)

    # Filtra per severita' se richiesto
    if min_severity:
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_level = severity_order.get(min_severity, 0)
        all_problems = [p for p in all_problems if severity_order.get(p.severity.value, 0) >= min_level]

    # Calcola metriche
    fallback_rate = (total_fallbacks / total_messages * 100) if total_messages > 0 else 0
    avg_session_length = total_messages / len(sessions) if sessions else 0

    # Genera raccomandazioni
    recommendations = []
    problem_types = {}
    for p in all_problems:
        problem_types[p.type] = problem_types.get(p.type, 0) + 1

    if problem_types.get("fallback_loop", 0) > 5:
        recommendations.append("Troppi loop di fallback: verificare copertura intent e training router")
    if problem_types.get("repeated_question", 0) > 10:
        recommendations.append("Molte domande ripetute: le risposte potrebbero non essere soddisfacenti")
    if problem_types.get("ignored_slots", 0) > 5:
        recommendations.append("Slot estratti ma ignorati: verificare tool e data retriever")
    if fallback_rate > 20:
        recommendations.append(f"Tasso fallback alto ({fallback_rate:.1f}%): espandere intent supportati")

    report = MonitorReport(
        period_days=days,
        generated_at=datetime.now().isoformat(),
        total_sessions=len(sessions),
        total_messages=total_messages,
        fallback_rate=fallback_rate,
        avg_session_length=avg_session_length,
        problems=all_problems,
        summary={
            "problem_types": problem_types,
            "recommendations": recommendations,
            "asl_filter": asl_filter,
        }
    )

    logger.info(f"[Monitor] Completato: {len(all_problems)} problemi rilevati")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Monitoraggio qualita' conversazioni GIAS-AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python -m tools.conversation_monitor --days 7 --format summary
  python -m tools.conversation_monitor --days 7 --output report.json
  python -m tools.conversation_monitor --days 7 --use-llm --llm-sample 20
  python -m tools.conversation_monitor --asl NA1 --days 30 --format html --output report.html
"""
    )

    parser.add_argument("--days", type=int, default=7, help="Numero di giorni da analizzare (default: 7)")
    parser.add_argument("--output", "-o", type=str, help="File di output (default: stdout)")
    parser.add_argument("--format", "-f", choices=["json", "html", "summary"], default="summary",
                        help="Formato output (default: summary)")
    parser.add_argument("--min-severity", choices=["low", "medium", "high", "critical"],
                        help="Severita' minima da includere")
    parser.add_argument("--asl", type=str, help="Filtra per ASL specifica")
    parser.add_argument("--use-llm", action="store_true",
                        help="Abilita analisi semantica con LLM (piu' lento)")
    parser.add_argument("--llm-sample", type=int, default=50,
                        help="Numero di conversazioni da analizzare con LLM (default: 50)")

    args = parser.parse_args()

    # Esegui monitoraggio
    report = run_monitor(
        days=args.days,
        asl_filter=args.asl,
        use_llm=args.use_llm,
        llm_sample=args.llm_sample,
        min_severity=args.min_severity
    )

    # Genera output
    generator = ReportGenerator()

    if args.format == "json":
        output = generator.generate_json(report)
    elif args.format == "html":
        output = generator.generate_html(report)
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
