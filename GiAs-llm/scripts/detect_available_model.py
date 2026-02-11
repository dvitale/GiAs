#!/usr/bin/env python3
"""
Auto-detect available LLM model for the environment
"""
import requests
import sys
import psutil

def get_available_memory_gb():
    """Get available system memory in GB"""
    try:
        memory = psutil.virtual_memory()
        return memory.available / (1024 ** 3)  # Convert bytes to GB
    except:
        return 8.0  # Conservative fallback

def detect_available_model():
    """Detect which LLM model is actually available via Ollama based on RAM"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            return None

        available_models = [model['name'] for model in response.json().get('models', [])]
        available_ram_gb = get_available_memory_gb()

        # Model requirements (VRAM + overhead)
        # Based on CLAUDE.md performance profiles
        model_ram_requirements = [
            ("Almawave/Velvet:latest", "velvet", 7.2),      # 7.2GB VRAM
            ("mistral-nemo:latest", "mistral-nemo", 6.1),   # 6.1GB VRAM
            ("llama3.1:8b", "llama3.1", 4.8),              # 4.8GB VRAM
            ("llama3.2:3b", "llama3.2", 3.5)               # Estimated lower
        ]

        # Filter models by RAM availability and sort by preference (Velvet first)
        compatible_models = []
        for ollama_name, gias_name, ram_req in model_ram_requirements:
            if ollama_name in available_models and available_ram_gb >= ram_req:
                compatible_models.append((ollama_name, gias_name, ram_req))

        if not compatible_models:
            # If no model fits RAM requirements, return smallest available
            for ollama_name, gias_name, _ in reversed(model_ram_requirements):
                if ollama_name in available_models:
                    return gias_name
            return None

        # Return first compatible model (Velvet has priority in the list)
        return compatible_models[0][1]

    except Exception as e:
        print(f"Error detecting models: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    model = detect_available_model()
    if model:
        print(model)
        sys.exit(0)
    else:
        print("velvet")  # Fallback default
        sys.exit(1)