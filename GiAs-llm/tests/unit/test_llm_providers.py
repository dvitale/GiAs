"""
Test per LLM provider backends.

Verifica:
1. Ogni provider formatta correttamente le request
2. Ogni provider parsa correttamente le response
3. json_mode funziona per ogni provider
4. Il GDPR gate blocca provider esterni senza autorizzazione
5. Il client delega correttamente al provider
6. Backward compatibility con ollama/llamacpp
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open


# ============================================================
# Test OllamaProvider
# ============================================================

class TestOllamaProvider:

    def test_query_request_format(self):
        """Verifica formato request Ollama nativo"""
        from llm.providers import OllamaProvider

        provider = OllamaProvider("llama3.2:3b", {
            "host": "http://localhost:11434",
            "api_endpoint": "/api/chat",
            "health_endpoint": "/api/tags",
            "timeout_seconds": 60
        }, keep_alive=-1)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'message': {'content': '{"intent": "greet"}'}
        }
        mock_response.raise_for_status = MagicMock()

        with patch('llm.providers.requests.post', return_value=mock_response) as mock_post:
            result = provider.query(
                [{'role': 'system', 'content': 'test'}, {'role': 'user', 'content': 'ciao'}],
                temperature=0.1, max_tokens=500, json_mode=True
            )

            # Verifica formato request Ollama
            call_args = mock_post.call_args
            body = call_args.kwargs['json']
            assert body['model'] == 'llama3.2:3b'
            assert body['format'] == 'json'
            assert body['options']['temperature'] == 0.1
            assert body['options']['num_predict'] == 500
            assert body['keep_alive'] == -1
            assert body['stream'] is False

        assert result == '{"intent": "greet"}'

    def test_ping(self):
        """Verifica health check Ollama"""
        from llm.providers import OllamaProvider

        provider = OllamaProvider("llama3.2:3b", {
            "host": "http://localhost:11434",
            "health_endpoint": "/api/tags"
        })

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch('llm.providers.requests.get', return_value=mock_response):
            assert provider.ping() is True

    def test_provider_name(self):
        from llm.providers import OllamaProvider
        provider = OllamaProvider("test", {})
        assert provider.provider_name == "Ollama"


# ============================================================
# Test LlamaCppProvider
# ============================================================

class TestLlamaCppProvider:

    def test_query_request_format(self):
        """Verifica formato request OpenAI-compatible per llama.cpp"""
        from llm.providers import LlamaCppProvider

        provider = LlamaCppProvider("model.gguf", {
            "host": "http://localhost:11435",
            "api_endpoint": "/v1/chat/completions",
            "health_endpoint": "/health",
            "timeout_seconds": 90
        })

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"intent": "greet"}'}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('llm.providers.requests.post', return_value=mock_response) as mock_post:
            result = provider.query(
                [{'role': 'user', 'content': 'ciao'}],
                temperature=0.1, max_tokens=500, json_mode=True
            )

            body = mock_post.call_args.kwargs['json']
            assert body['model'] == 'model.gguf'
            assert body['response_format'] == {'type': 'json_object'}
            assert body['temperature'] == 0.1
            assert body['max_tokens'] == 500
            assert body['stream'] is False

        assert result == '{"intent": "greet"}'

    def test_provider_name(self):
        from llm.providers import LlamaCppProvider
        provider = LlamaCppProvider("test", {})
        assert provider.provider_name == "Llama.cpp"


# ============================================================
# Test OpenAICompatProvider
# ============================================================

class TestOpenAICompatProvider:

    def test_query_with_auth_header(self):
        """Verifica che Authorization header sia presente"""
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "sk-test-123"}):
            from llm.providers import OpenAICompatProvider

            provider = OpenAICompatProvider("mistral-medium-latest", {
                "host": "https://api.mistral.ai",
                "api_endpoint": "/v1/chat/completions",
                "timeout_seconds": 30,
                "api_key_env": "MISTRAL_API_KEY"
            })

            mock_response = MagicMock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': '{"intent": "ask_help"}'}}]
            }
            mock_response.raise_for_status = MagicMock()

            with patch('llm.providers.requests.post', return_value=mock_response) as mock_post:
                result = provider.query(
                    [{'role': 'user', 'content': 'aiuto'}],
                    temperature=0.1, max_tokens=500, json_mode=True
                )

                call_args = mock_post.call_args
                headers = call_args.kwargs['headers']
                assert headers['Authorization'] == 'Bearer sk-test-123'
                body = call_args.kwargs['json']
                assert body['response_format'] == {'type': 'json_object'}

            assert result == '{"intent": "ask_help"}'

    def test_missing_api_key_raises(self):
        """Verifica errore chiaro se API key mancante"""
        with patch.dict(os.environ, {}, clear=True):
            # Rimuovi la key se esiste
            os.environ.pop("GIAS_LLM_API_KEY", None)
            os.environ.pop("MISTRAL_API_KEY", None)

            from llm.providers import OpenAICompatProvider
            with pytest.raises(ValueError, match="API key non trovata"):
                OpenAICompatProvider("model", {
                    "api_key_env": "MISTRAL_API_KEY"
                })

    def test_provider_name(self):
        with patch.dict(os.environ, {"GIAS_LLM_API_KEY": "test"}):
            from llm.providers import OpenAICompatProvider
            provider = OpenAICompatProvider("test", {"api_key_env": "GIAS_LLM_API_KEY"})
            assert provider.provider_name == "OpenAI-Compatible"


# ============================================================
# Test OpenAIProvider (mock SDK)
# ============================================================

class TestOpenAIProvider:

    def test_missing_sdk_raises(self):
        """Verifica errore chiaro se SDK non installato"""
        import sys
        # Simula SDK non installato
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'openai':
                raise ImportError("No module named 'openai'")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
                from llm.providers import OpenAIProvider
                with pytest.raises(ImportError, match="openai"):
                    OpenAIProvider("gpt-4o-mini", {"api_key_env": "OPENAI_API_KEY"})

    def test_missing_api_key_raises(self):
        """Verifica errore chiaro se API key mancante"""
        mock_openai = MagicMock()
        with patch.dict('sys.modules', {'openai': mock_openai}):
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("OPENAI_API_KEY", None)
                from llm.providers import OpenAIProvider
                with pytest.raises(ValueError, match="API key non trovata"):
                    OpenAIProvider("gpt-4o-mini", {"api_key_env": "OPENAI_API_KEY"})


# ============================================================
# Test AnthropicProvider (mock SDK)
# ============================================================

class TestAnthropicProvider:

    def test_system_message_extraction(self):
        """Verifica che il messaggio system venga estratto e passato separatamente"""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"intent": "greet"}')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                from llm.providers import AnthropicProvider
                provider = AnthropicProvider("claude-sonnet-4-20250514", {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "timeout_seconds": 30
                })

                messages = [
                    {'role': 'system', 'content': 'Sei un classificatore.'},
                    {'role': 'user', 'content': 'ciao'}
                ]

                result = provider.query(messages, temperature=0.1, max_tokens=500, json_mode=True)

                # Verifica che system sia passato separatamente
                call_kwargs = mock_client.messages.create.call_args.kwargs
                assert 'system' in call_kwargs
                assert 'classificatore' in call_kwargs['system']
                # Verifica che JSON instruction sia aggiunta al system (json_mode=True)
                assert 'JSON valido' in call_kwargs['system']
                # Verifica che i messaggi non contengano il system message
                msg_roles = [m['role'] for m in call_kwargs['messages']]
                assert 'system' not in msg_roles
                # Verifica prefill assistant per json_mode
                assert call_kwargs['messages'][-1] == {'role': 'assistant', 'content': '{'}

    def test_json_mode_prefill(self):
        """Verifica che json_mode aggiunga prefill '{' e ricostruisca output"""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        # Simula risposta senza '{' iniziale (perche' gia' prefillato)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='"intent": "greet"}')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                from llm.providers import AnthropicProvider
                provider = AnthropicProvider("claude-sonnet-4-20250514", {
                    "api_key_env": "ANTHROPIC_API_KEY"
                })

                result = provider.query(
                    [{'role': 'user', 'content': 'ciao'}],
                    temperature=0.1, max_tokens=500, json_mode=True
                )

                # Il provider deve ricostruire il JSON completo
                assert result.startswith('{')
                assert '"intent"' in result


# ============================================================
# Test GDPR Gate
# ============================================================

class TestGDPRGate:

    def test_gdpr_blocks_external_when_false(self):
        """Verifica che il GDPR gate blocchi provider esterni quando allow_external_llm=false"""
        config_data = json.dumps({
            "llm_backend": {"type": "openai_compat"},
            "gdpr": {"allow_external_llm": False}
        })

        with patch.dict(os.environ, {"GIAS_LLM_BACKEND": "openai_compat", "GIAS_LLM_API_KEY": "test"}):
            with patch('builtins.open', mock_open(read_data=config_data)):
                from llm.client import LLMClient
                # Il client dovrebbe fallire con errore GDPR
                client = LLMClient(use_real_llm=True)
                # Dovrebbe essere caduto in fallback stub
                assert client.use_real_llm is False

    def test_gdpr_allows_local_backends(self):
        """Verifica che il GDPR gate NON si attivi per backend locali"""
        from configs.config import LLMBackendConfig

        with patch.object(LLMBackendConfig, 'get_backend_type', return_value='ollama'):
            assert LLMBackendConfig.is_external_provider() is False

        with patch.object(LLMBackendConfig, 'get_backend_type', return_value='llamacpp'):
            assert LLMBackendConfig.is_external_provider() is False

    def test_external_backends_detected(self):
        """Verifica che tutti i backend esterni siano rilevati"""
        from configs.config import LLMBackendConfig

        for backend in ["openai", "anthropic", "openai_compat"]:
            with patch.object(LLMBackendConfig, 'get_backend_type', return_value=backend):
                assert LLMBackendConfig.is_external_provider() is True


# ============================================================
# Test LLMClient backward compatibility
# ============================================================

class TestLLMClientBackwardCompat:

    def test_stub_mode_unchanged(self):
        """Verifica che use_real_llm=False funzioni come prima"""
        from llm.client import LLMClient

        client = LLMClient(use_real_llm=False)
        assert client.use_real_llm is False
        assert client.ping() is True

        # Test classificazione stub
        result = client.query(
            messages=[
                {'role': 'system', 'content': 'classifica il messaggio intent'},
                {'role': 'user', 'content': 'MESSAGGIO: "ciao"'}
            ]
        )
        data = json.loads(result)
        assert data['intent'] == 'greet'

    def test_stub_streaming(self):
        """Verifica che lo streaming stub funzioni"""
        from llm.client import LLMClient

        client = LLMClient(use_real_llm=False)
        tokens = list(client.query_stream(prompt="classifica il messaggio intent ciao"))
        assert len(tokens) > 0

    def test_query_signature_unchanged(self):
        """Verifica che la firma di query() non sia cambiata"""
        from llm.client import LLMClient
        import inspect

        sig = inspect.signature(LLMClient.query)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'prompt' in params
        assert 'temperature' in params
        assert 'max_tokens' in params
        assert 'messages' in params
        assert 'json_mode' in params
        assert 'timeout' in params

    def test_init_signature_unchanged(self):
        """Verifica che la firma di __init__() non sia cambiata"""
        from llm.client import LLMClient
        import inspect

        sig = inspect.signature(LLMClient.__init__)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'model' in params
        assert 'use_real_llm' in params


# ============================================================
# Test Config Backend Resolution
# ============================================================

class TestConfigBackendResolution:

    def test_valid_backends_include_new(self):
        """Verifica che i nuovi backend siano nella lista VALID_BACKENDS"""
        from configs.config import LLMBackendConfig

        assert "openai" in LLMBackendConfig.VALID_BACKENDS
        assert "anthropic" in LLMBackendConfig.VALID_BACKENDS
        assert "openai_compat" in LLMBackendConfig.VALID_BACKENDS
        # Verificare che quelli vecchi siano ancora presenti
        assert "ollama" in LLMBackendConfig.VALID_BACKENDS
        assert "llamacpp" in LLMBackendConfig.VALID_BACKENDS

    def test_env_var_priority(self):
        """Verifica che la variabile ambiente abbia priorita' sul config.json"""
        from configs.config import LLMBackendConfig

        with patch.dict(os.environ, {"GIAS_LLM_BACKEND": "openai"}):
            assert LLMBackendConfig.get_backend_type() == "openai"

    def test_get_api_key_returns_none_for_local(self):
        """Verifica che get_api_key ritorni None per backend locali"""
        from configs.config import LLMBackendConfig

        with patch.object(LLMBackendConfig, 'get_backend_type', return_value='ollama'):
            assert LLMBackendConfig.get_api_key() is None

    def test_get_api_key_reads_env(self):
        """Verifica che get_api_key legga dalla variabile ambiente configurata"""
        from configs.config import LLMBackendConfig

        with patch.object(LLMBackendConfig, 'get_backend_type', return_value='openai'):
            with patch.object(LLMBackendConfig, 'get_backend_config', return_value={"api_key_env": "OPENAI_API_KEY"}):
                with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-abc"}):
                    assert LLMBackendConfig.get_api_key() == "sk-test-abc"


# ============================================================
# Test Provider Base Class
# ============================================================

class TestProviderBase:

    def test_abstract_methods_enforced(self):
        """Verifica che non si possa istanziare LLMProvider direttamente"""
        from llm.provider_base import LLMProvider

        with pytest.raises(TypeError):
            LLMProvider("model", {})
