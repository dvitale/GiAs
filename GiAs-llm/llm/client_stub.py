import json
import re


class LLMClient:
    """
    Stub client per LLaMA 3.1.

    In produzione, questo dovrebbe fare chiamate API reali a:
    - Ollama (ollama.ai)
    - vLLM (vllm.readthedocs.io)
    - OpenAI-compatible API
    - etc.

    Per ora, implementa una logica rule-based per testing.
    """

    def query(self, prompt: str = None, temperature: float = None, max_tokens: int = None,
              messages: list = None, json_mode: bool = False, timeout: float = None) -> str:
        """
        Simula risposta LLM per testing.

        In produzione, sostituire con:
            import requests
            response = requests.post("http://localhost:11434/api/generate",
                                    json={"model": "llama3.1", "prompt": prompt})
            return response.json()["response"]
        """

        # Resolve effective prompt from messages if needed
        if messages:
            prompt = '\n'.join(m.get('content', '') for m in messages)
        elif prompt is None:
            prompt = ''

        prompt_lower = prompt.lower()

        if "classifica il messaggio" in prompt_lower or "intent" in prompt_lower:
            return self._mock_classification(prompt)

        if "genera una risposta" in prompt_lower or "spiega i risultati" in prompt_lower:
            return self._mock_response_generation(prompt)

        return "Questa è una risposta stub dal LLM. Implementare il client reale."

    def _mock_classification(self, prompt: str) -> str:
        """Mock intent classification basato su pattern nel prompt"""

        prompt_lower = prompt.lower()

        # Try both prompt formats: old (**messaggio utente:**) and new (MESSAGGIO:)
        user_message_match = re.search(r'\*\*messaggio utente:\*\*\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
        if not user_message_match:
            user_message_match = re.search(r'messaggio:\s*["\']([^"\']+)["\']', prompt_lower, re.IGNORECASE)
        if user_message_match:
            user_message = user_message_match.group(1).strip()
        else:
            user_message = prompt_lower

        if re.match(r'^\s*(ciao|salve|buongiorno|buonasera|hello|hey)\s*[!.?]?\s*$', user_message):
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

        if re.match(r'^\s*(arrivederci|addio|bye|ciao ciao)\s*[!.?]?\s*$', user_message):
            return json.dumps({
                "intent": "goodbye",
                "slots": {},
                "needs_clarification": False
            })

        piano_match = re.search(r'\b([A-F]\d{1,2}(?:_[A-Z0-9]+)?)\b', user_message, re.IGNORECASE)
        piano_code = piano_match.group(1).upper() if piano_match else None

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
                "intent": "ask_piano_generic",
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
                "bovini", "bovino", "vacche", "vitelli",
                "suini", "suino", "maiali", "porci",
                "ovini", "ovino", "pecore", "agnelli",
                "caprini", "caprino", "capre",
                "avicoli", "avicolo", "polli", "pollame", "galline",
                "equini", "equino", "cavalli",
                "latte", "lattiero", "caseario",
                "carne", "macellazione", "macello",
                "mangimi", "mangime", "alimentazione",
                "allevamenti", "allevamento",
                "benessere", "biosicurezza",
                "salmonella", "residui", "farmaco"
            ]

            for word in keywords:
                if word in user_message:
                    topic_words.append(word)

            return json.dumps({
                "intent": "search_piani_by_topic",
                "slots": {"topic": " ".join(topic_words) if topic_words else "generico"},
                "needs_clarification": False
            })

        return json.dumps({
            "intent": "fallback",
            "slots": {},
            "needs_clarification": True
        })

    def _mock_response_generation(self, prompt: str) -> str:
        """Mock response generation - estrae formatted_response dal prompt o genera risposta generica"""

        formatted_match = re.search(r'\*\*RISULTATI OTTENUTI:\*\*\s*\{[^}]*["\']formatted_response["\']:\s*["\']([^"\']+)["\']', prompt, re.DOTALL)
        if formatted_match:
            formatted_text = formatted_match.group(1)
            return formatted_text[:2000]

        data_section = re.search(r'\*\*RISULTATI OTTENUTI:\*\*\s*(.+?)(?:\*\*|$)', prompt, re.DOTALL)
        if data_section:
            data_text = data_section.group(1).strip()[:500]
            return f"Ecco i risultati della tua richiesta:\n\n{data_text}\n\nPosso aiutarti con ulteriori dettagli?"

        return "Ciao! Come posso aiutarti con i piani di monitoraggio veterinario?"
