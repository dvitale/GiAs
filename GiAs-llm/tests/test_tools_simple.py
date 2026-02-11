"""
Test semplificati per tools (senza mock complessi)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd


def test_piano_tool_router_description():
    """Test router piano_tool con action description"""
    from tools.piano_tools import piano_tool

    with patch('tools.piano_tools.get_piano_description') as mock_func:
        mock_func.return_value = {"piano_code": "A1", "description": "Test"}
        result = piano_tool(action="description", piano_code="A1")
        assert result["piano_code"] == "A1"
        mock_func.assert_called_once_with("A1")


def test_piano_tool_router_stabilimenti():
    """Test router piano_tool con action stabilimenti"""
    from tools.piano_tools import piano_tool

    with patch('tools.piano_tools.get_piano_attivita') as mock_func:
        mock_func.return_value = {"piano_code": "A1", "top_stabilimenti": []}
        result = piano_tool(action="stabilimenti", piano_code="A1")
        assert result["piano_code"] == "A1"


def test_piano_tool_router_invalid_action():
    """Test router piano_tool con azione non valida"""
    from tools.piano_tools import piano_tool

    result = piano_tool(action="invalid_action", piano_code="A1")
    assert "error" in result


def test_search_tool_router():
    """Test router search_tool"""
    from tools.search_tools import search_tool

    with patch('tools.search_tools.search_piani_by_topic') as mock_func:
        mock_func.return_value = {"total_found": 2, "matches": []}
        result = search_tool(query="bovini")
        assert result["total_found"] == 2
        mock_func.assert_called_once_with("bovini")


def test_search_piani_empty_query():
    """Test search con query vuota"""
    from tools.search_tools import search_piani_by_topic

    result = search_piani_by_topic("")
    assert "error" in result
    assert result["error"] == "Query di ricerca non specificata"


def test_priority_tool_router_priority():
    """Test router priority_tool con action priority"""
    from tools.priority_tools import priority_tool

    with patch('tools.priority_tools.get_priority_establishment') as mock_func:
        mock_func.return_value = {"asl": "NA1", "priority_establishments": []}
        result = priority_tool(asl="NA1", uoc="UOC1", action="priority")
        assert result["asl"] == "NA1"


def test_priority_tool_router_delayed():
    """Test router priority_tool con action delayed_plans"""
    from tools.priority_tools import priority_tool

    with patch('tools.priority_tools.get_delayed_plans') as mock_func:
        mock_func.return_value = {"asl": "NA1", "delayed_plans": []}
        result = priority_tool(asl="NA1", uoc="UOC1", action="delayed_plans")
        assert result["asl"] == "NA1"


def test_priority_tool_router_suggest():
    """Test router priority_tool con action suggest"""
    from tools.priority_tools import priority_tool

    with patch('tools.priority_tools.suggest_controls') as mock_func:
        mock_func.return_value = {"total_never_controlled": 5}
        result = priority_tool(asl="NA1", action="suggest")
        assert result["total_never_controlled"] == 5


def test_get_priority_establishment_missing_asl():
    """Test priority establishment senza ASL"""
    from tools.priority_tools import get_priority_establishment

    result = get_priority_establishment(None, "UOC1")
    assert "error" in result
    assert "ASL non specificata" in result["error"]


def test_get_priority_establishment_missing_uoc():
    """Test priority establishment senza UOC"""
    from tools.priority_tools import get_priority_establishment

    result = get_priority_establishment("NA1", None)
    assert "error" in result
    assert "UOC non specificata" in result["error"]


def test_risk_tool_router():
    """Test router risk_tool"""
    from tools.risk_tools import risk_tool

    with patch('tools.risk_tools.get_risk_based_priority') as mock_func:
        mock_func.return_value = {"asl": "NA1", "total_risky": 10}
        result = risk_tool(asl="NA1", piano_code="A1")
        assert result["asl"] == "NA1"


def test_get_risk_based_priority_missing_asl():
    """Test risk priority senza ASL"""
    from tools.risk_tools import get_risk_based_priority

    result = get_risk_based_priority(None)
    assert "error" in result
    assert "ASL non specificata" in result["error"]


def test_piano_description_empty_code():
    """Test piano description con codice vuoto"""
    from tools.piano_tools import get_piano_description

    result = get_piano_description("")
    assert "error" in result
    assert "non specificato" in result["error"].lower()


def test_compare_piani_missing_codes():
    """Test compare piani senza codici"""
    from tools.piano_tools import compare_piani

    result = compare_piani("A1", None)
    assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
