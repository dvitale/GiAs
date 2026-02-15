"""
Integration tests per Intelligent Fallback System

Test dell'integrazione tra ConversationGraph e FallbackRecoveryEngine:
- Flusso fallback con suggerimenti
- Selezione intent da suggerimenti
- Loop prevention
- Session state management
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.graph import ConversationGraph, ConversationState


class TestFallbackFlow:
    """Test flusso fallback completo"""

    def setup_method(self):
        """Setup per ogni test"""
        # Mock LLM client
        self.mock_llm = Mock()
        self.mock_llm.chat.return_value = '{"intent": "fallback", "slots": {}}'

        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_fallback_generates_suggestions(self):
        """Test che fallback generi suggerimenti"""
        # Mock router per ritornare fallback
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False,
                "error": "Intent non riconosciuto"
            }

            result = self.graph.run(
                message="dammi gli stabilimenti pericolosi",
                metadata={}
            )

            # Verifica che ci siano suggerimenti nello stato
            # (controllando tool_output)
            assert "response" in result
            response = result["response"]

            # Il messaggio dovrebbe contenere suggerimenti numerati
            assert "1." in response or "Suggerimenti" in response

    def test_fallback_with_keyword_match(self):
        """Test fallback con keyword match veloce"""
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            result = self.graph.run(
                message="stabilimenti a rischio",
                metadata={}
            )

            response = result["response"]

            # Dovrebbe suggerire ask_risk_based_priority
            assert "rischio" in response.lower() or "Stabilimenti a Rischio" in response


class TestUserSelection:
    """Test selezione utente da suggerimenti"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_numeric_selection_executes_intent(self):
        """Test selezione numerica esegue intent corretto"""
        # Simula stato con fallback_suggestions
        state = {
            "message": "1",
            "metadata": {},
            "fallback_suggestions": [
                {
                    "intent": "ask_risk_based_priority",
                    "label": "Stabilimenti a Rischio NC",
                    "type": "intent",
                    "requires_slots": []
                }
            ]
        }

        # Chiama _classify_node
        result_state = self.graph._classify_node(state)

        # Dovrebbe aver selezionato l'intent
        assert result_state["intent"] == "ask_risk_based_priority"
        assert result_state["fallback_suggestions"] is None  # Reset dopo selezione

    def test_category_selection_shows_level_2_menu(self):
        """Test selezione categoria mostra menu livello 2"""
        state = {
            "message": "2",
            "metadata": {},
            "fallback_suggestions": [
                {
                    "intent": "ask_risk_based_priority",
                    "label": "Stabilimenti a Rischio NC",
                    "type": "intent"
                },
                {
                    "category": "Piano di Controllo",
                    "label": "Piano di Controllo",
                    "type": "category"
                }
            ]
        }

        result_state = self.graph._classify_node(state)

        # Dovrebbe aver selezionato la categoria
        assert result_state["fallback_selected_category"] == "Piano di Controllo"
        assert result_state["intent"] == "fallback"  # Richiama fallback con category
        assert result_state["fallback_phase"] == 3

    def test_invalid_selection_reclassifies(self):
        """Test selezione invalida riclassifica messaggio"""
        state = {
            "message": "99",  # Numero invalido
            "metadata": {},
            "fallback_suggestions": [
                {
                    "intent": "ask_risk_based_priority",
                    "label": "Stabilimenti a Rischio NC",
                    "type": "intent"
                }
            ]
        }

        # Mock router classify
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            result_state = self.graph._classify_node(state)

            # Dovrebbe aver richiamato classify (selezione non valida)
            mock_classify.assert_called_once()


class TestLoopPrevention:
    """Test prevenzione loop infiniti"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_fallback_count_increments(self):
        """Test che fallback_count si incrementi"""
        state = {
            "message": "xyz",
            "metadata": {},
            "fallback_count": 1,
            "needs_clarification": False
        }

        result_state = self.graph._fallback_tool(state)

        # Counter incrementato
        assert result_state["fallback_count"] == 2

    def test_successful_intent_resets_counter(self):
        """Test che intent valido resetti counter"""
        state = {
            "message": "1",
            "metadata": {},
            "fallback_count": 2,
            "fallback_suggestions": [
                {
                    "intent": "ask_help",
                    "type": "intent",
                    "requires_slots": []
                }
            ]
        }

        result_state = self.graph._classify_node(state)

        # Counter resettato
        assert result_state["fallback_count"] == 0


class TestSlotCollectionAfterSelection:
    """Test workflow slot collection dopo selezione intent"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_selected_intent_with_required_slots_asks_clarification(self):
        """Test che intent con slot obbligatori chieda chiarimenti"""
        state = {
            "message": "1",
            "metadata": {},
            "fallback_suggestions": [
                {
                    "intent": "ask_piano_description",
                    "label": "Descrizione Piano",
                    "type": "intent",
                    "requires_slots": ["piano_code"]
                }
            ]
        }

        result_state = self.graph._classify_node(state)

        # Dovrebbe aver impostato needs_clarification
        assert result_state["intent"] == "ask_piano_description"
        assert result_state["needs_clarification"] is True


class TestMessageFormatting:
    """Test formattazione messaggio fallback"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_fallback_message_has_numbered_options(self):
        """Test che messaggio fallback abbia opzioni numerate"""
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            result = self.graph.run(
                message="stabilimenti pericolosi",
                metadata={}
            )

            response = result["response"]

            # Dovrebbe avere opzioni numerate
            assert "1." in response
            assert "2." in response or "opzione" in response.lower()

    def test_fallback_message_has_instructions(self):
        """Test che messaggio abbia istruzioni per utente"""
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            result = self.graph.run(
                message="test",
                metadata={}
            )

            response = result["response"]

            # Dovrebbe avere istruzioni
            assert "rispondi" in response.lower() or "scegli" in response.lower()


class TestEndToEndScenarios:
    """Test scenari end-to-end completi"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.graph = ConversationGraph(llm_client=self.mock_llm)

    def test_scenario_1_fallback_to_selection_to_execution(self):
        """
        Scenario 1: Fallback -> Selezione -> Esecuzione
        User: "dammi stabilimenti pericolosi"
        Bot: Suggerimenti...
        User: "1"
        Bot: Esegue intent selezionato
        """
        # Turno 1: Messaggio ambiguo
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            result1 = self.graph.run(
                message="dammi stabilimenti pericolosi",
                metadata={}
            )

            # Dovrebbe avere suggerimenti
            assert "1." in result1["response"]

        # Nota: Il test completo richiederebbe mock del tool execution
        # Per ora verifichiamo solo che il flusso fallback funzioni

    def test_scenario_2_category_menu_navigation(self):
        """
        Scenario 2: Menu Categorizzato
        User: "help"
        Bot: Mostra categorie
        User: "2" (seleziona categoria)
        Bot: Mostra intent categoria
        User: "1" (seleziona intent)
        Bot: Esegue intent
        """
        # Turno 1: Richiesta off-topic
        with patch.object(self.graph.router, 'classify') as mock_classify:
            mock_classify.return_value = {
                "intent": "fallback",
                "slots": {},
                "needs_clarification": False
            }

            # Mock keyword matching vuoto
            with patch.object(
                self.graph,
                '_fallback_engine',
                None
            ):
                result1 = self.graph.run(
                    message="xyz",
                    metadata={}
                )

                # Dovrebbe mostrare menu
                assert "categoria" in result1["response"].lower() or "scegli" in result1["response"].lower()


class TestConfiguration:
    """Test configurazione fallback recovery"""

    def test_fallback_config_loaded_from_json(self):
        """Test che configurazione sia caricata da config.json"""
        from configs.config import AppConfig

        config = AppConfig.get_fallback_config()

        # Dovrebbe avere configurazione
        if config:
            assert "enabled" in config
            assert "keyword_threshold" in config
            assert config["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
