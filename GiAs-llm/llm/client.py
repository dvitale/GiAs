import json
import re
from typing import Optional, Generator
import sys
import os

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
            elif self.backend_type in ("openai", "anthropic", "openai_compat"):
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

                print(f"✅ LLM Client initialized with backend: {backend_name}")
                print(f"   🔌 URL: {self.base_url}")
                print(f"   🤖 Model: {model}")
                print(f"   📝 {model_info.get('description', '')}")
            except Exception as e:
                print(f"⚠️ Warning: {self.backend_type} not available ({e}), falling back to stub")
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
        elif self.backend_type == "openai_compat":
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
            print(f"❌ LLM query timeout after {self.timeout}s")
            return self._fallback_stub(prompt)
        except Exception as e:
            print(f"❌ LLM query error: {e}")
            print(f"Falling back to stub for this request")
            return self._fallback_stub(prompt)

    def _fallback_stub(self, prompt: str) -> str:
        """
        Fallback stub implementation (same as original client.py).
        Used when Ollama is not available.
        """
        # Handle None or empty prompt
        if not prompt:
            return "Errore: nessun prompt fornito allo stub LLM"

        prompt_lower = prompt.lower()

        if "classifica il messaggio" in prompt_lower or "intent" in prompt_lower:
            return self._mock_classification(prompt)

        if "genera una risposta" in prompt_lower or "spiega i risultati" in prompt_lower:
            return self._mock_response_generation(prompt)

        return "Questa è una risposta stub dal LLM. Implementare il client reale."

    def _mock_classification(self, prompt: str) -> str:
        """Mock intent classification basato su pattern nel prompt"""

        # Handle None prompt
        if not prompt:
            return json.dumps({"intent": "fallback", "slots": {}, "needs_clarification": True})

        prompt_lower = prompt.lower()

        # Try both prompt formats: old (**messaggio utente:**) and new (MESSAGGIO:)
        user_message_match = re.search(r'\*\*messaggio utente:\*\*\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
        if not user_message_match:
            user_message_match = re.search(r'messaggio:\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
        if user_message_match:
            user_message = user_message_match.group(1).strip()
        else:
            user_message = prompt_lower

        if re.match(r'^\s*(ciao|salve|buongiorno|buonasera|buonanotte|buondì|buon\s*pomeriggio|'
                    r'hello|hey|hi|ehilà|ehi|eccomi|ben\s*trovato|ben\s*tornato|come\s*(stai|va))\s*[!.?]?\s*$', user_message):
            return json.dumps({
                "intent": "greet",
                "slots": {},
                "needs_clarification": False
            })

        if any(word in user_message for word in ["aiuto", "help", "che domande", "cosa sai", "cosa posso", "come posso", "come puoi"]):
            return json.dumps({
                "intent": "ask_help",
                "slots": {},
                "needs_clarification": False
            })

        if re.match(r'^\s*(arrivederci|addio|bye|ciao\s*ciao|tanti\s*saluti|'
                    r'alla\s*prossima|ci\s*vediamo|a\s*domani|stammi?\s*bene)\s*[!.?]?\s*$', user_message):
            return json.dumps({
                "intent": "goodbye",
                "slots": {},
                "needs_clarification": False
            })

        # Confirm/Decline details (two-phase flow)
        if re.match(r'^\s*(s[ìi]|yes|ok|va bene|mostra|dettagli|tutti)\s*[!.?]?\s*$', user_message):
            return json.dumps({
                "intent": "confirm_show_details",
                "slots": {},
                "needs_clarification": False
            })

        if re.match(r'^\s*(no|non|niente|basta|va bene cos[ìi])\s*[!.?]?\s*$', user_message):
            return json.dumps({
                "intent": "decline_show_details",
                "slots": {},
                "needs_clarification": False
            })

        piano_match = re.search(r'\b([A-F]\d{1,2}(?:_[A-Z0-9]+)?)\b', user_message, re.IGNORECASE)
        piano_code = piano_match.group(1).upper() if piano_match else None

        # Check ritardo con piano specifico → check_if_plan_delayed
        if piano_code and any(word in user_message for word in ["ritardo", "ritardi", "in ritardo", "è in ritardo", "scadut"]):
            return json.dumps({
                "intent": "check_if_plan_delayed",
                "slots": {"piano_code": piano_code},
                "needs_clarification": False
            })

        if piano_code:
            if any(word in user_message for word in ["descrizione", "descrivi", "cos'è", "cosa è", "di cosa tratta", "cosa tratta"]):
                return json.dumps({
                    "intent": "ask_piano_description",
                    "slots": {"piano_code": piano_code},
                    "needs_clarification": False
                })

            if any(word in user_message for word in ["stabilimenti", "dove", "applicazione", "applica"]):
                return json.dumps({
                    "intent": "ask_piano_stabilimenti",
                    "slots": {"piano_code": piano_code},
                    "needs_clarification": False
                })

            return json.dumps({
                "intent": "ask_piano_stabilimenti",
                "slots": {"piano_code": piano_code},
                "needs_clarification": False
            })

        if any(word in user_message for word in ["priorità", "per primo", "prima", "urgenti", "controllare subito"]):
            return json.dumps({
                "intent": "ask_priority_establishment",
                "slots": {},
                "needs_clarification": False
            })

        if any(word in user_message for word in ["rischio", "non conformità", "nc", "pericolosi", "alto rischio"]):
            return json.dumps({
                "intent": "ask_risk_based_priority",
                "slots": {},
                "needs_clarification": False
            })

        if any(word in user_message for word in ["ritardo", "ritardi", "programmati", "in ritardo"]):
            return json.dumps({
                "intent": "ask_delayed_plans",
                "slots": {},
                "needs_clarification": False
            })

        if any(word in user_message for word in ["cerca", "ricerca", "trova piani", "piani che", "quali piani", "quali sono i piani", "piani di", "piani per", "piani sul", "piani riguardanti", "piani relativi"]):
            topic_words = []

            keywords = [
                "bovini", "bovino", "vacche", "vitelli", "bufalini", "bufale", "bufala",
                "suini", "suino", "maiali", "porci", "scrofe", "scrofa", "verri", "verro", "suinetti",
                "ovini", "ovino", "pecore", "agnelli", "arieti",
                "caprini", "caprino", "capre", "capretti",
                "avicoli", "avicolo", "polli", "pollame", "galline", "tacchini", "oche", "anatre",
                "equini", "equino", "cavalli", "asini", "muli",
                "latte", "lattiero", "caseario", "latticini",
                "carne", "macellazione", "macello", "carni",
                "mangimi", "mangime", "alimentazione",
                "allevamenti", "allevamento", "zootecniche", "zootecnia", "zootecnico",
                "benessere", "biosicurezza",
                "salmonella", "residui", "farmaco", "farmaci",
                "api", "apicoltura", "miele",
                "acquacoltura", "ittico", "pesca", "pesci",
                "cani", "gatti", "randagismo", "canile",
                "selvaggina", "selvatici", "cinghiali",
            ]

            for word in keywords:
                if word in user_message:
                    topic_words.append(word)

            slots = {"topic": " ".join(topic_words)} if topic_words else {}
            return json.dumps({
                "intent": "search_piani_by_topic",
                "slots": slots,
                "needs_clarification": False
            })

        return json.dumps({
            "intent": "fallback",
            "slots": {},
            "needs_clarification": True
        })

    def _mock_response_generation(self, prompt: str) -> str:
        """Mock response generation - estrae formatted_response dal prompt o genera risposta generica"""

        # Handle None prompt
        if not prompt:
            return "Ciao! Come posso aiutarti con i piani di monitoraggio veterinario?"

        formatted_match = re.search(r'\*\*RISULTATI OTTENUTI:\*\*\s*\{[^}]*["\']formatted_response["\']:\s*["\']([^"\']+)["\']', prompt, re.DOTALL)
        if formatted_match:
            formatted_text = formatted_match.group(1)
            return formatted_text[:2000]

        data_section = re.search(r'\*\*RISULTATI OTTENUTI:\*\*\s*(.+?)(?:\*\*|$)', prompt, re.DOTALL)
        if data_section:
            data_text = data_section.group(1).strip()[:500]
            return f"Ecco i risultati della tua richiesta:\n\n{data_text}\n\nPosso aiutarti con ulteriori dettagli?"

        return "Ciao! Come posso aiutarti con i piani di monitoraggio veterinario?"

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
            print(f"❌ LLM streaming timeout after {timeout or self.timeout}s")
            return
        except Exception as e:
            print(f"❌ LLM streaming error: {e}")
            return

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
