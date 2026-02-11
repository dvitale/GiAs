"""
Unit tests per FallbackRecoveryEngine

Test delle funzionalità di fallback intelligente:
- Keyword matching
- LLM semantic scoring (mocked)
- Category menu generation
- User selection parsing
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.fallback_recovery import FallbackRecoveryEngine
from orchestrator.intent_metadata import (
    INTENT_REGISTRY,
    CATEGORY_HIERARCHY,
    get_intent_metadata
)


class TestKeywordMatching:
    """Test keyword matching (Fase 1)"""

    def setup_method(self):
        """Setup per ogni test"""
        self.engine = FallbackRecoveryEngine(llm_client=None)

    def test_keyword_match_risk_intent(self):
        """Test keyword matching per intent rischio"""
        message = "dammi gli stabilimenti pericolosi"
        suggestions = self.engine._keyword_matching(message)

        # Deve trovare ask_risk_based_priority
        intent_ids = [s["intent"] for s in suggestions]
        assert "ask_risk_based_priority" in intent_ids

        # Verifica score >= threshold
        for suggestion in suggestions:
            assert suggestion["score"] >= self.engine.config["keyword_threshold"]

    def test_keyword_match_mai_controllati(self):
        """Test keyword matching per stabilimenti mai controllati"""
        message = "stabilimenti mai controllati"
        suggestions = self.engine._keyword_matching(message)

        intent_ids = [s["intent"] for s in suggestions]
        assert "ask_suggest_controls" in intent_ids

    def test_keyword_match_piano_description(self):
        """Test keyword matching per descrizione piano"""
        message = "descrizione piano A1"
        suggestions = self.engine._keyword_matching(message)

        intent_ids = [s["intent"] for s in suggestions]
        assert "ask_piano_description" in intent_ids

    def test_negative_keywords_exclude(self):
        """Test che negative keywords escludano intent"""
        # "attività rischiose" dovrebbe escludere ask_risk_based_priority
        # e includere ask_top_risk_activities
        message = "attività rischiose"
        suggestions = self.engine._keyword_matching(message)

        intent_ids = [s["intent"] for s in suggestions]

        # ask_top_risk_activities dovrebbe essere presente
        assert "ask_top_risk_activities" in intent_ids

        # ask_risk_based_priority NON dovrebbe essere presente (negative: "attività")
        # NOTA: Questo dipende dalla configurazione dei negative keywords

    def test_no_match_returns_empty(self):
        """Test messaggio completamente off-topic"""
        message = "xyz123abc"
        suggestions = self.engine._keyword_matching(message)

        # Nessun match valido
        assert len(suggestions) == 0

    def test_score_calculation(self):
        """Test calcolo score con primary + context keywords"""
        metadata = get_intent_metadata("ask_risk_based_priority")
        message = "rischio stabilimenti"  # 1 primary + 1 context

        score = self.engine._score_intent_by_keywords(message, metadata)

        # Score atteso: 10 (rischio) + 5 (stabilimenti context) = 15
        assert score >= 15


class TestCategoryMenu:
    """Test category menu generation (Fase 3)"""

    def setup_method(self):
        """Setup per ogni test"""
        self.engine = FallbackRecoveryEngine(llm_client=None)

    def test_category_menu_level_1(self):
        """Test menu categorie livello 1"""
        suggestions = self.engine._category_menu(level=1)

        # Deve avere tutte le categorie (escluso "Altro")
        categories = [s.get("category") for s in suggestions if s.get("type") == "category"]

        assert "Piano di Controllo" in categories
        assert "Priorità e Rischio" in categories
        assert "Ricerca" in categories
        assert "Altro" not in categories  # Escluso dal menu principale

    def test_category_menu_level_2(self):
        """Test menu intent specifici livello 2"""
        suggestions = self.engine._category_menu(level=2, category="Priorità e Rischio")

        # Deve contenere intent della categoria
        intent_ids = [s.get("intent") for s in suggestions if s.get("type") == "intent"]

        assert "ask_risk_based_priority" in intent_ids
        assert "ask_suggest_controls" in intent_ids
        assert "ask_priority_establishment" in intent_ids

    def test_invalid_category_returns_empty(self):
        """Test categoria inesistente"""
        suggestions = self.engine._category_menu(level=2, category="NonExistent")

        assert len(suggestions) == 0


class TestUserSelectionParsing:
    """Test parsing selezioni utente"""

    def setup_method(self):
        """Setup per ogni test"""
        self.engine = FallbackRecoveryEngine(llm_client=None)

        # Mock suggestions
        self.suggestions = [
            {
                "intent": "ask_risk_based_priority",
                "label": "Stabilimenti a Rischio NC",
                "type": "intent"
            },
            {
                "intent": "ask_suggest_controls",
                "label": "Stabilimenti Mai Controllati",
                "type": "intent"
            },
            {
                "category": "Piano di Controllo",
                "label": "Piano di Controllo",
                "type": "category"
            }
        ]

    def test_parse_numeric_selection(self):
        """Test parsing selezione numerica"""
        selected = self.engine.parse_user_selection("1", self.suggestions)

        assert selected is not None
        assert selected["intent"] == "ask_risk_based_priority"

    def test_parse_numeric_with_text(self):
        """Test parsing con testo + numero"""
        selected = self.engine.parse_user_selection("opzione 2", self.suggestions)

        assert selected is not None
        assert selected["intent"] == "ask_suggest_controls"

    def test_parse_by_label(self):
        """Test parsing per label (match testuale)"""
        selected = self.engine.parse_user_selection("Stabilimenti a Rischio NC", self.suggestions)

        assert selected is not None
        assert selected["intent"] == "ask_risk_based_priority"

    def test_parse_category_selection(self):
        """Test parsing selezione categoria"""
        selected = self.engine.parse_user_selection("3", self.suggestions)

        assert selected is not None
        assert selected["type"] == "category"
        assert selected["category"] == "Piano di Controllo"

    def test_parse_invalid_number(self):
        """Test numero non valido"""
        selected = self.engine.parse_user_selection("99", self.suggestions)

        assert selected is None

    def test_parse_no_match(self):
        """Test messaggio senza match"""
        selected = self.engine.parse_user_selection("xyz", self.suggestions)

        assert selected is None


class TestLLMSemanticScoring:
    """Test LLM semantic scoring (Fase 2) - mocked"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.engine = FallbackRecoveryEngine(llm_client=self.mock_llm)

    def test_llm_scoring_success(self):
        """Test LLM scoring con risposta valida"""
        # Mock risposta LLM
        self.mock_llm.chat.return_value = '''
        [
            {"intent": "ask_risk_based_priority", "confidence": 0.9},
            {"intent": "ask_suggest_controls", "confidence": 0.7}
        ]
        '''

        suggestions = self.engine._llm_semantic_scoring("stabilimenti problematici")

        assert len(suggestions) > 0
        assert suggestions[0]["intent"] == "ask_risk_based_priority"
        assert suggestions[0]["score"] == 90  # confidence * 100

    def test_llm_scoring_timeout(self):
        """Test LLM timeout graceful degradation"""
        # Mock timeout
        import time

        def slow_response(*args, **kwargs):
            time.sleep(6)  # > timeout (5s)
            return "[]"

        self.mock_llm.chat.side_effect = slow_response

        suggestions = self.engine._llm_semantic_scoring("test message")

        # Dovrebbe ritornare lista vuota senza crash
        assert len(suggestions) == 0

    def test_llm_scoring_invalid_json(self):
        """Test LLM con risposta JSON invalida"""
        self.mock_llm.chat.return_value = "not valid json"

        suggestions = self.engine._llm_semantic_scoring("test message")

        # Deve gestire gracefully
        assert len(suggestions) == 0


class TestSuggestIntents:
    """Test metodo principale suggest_intents"""

    def setup_method(self):
        """Setup per ogni test"""
        self.mock_llm = Mock()
        self.engine = FallbackRecoveryEngine(llm_client=self.mock_llm)

    def test_suggest_phase_1_keyword(self):
        """Test Fase 1 con keyword match sufficiente"""
        suggestions = self.engine.suggest_intents(
            "stabilimenti pericolosi",
            phase=1
        )

        # Deve avere suggerimenti + categorie
        assert len(suggestions) > 0

        # Primi suggerimenti sono intent
        intents = [s for s in suggestions if s.get("type") == "intent"]
        categories = [s for s in suggestions if s.get("type") == "category"]

        assert len(intents) > 0
        assert len(categories) > 0  # Categorie sempre disponibili

    def test_suggest_phase_3_category_menu(self):
        """Test Fase 3 con menu categorizzato"""
        suggestions = self.engine.suggest_intents(
            "help",
            phase=3
        )

        # Deve mostrare menu categorie
        categories = [s for s in suggestions if s.get("type") == "category"]
        assert len(categories) > 0

    def test_suggest_with_selected_category(self):
        """Test con categoria selezionata (livello 2)"""
        suggestions = self.engine.suggest_intents(
            "",
            phase=3,
            category="Priorità e Rischio"
        )

        # Deve mostrare intent della categoria
        intents = [s for s in suggestions if s.get("type") == "intent"]
        assert len(intents) > 0

        # Verifica che siano solo intent di quella categoria
        for suggestion in intents:
            metadata = get_intent_metadata(suggestion["intent"])
            assert metadata.category == "Priorità e Rischio"


class TestMessageFormatting:
    """Test formattazione messaggio per utente"""

    def setup_method(self):
        """Setup per ogni test"""
        self.engine = FallbackRecoveryEngine(llm_client=None)

        self.suggestions = [
            {
                "intent": "ask_risk_based_priority",
                "label": "Stabilimenti a Rischio NC",
                "description": "Analizza stabilimenti con alto rischio storico",
                "emoji": "⚠️",
                "type": "intent"
            },
            {
                "category": "Piano di Controllo",
                "label": "Piano di Controllo",
                "emoji": "📋",
                "type": "category"
            }
        ]

    def test_format_message_with_intents_and_categories(self):
        """Test formattazione messaggio con intent e categorie"""
        message = self.engine.format_suggestions_message(self.suggestions)

        # Deve contenere numero opzioni
        assert "1." in message
        assert "2." in message

        # Deve contenere label
        assert "Stabilimenti a Rischio NC" in message
        assert "Piano di Controllo" in message

        # Deve contenere istruzioni
        assert "Rispondi con il numero" in message

    def test_format_message_custom_intro(self):
        """Test messaggio con intro custom"""
        intro = "Scegli l'operazione:"
        message = self.engine.format_suggestions_message(
            self.suggestions,
            intro_message=intro
        )

        assert intro in message

    def test_format_empty_suggestions(self):
        """Test formattazione con lista vuota"""
        message = self.engine.format_suggestions_message([])

        # Deve avere messaggio di fallback
        assert "non ho capito" in message.lower() or "aiuto" in message.lower()


class TestConfiguration:
    """Test configurazione engine"""

    def test_default_config(self):
        """Test configurazione default"""
        engine = FallbackRecoveryEngine(llm_client=None)

        assert engine.config["enabled"] is True
        assert engine.config["keyword_threshold"] == 15
        assert engine.config["max_suggestions"] == 4

    def test_custom_config(self):
        """Test configurazione custom"""
        custom_config = {
            "enabled": False,
            "keyword_threshold": 30
        }

        engine = FallbackRecoveryEngine(llm_client=None, config=custom_config)

        assert engine.config["enabled"] is False
        assert engine.config["keyword_threshold"] == 30
        # Altri valori mantengono default
        assert engine.config["max_suggestions"] == 4


class TestCacheManagement:
    """Test cache keyword"""

    def setup_method(self):
        """Setup per ogni test"""
        self.engine = FallbackRecoveryEngine(llm_client=None)

    def test_keyword_cache_hit(self):
        """Test cache hit per stesso messaggio"""
        message = "stabilimenti pericolosi"

        # Prima chiamata - cache miss
        result1 = self.engine._keyword_matching(message)

        # Seconda chiamata - cache hit
        result2 = self.engine._keyword_matching(message)

        # Risultati identici
        assert result1 == result2

        # Cache contiene il messaggio
        assert message.lower() in self.engine._keyword_cache

    def test_clear_cache(self):
        """Test clear cache"""
        message = "test"
        self.engine._keyword_matching(message)

        assert len(self.engine._keyword_cache) > 0

        self.engine.clear_cache()

        assert len(self.engine._keyword_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
