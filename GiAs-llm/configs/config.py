#!/usr/bin/env python3
"""
Configurazione per GiAs-llm chatbot
"""

import os
from typing import Dict, Any

class ModelConfig:
    """Configurazione modelli disponibili"""

    # Modelli supportati con le loro caratteristiche
    AVAILABLE_MODELS = {
        "falcon": {
            "name": "falcon-gias:latest",
            "description": "Falcon GIAS - Modello personalizzato per dominio GIAS",
            "parameters": "7B",
            "vram_gb": 4.0,
            "avg_response_time": 1.5,
            "accuracy_score": 0.90,
            "recommended": False
        },
        "velvet": {
            "name": "Almawave/Velvet:latest",
            "description": "Almawave Velvet - LLM nativo italiano/europeo, GDPR compliant",
            "parameters": "14B",
            "vram_gb": 8.5,
            "avg_response_time": 4.2,
            "accuracy_score": 0.95,
            "recommended": True,
            "languages": ["Italiano", "Inglese", "Spagnolo", "Portoghese", "Tedesco", "Francese"]
        },
        "mistral-nemo": {
            "name": "mistral-nemo:latest",
            "description": "Mistral Nemo - Alta accuratezza ma lento (24s+ per classificazione)",
            "parameters": "12.2B",
            "vram_gb": 6.1,
            "avg_response_time": 24.6,
            "accuracy_score": 1.0,
            "recommended": False
        },
        "llama3.1": {
            "name": "llama3.1:8b",
            "description": "LLaMA 3.1 8B - Alta accuratezza, richiede più risorse",
            "parameters": "8B",
            "vram_gb": 4.8,
            "avg_response_time": 1.9,
            "accuracy_score": 1.0,
            "recommended": False
        },
        "llama3.2": {
            "name": "llama3.2:3b",
            "description": "LLaMA 3.2 3B - Velocissimo, ottimo per hardware limitato (2GB VRAM)",
            "parameters": "3B",
            "vram_gb": 2.0,
            "avg_response_time": 0.8,
            "accuracy_score": 0.85,
            "recommended": False
        },
        "ministral": {
            "name": "ministral-3:3b",
            "description": "Ministral 3B - Context 256K, function calling nativo, ottimo italiano",
            "parameters": "3.85B",
            "vram_gb": 3.0,
            "avg_response_time": 1.0,
            "accuracy_score": 0.90,
            "recommended": True,
            "languages": ["Italiano", "Inglese", "Francese", "Spagnolo", "Tedesco", "Portoghese", "Olandese", "Cinese", "Giapponese", "Coreano", "Arabo"],
            "features": ["function_calling", "structured_outputs", "vision", "256k_context"]
        }
    }

    # Modello di default (LLaMA 3.2 3B - veloce, disponibile, buon italiano)
    DEFAULT_MODEL = "llama3.2"

    @classmethod
    def get_model_name(cls, model_key: str = None) -> str:
        """Ottiene il nome completo del modello"""
        if not model_key:
            model_key = cls.DEFAULT_MODEL

        if model_key in cls.AVAILABLE_MODELS:
            return cls.AVAILABLE_MODELS[model_key]["name"]

        # Fallback al default se modello non riconosciuto
        return cls.AVAILABLE_MODELS[cls.DEFAULT_MODEL]["name"]

    @classmethod
    def get_model_info(cls, model_key: str = None) -> Dict[str, Any]:
        """Ottiene informazioni complete del modello"""
        if not model_key:
            model_key = cls.DEFAULT_MODEL

        if model_key in cls.AVAILABLE_MODELS:
            return cls.AVAILABLE_MODELS[model_key]

        # Fallback al default
        return cls.AVAILABLE_MODELS[cls.DEFAULT_MODEL]

    @classmethod
    def list_models(cls) -> Dict[str, Dict[str, Any]]:
        """Lista tutti i modelli disponibili"""
        return cls.AVAILABLE_MODELS

class LLMBackendConfig:
    """Configurazione backend LLM (Ollama, Llama.cpp, OpenAI, Anthropic, OpenAI-Compatible)"""

    VALID_BACKENDS = ["ollama", "llamacpp", "openai", "anthropic", "openai_compat"]
    EXTERNAL_BACKENDS = ["openai", "anthropic", "openai_compat"]
    DEFAULT_BACKEND = "llamacpp"

    @classmethod
    def get_backend_type(cls) -> str:
        """
        Ottiene il tipo di backend LLM configurato.
        Priorità: variabile ambiente > config.json > default
        """
        # 1. Variabile ambiente
        env_backend = os.getenv("GIAS_LLM_BACKEND")
        if env_backend and env_backend in cls.VALID_BACKENDS:
            return env_backend

        # 2. config.json
        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    json_backend = config.get("llm_backend", {}).get("type")
                    if json_backend and json_backend in cls.VALID_BACKENDS:
                        return json_backend
        except Exception:
            pass

        # 3. Default
        return cls.DEFAULT_BACKEND

    @classmethod
    def get_backend_config(cls) -> Dict[str, Any]:
        """Ottiene la configurazione completa del backend selezionato"""
        backend_type = cls.get_backend_type()

        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("llm_backend", {}).get(backend_type, {})
        except Exception:
            pass

        # Fallback defaults
        if backend_type == "llamacpp":
            return {
                "host": "http://localhost:11435",
                "api_endpoint": "/v1/chat/completions",
                "health_endpoint": "/health",
                "model_name": "Llama-3.2-3B-Instruct-Q6_K_L.gguf",
                "timeout_seconds": 90
            }
        elif backend_type == "openai":
            return {
                "model": "gpt-4o-mini",
                "timeout_seconds": 30,
                "api_key_env": "OPENAI_API_KEY"
            }
        elif backend_type == "anthropic":
            return {
                "model": "claude-sonnet-4-20250514",
                "timeout_seconds": 30,
                "api_key_env": "ANTHROPIC_API_KEY"
            }
        elif backend_type == "openai_compat":
            return {
                "host": "https://api.mistral.ai",
                "api_endpoint": "/v1/chat/completions",
                "model": "mistral-medium-latest",
                "timeout_seconds": 30,
                "api_key_env": "MISTRAL_API_KEY"
            }
        else:  # ollama
            return {
                "host": "http://localhost:11434",
                "api_endpoint": "/api/chat",
                "health_endpoint": "/api/tags",
                "timeout_seconds": 60
            }

    @classmethod
    def is_ollama(cls) -> bool:
        """Ritorna True se il backend è Ollama"""
        return cls.get_backend_type() == "ollama"

    @classmethod
    def is_llamacpp(cls) -> bool:
        """Ritorna True se il backend è Llama.cpp"""
        return cls.get_backend_type() == "llamacpp"

    @classmethod
    def is_external_provider(cls) -> bool:
        """Ritorna True se il backend invia dati a server esterni"""
        return cls.get_backend_type() in cls.EXTERNAL_BACKENDS

    @classmethod
    def get_api_key(cls) -> str:
        """
        Ottiene la API key per il backend configurato dalla variabile ambiente.
        Ritorna None se non trovata o se il backend e' locale.
        """
        backend_type = cls.get_backend_type()
        if backend_type not in cls.EXTERNAL_BACKENDS:
            return None

        backend_config = cls.get_backend_config()
        api_key_env = backend_config.get("api_key_env")
        if api_key_env:
            return os.getenv(api_key_env)

        # Fallback env var names
        fallbacks = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai_compat": "GIAS_LLM_API_KEY",
        }
        env_name = fallbacks.get(backend_type)
        return os.getenv(env_name) if env_name else None


class RiskPredictorConfig:
    """Configurazione predittore di rischio"""

    VALID_TYPES = ["ml", "statistical"]
    DEFAULT_TYPE = "ml"

    @classmethod
    def get_predictor_type(cls) -> str:
        """
        Ottiene il tipo di predittore configurato.
        Priorità: variabile ambiente > config.json > default
        """
        # 1. Variabile ambiente
        env_type = os.getenv("GIAS_RISK_PREDICTOR")
        if env_type and env_type in cls.VALID_TYPES:
            return env_type

        # 2. config.json
        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    json_type = config.get("risk_predictor", {}).get("type")
                    if json_type and json_type in cls.VALID_TYPES:
                        return json_type
        except Exception:
            pass

        # 3. Default
        return cls.DEFAULT_TYPE

    @classmethod
    def is_ml_predictor(cls) -> bool:
        """Ritorna True se il predittore configurato è ML"""
        return cls.get_predictor_type() == "ml"

    @classmethod
    def is_statistical_predictor(cls) -> bool:
        """Ritorna True se il predittore configurato è statistico"""
        return cls.get_predictor_type() == "statistical"


class AppConfig:
    """Configurazione generale applicazione"""

    # Configurazione da variabili ambiente o valori di default
    LLM_MODEL = os.getenv("GIAS_LLM_MODEL", ModelConfig.DEFAULT_MODEL)

    # Backend LLM (ollama o llamacpp)
    LLM_BACKEND = LLMBackendConfig.get_backend_type()
    LLM_BACKEND_CONFIG = LLMBackendConfig.get_backend_config()

    # Tipo di predittore rischio (ml o statistical)
    RISK_PREDICTOR_TYPE = RiskPredictorConfig.get_predictor_type()

    # Temperature per i diversi tipi di task
    CLASSIFICATION_TEMPERATURE = float(os.getenv("GIAS_CLASSIFICATION_TEMP", "0.1"))
    RESPONSE_GENERATION_TEMPERATURE = float(os.getenv("GIAS_RESPONSE_TEMP", "0.3"))

    # Timeout e limiti
    LLM_TIMEOUT_SECONDS = int(os.getenv("GIAS_LLM_TIMEOUT", "60"))
    MAX_TOKENS = int(os.getenv("GIAS_MAX_TOKENS", "2000"))

    # Ollama keep-alive
    KEEP_ALIVE_DURATION = int(os.getenv("OLLAMA_KEEP_ALIVE", "-1"))

    # Logging
    LOG_LEVEL = os.getenv("GIAS_LOG_LEVEL", "INFO")

    @classmethod
    def get_model_name(cls) -> str:
        """Ottiene il nome completo del modello configurato"""
        return ModelConfig.get_model_name(cls.LLM_MODEL)

    @classmethod
    def get_model_info(cls) -> Dict[str, Any]:
        """Ottiene informazioni del modello configurato"""
        return ModelConfig.get_model_info(cls.LLM_MODEL)

    @classmethod
    def get_fallback_config(cls) -> Dict[str, Any]:
        """
        Ottiene configurazione fallback recovery da config.json.

        Returns:
            Dict con configurazione fallback o None se non presente
        """
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "config.json"
        )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return config_data.get("fallback_recovery")
        except Exception as e:
            print(f"[WARNING] Could not load fallback config from config.json: {e}")
            return None

    @classmethod
    def print_config(cls):
        """Stampa la configurazione corrente"""
        model_info = cls.get_model_info()
        print("🔧 Configurazione GiAs-llm")
        print("=" * 40)
        print(f"🤖 Modello: {cls.LLM_MODEL}")
        print(f"   Nome: {model_info['name']}")
        print(f"   Descrizione: {model_info['description']}")
        print(f"   Parametri: {model_info['parameters']}")
        print(f"   VRAM: {model_info['vram_gb']}GB")
        print(f"   Accuratezza: {model_info['accuracy_score']*100:.0f}%")
        print(f"   Velocità media: {model_info['avg_response_time']:.1f}s")
        if model_info['recommended']:
            print("   ✅ Raccomandato")
        print(f"🌡️  Temperature:")
        print(f"   Classificazione: {cls.CLASSIFICATION_TEMPERATURE}")
        print(f"   Generazione: {cls.RESPONSE_GENERATION_TEMPERATURE}")
        print(f"⏱️  Timeout: {cls.LLM_TIMEOUT_SECONDS}s")
        print(f"🔄 Keep-alive: {cls.KEEP_ALIVE_DURATION}")

# Funzioni di utilità per cambio modello runtime
def set_model(model_key: str) -> bool:
    """Imposta il modello da utilizzare"""
    if model_key in ModelConfig.AVAILABLE_MODELS:
        AppConfig.LLM_MODEL = model_key
        return True
    return False

def get_available_models_summary() -> str:
    """Ritorna un summary dei modelli disponibili"""
    summary = "🤖 Modelli disponibili:\n"
    for key, info in ModelConfig.AVAILABLE_MODELS.items():
        recommended = " ⭐" if info['recommended'] else ""
        current = " 📍" if key == AppConfig.LLM_MODEL else ""
        summary += f"  • {key}: {info['description']} (Acc: {info['accuracy_score']*100:.0f}%, {info['avg_response_time']:.1f}s){recommended}{current}\n"
    return summary
