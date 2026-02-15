"""
Test semplificati per Router (senza dipendenze esterne)
"""

import pytest
import json
from unittest.mock import Mock


def test_router_initialization():
    """Test inizializzazione Router con LLM client mock"""
    from orchestrator.router import Router

    mock_llm = Mock()
    router = Router(mock_llm)

    assert router.llm_client == mock_llm
    assert len(Router.VALID_INTENTS) == 20


def test_router_empty_message():
    """Test con messaggio vuoto"""
    from orchestrator.router import Router

    mock_llm = Mock()
    router = Router(mock_llm)

    result = router.classify("")

    assert result["intent"] == "fallback"
    assert "error" in result


def test_router_valid_classification():
    """Test classificazione valida"""
    from orchestrator.router import Router

    mock_llm = Mock()
    mock_llm.query.return_value = json.dumps({
        "intent": "greet",
        "slots": {},
        "needs_clarification": False
    })

    router = Router(mock_llm)
    result = router.classify("ciao")

    assert result["intent"] == "greet"
    assert result["slots"] == {}


def test_router_invalid_intent():
    """Test intent non valido"""
    from orchestrator.router import Router

    mock_llm = Mock()
    mock_llm.query.return_value = json.dumps({
        "intent": "invalid_intent_xyz",
        "slots": {},
        "needs_clarification": False
    })

    router = Router(mock_llm)
    result = router.classify("test")

    assert result["intent"] == "fallback"


def test_router_malformed_json():
    """Test JSON malformato"""
    from orchestrator.router import Router

    mock_llm = Mock()
    mock_llm.query.return_value = "not valid json{"

    router = Router(mock_llm)
    result = router.classify("test")

    assert result["intent"] == "fallback"


def test_router_with_slots():
    """Test estrazione slots"""
    from orchestrator.router import Router

    mock_llm = Mock()
    mock_llm.query.return_value = json.dumps({
        "intent": "ask_piano_description",
        "slots": {"piano_code": "A1"},
        "needs_clarification": False
    })

    router = Router(mock_llm)
    result = router.classify("descrivi piano A1")

    assert result["intent"] == "ask_piano_description"
    assert result["slots"]["piano_code"] == "A1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
