"""
Query Analyzer for Hybrid Search

Analyzes user queries to determine optimal search strategy.
"""

import re
from typing import Dict, List, Set
from dataclasses import dataclass

@dataclass
class QueryAnalysis:
    """Analysis results for a user query"""
    complexity_score: float      # 0-1, higher = more complex
    domain_terms: List[str]      # Veterinary terms detected
    semantic_indicators: List[str] # Words suggesting semantic search needed
    length_score: float          # Based on word count
    entity_count: int            # Number of domain entities
    query_type: str              # Classification of query type

class QueryAnalyzer:
    """Analyzes queries for optimal search strategy selection"""

    def __init__(self):
        self.veterinary_terms = self._load_veterinary_terms()
        self.semantic_indicators = [
            "riguardano", "relativo", "correlato", "connesso", "concernente",
            "simile", "tipo", "categoria", "genere", "specie",
            "benessere", "sicurezza", "qualità", "controllo", "monitoraggio",
            "trattano", "parlano", "includono", "comprendono",
            "nell'ambito", "settore", "campo", "dominio"
        ]
        self.complexity_patterns = [
            r"che\s+(riguardano|trattano|parlano|includono)",  # Relative clauses
            r"per\s+quanto\s+(riguarda|concerne)",            # Complex prepositional
            r"nell'ambito\s+di",                              # Domain-specific
            r"in\s+materia\s+di",                             # Technical context
            r"correlat[oi]\s+(a|con)",                        # Correlation expressions
            r"simil[ie]\s+(a|al)",                            # Similarity expressions
            r"tipo\s+di|genere\s+di|categoria\s+di"          # Classification queries
        ]

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Comprehensive query analysis for routing decision.

        Args:
            query: User query string

        Returns:
            QueryAnalysis with scoring and categorization
        """
        query_lower = query.lower().strip()
        words = query_lower.split()

        # Core analysis components
        complexity_score = self._calculate_complexity(query_lower, words)
        domain_terms = self._extract_domain_terms(query_lower)
        semantic_indicators = self._extract_semantic_indicators(query_lower)
        length_score = self._calculate_length_score(words)
        entity_count = len(domain_terms)
        query_type = self._classify_query_type(query_lower, words)

        return QueryAnalysis(
            complexity_score=complexity_score,
            domain_terms=domain_terms,
            semantic_indicators=semantic_indicators,
            length_score=length_score,
            entity_count=entity_count,
            query_type=query_type
        )

    def _calculate_complexity(self, query: str, words: List[str]) -> float:
        """Calculate query complexity score (0-1)"""
        score = 0.0

        # Pattern-based complexity (complex grammatical structures)
        for pattern in self.complexity_patterns:
            if re.search(pattern, query):
                score += 0.25
                break  # Don't double-count patterns

        # Word count complexity
        word_count = len(words)
        if word_count > 10:
            score += 0.3
        elif word_count > 6:
            score += 0.2
        elif word_count > 4:
            score += 0.1

        # Question word complexity (often need semantic understanding)
        question_words = ["quali", "che", "come", "dove", "quando", "perché", "cosa"]
        question_found = any(word in words for word in question_words)
        if question_found:
            score += 0.2

        # Semantic relationship words
        relationship_words = ["correlato", "simile", "riguardante", "relativo", "connesso"]
        if any(word in query for word in relationship_words):
            score += 0.25

        # Multiple domain terms suggest complex domain query
        domain_count = len(self._extract_domain_terms(query))
        if domain_count > 2:
            score += 0.2
        elif domain_count > 1:
            score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def _extract_domain_terms(self, query: str) -> List[str]:
        """Extract veterinary domain terms from query"""
        found_terms = []

        for term in self.veterinary_terms:
            if term in query:
                found_terms.append(term)

        return found_terms

    def _extract_semantic_indicators(self, query: str) -> List[str]:
        """Extract words that indicate need for semantic search"""
        found_indicators = []

        for indicator in self.semantic_indicators:
            if indicator in query:
                found_indicators.append(indicator)

        return found_indicators

    def _calculate_length_score(self, words: List[str]) -> float:
        """Calculate normalized length score (0-1)"""
        # Longer queries generally need more semantic understanding
        return min(len(words) / 12.0, 1.0)  # Normalize to 0-1, cap at 12 words

    def _classify_query_type(self, query: str, words: List[str]) -> str:
        """Classify the type of query for strategy optimization"""

        # Exact code patterns (piano codes like A1, B23)
        if re.match(r'^[A-Z]\d+[_-]?\w*$', query.upper().strip()):
            return "exact_code"

        # Simple keyword queries
        if len(words) <= 2 and not any(ind in query for ind in self.semantic_indicators):
            return "simple_keyword"

        # Question queries
        question_words = ["quali", "che", "come", "dove", "quando", "perché", "cosa"]
        if any(word in words for word in question_words):
            return "question"

        # Complex semantic queries with relationships
        if any(ind in query for ind in self.semantic_indicators):
            return "semantic_relationship"

        # Domain-specific queries
        if len(self._extract_domain_terms(query)) > 1:
            return "domain_specific"

        return "general"

    def _load_veterinary_terms(self) -> Set[str]:
        """Load comprehensive veterinary domain terms"""

        # Comprehensive veterinary terminology for Italian ASL context
        terms = {
            # Animal categories
            "bovini", "bovino", "vacche", "vitelli", "bufalini", "bufale",
            "suini", "suino", "maiali", "porci", "scrofe", "lattonzoli",
            "ovini", "ovino", "pecore", "agnelli", "montoni",
            "caprini", "caprino", "capre", "capretti", "becchi",
            "avicoli", "avicolo", "polli", "pollame", "galline", "galli",
            "equini", "equino", "cavalli", "puledri", "asini",
            "animali", "bestiame", "gregge", "mandria",

            # Food products
            "latte", "lattiero", "latticini", "caseario", "formaggi",
            "carne", "carni", "macellazione", "macello", "salumi",
            "miele", "prodotti dell'alveare", "api", "apicoltura",
            "uova", "ovoprodotti",

            # Farm operations
            "allevamenti", "allevamento", "stalla", "stalle",
            "aziende zootecniche", "azienda zootecnica",
            "zootecnico", "zootecnica", "zootecniche",
            "pascolo", "pascoli", "mangimi", "mangime", "alimentazione",

            # Health and welfare
            "benessere", "biosicurezza", "igiene", "sanità",
            "vaccini", "vaccinazioni", "profilassi",
            "malattie", "patologie", "zoonosi",
            "residui", "farmaci", "antibiotici", "fitosanitari",

            # Control and monitoring
            "controlli", "controllo", "ispezioni", "verifiche",
            "monitoraggio", "sorveglianza", "piani",
            "haccp", "autocontrollo", "tracciabilità",
            "etichettatura", "registrazione", "riconoscimento",

            # Specialized areas
            "acquacoltura", "ittico", "pesci", "molluschi",
            "selvaggina", "caccia", "fauna",
            "mangimifici", "stabilimenti", "impianti",
            "trasporto", "movimentazione",

            # Regulatory
            "nc", "non conformità", "sanzioni", "verbali",
            "normativa", "regolamento", "decreto",
            "asl", "uoc", "servizi veterinari"
        }

        return terms

    def get_analysis_summary(self, analysis: QueryAnalysis) -> str:
        """Get human-readable summary of query analysis"""

        summary_parts = []

        # Complexity assessment
        if analysis.complexity_score > 0.7:
            summary_parts.append("Query complessa")
        elif analysis.complexity_score > 0.4:
            summary_parts.append("Query media complessità")
        else:
            summary_parts.append("Query semplice")

        # Domain coverage
        if analysis.entity_count > 2:
            summary_parts.append(f"Multi-dominio ({analysis.entity_count} entità)")
        elif analysis.entity_count > 0:
            summary_parts.append("Domain-specific")

        # Semantic needs
        if len(analysis.semantic_indicators) > 0:
            summary_parts.append("Richiede comprensione semantica")

        # Query type
        summary_parts.append(f"Tipo: {analysis.query_type}")

        return " | ".join(summary_parts)