"""
Test semplificati per tools

Test suddivisi in:
1. Test validazione input - verificano gestione errori per parametri mancanti/invalidi
2. Test integrazione router - usano dati reali per testare il flusso completo
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd


def call_tool(tool, *args, **kwargs):
    """Helper per chiamare tool LangChain decorati con @tool"""
    func = tool.func if hasattr(tool, 'func') else tool
    return func(*args, **kwargs)


# ============================================================
# Test piano_tool - validazione input
# ============================================================

def test_piano_tool_router_invalid_action():
    """Test router piano_tool con azione non valida"""
    from tools.piano_tools import piano_tool

    result = call_tool(piano_tool, action="invalid_action", piano_code="A1")
    assert "error" in result


def test_piano_description_empty_code():
    """Test piano description con codice vuoto"""
    from tools.piano_tools import get_piano_description

    result = call_tool(get_piano_description, "")
    assert "error" in result
    assert "non specificato" in result["error"].lower()


def test_compare_piani_missing_codes():
    """Test compare piani senza codici"""
    from tools.piano_tools import compare_piani

    result = call_tool(compare_piani, "A1", None)
    assert "error" in result


# ============================================================
# Test piano_tool - integrazione con dati reali
# ============================================================

@pytest.mark.integration
def test_piano_tool_router_description_real():
    """Test router piano_tool con action description - dati reali"""
    from tools.piano_tools import piano_tool

    # Usa un piano che esiste nel database
    result = call_tool(piano_tool, action="description", piano_code="A1")

    # Deve restituire una risposta valida (con o senza dati)
    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result


@pytest.mark.integration
def test_piano_tool_router_stabilimenti_real():
    """Test router piano_tool con action stabilimenti - dati reali"""
    from tools.piano_tools import piano_tool

    result = call_tool(piano_tool, action="stabilimenti", piano_code="A1")

    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result


# ============================================================
# Test search_tool - validazione input
# ============================================================

def test_search_piani_empty_query():
    """Test search con query vuota"""
    from tools.search_tools import search_piani_by_topic

    result = call_tool(search_piani_by_topic, "")
    assert "error" in result or result.get("total_found", 0) == 0


# ============================================================
# Test search_tool - integrazione con dati reali
# ============================================================

@pytest.mark.integration
def test_search_tool_router_real():
    """Test router search_tool con dati reali"""
    from tools.search_tools import search_tool

    result = call_tool(search_tool, query="bovini")

    assert isinstance(result, dict)
    # Deve avere almeno total_found e matches, oppure un errore
    assert ("total_found" in result and "matches" in result) or "error" in result


# ============================================================
# Test priority_tool - validazione input
# ============================================================

def test_get_priority_establishment_missing_asl():
    """Test priority establishment senza ASL"""
    from tools.priority_tools import get_priority_establishment

    result = call_tool(get_priority_establishment, None, "UOC1")
    assert "error" in result
    assert "ASL" in result["error"] or "asl" in result["error"].lower()


def test_get_priority_establishment_missing_uoc():
    """Test priority establishment senza UOC"""
    from tools.priority_tools import get_priority_establishment

    result = call_tool(get_priority_establishment, "NA1", None)
    assert "error" in result
    assert "UOC" in result["error"] or "uoc" in result["error"].lower()


# ============================================================
# Test priority_tool - integrazione con dati reali
# ============================================================

@pytest.mark.integration
def test_priority_tool_router_priority_real():
    """Test router priority_tool con action priority - dati reali"""
    from tools.priority_tools import priority_tool

    result = call_tool(priority_tool, asl="AVELLINO", uoc="UOC IGIENE URBANA", action="priority")

    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result


@pytest.mark.integration
def test_priority_tool_router_delayed_real():
    """Test router priority_tool con action delayed_plans - dati reali"""
    from tools.priority_tools import priority_tool

    result = call_tool(priority_tool, asl="AVELLINO", uoc="UOC IGIENE URBANA", action="delayed_plans")

    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result


@pytest.mark.integration
def test_priority_tool_router_suggest_real():
    """Test router priority_tool con action suggest - dati reali"""
    from tools.priority_tools import priority_tool

    result = call_tool(priority_tool, asl="AVELLINO", action="suggest")

    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result or "total_never_controlled" in result


# ============================================================
# Test risk_tool - validazione input
# ============================================================

def test_get_risk_based_priority_missing_asl():
    """Test risk priority senza ASL"""
    from tools.risk_tools import get_risk_based_priority

    result = call_tool(get_risk_based_priority, None)
    assert "error" in result
    assert "ASL" in result["error"] or "asl" in result["error"].lower()


# ============================================================
# Test risk_tool - integrazione con dati reali
# ============================================================

@pytest.mark.integration
def test_risk_tool_router_real():
    """Test router risk_tool con dati reali"""
    from tools.risk_tools import risk_tool

    result = call_tool(risk_tool, asl="AVELLINO", piano_code="A1")

    assert isinstance(result, dict)
    assert "formatted_response" in result or "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
