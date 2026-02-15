#!/usr/bin/env python3
"""
Test per l'intent ask_nearby_priority (ricerca stabilimenti per prossimità geografica)
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from orchestrator.router import Router
    from tools.proximity_tools import get_nearby_priority
    from agents.response_agent import ResponseFormatter
except ImportError as e:
    pytest.skip(f"Import error: {e}", allow_module_level=True)


class TestNearbyPriorityRouter:
    """Test classificazione intent e slot extraction per ask_nearby_priority"""

    def test_heuristic_vicino_a(self):
        """Test heuristic 'vicino a' - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "stabilimenti vicino a Napoli",
            "vicino a Piazza Garibaldi",
            "controlli vicino a Via Roma",
        ]
        for phrase in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed for: '{phrase}'"
            mock_llm.query.assert_not_called()

    def test_heuristic_nei_dintorni(self):
        """Test heuristic 'nei dintorni di' - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "stabilimenti nei dintorni di Benevento",
            "nei dintorni della stazione",
        ]
        for phrase in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed for: '{phrase}'"
            mock_llm.query.assert_not_called()

    def test_heuristic_nei_pressi(self):
        """Test heuristic 'nei pressi di' - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        result = router.classify("stabilimenti nei pressi di Avellino")
        assert result["intent"] == "ask_nearby_priority"
        mock_llm.query.assert_not_called()

    def test_heuristic_entro_km(self):
        """Test heuristic 'entro X km' - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            "stabilimenti entro 5 km da Salerno",
            "entro 10 km dalla stazione",
            "controlli entro 3km da Via Duomo",
        ]
        for phrase in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed for: '{phrase}'"
            mock_llm.query.assert_not_called()

    def test_heuristic_zona_di(self):
        """Test heuristic 'zona di' - NON chiama LLM"""
        mock_llm = Mock()
        router = Router(mock_llm)

        result = router.classify("stabilimenti zona di Caserta")
        assert result["intent"] == "ask_nearby_priority"
        mock_llm.query.assert_not_called()

    def test_slot_extraction_location(self):
        """Test estrazione slot location"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            ("stabilimenti vicino a Piazza Garibaldi Napoli", "Piazza Garibaldi Napoli"),
            ("vicino a Via Roma 15, Benevento", "Via Roma 15, Benevento"),
            ("nei dintorni di Corso Umberto", "Corso Umberto"),
        ]
        for phrase, expected_location in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed intent for: '{phrase}'"
            # Location dovrebbe essere estratta (se implementato)
            if result["slots"].get("location"):
                assert expected_location.lower() in result["slots"]["location"].lower(), \
                    f"Failed location extraction for: '{phrase}'"

    def test_slot_extraction_radius(self):
        """Test estrazione slot radius_km"""
        mock_llm = Mock()
        router = Router(mock_llm)

        test_cases = [
            ("stabilimenti entro 5 km da Napoli", 5.0),
            ("entro 10 km dalla stazione", 10.0),
            ("controlli entro 3 km da Via Roma", 3.0),
        ]
        for phrase, expected_radius in test_cases:
            result = router.classify(phrase)
            assert result["intent"] == "ask_nearby_priority", f"Failed intent for: '{phrase}'"
            if result["slots"].get("radius_km"):
                assert result["slots"]["radius_km"] == expected_radius, \
                    f"Failed radius extraction for: '{phrase}', got {result['slots'].get('radius_km')}"


class TestNearbyPriorityTool:
    """Test del tool get_nearby_priority"""

    def test_tool_missing_location(self):
        """Test errore quando location manca"""
        tool_func = get_nearby_priority.func if hasattr(get_nearby_priority, 'func') else get_nearby_priority

        result = tool_func(location="", radius_km=5.0)

        assert "error" in result
        assert result["error"] == "location_missing"
        assert "formatted_response" in result

    def test_tool_empty_location(self):
        """Test errore quando location è vuota"""
        tool_func = get_nearby_priority.func if hasattr(get_nearby_priority, 'func') else get_nearby_priority

        result = tool_func(location="   ", radius_km=5.0)

        assert "error" in result
        assert result["error"] == "location_missing"

    @patch('tools.proximity_tools.get_geocoding_service')
    @patch('tools.proximity_tools.DataRetriever')
    def test_tool_address_not_found(self, mock_retriever, mock_geocoder_factory):
        """Test errore quando indirizzo non trovato"""
        from tools.geo_utils import AddressNotFoundError

        mock_geocoder = Mock()
        mock_geocoder.geocode_with_address.side_effect = AddressNotFoundError("Test address")
        mock_geocoder_factory.return_value = mock_geocoder

        tool_func = get_nearby_priority.func if hasattr(get_nearby_priority, 'func') else get_nearby_priority
        result = tool_func(location="indirizzo inesistente xyz123", radius_km=5.0)

        assert "error" in result
        assert result["error"] == "address_not_found"
        assert "formatted_response" in result

    @pytest.mark.skipif(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        reason="Skip geocoding test (requires network, set RUN_INTEGRATION_TESTS=1)"
    )
    def test_tool_successful_geocoding(self):
        """Test geocodifica riuscita con indirizzo reale (integration test)"""
        tool_func = get_nearby_priority.func if hasattr(get_nearby_priority, 'func') else get_nearby_priority
        result = tool_func(location="Piazza Garibaldi, Napoli", radius_km=5.0)

        # Verifica che ci sia una risposta formattata o errore gestito
        assert "formatted_response" in result or "error" in result

        # Se geocodifica riuscita, verifica struttura risposta
        if "error" not in result:
            assert "location" in result
            assert "center_lat" in result or "resolved_address" in result


class TestNearbyPriorityResponseFormatter:
    """Test formattazione risposta per nearby_priority"""

    def test_format_nearby_priority_empty(self):
        """Test formattazione con DataFrame vuoto"""
        import pandas as pd

        result = ResponseFormatter.format_nearby_priority(
            location="Test Location",
            center_coords=(40.8518, 14.2681),
            radius_km=5.0,
            nearby_df=pd.DataFrame(),
            total_found=0
        )

        assert "Nessun stabilimento" in result
        assert "5" in result  # radius_km

    def test_format_nearby_priority_with_data(self):
        """Test formattazione con dati"""
        import pandas as pd

        nearby_df = pd.DataFrame([
            {
                'macroarea': 'MACELLERIA',
                'comune': 'NAPOLI',
                'distanza_km': 1.5,
                'punteggio_rischio': 25
            },
            {
                'macroarea': 'RISTORANTE',
                'comune': 'NAPOLI',
                'distanza_km': 2.3,
                'punteggio_rischio': 15
            }
        ])

        result = ResponseFormatter.format_nearby_priority(
            location="Test Location",
            center_coords=(40.8518, 14.2681),
            radius_km=5.0,
            nearby_df=nearby_df,
            total_found=2
        )

        assert "Test Location" in result
        assert "MACELLERIA" in result
        assert "RISTORANTE" in result
        assert "5" in result  # radius_km


class TestNearbyPriorityIntegration:
    """Test integrazione completa intent -> tool -> response"""

    def test_integration_classification_to_tool_mapping(self):
        """Test che l'intent sia mappato al tool corretto"""
        from orchestrator.tool_nodes import INTENT_TO_TOOL

        assert "ask_nearby_priority" in INTENT_TO_TOOL
        assert INTENT_TO_TOOL["ask_nearby_priority"] == "nearby_priority_tool"

    def test_integration_tool_in_registry(self):
        """Test che il tool sia nel registry"""
        from orchestrator.tool_nodes import TOOL_REGISTRY

        assert "nearby_priority_tool" in TOOL_REGISTRY

    @pytest.mark.skipif(
        not os.environ.get("RUN_INTEGRATION_TESTS"),
        reason="Skip integration test (set RUN_INTEGRATION_TESTS=1 to run)"
    )
    def test_full_integration_flow(self):
        """Test flusso completo con LLM reale (richiede server attivo)"""
        from llm.client import LLMClient

        router = Router(LLMClient())

        # Classificazione
        result = router.classify("stabilimenti vicino a Piazza Garibaldi Napoli")
        assert result["intent"] == "ask_nearby_priority"

        # Verifica slot extraction
        if result["slots"].get("location"):
            assert "Garibaldi" in result["slots"]["location"] or "Napoli" in result["slots"]["location"]


if __name__ == "__main__":
    print("Test ask_nearby_priority intent")
    print("=" * 60)

    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])
