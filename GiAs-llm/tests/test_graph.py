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
    def test_route_by_intent(self, mock_router_class, mock_llm_class):
        """Test routing per intent"""
        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "",
            "metadata": {},
            "intent": "greet",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        route = graph._route_by_intent(state)
        assert route == "greet"

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_greet_tool_node(self, mock_router_class, mock_llm_class):
        """Test nodo greet"""
        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "ciao",
            "metadata": {},
            "intent": "greet",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._greet_tool(state)

        assert result["tool_output"]["type"] == "greet"
        assert "Benvenuto" in result["tool_output"]["data"]

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_help_tool_node(self, mock_router_class, mock_llm_class):
        """Test nodo help"""
        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "aiuto",
            "metadata": {},
            "intent": "ask_help",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._help_tool(state)

        assert result["tool_output"]["type"] == "help"
        assert "formatted_response" in result["tool_output"]["data"]
        assert len(result["tool_output"]["data"]["formatted_response"]) > 0

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    @patch('orchestrator.graph.piano_tool')
    def test_piano_description_tool_node(self, mock_piano_tool, mock_router_class, mock_llm_class):
        """Test nodo piano_description"""
        mock_piano_tool.return_value = {"piano_code": "A1", "description": "Test"}

        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "descrivi piano A1",
            "metadata": {},
            "intent": "ask_piano_description",
            "slots": {"piano_code": "A1"},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._piano_description_tool(state)

        assert result["tool_output"]["type"] == "piano_description"
        assert result["tool_output"]["data"]["piano_code"] == "A1"
        mock_piano_tool.assert_called_once_with(action="description", piano_code="A1")

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    @patch('orchestrator.graph.search_tool')
    def test_search_piani_tool_node(self, mock_search_tool, mock_router_class, mock_llm_class):
        """Test nodo search_piani"""
        mock_search_tool.return_value = {"total_found": 2, "matches": []}

        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "cerca piani bovini",
            "metadata": {},
            "intent": "search_piani_by_topic",
            "slots": {"topic": "bovini"},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._search_piani_tool(state)

        assert result["tool_output"]["type"] == "search_piani"
        mock_search_tool.assert_called_once_with(query="bovini")

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    @patch('orchestrator.graph.priority_tool')
    def test_priority_establishment_tool_node(self, mock_priority_tool, mock_router_class, mock_llm_class):
        """Test nodo priority_establishment"""
        mock_priority_tool.return_value = {"asl": "NA1", "priority_establishments": []}

        graph = ConversationGraph(Mock())

        state: ConversationState = {
            "message": "chi controllare",
            "metadata": {"asl": "NA1", "uoc": "UOC Test"},
            "intent": "ask_priority_establishment",
            "slots": {},
            "tool_output": None,
            "final_response": "",
            "needs_clarification": False,
            "error": ""
        }

        result = graph._priority_establishment_tool(state)

        assert result["tool_output"]["type"] == "priority_establishment"
        mock_priority_tool.assert_called_once_with(asl="NA1", uoc="UOC Test", piano_code=None)

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

    @patch('orchestrator.graph.LLMClient')
    @patch('orchestrator.graph.Router')
    def test_build_response_messages(self, mock_router_class, mock_llm_class):
        """Test costruzione messages per response generation"""
        graph = ConversationGraph(Mock())

        tool_output = {
            "type": "piano_description",
            "data": {
                "piano_code": "A1",
                "formatted_response": "Test response"
            }
        }

        messages = graph._build_response_messages("ask_piano_description", tool_output, "descrivi piano A1")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        # System prompt has the general instructions
        assert "italiano" in messages[0]["content"].lower()
        assert "priorità" in messages[0]["content"].lower() or "priorita" in messages[0]["content"].lower()
        # User prompt has the specific request details
        assert "ask_piano_description" in messages[1]["content"]
        assert "descrivi piano A1" in messages[1]["content"]
        assert "Test response" in messages[1]["content"]


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
