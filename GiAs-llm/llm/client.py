import json
import logging
from typing import Optional, Generator
import sys
import os

logger = logging.getLogger(__name__)

import requests

# Aggiungi il path per importare config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configs.config import AppConfig, LLMBackendConfig


class LLMClient:
    """
    Configurable LLM client supporting multiple backends.
    Uses the Strategy Pattern to delegate to provider implementations.

    Backends supported:
    - Ollama: API /api/chat (Ollama native format)
    - Llama.cpp: API /v1/chat/completions (OpenAI-compatible format)
    - OpenAI: API via SDK (GPT-4o, GPT-4o-mini)
    - Anthropic: API via SDK (Claude Sonnet, Haiku)
    - OpenAI-Compatible: Generic /v1/chat/completions with API key (Mistral, Groq, etc.)
    - OpenRouter: OpenRouter.ai aggregator (OpenAI-compatible protocol)
    """

    def __init__(self, model: str = None, use_real_llm: bool = True):
        """
        Initialize LLM client with configurable backend and model.

        Args:
            model: Model name (if None, uses config default)
            use_real_llm: If False, falls back to stub (for testing)
        """
        # Determina backend dalla configurazione
        self.backend_type = LLMBackendConfig.get_backend_type()
        self.backend_config = LLMBackendConfig.get_backend_config()

        # Usa il modello dalla configurazione se non specificato
        if model is None:
            if self.backend_type == "llamacpp":
                model = self.backend_config.get("model_name", "Llama-3.2-3B-Instruct-Q6_K_L.gguf")
                model_key = "llamacpp"
            elif self.backend_type in ("openai", "anthropic", "openai_compat", "openrouter"):
                model = self.backend_config.get("model", "gpt-4o-mini")
                model_key = "external"
            else:
                model = AppConfig.get_model_name()
                model_key = AppConfig.LLM_MODEL
        else:
            model_key = "custom"

        self.model = model
        self.model_key = model_key
        self.use_real_llm = use_real_llm
        self.base_url = self.backend_config.get("host", "http://localhost:11435")
        self.api_endpoint = self.backend_config.get("api_endpoint", "/v1/chat/completions")
        self.health_endpoint = self.backend_config.get("health_endpoint", "/health")
        # Usa timeout specifico del backend, fallback al timeout globale
        self.timeout = self.backend_config.get("timeout_seconds", AppConfig.LLM_TIMEOUT_SECONDS)

        self._provider = None

        if use_real_llm:
            try:
                # GDPR check per provider esterni
                if LLMBackendConfig.is_external_provider():
                    self._check_gdpr_consent()

                self._provider = self._create_provider()
                backend_name = self._provider.provider_name
                if model_key not in ("custom", "llamacpp", "external"):
                    model_info = AppConfig.get_model_info()
                else:
                    model_info = {"description": f"Model: {model}"}

                logger.info(f"LLM Client initialized with backend: {backend_name}")
                logger.info(f"   URL: {self.base_url}")
                logger.info(f"   Model: {model}")
                logger.info(f"   {model_info.get('description', '')}")
            except Exception as e:
                logger.warning(f"{self.backend_type} not available ({e}), falling back to stub")
                self.use_real_llm = False
                self._provider = None

    def _create_provider(self):
        """Factory method: creates the appropriate provider backend."""
        from .providers import (
            OllamaProvider, LlamaCppProvider,
            OpenAIProvider, AnthropicProvider, OpenAICompatProvider
        )

        if self.backend_type == "ollama":
            provider = OllamaProvider(
                self.model, self.backend_config,
                keep_alive=AppConfig.KEEP_ALIVE_DURATION
            )
        elif self.backend_type == "llamacpp":
            provider = LlamaCppProvider(self.model, self.backend_config)
        elif self.backend_type == "openai":
            provider = OpenAIProvider(self.model, self.backend_config)
        elif self.backend_type == "anthropic":
            provider = AnthropicProvider(self.model, self.backend_config)
        elif self.backend_type in ("openai_compat", "openrouter"):
            provider = OpenAICompatProvider(self.model, self.backend_config)
        else:
            raise ValueError(f"Backend LLM non supportato: {self.backend_type}")

        # Verifica disponibilita' (ping)
        if not provider.ping():
            raise ConnectionError(f"{provider.provider_name} non raggiungibile")

        return provider

    def _check_gdpr_consent(self):
        """Verifica che l'uso di provider esterni sia esplicitamente autorizzato in config."""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "configs", "config.json"
            )
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            allowed = config.get("gdpr", {}).get("allow_external_llm", False)
            if not allowed:
                raise ValueError(
                    "⛔ Provider LLM esterno configurato ma gdpr.allow_external_llm e' False in config.json. "
                    "I dati delle query verrebbero inviati a server esterni. "
                    "Impostare a True solo dopo aver verificato la conformita' GDPR con le normative "
                    "della Regione Campania per il trattamento dei dati sanitari veterinari."
                )
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Nessun config file, consenti (modalita' sviluppo)

    def query(self, prompt: str = None, temperature: float = None, max_tokens: int = None,
              messages: list = None, json_mode: bool = False, timeout: float = None) -> str:
        """
        Query the LLM with a prompt using configured defaults.

        Args:
            prompt: The prompt to send to the LLM (used if messages is None)
            temperature: Sampling temperature (uses config default if None)
            max_tokens: Maximum tokens in response (uses config default if None)
            messages: List of {role, content} dicts as alternative to prompt
            json_mode: If True, requests JSON output (Ollama: format:"json", Llama.cpp: response_format)
            timeout: Override timeout for this specific call (seconds)

        Returns:
            String response from LLM
        """
        if not self.use_real_llm:
            # Concatenate all message contents for stub matching
            if messages:
                effective_prompt = '\n'.join(m.get('content', '') for m in messages)
            else:
                effective_prompt = prompt or ''
            return self._fallback_stub(effective_prompt)

        # Usa valori di default dalla configurazione
        if temperature is None:
            temperature = AppConfig.RESPONSE_GENERATION_TEMPERATURE
        if max_tokens is None:
            max_tokens = AppConfig.MAX_TOKENS

        # Build messages: use explicit messages list or wrap prompt
        effective_messages = messages or [{'role': 'user', 'content': prompt}]

        try:
            return self._provider.query(
                effective_messages, temperature, max_tokens,
                json_mode=json_mode,
                timeout=timeout
            )
        except requests.exceptions.Timeout:
            logger.error(f"LLM query timeout after {self.timeout}s")
            fallback_prompt = '\n'.join(m.get('content', '') for m in effective_messages) if effective_messages else (prompt or '')
            return self._fallback_stub(fallback_prompt)
        except Exception as e:
            logger.error(f"LLM query error: {e}, falling back to stub")
            fallback_prompt = '\n'.join(m.get('content', '') for m in effective_messages) if effective_messages else (prompt or '')
            return self._fallback_stub(fallback_prompt)

    def _fallback_stub(self, prompt: str) -> str:
        """Fallback stub: delega a fallback_classifier."""
        from .fallback_classifier import classify, generate_response

        if not prompt:
            return "Errore: nessun prompt fornito allo stub LLM"

        prompt_lower = prompt.lower()

        if "classifica il messaggio" in prompt_lower or "intent" in prompt_lower:
            return classify(prompt)

        if "genera una risposta" in prompt_lower or "spiega i risultati" in prompt_lower:
            return generate_response(prompt)

        return "Questa è una risposta stub dal LLM. Implementare il client reale."

    def query_stream(self, prompt: str = None, temperature: float = None, max_tokens: int = None,
                     messages: list = None, json_mode: bool = False, timeout: float = None):
        """
        Query the LLM with streaming response (yields tokens as they arrive).

        Args:
            prompt: The prompt to send to the LLM (used if messages is None)
            temperature: Sampling temperature (uses config default if None)
            max_tokens: Maximum tokens in response (uses config default if None)
            messages: List of {role, content} dicts as alternative to prompt
            json_mode: If True, requests JSON output (Ollama: format:"json", Llama.cpp: response_format)
            timeout: Override timeout for this specific call (seconds)

        Yields:
            String tokens from LLM as they arrive
        """
        if not self.use_real_llm:
            # Fallback stub per streaming non supportato
            full_response = self._fallback_stub(prompt or '\n'.join(m.get('content', '') for m in (messages or [])))
            # Simula streaming dividendo in token
            words = full_response.split()
            for word in words:
                yield word + " "
            return

        # Usa valori di default dalla configurazione
        if temperature is None:
            temperature = AppConfig.RESPONSE_GENERATION_TEMPERATURE
        if max_tokens is None:
            max_tokens = AppConfig.MAX_TOKENS

        # Build messages: use explicit messages list or wrap prompt
        effective_messages = messages or [{'role': 'user', 'content': prompt}]

        try:
            yield from self._provider.query_stream(
                effective_messages, temperature, max_tokens,
                json_mode=json_mode,
                timeout=timeout
            )
        except requests.exceptions.Timeout:
            logger.error(f"LLM streaming timeout after {timeout or self.timeout}s")
            return
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            return

    def supports_tool_calling(self) -> bool:
        """Return True if the underlying provider supports native tool calling."""
        if not self.use_real_llm or self._provider is None:
            return False
        return self._provider.supports_tool_calling()

    def query_with_tools(self, messages: list, tools: list,
                         temperature: float = None, max_tokens: int = None,
                         timeout: float = None, tool_choice: str = None) -> dict:
        """Facade for tool-calling requests. Returns the normalized provider dict
        {content, tool_calls, finish_reason}. Raises if the provider does not
        support tool calling or the LLM is unavailable.
        """
        if not self.use_real_llm or self._provider is None:
            raise RuntimeError("LLM not available, cannot call tools")
        if temperature is None:
            temperature = AppConfig.CLASSIFICATION_TEMPERATURE
        if max_tokens is None:
            max_tokens = AppConfig.MAX_TOKENS
        return self._provider.query_with_tools(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tool_choice=tool_choice,
        )

    def ping(self) -> bool:
        """
        Health check for LLM availability.

        Returns:
            True if LLM is available and responding
        """
        if not self.use_real_llm:
            return True

        if self._provider:
            return self._provider.ping()
        return False
