"""
Follow-up suggestions per continuazione conversazione.

Dopo ogni risposta a un intent non banale, appende suggerimenti
contestuali cliccabili per guidare l'utente verso approfondimenti.

Pattern analogo a two_phase.py per il suffix.
"""

from typing import Dict, Any, List, Optional


# Intent esclusi dai suggerimenti di follow-up
EXCLUDED_INTENTS = {
    "greet", "goodbye", "ask_help",
    "confirm_show_details", "decline_show_details", "fallback"
}

# Header del blocco suggerimenti
FOLLOWUP_HEADER = "\n\n---\n**Vuoi approfondire?** Ecco cosa posso fare:"

# Lunghezza minima della risposta per appendere suggerimenti
MIN_RESPONSE_LENGTH = 50


class FollowUpSuggestionEngine:
    """
    Engine per generare suggerimenti di follow-up contestuali.

    Genera 2-3 suggerimenti dinamici basati su intent, slot e dati
    restituiti dal tool, formattati come link markdown cliccabili.
    """

    def should_append(self, state: Dict[str, Any]) -> bool:
        """
        Determina se appendere suggerimenti alla risposta.

        Returns False se:
        - two-phase attivo (has_more_details=True)
        - intent escluso (triviale)
        - risposta contiene errore
        - risposta troppo corta o vuota
        """
        if state.get("has_more_details"):
            return False

        intent = state.get("intent", "")
        if intent in EXCLUDED_INTENTS or not intent:
            return False

        tool_output = state.get("tool_output") or {}
        data = tool_output.get("data", {})
        if isinstance(data, dict) and data.get("error"):
            return False

        final_response = state.get("final_response", "")
        if not final_response or len(final_response) < MIN_RESPONSE_LENGTH:
            return False

        return True

    def get_suggestions(
        self,
        intent: str,
        slots: Dict[str, Any],
        tool_output: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Genera suggerimenti contestuali per l'intent corrente.

        Args:
            intent: Intent classificato
            slots: Slot estratti (piano_code, topic, ecc.)
            tool_output: Output completo del tool

        Returns:
            Lista di max 3 dict {"text": "...", "query": "..."}
        """
        data = tool_output.get("data", {}) if isinstance(tool_output, dict) else {}

        dispatch = {
            "ask_piano_description": self._suggest_piano_description,
            "ask_piano_stabilimenti": self._suggest_piano_stabilimenti,
            "ask_piano_statistics": self._suggest_piano_statistics,
            "search_piani_by_topic": self._suggest_search_piani,
            "ask_priority_establishment": self._suggest_priority,
            "ask_risk_based_priority": self._suggest_risk,
            "ask_suggest_controls": self._suggest_controls,
            "ask_delayed_plans": self._suggest_delayed_plans,
            "check_if_plan_delayed": self._suggest_check_plan,
            "ask_establishment_history": self._suggest_establishment_history,
            "ask_top_risk_activities": self._suggest_top_risk,
            "analyze_nc_by_category": self._suggest_nc_analysis,
            "info_procedure": self._suggest_info_procedure,
        }

        handler = dispatch.get(intent)
        if not handler:
            return []

        suggestions = handler(slots, data)
        return suggestions[:3]

    def format_suggestions(self, suggestions: List[Dict[str, str]]) -> str:
        """
        Formatta suggerimenti come blocco markdown con link cliccabili.

        Formato:
        ---
        **Vuoi approfondire?** Ecco cosa posso fare:
        - [Vedere gli stabilimenti del piano A1]
        - [Verificare se il piano A1 e' in ritardo]
        """
        if not suggestions:
            return ""

        lines = [FOLLOWUP_HEADER]
        for s in suggestions:
            lines.append(f"- [{s['text']}]")

        return "\n".join(lines)

    # =================================================================
    # Generatori per intent specifici
    # =================================================================

    def _suggest_piano_description(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        piano = _get_piano_code(slots)
        if not piano:
            return []
        return [
            {
                "text": f"Stabilimenti controllati per il piano {piano}",
                "query": f"quali stabilimenti per piano {piano}"
            },
            {
                "text": f"Il piano {piano} e' in ritardo?",
                "query": f"il piano {piano} e' in ritardo?"
            },
        ]

    def _suggest_piano_stabilimenti(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        piano = _get_piano_code(slots)
        if not piano:
            return []
        return [
            {
                "text": f"Descrizione del piano {piano}",
                "query": f"di cosa tratta il piano {piano}"
            },
            {
                "text": f"Statistiche piano {piano}",
                "query": f"statistiche piano {piano}"
            },
        ]

    def _suggest_piano_statistics(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        piano = _get_piano_code(slots)
        if piano:
            return [
                {
                    "text": f"Stabilimenti del piano {piano}",
                    "query": f"quali stabilimenti per piano {piano}"
                },
                {
                    "text": f"Il piano {piano} e' in ritardo?",
                    "query": f"il piano {piano} e' in ritardo?"
                },
            ]
        return [
            {
                "text": "Piani in ritardo",
                "query": "piani in ritardo"
            },
            {
                "text": "Attivita' piu' rischiose",
                "query": "attivita' piu' rischiose"
            },
        ]

    def _suggest_search_piani(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        suggestions = []

        # Suggerisci il primo match trovato
        matches = data.get("matches", [])
        if matches and isinstance(matches, list) and len(matches) > 0:
            first = matches[0]
            alias = first.get("alias", "")
            if alias:
                suggestions.append({
                    "text": f"Di cosa tratta il piano {alias}?",
                    "query": f"di cosa tratta il piano {alias}"
                })

        suggestions.append({
            "text": "Stabilimenti prioritari",
            "query": "stabilimenti prioritari"
        })

        return suggestions

    def _suggest_priority(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Stabilimenti a rischio",
                "query": "stabilimenti a rischio"
            },
            {
                "text": "Piani in ritardo",
                "query": "piani in ritardo"
            },
        ]

    def _suggest_risk(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Stabilimenti mai controllati",
                "query": "stabilimenti mai controllati"
            },
            {
                "text": "Attivita' piu' rischiose",
                "query": "attivita' piu' rischiose"
            },
        ]

    def _suggest_controls(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Stabilimenti a rischio",
                "query": "stabilimenti a rischio"
            },
            {
                "text": "Stabilimenti prioritari",
                "query": "stabilimenti prioritari"
            },
        ]

    def _suggest_delayed_plans(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        suggestions = []

        # Suggerisci il piano con piu' ritardo
        delayed_plans = data.get("delayed_plans", [])
        if delayed_plans and isinstance(delayed_plans, list) and len(delayed_plans) > 0:
            worst = delayed_plans[0]
            worst_code = worst.get("indicatore", "")
            if worst_code:
                suggestions.append({
                    "text": f"Dettaglio ritardo piano {worst_code}",
                    "query": f"il piano {worst_code} e' in ritardo?"
                })

        suggestions.append({
            "text": "Stabilimenti prioritari",
            "query": "stabilimenti prioritari"
        })

        return suggestions

    def _suggest_check_plan(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Tutti i piani in ritardo",
                "query": "piani in ritardo"
            },
            {
                "text": "Stabilimenti prioritari",
                "query": "stabilimenti prioritari"
            },
        ]

    def _suggest_establishment_history(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Analisi non conformita' HACCP",
                "query": "non conformita' HACCP"
            },
            {
                "text": "Stabilimenti a rischio",
                "query": "stabilimenti a rischio"
            },
        ]

    def _suggest_top_risk(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Stabilimenti a rischio",
                "query": "stabilimenti a rischio"
            },
            {
                "text": "Analisi non conformita' HACCP",
                "query": "non conformita' HACCP"
            },
        ]

    def _suggest_nc_analysis(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        return [
            {
                "text": "Attivita' piu' rischiose",
                "query": "attivita' piu' rischiose"
            },
            {
                "text": "Stabilimenti a rischio",
                "query": "stabilimenti a rischio"
            },
        ]

    def _suggest_info_procedure(
        self, slots: Dict, data: Dict
    ) -> List[Dict[str, str]]:
        """
        Genera suggerimenti DINAMICI per info_procedure basati sui chunk RAG trovati.

        Estrae sezioni, titoli e documenti dai metadati dei chunk per suggerire
        approfondimenti contestuali e pertinenti.
        """
        if not isinstance(data, dict):
            return self._fallback_procedure_suggestions()

        chunks_metadata = data.get("chunks_metadata", [])
        query_raw = data.get("query", "")
        query = query_raw.lower() if isinstance(query_raw, str) else ""

        if not chunks_metadata:
            return self._fallback_procedure_suggestions()

        suggestions = []
        seen_suggestions = set()  # Evita duplicati

        # Aggiungi la query originale a seen per evitare di suggerire la stessa cosa
        if query:
            seen_suggestions.add(query)

        # 1. Estrai sezioni e titoli unici dai chunk (escludi il primo)
        for chunk in chunks_metadata[1:4]:  # Chunk 2-4 (salta il primo)
            if not isinstance(chunk, dict):
                continue

            section = chunk.get("section", "")
            title = chunk.get("title", "")

            # Assicurati che siano stringhe
            section = section.strip() if isinstance(section, str) else ""
            title = title.strip() if isinstance(title, str) else ""

            # Priorità: sezione > titolo
            text_to_use = section if section else title

            if text_to_use and text_to_use.lower() not in seen_suggestions:
                # Evita sezioni troppo generiche o tecniche
                if not self._is_generic_section(text_to_use):
                    suggestion_query = self._section_to_query(text_to_use)
                    suggestions.append({
                        "text": self._truncate_text(text_to_use, 40),
                        "query": suggestion_query
                    })
                    seen_suggestions.add(text_to_use.lower())

            if len(suggestions) >= 2:
                break

        # 2. Se ci sono documenti diversi, suggerisci altri documenti
        if len(suggestions) < 2:
            source_files = []
            for c in chunks_metadata:
                if isinstance(c, dict):
                    sf = c.get("source_file", "")
                    if isinstance(sf, str) and sf:
                        source_files.append(sf)
            source_files = list(set(source_files))

            if len(source_files) > 1:
                main_source = ""
                if chunks_metadata and isinstance(chunks_metadata[0], dict):
                    main_source = chunks_metadata[0].get("source_file", "") or ""

                for other_source in source_files:
                    if other_source != main_source:
                        other_title = self._source_to_title(other_source)
                        if other_title and other_title.lower() not in seen_suggestions:
                            suggestions.append({
                                "text": f"Vedi anche: {other_title}",
                                "query": f"cosa dice {other_title}"
                            })
                            seen_suggestions.add(other_title.lower())
                            break

        # 3. Suggerisci variante della query originale se abbiamo spazio
        if len(suggestions) < 2 and query:
            variant = self._generate_query_variant(query)
            if variant and variant.get("text", "").lower() not in seen_suggestions:
                suggestions.append({
                    "text": variant["text"],
                    "query": variant["query"]
                })
                seen_suggestions.add(variant["text"].lower())

        # 4. Usa il documento principale come fallback
        if len(suggestions) < 2 and chunks_metadata:
            main_title = ""
            if isinstance(chunks_metadata[0], dict):
                main_title = chunks_metadata[0].get("title", "") or ""
            if isinstance(main_title, str) and main_title and main_title.lower() not in seen_suggestions:
                suggestions.append({
                    "text": f"Altro su: {self._truncate_text(main_title, 30)}",
                    "query": f"altre informazioni {main_title}"
                })

        # 5. Fallback finale
        if not suggestions:
            return self._fallback_procedure_suggestions()

        return suggestions[:2]

    def _is_generic_section(self, text: str) -> bool:
        """Verifica se la sezione è troppo generica per essere utile."""
        generic_terms = [
            "aa.ss.ll", "introduzione", "premessa", "indice",
            "sommario", "note", "appendice", "allegat",
            "figura", "tabella", "immagine", "screenshot"
        ]
        text_lower = text.lower()
        # Escludi sezioni troppo corte, generiche, o che iniziano con "Figura X:"
        if len(text) < 5:
            return True
        if any(term in text_lower for term in generic_terms):
            return True
        # Escludi pattern "Figura N:" o "Tab. N:"
        import re
        if re.match(r'^(figura|fig\.?|tab\.?|tabella)\s*\d+', text_lower):
            return True
        return False

    def _generate_query_variant(self, query: str) -> Optional[Dict[str, str]]:
        """Genera una variante della query per approfondimento."""
        # Rimuovi parole comuni per creare variante
        stop_words = ["come", "funziona", "cosa", "è", "il", "la", "lo", "un", "una", "per", "in", "si"]
        words = [w for w in query.split() if w.lower() not in stop_words]

        if len(words) >= 2:
            topic = " ".join(words[:3])
            return {
                "text": f"Dettagli su {topic}",
                "query": f"dettagli procedura {topic}"
            }
        return None

    def _section_to_query(self, section: str) -> str:
        """Converte un nome sezione in una query naturale."""
        if not section:
            return ""

        section_lower = section.lower()

        # Pattern comuni per creare query naturali
        if any(kw in section_lower for kw in ["come", "procedura", "guida"]):
            return section  # Già una query naturale
        elif any(kw in section_lower for kw in ["inserimento", "registrazione", "compilazione"]):
            return f"come si fa {section}"
        elif any(kw in section_lower for kw in ["gestione", "controllo", "verifica"]):
            return f"come funziona {section}"
        else:
            return f"informazioni su {section}"

    def _source_to_title(self, source_file: str) -> str:
        """Converte nome file sorgente in titolo leggibile."""
        if not source_file:
            return ""

        # Rimuovi estensione e path
        name = source_file.replace(".pdf", "").replace(".docx", "").replace(".txt", "")
        name = name.split("/")[-1]  # Solo filename

        # Mappa nomi file → titoli leggibili
        title_map = {
            "ManualeGisa": "Manuale GISA",
            "help_matrix_rev1.5": "Guida Matrix",
            "help_matrix": "Guida Matrix",
            "Manuale_bdu": "Manuale BDU",
            "info_sito_viaggiare": "Info Viaggiare con Animali",
            "info_sito_anagrafe": "Info Anagrafe Animali",
            "help_vam": "Guida VAM",
        }

        # Cerca match parziale
        for key, title in title_map.items():
            if key.lower() in name.lower():
                return title

        # Fallback: formatta il nome file
        return name.replace("_", " ").title()

    def _truncate_text(self, text: str, max_len: int) -> str:
        """Tronca testo a max_len caratteri."""
        if len(text) <= max_len:
            return text
        return text[:max_len-3].rsplit(" ", 1)[0] + "..."

    def _fallback_procedure_suggestions(self) -> List[Dict[str, str]]:
        """Suggerimenti fallback quando non ci sono metadati chunk."""
        return [
            {"text": "Controllo ufficiale", "query": "come si esegue un controllo ufficiale"},
            {"text": "Non conformita'", "query": "come registrare una non conformita"},
        ]


# =================================================================
# Utility
# =================================================================

def _get_piano_code(slots: Dict[str, Any]) -> Optional[str]:
    """Estrae e normalizza il codice piano dagli slot."""
    code = slots.get("piano_code", "")
    if code:
        return str(code).upper()
    return None
