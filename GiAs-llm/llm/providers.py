"""
LLM Provider implementations for GiAs-llm.

Supported providers:
- OllamaProvider: Ollama native API (/api/chat)
- LlamaCppProvider: llama.cpp OpenAI-compatible API (/v1/chat/completions)
- OpenAIProvider: OpenAI API via SDK (GPT-4o, GPT-4o-mini)
- AnthropicProvider: Anthropic API via SDK (Claude)
- OpenAICompatProvider: Generic OpenAI-compatible endpoint (Mistral, Groq, Together, DeepSeek, etc.)
"""

import json
import os
from typing import Generator, Dict, Any

import requests

from .provider_base import LLMProvider


class OllamaProvider(LLMProvider):
    """Ollama native API provider (/api/chat)."""

    def __init__(self, model: str, config: Dict[str, Any], keep_alive: int = -1):
        super().__init__(model, config)
        self.base_url = config.get("host", "http://localhost:11434")
        self.api_endpoint = config.get("api_endpoint", "/api/chat")
        self.health_endpoint = config.get("health_endpoint", "/api/tags")
        self.keep_alive = keep_alive

    @property
    def provider_name(self) -> str:
        return "Ollama"

    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        request_body = {
            'model': self.model,
            'messages': messages,
            'options': {
                'temperature': temperature,
                'num_predict': max_tokens
            },
            'keep_alive': self.keep_alive,
            'stream': False
        }
        if json_mode:
            request_body['format'] = 'json'

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            json=request_body,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()
        result = response.json()
        return result['message']['content'].strip()

    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        request_body = {
            'model': self.model,
            'messages': messages,
            'options': {
                'temperature': temperature,
                'num_predict': max_tokens
            },
            'keep_alive': self.keep_alive,
            'stream': True
        }
        if json_mode:
            request_body['format'] = 'json'

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            json=request_body,
            stream=True,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'message' in data:
                        content = data['message'].get('content', '')
                        if content:
                            yield content
                    if data.get('done', False):
                        break
                except json.JSONDecodeError:
                    continue

    def ping(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}{self.health_endpoint}",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False


class LlamaCppProvider(LLMProvider):
    """Llama.cpp OpenAI-compatible API provider (/v1/chat/completions)."""

    def __init__(self, model: str, config: Dict[str, Any]):
        super().__init__(model, config)
        self.base_url = config.get("host", "http://localhost:11435")
        self.api_endpoint = config.get("api_endpoint", "/v1/chat/completions")
        self.health_endpoint = config.get("health_endpoint", "/health")

    @property
    def provider_name(self) -> str:
        return "Llama.cpp"

    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        request_body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False
        }
        if json_mode:
            request_body['response_format'] = {'type': 'json_object'}

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            json=request_body,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        request_body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True
        }
        if json_mode:
            request_body['response_format'] = {'type': 'json_object'}

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            json=request_body,
            stream=True,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_json = line_text[6:]
                    if data_json.strip() == '[DONE]':
                        break
                    try:
                        data = json.loads(data_json)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue

    def ping(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}{self.health_endpoint}",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider via SDK (GPT-4o, GPT-4o-mini, etc.)."""

    def __init__(self, model: str, config: Dict[str, Any]):
        super().__init__(model, config)
        try:
            import openai as _openai
            self._openai = _openai
        except ImportError:
            raise ImportError(
                "Il pacchetto 'openai' e' richiesto per il backend OpenAI. "
                "Installare con: pip install openai>=1.0.0"
            )
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"API key non trovata. Impostare la variabile ambiente {api_key_env}"
            )
        self.client = _openai.OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        kwargs = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'timeout': timeout or self.timeout,
        }
        if json_mode:
            kwargs['response_format'] = {'type': 'json_object'}

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        kwargs = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True,
            'timeout': timeout or self.timeout,
        }
        if json_mode:
            kwargs['response_format'] = {'type': 'json_object'}

        stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def ping(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class AnthropicProvider(LLMProvider):
    """Anthropic API provider via SDK (Claude Sonnet, Haiku, etc.)."""

    def __init__(self, model: str, config: Dict[str, Any]):
        super().__init__(model, config)
        try:
            import anthropic as _anthropic
            self._anthropic = _anthropic
        except ImportError:
            raise ImportError(
                "Il pacchetto 'anthropic' e' richiesto per il backend Anthropic. "
                "Installare con: pip install anthropic>=0.30.0"
            )
        api_key_env = config.get("api_key_env", "ANTHROPIC_API_KEY")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"API key non trovata. Impostare la variabile ambiente {api_key_env}"
            )
        self.client = _anthropic.Anthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    def _extract_system_and_messages(self, messages: list, json_mode: bool = False):
        """
        Anthropic API richiede system come parametro separato.
        Estrae il primo messaggio system e lo separa dai messaggi.
        Se json_mode, aggiunge istruzione JSON al system prompt.
        """
        system_text = None
        filtered_messages = []

        for msg in messages:
            if msg.get('role') == 'system':
                system_text = msg.get('content', '')
            else:
                filtered_messages.append(msg)

        if json_mode:
            json_instruction = "\n\nRispondi SOLO con JSON valido, niente altro testo prima o dopo il JSON."
            if system_text:
                system_text += json_instruction
            else:
                system_text = json_instruction.strip()
            # Prefill assistant con '{' per forzare output JSON
            filtered_messages.append({'role': 'assistant', 'content': '{'})

        return system_text, filtered_messages

    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        system_text, filtered_messages = self._extract_system_and_messages(messages, json_mode)

        kwargs = {
            'model': self.model,
            'messages': filtered_messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'timeout': timeout or self.timeout,
        }
        if system_text:
            kwargs['system'] = system_text

        response = self.client.messages.create(**kwargs)
        content = response.content[0].text.strip()

        # Se json_mode, ricostruire il JSON completo (abbiamo prefillato '{')
        if json_mode and not content.startswith('{'):
            content = '{' + content

        return content

    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        system_text, filtered_messages = self._extract_system_and_messages(messages, json_mode)

        kwargs = {
            'model': self.model,
            'messages': filtered_messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if system_text:
            kwargs['system'] = system_text

        # Se json_mode, emetti il '{' prefillato come primo token
        if json_mode:
            yield '{'

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def ping(self) -> bool:
        try:
            # Ping minimale: richiesta con 1 token
            self.client.messages.create(
                model=self.model,
                messages=[{'role': 'user', 'content': 'ping'}],
                max_tokens=1
            )
            return True
        except Exception:
            return False


class OpenAICompatProvider(LLMProvider):
    """
    Generic OpenAI-compatible API provider via raw requests.
    Funziona con: Mistral, Groq, Together, DeepSeek, OpenRouter, DeepInfra, etc.
    Non richiede SDK aggiuntivi.
    """

    def __init__(self, model: str, config: Dict[str, Any]):
        super().__init__(model, config)
        self.base_url = config.get("host", "https://api.mistral.ai")
        self.api_endpoint = config.get("api_endpoint", "/v1/chat/completions")
        api_key_env = config.get("api_key_env", "GIAS_LLM_API_KEY")
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(
                f"API key non trovata. Impostare la variabile ambiente {api_key_env}"
            )

    @property
    def provider_name(self) -> str:
        return "OpenAI-Compatible"

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def query(self, messages: list, temperature: float, max_tokens: int,
              json_mode: bool = False, timeout: float = None) -> str:
        request_body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False
        }
        if json_mode:
            request_body['response_format'] = {'type': 'json_object'}

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            headers=self._headers(),
            json=request_body,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    def query_stream(self, messages: list, temperature: float, max_tokens: int,
                     json_mode: bool = False, timeout: float = None) -> Generator[str, None, None]:
        request_body = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True
        }
        if json_mode:
            request_body['response_format'] = {'type': 'json_object'}

        response = requests.post(
            f"{self.base_url}{self.api_endpoint}",
            headers=self._headers(),
            json=request_body,
            stream=True,
            timeout=timeout or self.timeout
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_json = line_text[6:]
                    if data_json.strip() == '[DONE]':
                        break
                    try:
                        data = json.loads(data_json)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue

    def ping(self) -> bool:
        try:
            # Tentativo minimale: richiesta con 1 token
            request_body = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': 'ping'}],
                'max_tokens': 1,
                'stream': False
            }
            response = requests.post(
                f"{self.base_url}{self.api_endpoint}",
                headers=self._headers(),
                json=request_body,
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
