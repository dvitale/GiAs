"""
Fallback Recovery Engine per Sistema di Suggerimenti Intelligenti

Implementa un meccanismo ibrido (keyword + LLM) con menu categorizzato a 2 livelli
per guidare l'utente verso intent validi quando la classificazione fallisce.
"""

import re
import json
import time
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

try:
    from llm.client import LLMClient
    from configs.config import AppConfig
    from .intent_metadata import (
        INTENT_REGISTRY,
        CATEGORY_HIERARCHY,
        CATEGORY_EMOJI,
        get_all_categories,
        get_category_intents,
        get_intent_metadata
    )
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from llm.client import LLMClient
    from configs.config import AppConfig
    from orchestrator.intent_metadata import (
        INTENT_REGISTRY,
        CATEGORY_HIERARCHY,
        CATEGORY_EMOJI,
        get_all_categories,
        get_category_intents,
        get_intent_metadata
    )


class FallbackRecoveryEngine:
    """
    Engine per recupero fallback con approssimazioni successive.

    Fasi:
    1. Keyword Matching (~50ms) - Pattern matching veloce
    2. LLM Semantic Scoring (~1-2s) - Similarità semantica
    3. Category Menu (sempre disponibile) - Menu strutturato a 2 livelli
    """

    # Configurazione default (può essere sovrascritta da config.json)
    DEFAULT_CONFIG = {
        "enabled": True,
        "keyword_threshold": 15,  # Threshold minimo per considerare un intent
        "max_suggestions": 4,  # Numero massimo di suggerimenti diretti
        "llm_timeout": 5,  # Timeout LLM in secondi
        "max_consecutive_fallbacks": 3,  # Max fallback prima di escalation
        "enable_llm_phase": True,  # Abilita Fase 2 (LLM)
        "enable_category_menu": True  # Abilita Fase 3 (Menu)
    }

    # Punteggi per keyword matching
    SCORE_PRIMARY_KEYWORD = 10
    SCORE_CONTEXT_KEYWORD = 5
    SCORE_NEGATIVE_KEYWORD = -50

    def __init__(self, llm_client: LLMClient = None, config: Dict = None):
        """
        Inizializza engine.

        Args:
            llm_client: Client LLM per semantic scoring
            config: Configurazione custom (override DEFAULT_CONFIG)
        """
        self.llm_client = llm_client or LLMClient()

        # Merge config
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # Cache per performance
        self._keyword_cache = {}

    def suggest_intents(
        self,
        user_message: str,
        phase: int = 1,
        category: str = None
    ) -> List[Dict]:
        """
        Suggerisce intent basati sul messaggio utente.

        Args:
            user_message: Input utente non classificato
            phase: Fase corrente (1=keyword, 2=LLM, 3=category menu)
            category: Categoria selezionata (per menu livello 2)

        Returns:
            Lista di suggerimenti: [
                {
                    "intent": "ask_risk_based_priority",
                    "score": 35,
                    "label": "Stabilimenti a Rischio NC",
                    "description": "...",
                    "emoji": "⚠️",
                    "type": "intent"  # o "category"
                },
                ...
            ]
        """
        if not self.config["enabled"]:
            return self._fallback_to_category_menu(category)

        # Fase 3: Category Menu (se richiesto esplicitamente o se category specificata)
        if phase == 3 or category is not None:
            return self._category_menu(level=2 if category else 1, category=category)

        # Fase 1: Keyword Matching
        keyword_suggestions = self._keyword_matching(user_message)

        # Se abbastanza suggerimenti validi, ritorna con categorie
        if len(keyword_suggestions) >= 2:
            return self._prepare_suggestions_with_categories(keyword_suggestions)

        # Se c'è almeno un suggerimento, tienilo ma cerca anche con LLM
        if len(keyword_suggestions) == 1:
            # Fase 2: LLM Semantic Scoring per trovare più suggerimenti
            if self.config["enable_llm_phase"] and phase >= 2:
                llm_suggestions = self._llm_semantic_scoring(user_message)
                if llm_suggestions:
                    # Merge keyword + LLM suggestions
                    combined = keyword_suggestions + llm_suggestions
                    # Remove duplicates
                    seen = set()
                    unique = []
                    for s in combined:
                        intent_id = s.get("intent")
                        if intent_id and intent_id not in seen:
                            seen.add(intent_id)
                            unique.append(s)
                    return self._prepare_suggestions_with_categories(unique)

            # Solo un suggerimento, ritorna con categorie
            return self._prepare_suggestions_with_categories(keyword_suggestions)

        # Nessun suggerimento da keyword, prova LLM
        if self.config["enable_llm_phase"] and phase >= 2:
            llm_suggestions = self._llm_semantic_scoring(user_message)
            if llm_suggestions:
                return self._prepare_suggestions_with_categories(llm_suggestions)

        # Fallback a menu categorizzato
        return self._category_menu(level=1, category=None)

    def _keyword_matching(self, message: str) -> List[Dict]:
        """
        Fase 1: Keyword matching veloce.

        Args:
            message: Messaggio utente

        Returns:
            Lista di intent con score >= threshold
        """
        # Normalizza messaggio
        message_lower = message.lower().strip()

        # Check cache
        if message_lower in self._keyword_cache:
            return self._keyword_cache[message_lower]

        # Calcola score per ogni intent
        scored_intents = []
        for intent_id, metadata in INTENT_REGISTRY.items():
            # Skip fallback e intent interni
            if intent_id in ["fallback", "confirm_show_details", "decline_show_details"]:
                continue

            score = self._score_intent_by_keywords(message_lower, metadata)

            if score >= self.config["keyword_threshold"]:
                scored_intents.append({
                    "intent": intent_id,
                    "score": score,
                    "label": metadata.label,
                    "description": metadata.description,
                    "emoji": metadata.emoji,
                    "category": metadata.category,
                    "requires_slots": metadata.requires_slots,
                    "type": "intent"
                })

        # Ordina per score decrescente
        scored_intents.sort(key=lambda x: x["score"], reverse=True)

        # Limita a max_suggestions
        result = scored_intents[:self.config["max_suggestions"]]

        # Cache result
        self._keyword_cache[message_lower] = result

        return result

    def _score_intent_by_keywords(self, message: str, metadata) -> int:
        """
        Calcola score keyword per un intent.

        Logica:
        - Ogni primary keyword match: +10 punti
        - Ogni context keyword match: +5 punti
        - Ogni negative keyword match: -50 punti (esclude intent)

        Args:
            message: Messaggio normalizzato (lowercase)
            metadata: IntentMetadata

        Returns:
            Score totale
        """
        score = 0

        # Check negative keywords (esclusione forte)
        for neg_kw in metadata.negative_keywords:
            if neg_kw.lower() in message:
                score += self.SCORE_NEGATIVE_KEYWORD

        # Se score negativo, intent escluso
        if score < 0:
            return score

        # Check primary keywords
        for keyword in metadata.keywords:
            if keyword.lower() in message:
                score += self.SCORE_PRIMARY_KEYWORD

        # Check context keywords
        for ctx_kw in metadata.context_keywords:
            if ctx_kw.lower() in message:
                score += self.SCORE_CONTEXT_KEYWORD

        return score

    def _llm_semantic_scoring(self, message: str) -> List[Dict]:
        """
        Fase 2: LLM similarity scoring per casi ambigui.

        Args:
            message: Messaggio utente

        Returns:
            Lista di intent suggeriti da LLM
        """
        try:
            # Prepara lista intent con descrizioni
            intent_descriptions = []
            for intent_id, metadata in INTENT_REGISTRY.items():
                if intent_id not in ["fallback", "confirm_show_details", "decline_show_details"]:
                    intent_descriptions.append({
                        "intent": intent_id,
                        "label": metadata.label,
                        "description": metadata.description,
                        "examples": metadata.examples[:2]  # Max 2 esempi per ridurre token
                    })

            # Prompt compatto per LLM
            prompt = self._build_semantic_scoring_prompt(message, intent_descriptions)

            # Chiamata LLM con timeout
            start_time = time.time()
            response = self.llm_client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed > self.config["llm_timeout"]:
                print(f"[WARNING] LLM timeout: {elapsed:.2f}s > {self.config['llm_timeout']}s")
                return []

            # Parse risposta
            suggestions = self._parse_llm_response(response)
            return suggestions[:self.config["max_suggestions"]]

        except Exception as e:
            print(f"[ERROR] LLM semantic scoring fallito: {e}")
            return []

    def _build_semantic_scoring_prompt(self, message: str, intent_descriptions: List[Dict]) -> str:
        """Costruisce prompt per LLM semantic scoring"""
        intents_text = "\n".join([
            f"{i+1}. {item['label']}: {item['description']}"
            for i, item in enumerate(intent_descriptions)
        ])

        prompt = f"""Sei un assistente di classificazione intent. Dato il messaggio utente, identifica i 3 intent più rilevanti.

Messaggio utente: "{message}"

Intent disponibili:
{intents_text}

Rispondi SOLO con un JSON array di max 3 intent, ordinati per rilevanza:
[
  {{"intent": "intent_id", "confidence": 0.9}},
  ...
]

JSON:"""
        return prompt

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """Parse risposta LLM in lista di suggerimenti"""
        try:
            # Estrai JSON da risposta
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
            if not json_match:
                return []

            parsed = json.loads(json_match.group(0))

            # Converti in formato suggerimenti
            suggestions = []
            for item in parsed:
                intent_id = item.get("intent")
                confidence = item.get("confidence", 0.5)

                metadata = get_intent_metadata(intent_id)
                if metadata:
                    suggestions.append({
                        "intent": intent_id,
                        "score": int(confidence * 100),  # Converti confidence in score 0-100
                        "label": metadata.label,
                        "description": metadata.description,
                        "emoji": metadata.emoji,
                        "category": metadata.category,
                        "requires_slots": metadata.requires_slots,
                        "type": "intent"
                    })

            return suggestions

        except Exception as e:
            print(f"[ERROR] Parse LLM response fallito: {e}")
            return []

    def _category_menu(self, level: int = 1, category: str = None) -> List[Dict]:
        """
        Fase 3: Menu categorizzato a 2 livelli.

        Args:
            level: 1 = mostra categorie, 2 = mostra intent in categoria
            category: Categoria selezionata (per livello 2)

        Returns:
            Lista di suggerimenti (categorie o intent)
        """
        if not self.config["enable_category_menu"]:
            return []

        if level == 1:
            # Livello 1: Mostra categorie
            categories = get_all_categories()
            suggestions = []
            for cat in categories:
                emoji = CATEGORY_EMOJI.get(cat, "📋")
                suggestions.append({
                    "category": cat,
                    "label": cat,
                    "description": f"Operazioni relative a {cat.lower()}",
                    "emoji": emoji,
                    "type": "category"
                })
            return suggestions

        elif level == 2 and category:
            # Livello 2: Mostra intent in categoria
            intent_ids = get_category_intents(category)
            suggestions = []
            for intent_id in intent_ids:
                metadata = get_intent_metadata(intent_id)
                if metadata:
                    suggestions.append({
                        "intent": intent_id,
                        "label": metadata.label,
                        "description": metadata.description,
                        "emoji": metadata.emoji,
                        "category": metadata.category,
                        "requires_slots": metadata.requires_slots,
                        "type": "intent"
                    })
            return suggestions

        return []

    def _prepare_suggestions_with_categories(self, intent_suggestions: List[Dict]) -> List[Dict]:
        """
        Aggiunge opzioni categoria menu alla fine dei suggerimenti intent.

        Args:
            intent_suggestions: Lista suggerimenti intent (max 4)

        Returns:
            Lista combinata intent + categorie
        """
        # Limita intent a max_suggestions
        result = intent_suggestions[:self.config["max_suggestions"]]

        # Aggiungi separatore virtuale (gestito nel formatting)
        # Non aggiunto qui per mantenere lista pulita

        # Aggiungi categorie come opzioni finali
        categories = get_all_categories()
        for cat in categories:
            emoji = CATEGORY_EMOJI.get(cat, "📋")
            result.append({
                "category": cat,
                "label": cat,
                "description": f"Operazioni relative a {cat.lower()}",
                "emoji": emoji,
                "type": "category"
            })

        return result

    def _fallback_to_category_menu(self, category: str = None) -> List[Dict]:
        """Fallback sicuro a menu categorizzato"""
        return self._category_menu(level=2 if category else 1, category=category)

    def parse_user_selection(
        self,
        message: str,
        suggestions: List[Dict]
    ) -> Optional[Dict]:
        """
        Parse selezione utente da numero o testo.

        Args:
            message: Messaggio utente (es. "1", "opzione 2", "scegli 3")
            suggestions: Lista suggerimenti mostrati

        Returns:
            Suggerimento selezionato o None
        """
        # Try parse numero
        num = self._parse_numeric_selection(message)
        if num is not None:
            # Indice 1-based
            if 1 <= num <= len(suggestions):
                return suggestions[num - 1]

        # Try match per label/testo
        message_lower = message.lower().strip()
        for suggestion in suggestions:
            label = suggestion.get("label", "").lower()
            if message_lower == label or message_lower in label:
                return suggestion

        return None

    def _parse_numeric_selection(self, message: str) -> Optional[int]:
        """Parse selezione numerica da messaggio"""
        patterns = [
            r'^\s*(\d+)\s*$',  # "1", " 2 "
            r'^\s*opzione\s+(\d+)',  # "opzione 1"
            r'^\s*scegli\s+(\d+)',  # "scegli 2"
            r'^\s*numero\s+(\d+)',  # "numero 3"
            r'^\s*scelta\s+(\d+)',  # "scelta 4"
        ]

        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return int(match.group(1))

        return None

    def is_category_selection(self, suggestion: Dict) -> bool:
        """Verifica se suggerimento è una categoria"""
        return suggestion.get("type") == "category"

    def format_suggestions_message(
        self,
        suggestions: List[Dict],
        phase: int = 1,
        intro_message: str = None
    ) -> str:
        """
        Formatta messaggio con suggerimenti per l'utente.

        Args:
            suggestions: Lista suggerimenti
            phase: Fase corrente (1-3)
            intro_message: Messaggio introduttivo custom

        Returns:
            Messaggio formattato
        """
        if not suggestions:
            return "Scusa, non ho capito la tua richiesta. Usa 'aiuto' per vedere cosa posso fare."

        # Messaggio introduttivo
        if intro_message is None:
            intro_message = "Non sono sicuro di aver capito. Intendevi una di queste operazioni?"

        lines = [intro_message, ""]

        # Separa intent da categorie
        intents = [s for s in suggestions if s.get("type") == "intent"]
        categories = [s for s in suggestions if s.get("type") == "category"]

        # Mostra suggerimenti intent
        if intents:
            lines.append("**💡 Suggerimenti basati sulla tua richiesta:**")
            for i, suggestion in enumerate(intents, 1):
                emoji = suggestion.get("emoji", "📋")
                label = suggestion.get("label", "")
                description = suggestion.get("description", "")
                lines.append(f"{i}. {emoji} **{label}** - {description}")
            lines.append("")

        # Mostra menu categorie
        if categories:
            if intents:
                lines.append("**Oppure scegli per categoria:**")
            else:
                lines.append("**Scegli una categoria:**")

            start_num = len(intents) + 1
            for i, suggestion in enumerate(categories, start_num):
                emoji = suggestion.get("emoji", "📋")
                label = suggestion.get("label", "")
                lines.append(f"{i}. {emoji} {label}")
            lines.append("")

        # Istruzioni finali
        max_num = len(suggestions)
        lines.append(f"Rispondi con il numero (1-{max_num}) o descrivi meglio la tua richiesta.")

        return "\n".join(lines)

    def clear_cache(self):
        """Pulisce cache keyword"""
        self._keyword_cache.clear()
