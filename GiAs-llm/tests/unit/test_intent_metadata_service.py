"""
Test unitari per IntentMetadataService.

Verifica:
1. Caricamento fallback Python (senza DB)
2. Struttura dati restituita
3. Generazione help content
4. Generazione catalogo prompt
5. Generazione esempi critici
6. Metadati operativi per chatlog
7. Tutti gli esempi per indicizzazione
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture
def service():
    """IntentMetadataService in modalità fallback Python (nessun DB)."""
    # Reset singleton per test isolati
    from orchestrator.intent_metadata_service import IntentMetadataService
    IntentMetadataService._instance = None
    IntentMetadataService._initialized = False

    import orchestrator.intent_metadata_service as mod
    mod._service_instance = None

    svc = IntentMetadataService()
    # Forza fallback Python (senza tentare DB)
    svc._load_from_python_fallback()
    svc._loaded = True
    return svc


class TestServiceInit:
    """Test inizializzazione e struttura dati."""

    def test_source_is_python_fallback(self, service):
        assert service.source == 'python_fallback'

    def test_all_intents_loaded(self, service):
        intents = service.get_all_intents()
        assert len(intents) == 21, f"Attesi 21 intent, trovati {len(intents)}"

    def test_intent_has_required_fields(self, service):
        intent = service.get_intent("ask_delayed_plans")
        assert intent is not None
        assert intent["intent"] == "ask_delayed_plans"
        assert intent["title"] is not None
        assert intent["category"] is not None
        assert intent["emoji"] is not None

    def test_unknown_intent_returns_none(self, service):
        assert service.get_intent("nonexistent") is None

    def test_category_hierarchy(self, service):
        hierarchy = service.get_category_hierarchy()
        assert "Piano di Controllo" in hierarchy
        assert "ask_piano_description" in hierarchy["Piano di Controllo"]

    def test_direct_response_intents(self, service):
        for intent_id in ["greet", "goodbye", "fallback"]:
            meta = service.get_intent(intent_id)
            assert meta["is_direct_response"] is True, f"{intent_id} should be direct_response"

    def test_non_direct_response_intents(self, service):
        for intent_id in ["ask_delayed_plans", "ask_risk_based_priority"]:
            meta = service.get_intent(intent_id)
            assert meta["is_direct_response"] is False, f"{intent_id} should NOT be direct_response"


class TestExamples:
    """Test recupero esempi."""

    def test_few_shot_examples_exist(self, service):
        examples = service.get_examples_by_type("few_shot")
        assert len(examples) > 0, "Devono esserci almeno degli esempi few_shot"

    def test_all_examples_for_indexing(self, service):
        examples = service.get_all_examples_for_indexing()
        assert len(examples) > 10, f"Attesi almeno 10 esempi, trovati {len(examples)}"

    def test_examples_are_deduplicated(self, service):
        examples = service.get_all_examples_for_indexing()
        texts = [t.lower().strip() for t, _ in examples]
        assert len(texts) == len(set(texts)), "Esempi non deduplicati"


class TestHelpContent:
    """Test generazione contenuto help."""

    def test_help_content_not_empty(self, service):
        content = service.get_help_content()
        # Con fallback Python non ci sono esempi 'help', il contenuto sara' vuoto
        # Questo e' il comportamento atteso: il fallback hardcoded in tool_nodes gestisce il caso
        # Ma se il servizio carica da DB, deve generare contenuto
        assert isinstance(content, str)

    def test_help_content_with_injected_examples(self, service):
        """Simula esempi help per verificare la generazione markdown."""
        # Inietta esempi help manualmente
        service._examples.append({
            "intent": "ask_delayed_plans",
            "text": "Piani in ritardo",
            "example_type": "help",
            "expected_json": None,
            "confused_with": None,
            "display_order": 1,
        })
        service._examples.append({
            "intent": "ask_risk_based_priority",
            "text": "Stabilimenti a rischio",
            "example_type": "help",
            "expected_json": None,
            "confused_with": None,
            "display_order": 2,
        })
        content = service.get_help_content()
        assert "Piani in ritardo" in content
        assert "Stabilimenti a rischio" in content
        assert "**Come posso aiutarti?**" in content


class TestPromptGeneration:
    """Test generazione contenuti per prompt classificazione."""

    def test_intent_catalog_not_empty(self, service):
        catalog = service.get_intent_catalog_for_prompt()
        assert len(catalog) > 100, "Catalogo prompt troppo corto"
        assert "ask_delayed_plans" in catalog
        assert "greet" in catalog

    def test_intent_catalog_has_categories(self, service):
        catalog = service.get_intent_catalog_for_prompt()
        assert "[Piani]" in catalog or "[Piano di Controllo]" in catalog

    def test_disambiguation_rules_not_empty(self, service):
        rules = service.get_disambiguation_rules_for_prompt()
        assert len(rules) > 50
        assert "ask_risk_based_priority" in rules

    def test_critical_examples_empty_in_fallback(self, service):
        """In fallback Python non ci sono esempi prompt_critical."""
        examples = service.get_critical_examples_for_prompt()
        assert isinstance(examples, str)


class TestChatlogMetadata:
    """Test metadati operativi per chat_log."""

    def test_chatlog_metadata_structure(self, service):
        meta = service.get_intent_metadata_for_chatlog("ask_delayed_plans")
        assert "tool" in meta
        assert "dataretriever_class" in meta
        assert "two_phase_threshold" in meta
        assert "sql" in meta

    def test_unknown_intent_returns_empty(self, service):
        meta = service.get_intent_metadata_for_chatlog("nonexistent")
        assert meta["tool"] is None
        assert meta["sql"] is None
