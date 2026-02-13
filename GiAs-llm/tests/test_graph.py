"""
Test per ConversationGraph e orchestrazione
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.graph import ConversationGraph, ConversationState


class TestConversationGraph:
    """Test per ConversationGraph"""

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_graph_initialization(self, mock_router_class, mock_llm_class):
        """Test inizializzazione grafo"""
        mock_llm = Mock()
        mock_router = Mock()
        mock_router_class.return_value = mock_router

        graph = ConversationGraph(mock_llm)

        assert graph.llm_client == mock_llm
        assert graph.router is not None
        assert graph.graph is not None

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_classify_node(self, mock_router_class, mock_llm_class):
        """Test nodo di classificazione"""
        mock_llm = Mock()
        mock_router = Mock()
        mock_router.classify.return_value = {
            "intent": "greet",
            "slots": {},
            "needs_clarification": False,
            "error": ""
        }
        mock_router_class.return_value = mock_router

        graph = ConversationGraph(mock_llm)

        state: ConversationState = {
            "message": "ciao",
            "metadata": {},
            "intent": "",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._classify_node(state)

        assert result["intent"] == "greet"
        assert result["slots"] == {}
        mock_router.classify.assert_called_once_with("ciao", {})

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_response_generator_simple_intents(self, mock_router_class, mock_llm_class):
        """Test response generator per intent semplici (greet, goodbye, fallback)"""
        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "ciao",
            "metadata": {},
            "intent": "greet",
            "slots": {},
            "tool_output": {"type": "greet", "data": "Benvenuto!"},
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._response_generator_node(state)

        assert result["final_response"] == "Benvenuto!"

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_response_generator_with_formatted_response(self, mock_router_class, mock_llm_class):
        """Test response generator con formatted_response preesistente (no LLM call)"""
        mock_llm = Mock()
        graph = ConversationGraph(mock_llm)

        state: ConversationState = {
            "message": "descrivi piano A1",
            "metadata": {},
            "intent": "ask_piano_description",
            "slots": {"piano_code": "A1"},
            "tool_output": {
                "type": "piano_description",
                "data": {"piano_code": "A1", "formatted_response": "Descrizione piano"}
            },
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._response_generator_node(state)

        # formatted_response presente → usata direttamente, no LLM
        assert result["final_response"] == "Descrizione piano"
        mock_llm.query.assert_not_called()

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_response_generator_with_llm(self, mock_router_class, mock_llm_class):
        """Test response generator con chiamata LLM (no formatted_response)"""
        mock_llm = Mock()
        mock_llm.query.return_value = "Risposta generata dall'LLM"

        graph = ConversationGraph(mock_llm)

        state: ConversationState = {
            "message": "descrivi piano A1",
            "metadata": {},
            "intent": "ask_piano_description",
            "slots": {"piano_code": "A1"},
            "tool_output": {
                "type": "piano_description",
                "data": {"piano_code": "A1", "description": "Piano A1 description"}
            },
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._response_generator_node(state)

        assert result["final_response"] == "Risposta generata dall'LLM"
        mock_llm.query.assert_called_once()

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_response_generator_llm_error(self, mock_router_class, mock_llm_class):
        """Test response generator con errore LLM"""
        mock_llm = Mock()
        mock_llm.query.side_effect = Exception("LLM Error")

        graph = ConversationGraph(mock_llm)

        state: ConversationState = {
            "message": "test",
            "metadata": {},
            "intent": "ask_piano_description",
            "slots": {},
            "tool_output": {"type": "piano_description", "data": {}},
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._response_generator_node(state)

        assert "Errore" in result["final_response"]


class TestConversationState:
    """Test per ConversationState TypedDict"""

    def test_conversation_state_structure(self):
        """Test struttura ConversationState"""
        state: ConversationState = {
            "message": "test",
            "metadata": {"asl": "NA1"},
            "intent": "greet",
            "slots": {"piano_code": "A1"},
            "tool_output": {"type": "test", "data": {}},
            "final_response": "response",
            "needs_clarification": False,
            "error": ""
        }

        assert state["message"] == "test"
        assert state["metadata"]["asl"] == "NA1"
        assert state["intent"] == "greet"
        assert state["slots"]["piano_code"] == "A1"
        assert state["needs_clarification"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
