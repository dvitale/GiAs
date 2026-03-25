"""
IntentMetadataService - Broker centrale tra DB e consumatori di metadati intent.

Singleton con lazy loading. Logica: DB-first, Python-fallback.
Pattern: stesso del FewShotRetriever (singleton, lazy init, graceful fallback).

Consumatori:
- Router: catalogo intent per prompt, esempi critici, regole disambiguazione
- help_tool: contenuto help formattato markdown
- build_intent_examples_index: tutti gli esempi per indicizzazione Qdrant
- api.py log_chat: metadati operativi (tool, dataretriever_class, two_phase)
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict

logger = logging.getLogger(__name__)


class IntentMetadataService:
    """Broker centrale tra DB e consumatori di metadati intent."""

    _instance: Optional['IntentMetadataService'] = None
    _initialized: bool = False

    # --- Singleton ---
    def __new__(cls) -> 'IntentMetadataService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if IntentMetadataService._initialized:
            return

        self._intents: Dict[str, Dict[str, Any]] = {}
        self._examples: List[Dict[str, Any]] = []
        self._source: str = 'not_loaded'
        self._loaded: bool = False

        IntentMetadataService._initialized = True

    # --- Loading ---

    def _ensure_loaded(self):
        """Lazy loading: carica alla prima chiamata."""
        if self._loaded:
            return
        if not self._load_from_db():
            self._load_from_python_fallback()
        self._loaded = True

    def _load_from_db(self) -> bool:
        """Carica metadati e esempi dal DB. Ritorna True se OK."""
        try:
            from data_sources.postgresql_source import PostgreSQLDataSource
            engine = PostgreSQLDataSource._engine
            if engine is None:
                logger.info("[IntentMetaService] DB engine non disponibile, uso fallback Python")
                return False

            from sqlalchemy import text

            # Carica intents
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT intent, title, category, emoji,
                           tool, graph_node, data_retriever, business_logic,
                           two_phase_threshold, required_slots,
                           keywords, context_keywords, negative_keywords,
                           is_direct_response, disambiguation_rules,
                           query_equivalent, notes, section_number
                    FROM intents
                    ORDER BY section_number
                """)).fetchall()

                if not rows:
                    logger.warning("[IntentMetaService] Tabella intents vuota, uso fallback Python")
                    return False

                for row in rows:
                    intent_id = row[0]
                    self._intents[intent_id] = {
                        "intent": intent_id,
                        "title": row[1],
                        "category": row[2],
                        "emoji": row[3] or "📋",
                        "tool": row[4],
                        "graph_node": row[5],
                        "data_retriever": row[6],
                        "business_logic": row[7],
                        "two_phase_threshold": row[8],
                        "required_slots": row[9] if row[9] else [],
                        "keywords": row[10] if row[10] else [],
                        "context_keywords": row[11] if row[11] else [],
                        "negative_keywords": row[12] if row[12] else [],
                        "is_direct_response": row[13] or False,
                        "disambiguation_rules": row[14] if row[14] else [],
                        "query_equivalent": row[15],
                        "notes": row[16],
                        "section_number": row[17],
                    }

                # Carica esempi
                example_rows = conn.execute(text("""
                    SELECT intent, text, example_type, expected_json,
                           confused_with, display_order
                    FROM intent_examples
                    ORDER BY intent, example_type, display_order
                """)).fetchall()

                for row in example_rows:
                    self._examples.append({
                        "intent": row[0],
                        "text": row[1],
                        "example_type": row[2],
                        "expected_json": row[3],
                        "confused_with": row[4],
                        "display_order": row[5],
                    })

            self._source = 'database'
            logger.info(
                f"[IntentMetaService] Caricati da DB: {len(self._intents)} intent, "
                f"{len(self._examples)} esempi"
            )
            return True

        except Exception as e:
            logger.warning(f"[IntentMetaService] Errore caricamento DB: {e}")
            return False

    def _load_from_python_fallback(self):
        """Fallback a INTENT_REGISTRY + hardcoded."""
        from orchestrator.intent_metadata import (
            INTENT_REGISTRY, CATEGORY_HIERARCHY, CATEGORY_EMOJI
        )
        from orchestrator.response_node import DIRECT_RESPONSE_INTENTS

        section = 0
        for intent_id, meta in INTENT_REGISTRY.items():
            section += 1
            self._intents[intent_id] = {
                "intent": intent_id,
                "title": meta.label,
                "category": meta.category,
                "emoji": meta.emoji,
                "tool": meta.tool,
                "graph_node": meta.graph_node,
                "data_retriever": None,
                "business_logic": None,
                "two_phase_threshold": meta.two_phase_threshold,
                "required_slots": meta.requires_slots,
                "keywords": meta.keywords,
                "context_keywords": meta.context_keywords,
                "negative_keywords": meta.negative_keywords,
                "is_direct_response": intent_id in DIRECT_RESPONSE_INTENTS,
                "disambiguation_rules": meta.disambiguation_rules,
                "query_equivalent": None,
                "notes": None,
                "section_number": section,
            }

            # Esempi dal registry come few_shot
            for ex in meta.examples:
                if ex and ex.strip():
                    self._examples.append({
                        "intent": intent_id,
                        "text": ex.strip(),
                        "example_type": "few_shot",
                        "expected_json": None,
                        "confused_with": None,
                        "display_order": 0,
                    })

        self._source = 'python_fallback'
        logger.info(
            f"[IntentMetaService] Fallback Python: {len(self._intents)} intent, "
            f"{len(self._examples)} esempi"
        )

    # --- Accessori intent ---

    def get_intent(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """Recupera metadati completi per un intent."""
        self._ensure_loaded()
        return self._intents.get(intent_id)

    def get_all_intents(self) -> Dict[str, Dict[str, Any]]:
        """Recupera tutti gli intent."""
        self._ensure_loaded()
        return self._intents

    def get_category_hierarchy(self) -> Dict[str, List[str]]:
        """Restituisce gerarchia categoria -> lista intent."""
        self._ensure_loaded()
        hierarchy: Dict[str, List[str]] = {}
        # Ordina per section_number
        sorted_intents = sorted(
            self._intents.values(),
            key=lambda x: x.get("section_number", 999)
        )
        for meta in sorted_intents:
            cat = meta.get("category", "Altro")
            if cat not in hierarchy:
                hierarchy[cat] = []
            hierarchy[cat].append(meta["intent"])
        return hierarchy

    # --- Accessori esempi ---

    def get_examples_by_type(self, example_type: str) -> List[Tuple[str, str]]:
        """Restituisce (text, intent) per un tipo specifico."""
        self._ensure_loaded()
        return [
            (ex["text"], ex["intent"])
            for ex in self._examples
            if ex["example_type"] == example_type
        ]

    def get_all_examples_for_indexing(self) -> List[Tuple[str, str]]:
        """Restituisce TUTTI gli esempi deduplicati per indicizzazione Qdrant.

        Esclude prompt_critical (già presenti nel system prompt statico del Router).
        """
        self._ensure_loaded()
        seen = set()
        result = []
        for ex in self._examples:
            if ex.get("example_type") == "prompt_critical":
                continue
            key = ex["text"].lower().strip()
            if key not in seen:
                seen.add(key)
                result.append((ex["text"], ex["intent"]))
        return result

    # --- Generazione contenuti ---

    def get_help_content(self) -> str:
        """Genera markdown per help_tool da dati DB/fallback."""
        self._ensure_loaded()

        # Filtra esempi help
        help_examples = sorted(
            [ex for ex in self._examples if ex["example_type"] == "help"],
            key=lambda x: x.get("display_order", 0)
        )

        if not help_examples:
            return ""

        # Raggruppa per categoria dell'intent
        from collections import OrderedDict
        cat_questions: OrderedDict = OrderedDict()
        # Categorie ordinate e relative emoji
        cat_order = [
            "Piano di Controllo", "Ricerca", "Ritardi e Monitoraggio",
            "Priorità e Rischio", "Priorità e Rischio",  # nearby
            "Storico e Analisi", "Procedure Operative"
        ]
        cat_emoji_map = {
            "Piano di Controllo": "📋",
            "Ricerca": "🔍",
            "Ritardi e Monitoraggio": "⏰",
            "Priorità e Rischio": "⚠️",
            "Storico e Analisi": "📜",
            "Procedure Operative": "📋",
        }

        for ex in help_examples:
            intent_meta = self._intents.get(ex["intent"], {})
            cat = intent_meta.get("category", "Altro")
            # Raggruppa nearby sotto titolo speciale
            if ex["intent"] == "ask_nearby_priority":
                display_cat = "Ricerca per Prossimità"
            else:
                display_cat = cat
            if display_cat not in cat_questions:
                cat_questions[display_cat] = []
            cat_questions[display_cat].append(ex["text"])

        # Genera markdown
        md = "**Come posso aiutarti?**\n\n"
        md += "Ecco cosa posso fare, con esempi di domande:\n\n"

        # Ordine desiderato per display
        display_order = [
            "Piano di Controllo", "Ricerca", "Ritardi e Monitoraggio",
            "Priorità e Rischio", "Ricerca per Prossimità",
            "Storico e Analisi", "Procedure Operative"
        ]
        display_emoji = {
            "Piano di Controllo": "📋",
            "Ricerca": "🔍",
            "Ritardi e Monitoraggio": "⏰",
            "Priorità e Rischio": "⚠️",
            "Ricerca per Prossimità": "📍",
            "Storico e Analisi": "📜",
            "Procedure Operative": "📋",
        }

        for cat in display_order:
            if cat not in cat_questions:
                continue
            emoji = display_emoji.get(cat, "📋")
            md += f"**{emoji} {cat}**\n"
            for q in cat_questions[cat]:
                md += f"- [{q}]\n"
            md += "\n"

        return md.rstrip() + "\n"

    def get_intent_catalog_for_prompt(self) -> str:
        """Genera sezione catalogo intent per il prompt di classificazione."""
        self._ensure_loaded()

        # Mappa categoria -> nome display nel prompt
        prompt_cat_names = {
            "Piano di Controllo": "Piani",
            "Priorità e Rischio": "Priorità",
            "Ricerca": "Ricerca",
            "Ritardi e Monitoraggio": "Ritardi",
            "Storico e Analisi": "Storico",
            "Procedure Operative": "Procedure",
            "Altro": "Base",
        }

        hierarchy = self.get_category_hierarchy()
        lines = []

        for cat, intents in hierarchy.items():
            display_name = prompt_cat_names.get(cat, cat)
            lines.append(f"\n[{display_name}]")
            for intent_id in intents:
                meta = self._intents.get(intent_id, {})
                slots = meta.get("required_slots", [])
                slot_str = f"({','.join(slots)})" if slots else ""
                title = meta.get("title", intent_id)
                # Formato compatto: intent(slots) - descrizione
                lines.append(f"{intent_id}{slot_str} - {title}")

        return "\n".join(lines)

    def get_critical_examples_for_prompt(self) -> str:
        """Genera sezione esempi critici formattati per il prompt."""
        self._ensure_loaded()

        examples = [
            ex for ex in self._examples
            if ex["example_type"] == "prompt_critical" and ex.get("expected_json")
        ]

        if not examples:
            return ""

        lines = []
        for ex in examples:
            expected = ex["expected_json"]
            if isinstance(expected, str):
                expected_str = expected
            else:
                expected_str = json.dumps(expected, ensure_ascii=False)
            lines.append(f'"{ex["text"]}" → {expected_str}')

        return "\n".join(lines)

    def get_disambiguation_rules_for_prompt(self) -> str:
        """Genera regole disambiguazione formattate per il prompt."""
        self._ensure_loaded()

        # Regole statiche (invarianti, non cambiano con l'aggiunta di intent)
        rules = [
            '1. "STABILIMENTI a rischio" → ask_risk_based_priority (NON ask_top_risk_activities)',
            '2. "ATTIVITÀ rischiose" / "classifica attività" → ask_top_risk_activities (NON ask_risk_based_priority)',
            '3. "piani in ritardo" (plurale/generico) → ask_delayed_plans',
            '4. "il piano X è in ritardo" (specifico) → check_if_plan_delayed',
            '5. greet se messaggio è saluto/convenevole SENZA domande operative; goodbye se è commiato',
            '6. Slot mancante per intent che lo richiede → needs_clarification:true',
            '7. confidence: 0.95+ per match esatto, 0.70-0.90 per inferenza, <0.70 se incerto',
            '8. CAMBIO TOPIC: Se il messaggio è chiaramente un NUOVO ARGOMENTO, IGNORA la sessione precedente',
            '9. "PIANI controllare per primi" → ask_delayed_plans; "STABILIMENTI controllare per primi" → ask_priority_establishment',
            '10. Se la domanda potrebbe corrispondere a 2+ intent con confidence simile, restituisci il migliore come intent principale e gli altri in "alternatives".',
            '11. "piani della sezione X" con X in (A-G) → search_piani_by_topic con slot sezione=X',
            '12. Filtro per MACROAREA/AGGREGAZIONE → estrai come slot per filtrare i risultati dell\'intent più vicino',
            '13. "quanti controlli nell\'ASL X" / "controlli eseguiti a X" → query_data (conteggio su cu_eseguiti_x). NON ask_piano_statistics (che riguarda statistiche dei PIANI).',
            '14. query_data SOLO per domande su dati tabulari non coperte dagli intent specifici. Confidence MAI > 0.80 (preferire sempre intent specifici).',
        ]
        return "\n".join(rules)

    # --- Metadati operativi (per chat_log) ---

    def get_intent_tool_mapping(self) -> Dict[str, str]:
        """Restituisce mapping intent -> tool."""
        self._ensure_loaded()
        return {
            k: v["tool"]
            for k, v in self._intents.items()
            if v.get("tool")
        }

    def get_two_phase_thresholds(self) -> Dict[str, int]:
        """Restituisce mapping intent -> two_phase_threshold."""
        self._ensure_loaded()
        return {
            k: v["two_phase_threshold"]
            for k, v in self._intents.items()
            if v.get("two_phase_threshold") is not None
        }

    def get_intent_metadata_for_chatlog(self, intent: str) -> Dict[str, Any]:
        """Restituisce metadati operativi per chat_log (tool, dataretriever, two_phase, sql)."""
        self._ensure_loaded()
        meta = self._intents.get(intent, {})
        return {
            "tool": meta.get("tool"),
            "dataretriever_class": meta.get("data_retriever"),
            "two_phase_threshold": meta.get("two_phase_threshold"),
            "sql": meta.get("query_equivalent"),
        }

    def reload(self):
        """Hot-reload: resetta stato e ricarica metadati da DB."""
        self._loaded = False
        self._intents.clear()
        self._examples.clear()
        self._source = 'not_loaded'
        self._ensure_loaded()
        logger.info(
            f"[IntentMetaService] Reload completato: {len(self._intents)} intent, "
            f"{len(self._examples)} esempi (source: {self._source})"
        )

    @property
    def source(self) -> str:
        """Ritorna 'database', 'python_fallback' o 'not_loaded'."""
        self._ensure_loaded()
        return self._source


# --- Factory function (come get_few_shot_retriever) ---

_service_instance: Optional[IntentMetadataService] = None


def get_intent_metadata_service() -> IntentMetadataService:
    """Restituisce singleton IntentMetadataService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = IntentMetadataService()
    return _service_instance
