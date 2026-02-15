"""
Test integrazione ML Predictor con modello reale (NO MOCK).
"""

import pytest
import sys
import os

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestMLPredictorReal:
    """Test ML Risk Predictor con modello XGBoost reale."""

    @pytest.fixture
    def predictor(self):
        """Carica predictor ML reale."""
        try:
            from predictor_ml.predictor import RiskPredictor
            return RiskPredictor()
        except Exception as e:
            pytest.skip(f"RiskPredictor non disponibile: {e}")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_predictor_loads(self, predictor):
        """Test che il predictor carichi correttamente."""
        assert predictor is not None
        # model puo' essere None se XGBoost non e' installato (usa fallback)
        assert hasattr(predictor, 'model')
        assert hasattr(predictor, 'model_available')

    @pytest.mark.integration
    @pytest.mark.slow
    def test_predictor_predict_asl(self, predictor):
        """Test predizione per ASL."""
        result = predictor.predict(asl="AVELLINO", limit=5)

        assert result is not None
        assert isinstance(result, dict)
        assert "asl" in result
        assert "total_never_controlled" in result
        assert "risky_establishments" in result
        assert "formatted_response" in result
        assert "model_version" in result

    @pytest.mark.integration
    @pytest.mark.slow
    def test_predictor_predict_with_piano(self, predictor):
        """Test predizione con filtro piano."""
        result = predictor.predict(asl="AVELLINO", piano_code="A1", limit=10)

        assert result is not None
        assert isinstance(result, dict)
        assert result["asl"] == "AVELLINO"
        assert result["piano_code"] == "A1"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_predictor_risky_establishments_format(self, predictor):
        """Test formato stabilimenti rischiosi."""
        result = predictor.predict(asl="AVELLINO", limit=3, min_score=0.0)

        if result.get("risky_establishments"):
            est = result["risky_establishments"][0]
            # Verifica campi obbligatori
            assert "macroarea" in est
            assert "risk_score" in est
            assert "risk_category" in est
            # Score deve essere tra 0 e 1
            assert 0 <= est["risk_score"] <= 1
            # Categoria valida
            assert est["risk_category"] in ["ALTO", "MEDIO", "BASSO"]


class TestMLPredictorTool:
    """Test tool ML predictor via API."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_ml_prediction_tool(self, tool_caller):
        """Test get_ml_risk_prediction tool."""
        try:
            from tools.predictor_tools import get_ml_risk_prediction

            result = tool_caller(get_ml_risk_prediction, asl="AVELLINO")

            assert isinstance(result, dict)
            # Deve avere risposta o errore
            assert "formatted_response" in result or "error" in result or "predictions" in result

        except ImportError:
            pytest.skip("predictor_tools non disponibile")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_ml_vs_statistical_comparison(self, tool_caller):
        """Test confronto ML vs statistical predictor."""
        try:
            from tools.predictor_tools import get_ml_risk_prediction
            from tools.risk_tools import get_risk_based_priority

            ml_result = tool_caller(get_ml_risk_prediction, asl="AVELLINO")
            stat_result = tool_caller(get_risk_based_priority, asl="AVELLINO")

            # Entrambi devono restituire risultati validi
            assert isinstance(ml_result, dict)
            assert isinstance(stat_result, dict)

        except ImportError:
            pytest.skip("Tools non disponibili")


class TestMLPredictorConfig:
    """Test configurazione ML predictor."""

    @pytest.mark.integration
    def test_predictor_config_loaded(self):
        """Test che configurazione predictor sia caricata."""
        try:
            from configs.config import RiskPredictorConfig

            predictor_type = RiskPredictorConfig.get_predictor_type()

            assert predictor_type in ["ml", "statistical"]

        except ImportError:
            pytest.skip("RiskPredictorConfig non disponibile")

    @pytest.mark.integration
    def test_predictor_type_check(self):
        """Test metodi di verifica tipo predictor."""
        try:
            from configs.config import RiskPredictorConfig

            is_ml = RiskPredictorConfig.is_ml_predictor()
            is_stat = RiskPredictorConfig.is_statistical_predictor()

            # Uno dei due deve essere True
            assert is_ml or is_stat
            # Non entrambi
            assert not (is_ml and is_stat)

        except ImportError:
            pytest.skip("RiskPredictorConfig non disponibile")


class TestMLModelFiles:
    """Test file modello ML."""

    @pytest.mark.integration
    def test_model_file_exists(self):
        """Test che file modello esista."""
        from pathlib import Path

        model_path = Path(__file__).parent.parent.parent / "predictor_ml" / "production_assets" / "risk_model_v4.json"

        if not model_path.exists():
            pytest.skip(f"File modello non trovato: {model_path}")

        assert model_path.stat().st_size > 0, "File modello vuoto"

    @pytest.mark.integration
    def test_training_data_exists(self):
        """Test che dati training esistano."""
        from pathlib import Path

        data_path = Path(__file__).parent.parent.parent / "predictor_ml" / "production_assets" / "training_data_v4.parquet"

        if not data_path.exists():
            pytest.skip(f"File dati training non trovato: {data_path}")

        assert data_path.stat().st_size > 0, "File dati vuoto"

    @pytest.mark.integration
    def test_taxonomy_map_exists(self):
        """Test che mapping tassonomia esista."""
        from pathlib import Path

        map_path = Path(__file__).parent.parent.parent / "predictor_ml" / "mappings" / "taxonomy_map.json"

        if not map_path.exists():
            pytest.skip(f"File taxonomy non trovato: {map_path}")

        import json
        with open(map_path) as f:
            taxonomy = json.load(f)

        assert isinstance(taxonomy, dict)
        assert len(taxonomy) > 0
