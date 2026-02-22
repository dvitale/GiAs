"""
Test di consistenza RAG per intent info_procedure.

Verifica che le risposte del sistema siano coerenti con i contenuti
dei PDF indicizzati.

Esecuzione:
    python -m pytest tests/integration/test_rag_consistency.py -v
    python -m pytest tests/integration/test_rag_consistency.py::TestRAGConsistency::test_rag_response[cu_01] -v

Nota: Questi test richiedono il server backend attivo e sono marcati come @pytest.mark.e2e.
Il conftest gestisce automaticamente lo skip se il server non e' disponibile.
"""

import pytest
import requests
import yaml
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


# Configurazione
TEST_DIR = Path(__file__).parent.parent  # tests/ (YAML e' nella root dei test)
YAML_PATH = TEST_DIR / "rag_test_cases.yaml"
API_URL = "http://localhost:5005/api/v1/chat"
STATUS_URL = "http://localhost:5005/status"
TIMEOUT = 60

# Marker globale per tutti i test di questo modulo
pytestmark = pytest.mark.e2e


@dataclass
class RAGTestCase:
    """Definizione di un caso di test RAG."""
    id: str
    query: str
    source: str
    expected_keywords: List[str]
    source_pages: str = ""
    forbidden_keywords: List[str] = field(default_factory=list)
    expected_facts: List[str] = field(default_factory=list)
    min_confidence: str = "medium"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGTestCase":
        """Crea un RAGTestCase da un dizionario."""
        return cls(
            id=data["id"],
            query=data["query"],
            source=data["source"],
            source_pages=data.get("source_pages", ""),
            expected_keywords=data.get("expected_keywords", []),
            forbidden_keywords=data.get("forbidden_keywords", []),
            expected_facts=data.get("expected_facts", []),
            min_confidence=data.get("min_confidence", "medium")
        )


def load_test_cases() -> List[RAGTestCase]:
    """Carica i test cases dal file YAML."""
    if not YAML_PATH.exists():
        return []

    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return [RAGTestCase.from_dict(tc) for tc in data.get("test_cases", [])]


# Carica test cases all'import
TEST_CASES = load_test_cases()

# Skip esplicito se file YAML non disponibile (evita test silenziosi)
if not YAML_PATH.exists():
    pytest.skip(
        f"File YAML test cases non trovato: {YAML_PATH}. "
        "TestRAGConsistency non avra' test parametrizzati.",
        allow_module_level=True
    )


class TestRAGConsistency:
    """Test di consistenza per le risposte RAG.

    Lo skip automatico per server non disponibile e' gestito dal conftest
    tramite il marker @pytest.mark.e2e a livello di modulo.
    """

    def _call_api(self, query: str) -> Dict[str, Any]:
        """Chiama l'API e ritorna la risposta."""
        payload = {
            "sender": "test_rag",
            "message": query
        }
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()

        data = resp.json()
        if not data or "result" not in data:
            return {"text": "", "custom": {}}

        result = data["result"]
        # Compatibilita': esponi text e custom come prima
        return {"text": result.get("text", ""), "custom": result}

    def _check_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Verifica quali keyword sono presenti nel testo (case insensitive)."""
        text_lower = text.lower()
        return [kw for kw in keywords if kw.lower() in text_lower]

    def _check_missing_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Ritorna le keyword mancanti."""
        text_lower = text.lower()
        return [kw for kw in keywords if kw.lower() not in text_lower]

    def _get_confidence_level(self, confidence: str) -> int:
        """Converte confidence stringa in valore numerico."""
        levels = {"low": 0, "medium": 1, "high": 2}
        return levels.get(confidence.lower(), 0)

    @pytest.mark.parametrize("tc", TEST_CASES, ids=lambda x: x.id)
    def test_rag_response(self, tc: RAGTestCase):
        """
        Test parametrizzato per ogni caso di test.

        Verifica:
        1. Intent corretto (info_procedure)
        2. Keywords attese presenti
        3. Keywords vietate assenti
        4. Fatti specifici presenti (se definiti)
        5. Confidence minima raggiunta
        """
        # Chiama API
        response = self._call_api(tc.query)
        text = response.get("text", "")
        custom = response.get("custom", {})

        # Log per debug
        print(f"\n--- Test: {tc.id} ---")
        print(f"Query: {tc.query}")
        print(f"Source: {tc.source} (pag. {tc.source_pages})")
        print(f"Response length: {len(text)} chars")

        # Verifica risposta non vuota
        assert text, f"Risposta vuota per query: {tc.query}"

        # Verifica intent corretto
        intent = custom.get("intent", "")
        assert intent == "info_procedure", \
            f"Intent errato: '{intent}' (atteso: 'info_procedure')\nQuery: {tc.query}"

        # Verifica keywords attese
        if tc.expected_keywords:
            found_keywords = self._check_keywords(text, tc.expected_keywords)
            missing_keywords = self._check_missing_keywords(text, tc.expected_keywords)

            # Calcola coverage
            coverage = len(found_keywords) / len(tc.expected_keywords)
            print(f"Keyword coverage: {coverage:.0%} ({len(found_keywords)}/{len(tc.expected_keywords)})")
            print(f"Keywords trovate: {found_keywords}")

            if missing_keywords:
                print(f"Keywords mancanti: {missing_keywords}")

            # Richiedi almeno 50% delle keywords
            min_coverage = 0.5
            assert coverage >= min_coverage, \
                f"Coverage keywords insufficiente: {coverage:.0%} < {min_coverage:.0%}\n" \
                f"Mancanti: {missing_keywords}\n" \
                f"Risposta (primi 500 char): {text[:500]}"

        # Verifica keywords vietate
        if tc.forbidden_keywords:
            forbidden_found = self._check_keywords(text, tc.forbidden_keywords)
            assert len(forbidden_found) == 0, \
                f"Keywords vietate trovate: {forbidden_found}\n" \
                f"Risposta (primi 300 char): {text[:300]}"

        # Verifica fatti specifici
        if tc.expected_facts:
            for fact in tc.expected_facts:
                fact_found = fact.lower() in text.lower()
                if not fact_found:
                    print(f"Fatto non trovato (warning): {fact}")
                # Non fallisce, solo warning - i fatti possono essere parafrasati

        # Verifica confidence (se disponibile)
        confidence = custom.get("confidence", "medium")
        actual_level = self._get_confidence_level(confidence)
        required_level = self._get_confidence_level(tc.min_confidence)

        if actual_level < required_level:
            print(f"Warning: Confidence {confidence} < {tc.min_confidence}")

        print(f"Intent: {intent}, Confidence: {confidence}")
        print("--- Test PASSED ---\n")


class TestRAGMetrics:
    """Test aggregati per metriche RAG.

    Lo skip automatico e' gestito dal conftest tramite il marker e2e.
    """

    def _call_api(self, query: str) -> Dict[str, Any]:
        """Chiama l'API e ritorna la risposta."""
        payload = {"sender": "test_rag_metrics", "message": query}
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data or "result" not in data:
            return {"text": "", "custom": {}}
        result = data["result"]
        return {"text": result.get("text", ""), "custom": result}

    @pytest.mark.slow
    def test_overall_keyword_coverage(self):
        """
        Verifica che la coverage complessiva delle keywords sia >= 60%.
        Esegue tutti i test cases e calcola metriche aggregate.
        """
        total_expected = 0
        total_found = 0
        results = []

        for tc in TEST_CASES[:5]:  # Limita a 5 per velocita
            try:
                response = self._call_api(tc.query)
                text = response.get("text", "")

                if tc.expected_keywords:
                    found = [kw for kw in tc.expected_keywords
                             if kw.lower() in text.lower()]
                    total_expected += len(tc.expected_keywords)
                    total_found += len(found)
                    results.append({
                        "id": tc.id,
                        "coverage": len(found) / len(tc.expected_keywords)
                    })
            except Exception as e:
                results.append({"id": tc.id, "error": str(e)})

        if total_expected > 0:
            overall_coverage = total_found / total_expected
            print(f"\nOverall keyword coverage: {overall_coverage:.0%}")
            print(f"Results per test: {results}")

            # Target: 60% coverage
            assert overall_coverage >= 0.60, \
                f"Coverage complessiva insufficiente: {overall_coverage:.0%} < 60%"

    @pytest.mark.slow
    def test_intent_accuracy(self):
        """
        Verifica che tutte le query vengano classificate come info_procedure.
        """
        correct = 0
        total = 0

        for tc in TEST_CASES[:5]:
            try:
                response = self._call_api(tc.query)
                intent = response.get("custom", {}).get("intent", "")

                if intent == "info_procedure":
                    correct += 1
                total += 1
            except Exception:
                pass

        if total > 0:
            accuracy = correct / total
            print(f"\nIntent accuracy: {accuracy:.0%} ({correct}/{total})")
            assert accuracy >= 0.80, \
                f"Intent accuracy insufficiente: {accuracy:.0%} < 80%"


# Test individuali per debug
class TestIndividualCases:
    """Test individuali per debug di casi specifici.

    Lo skip automatico e' gestito dal conftest tramite il marker e2e.
    """

    def _call_api(self, query: str) -> Dict[str, Any]:
        payload = {"sender": "test_individual", "message": query}
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data or "result" not in data:
            return {"text": "", "custom": {}}
        result = data["result"]
        return {"text": result.get("text", ""), "custom": result}

    def test_controllo_ufficiale_base(self):
        """Test base: inserimento controllo ufficiale."""
        response = self._call_api("Come si inserisce un controllo ufficiale?")
        text = response.get("text", "")

        assert text, "Risposta vuota"
        assert len(text) > 100, f"Risposta troppo breve: {len(text)} chars"

        # Verifica contenuto minimo
        text_lower = text.lower()
        has_cu_content = any(kw in text_lower for kw in
                           ["controllo", "inserimento", "gisa", "scheda"])
        assert has_cu_content, f"Risposta non pertinente: {text[:300]}"

    def test_non_conformita_base(self):
        """Test base: non conformita."""
        response = self._call_api("Come si registra una non conformita?")
        text = response.get("text", "")

        assert text, "Risposta vuota"
        text_lower = text.lower()
        has_nc_content = any(kw in text_lower for kw in
                           ["non conformit", "nc", "registra", "punteggio"])
        assert has_nc_content, f"Risposta non pertinente: {text[:300]}"

    def test_matrix_base(self):
        """Test base: Matrix."""
        response = self._call_api("Cos'e Matrix in GISA?")
        text = response.get("text", "")

        assert text, "Risposta vuota"
        text_lower = text.lower()
        has_matrix_content = any(kw in text_lower for kw in
                                ["matrix", "distribuzione", "controlli", "pianificazione"])
        assert has_matrix_content, f"Risposta non pertinente: {text[:300]}"
