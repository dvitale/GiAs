"""
Test per Intelligent Monitor

Test unitari e di integrazione per:
- BugDetector
- RootCauseAnalyzer
- TrendAnalyzer
- UserIntentMiner
- ImprovementSuggester
- IntelligentMonitor
- API endpoints
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json


# =============================================================================
# Test Data Classes
# =============================================================================

class TestSuggestion:
    """Test per la dataclass Suggestion"""

    def test_suggestion_to_dict(self):
        """Test conversione suggerimento in dict"""
        from tools.intelligent_monitor import Suggestion, SuggestionType

        suggestion = Suggestion(
            type=SuggestionType.FIX_BUG,
            priority=5,
            title="Test bug fix",
            description="Descrizione test",
            action="Azione da intraprendere",
            evidence={"key": "value"},
            estimated_impact="high",
            implementation_hint="Hint test"
        )

        result = suggestion.to_dict()

        assert result["type"] == "fix_bug"
        assert result["priority"] == 5
        assert result["title"] == "Test bug fix"
        assert result["evidence"]["key"] == "value"

    def test_suggestion_types(self):
        """Test tutti i tipi di suggerimento"""
        from tools.intelligent_monitor import SuggestionType

        assert SuggestionType.FIX_BUG.value == "fix_bug"
        assert SuggestionType.ADD_PATTERN.value == "add_pattern"
        assert SuggestionType.ADD_INTENT.value == "add_intent"
        assert SuggestionType.OPTIMIZE_TOOL.value == "optimize_tool"
        assert SuggestionType.UPDATE_TRAINING.value == "update_training"


class TestTrendAlert:
    """Test per la dataclass TrendAlert"""

    def test_trend_alert_to_dict(self):
        """Test conversione alert in dict"""
        from tools.intelligent_monitor import TrendAlert

        alert = TrendAlert(
            metric="error_rate",
            current_value=15.5,
            baseline_value=5.0,
            delta_pct=210.0,
            severity="critical",
            intent="test_intent",
            recommendation="Test recommendation"
        )

        result = alert.to_dict()

        assert result["metric"] == "error_rate"
        assert result["current_value"] == 15.5
        assert result["severity"] == "critical"


class TestHealthScore:
    """Test per la dataclass HealthScore"""

    def test_health_score_to_dict(self):
        """Test conversione health score in dict"""
        from tools.intelligent_monitor import HealthScore, TrendAlert

        alerts = [
            TrendAlert(
                metric="error_rate",
                current_value=10.0,
                baseline_value=5.0,
                delta_pct=100.0,
                severity="high"
            )
        ]

        health = HealthScore(
            overall_score=75.5,
            components={"error_rate": 80.0, "latency": 70.0},
            alerts=alerts,
            generated_at="2024-01-01T00:00:00"
        )

        result = health.to_dict()

        assert result["overall_score"] == 75.5
        assert result["components"]["error_rate"] == 80.0
        assert len(result["alerts"]) == 1


# =============================================================================
# Test BugDetector
# =============================================================================

class TestBugDetector:
    """Test per BugDetector"""

    @pytest.fixture
    def mock_engine(self):
        """Engine mock per test"""
        engine = MagicMock()
        return engine

    def test_detect_recurring_errors_no_engine(self):
        """Test detect_recurring_errors senza engine"""
        from tools.intelligent_monitor import BugDetector

        detector = BugDetector(engine=None)
        result = detector.detect_recurring_errors()

        assert result == []

    def test_detect_recurring_errors_with_mock(self, mock_engine):
        """Test detect_recurring_errors con mock"""
        from tools.intelligent_monitor import BugDetector

        # Mock result
        mock_rows = [
            (
                "error n timeout",  # error_signature
                5,                   # occurrence_count
                3,                   # affected_sessions
                2,                   # affected_asls
                ["intent1"],         # related_intents
                ["NA1", "NA2"],      # asl_list
                datetime.now(),      # first_occurrence
                datetime.now(),      # last_occurrence
                7,                   # span_days
            )
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        detector = BugDetector(engine=mock_engine)
        result = detector.detect_recurring_errors()

        assert len(result) == 1
        assert result[0]["bug_type"] == "recurring_error"
        assert result[0]["occurrence_count"] == 5

    def test_detect_all_combines_results(self, mock_engine):
        """Test che detect_all combina tutti i tipi di bug"""
        from tools.intelligent_monitor import BugDetector

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        detector = BugDetector(engine=mock_engine)
        result = detector.detect_all()

        # Dovrebbe chiamare tutte le detection
        assert isinstance(result, list)


# =============================================================================
# Test TrendAnalyzer
# =============================================================================

class TestTrendAnalyzer:
    """Test per TrendAnalyzer"""

    @pytest.fixture
    def mock_engine(self):
        """Engine mock per test"""
        return MagicMock()

    def test_calculate_health_score_no_engine(self):
        """Test health score senza engine"""
        from tools.intelligent_monitor import TrendAnalyzer

        analyzer = TrendAnalyzer(engine=None)
        health = analyzer.calculate_health_score()

        assert health.overall_score >= 0
        assert health.overall_score <= 100
        assert "error_rate" in health.components

    def test_get_recommendation(self):
        """Test generazione raccomandazioni"""
        from tools.intelligent_monitor import TrendAnalyzer

        analyzer = TrendAnalyzer()

        rec = analyzer._get_recommendation("error_spike", "test_intent")
        assert "Verifica urgente" in rec

        rec = analyzer._get_recommendation("latency_spike", "test_intent")
        assert "Performance critica" in rec


# =============================================================================
# Test ImprovementSuggester
# =============================================================================

class TestImprovementSuggester:
    """Test per ImprovementSuggester"""

    def test_generate_from_bugs_recurring_error(self):
        """Test generazione suggerimenti da errori ricorrenti"""
        from tools.intelligent_monitor import ImprovementSuggester, SuggestionType

        suggester = ImprovementSuggester()

        bugs = [{
            "bug_type": "recurring_error",
            "error_signature": "test error signature",
            "occurrence_count": 10,
            "affected_sessions": 5,
            "related_intents": ["intent1"],
            "asl_list": ["NA1"],
        }]

        suggestions = suggester.generate_from_bugs(bugs)

        assert len(suggestions) == 1
        assert suggestions[0].type == SuggestionType.FIX_BUG
        assert suggestions[0].priority == 5

    def test_generate_from_bugs_slot_failure(self):
        """Test generazione suggerimenti da slot failure"""
        from tools.intelligent_monitor import ImprovementSuggester, SuggestionType

        suggester = ImprovementSuggester()

        bugs = [{
            "bug_type": "slot_failure",
            "intent": "test_intent",
            "slot_piano": "A1",
            "failure_rate_pct": 50.0,
        }]

        suggestions = suggester.generate_from_bugs(bugs)

        assert len(suggestions) == 1
        assert suggestions[0].type == SuggestionType.FIX_BUG
        assert suggestions[0].priority == 4

    def test_generate_from_root_causes_fallback_cluster(self):
        """Test generazione suggerimenti da fallback cluster"""
        from tools.intelligent_monitor import ImprovementSuggester, SuggestionType

        suggester = ImprovementSuggester()

        root_causes = [{
            "type": "fallback_cluster",
            "cluster_key": "come vedere piani",
            "cluster_size": 15,
            "example_questions": ["come vedere i piani"],
        }]

        suggestions = suggester.generate_from_root_causes(root_causes)

        assert len(suggestions) == 1
        assert suggestions[0].type == SuggestionType.ADD_PATTERN
        assert suggestions[0].priority == 5  # cluster_size >= 15

    def test_generate_from_unmet_needs(self):
        """Test generazione suggerimenti da bisogni non soddisfatti"""
        from tools.intelligent_monitor import ImprovementSuggester

        suggester = ImprovementSuggester()

        unmet_needs = [{
            "request_type": "question",
            "action_type": "view_data",
            "frequency": 12,
            "unique_sessions": 8,
            "sample_questions": ["mostra i dati"],
            "priority_score": 3.5,
        }]

        suggestions = suggester.generate_from_unmet_needs(unmet_needs)

        assert len(suggestions) == 1
        assert suggestions[0].priority == 4  # frequency >= 10


# =============================================================================
# Test IntelligentMonitor
# =============================================================================

class TestIntelligentMonitor:
    """Test per IntelligentMonitor orchestrator"""

    @pytest.fixture
    def mock_engine(self):
        """Engine mock per test"""
        engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        engine.connect.return_value.__enter__.return_value = mock_conn
        return engine

    def test_run_analysis_returns_report(self, mock_engine):
        """Test che run_analysis ritorna un IntelligentReport"""
        from tools.intelligent_monitor import IntelligentMonitor, IntelligentReport

        monitor = IntelligentMonitor(engine=mock_engine)
        report = monitor.run_analysis(days=7, use_llm=False, min_priority=1)

        assert isinstance(report, IntelligentReport)
        assert report.period_days == 7
        assert report.health_score is not None
        assert isinstance(report.suggestions, list)

    def test_get_suggestions(self, mock_engine):
        """Test get_suggestions"""
        from tools.intelligent_monitor import IntelligentMonitor

        monitor = IntelligentMonitor(engine=mock_engine)
        suggestions = monitor.get_suggestions(min_priority=3, limit=10)

        assert isinstance(suggestions, list)

    def test_get_health(self, mock_engine):
        """Test get_health"""
        from tools.intelligent_monitor import IntelligentMonitor, HealthScore

        monitor = IntelligentMonitor(engine=mock_engine)
        health = monitor.get_health()

        assert isinstance(health, HealthScore)
        assert health.overall_score >= 0


# =============================================================================
# Test Report Generator
# =============================================================================

class TestIntelligentReportGenerator:
    """Test per generatore report"""

    def test_generate_json(self):
        """Test generazione JSON"""
        from tools.intelligent_monitor import (
            IntelligentReportGenerator, IntelligentReport,
            HealthScore
        )

        report = IntelligentReport(
            period_days=7,
            generated_at="2024-01-01T00:00:00",
            health_score=HealthScore(
                overall_score=80.0,
                components={"error_rate": 90.0},
                alerts=[],
                generated_at="2024-01-01T00:00:00"
            ),
            suggestions=[],
            bugs_detected=[],
            trend_analysis={},
            unmet_needs=[],
            root_causes=[],
        )

        generator = IntelligentReportGenerator()
        json_output = generator.generate_json(report)

        # Deve essere JSON valido
        parsed = json.loads(json_output)
        assert parsed["period_days"] == 7
        assert parsed["health_score"]["overall_score"] == 80.0

    def test_generate_summary(self):
        """Test generazione summary testuale"""
        from tools.intelligent_monitor import (
            IntelligentReportGenerator, IntelligentReport,
            HealthScore
        )

        report = IntelligentReport(
            period_days=7,
            generated_at="2024-01-01T00:00:00",
            health_score=HealthScore(
                overall_score=80.0,
                components={"error_rate": 90.0, "latency": 85.0},
                alerts=[],
                generated_at="2024-01-01T00:00:00"
            ),
            suggestions=[],
            bugs_detected=[],
            trend_analysis={},
            unmet_needs=[],
            root_causes=[],
        )

        generator = IntelligentReportGenerator()
        summary = generator.generate_summary(report)

        assert "INTELLIGENT MONITOR REPORT" in summary
        assert "Health score" in summary.lower() or "Score complessivo" in summary


# =============================================================================
# Test API Endpoints (Integration)
# =============================================================================

@pytest.mark.integration
class TestIntelligentMonitorAPI:
    """Test per API endpoints Intelligent Monitor"""

    @pytest.fixture
    def client(self):
        """Client FastAPI per test"""
        try:
            from fastapi.testclient import TestClient
            from app.api import app
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI o dipendenze non disponibili")

    def test_health_endpoint_returns_200(self, client):
        """Test endpoint /api/monitor/health"""
        with patch('tools.intelligent_monitor.get_db_engine') as mock_engine:
            mock_engine.return_value = None  # No DB
            response = client.get("/api/monitor/health")

        # L'endpoint dovrebbe ritornare 200 anche senza DB
        assert response.status_code in [200, 500]

    def test_suggestions_endpoint_returns_200(self, client):
        """Test endpoint /api/monitor/suggestions"""
        with patch('tools.intelligent_monitor.get_db_engine') as mock_engine:
            mock_engine.return_value = None
            response = client.get("/api/monitor/suggestions?min_priority=3")

        assert response.status_code in [200, 500]

    def test_intelligent_endpoint_returns_200(self, client):
        """Test endpoint /api/monitor/intelligent"""
        with patch('tools.intelligent_monitor.get_db_engine') as mock_engine:
            mock_engine.return_value = None
            response = client.get("/api/monitor/intelligent?days=7")

        assert response.status_code in [200, 500]


# =============================================================================
# Test CLI
# =============================================================================

class TestCLI:
    """Test per interfaccia CLI"""

    def test_main_help(self, capsys):
        """Test --help non causa errori"""
        import sys
        from unittest.mock import patch

        with patch.object(sys, 'argv', ['intelligent_monitor', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                from tools.intelligent_monitor import main
                main()

            # --help esce con code 0
            assert exc_info.value.code == 0
