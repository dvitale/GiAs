"""
LLM Reranker for Hybrid Search

Uses LLM reasoning to rerank vector search candidates for improved semantic precision.
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class RerankingResult:
    """Result of LLM reranking operation"""
    reranked_items: List[Dict[str, Any]]
    confidence_score: float
    reasoning: str
    processing_time_ms: float
    fallback_used: bool = False

class LLMReranker:
    """
    LLM-powered reranker that improves vector search precision through semantic understanding.

    Uses structured prompts to have the LLM reason about semantic relevance
    and reorder candidates based on true meaning rather than just similarity scores.
    """

    def __init__(self, llm_client=None, timeout_ms: int = None):
        """
        Initialize LLM reranker.

        Args:
            llm_client: LLM client instance (will be injected from main system)
            timeout_ms: Timeout in milliseconds for LLM calls (None = use client default)
        """
        self.llm_client = llm_client  # Will be set by dependency injection
        self.timeout_s = timeout_ms / 1000.0 if timeout_ms is not None else None
        self.reranking_prompt_template = self._build_prompt_template()
        self.max_candidates = 20  # Maximum candidates to rerank
        self.max_tokens = 500  # Token limit for reranking response

    def rerank_candidates(self, query: str, candidates: List[Dict[str, Any]],
                         top_k: int = 10, context: Dict[str, Any] = None) -> RerankingResult:
        """
        Rerank search candidates using LLM semantic understanding.

        Args:
            query: Original user query
            candidates: List of candidate results from vector search
            top_k: Number of top results to return
            context: Additional context (ASL, user info, etc.)

        Returns:
            RerankingResult with reranked candidates and metadata
        """
        import time
        start_time = time.time()

        try:
            # Validate inputs
            if not query or not candidates:
                return self._create_fallback_result(candidates, start_time, "Empty input")

            if len(candidates) <= top_k:
                # Not enough candidates to rerank meaningfully
                return self._create_passthrough_result(candidates, start_time)

            # Limit candidates to manageable number for context window
            working_candidates = candidates[:self.max_candidates]

            # Build reranking prompt
            prompt = self._build_reranking_prompt(
                query=query,
                candidates=working_candidates,
                top_k=top_k,
                context=context or {}
            )

            # Get LLM reranking
            if not self.llm_client:
                return self._create_fallback_result(candidates, start_time, "No LLM client available")

            llm_response = self._call_llm_with_fallback(prompt)

            if not llm_response:
                return self._create_fallback_result(candidates, start_time, "LLM call failed")

            # Parse LLM response
            reranking_data = self._parse_llm_response(llm_response)

            if not reranking_data:
                return self._create_fallback_result(candidates, start_time, "Failed to parse LLM response")

            # Apply reranking to candidates
            reranked_candidates = self._apply_reranking(
                candidates=working_candidates,
                reranking_data=reranking_data,
                top_k=top_k
            )

            processing_time = (time.time() - start_time) * 1000

            return RerankingResult(
                reranked_items=reranked_candidates,
                confidence_score=reranking_data.get("confidence", 0.8),
                reasoning=reranking_data.get("reasoning", "LLM semantic reranking applied"),
                processing_time_ms=processing_time,
                fallback_used=False
            )

        except Exception as e:
            print(f"❌ LLM reranking failed: {e}")
            return self._create_fallback_result(candidates, start_time, f"Exception: {str(e)}")

    def _build_prompt_template(self) -> str:
        """Build the core prompt template for LLM reranking"""

        return """Sei un esperto del sistema di monitoraggio veterinario della Regione Campania con profonda conoscenza del dominio ASL.

COMPITO: Riordina i piani di monitoraggio per RILEVANZA SEMANTICA rispetto alla query dell'operatore.

QUERY OPERATORE: "{query}"
{context_section}

CANDIDATI DA RIORDINARE:
{candidates_context}

CRITERI DI RANKING (ordine di importanza):
1. **Rilevanza semantica diretta**: Il piano risponde direttamente alla richiesta?
2. **Comprensione dominio veterinario**: Correlazioni tecniche nel settore
3. **Intent operatore ASL**: Cosa sta realmente cercando l'operatore?
4. **Correlazioni concettuali**: Relazioni indirette ma rilevanti

IMPORTANTE:
- NON limitarti al keyword matching
- Considera sinonimi, correlazioni e contesto veterinario
- Pensa come un esperto ASL che conosce le interconnessioni tra piani

RISPOSTA (JSON rigoroso):
{{
    "reasoning": "Spiegazione concisa della logica di ranking (max 100 parole)",
    "confidence": 0.85,
    "reranked_plans": [
        {{"alias": "A1", "relevance_score": 0.95, "rationale": "motivo specifico"}},
        {{"alias": "B2", "relevance_score": 0.87, "rationale": "motivo specifico"}},
        // ... ordina per relevance_score decrescente, massimo {top_k} piani
    ]
}}

Concentrati sui {top_k} piani più rilevanti."""

    def _build_reranking_prompt(self, query: str, candidates: List[Dict],
                               top_k: int, context: Dict[str, Any]) -> str:
        """Build specific reranking prompt for current query"""

        # Build context section
        context_parts = []
        if context.get("asl"):
            context_parts.append(f"ASL: {context['asl']}")
        if context.get("uoc"):
            context_parts.append(f"UOC: {context['uoc']}")
        if context.get("user_type"):
            context_parts.append(f"Tipo operatore: {context['user_type']}")

        context_section = f"CONTESTO: {', '.join(context_parts)}" if context_parts else ""

        # Build candidates context (optimized for token efficiency)
        candidates_lines = []
        for i, candidate in enumerate(candidates, 1):
            alias = candidate.get('alias', f'Plan_{i}')

            # Combine descriptions efficiently
            desc_parts = []
            if candidate.get('descrizione'):
                desc_parts.append(str(candidate['descrizione']))
            if candidate.get('descrizione_2') or candidate.get('descrizione-2'):
                desc_parts.append(str(candidate.get('descrizione_2') or candidate.get('descrizione-2')))

            full_desc = " ".join(desc_parts).strip()

            # Truncate long descriptions
            if len(full_desc) > 120:
                full_desc = full_desc[:117] + "..."

            # Include vector score as additional context
            vector_score = candidate.get('similarity', 0.0)

            candidates_lines.append(f"{i}. {alias}: {full_desc} (vector: {vector_score:.2f})")

        candidates_context = "\n".join(candidates_lines)

        # Fill template
        return self.reranking_prompt_template.format(
            query=query,
            context_section=context_section,
            candidates_context=candidates_context,
            top_k=top_k
        )

    def _call_llm_with_fallback(self, prompt: str) -> Optional[str]:
        """Call LLM with error handling and fallbacks"""

        try:
            # Try primary LLM call with json_mode for structured output
            response = self.llm_client.query(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistent ranking
                max_tokens=self.max_tokens,
                json_mode=True,
                timeout=self.timeout_s if self.timeout_s else None
            )

            return response

        except Exception as e:
            print(f"⚠️  Primary LLM call failed: {e}")

            # Try simplified prompt as fallback
            try:
                simple_prompt = self._build_simple_fallback_prompt(prompt)
                response = self.llm_client.query(
                    prompt=simple_prompt,
                    temperature=0.2,
                    max_tokens=200,
                    json_mode=True,
                    timeout=self.timeout_s if self.timeout_s else None
                )
                return response

            except Exception as e2:
                print(f"❌ Fallback LLM call also failed: {e2}")
                return None

    def _build_simple_fallback_prompt(self, original_prompt: str) -> str:
        """Build simplified prompt for fallback scenarios"""

        # Extract just the essential parts
        query_match = re.search(r'QUERY OPERATORE: "([^"]+)"', original_prompt)
        candidates_match = re.search(r'CANDIDATI DA RIORDINARE:\n(.*?)\n\nCRITERI', original_prompt, re.DOTALL)

        if not query_match or not candidates_match:
            return "Errore nel parsing del prompt originale."

        query = query_match.group(1)
        candidates = candidates_match.group(1)

        return f"""Riordina questi piani per rilevanza alla query: "{query}"

{candidates}

Rispondi con JSON: {{"reranked_plans": [{{"alias": "A1", "relevance_score": 0.9}}]}}"""

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM reranking response with robust error handling and fallback chain."""

        if not response:
            return None

        try:
            # 1. Try direct parse (json_mode should produce clean JSON)
            try:
                parsed = json.loads(response.strip())
            except json.JSONDecodeError:
                # 2. Try extracting from ```json blocks
                json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_block_match:
                    try:
                        parsed = json.loads(json_block_match.group(1))
                    except json.JSONDecodeError:
                        parsed = None
                else:
                    parsed = None

                # 3. Balanced JSON extraction fallback
                if parsed is None:
                    extracted = self._extract_balanced_json(response)
                    if extracted:
                        try:
                            parsed = json.loads(extracted)
                        except json.JSONDecodeError:
                            parsed = None

                if parsed is None:
                    print("⚠️  No valid JSON found in LLM response")
                    return self._parse_fallback_response(response)

            # Validate structure
            if "reranked_plans" not in parsed:
                print("⚠️  Missing 'reranked_plans' in LLM response")
                return None

            # Validate each plan entry
            valid_plans = []
            for plan in parsed["reranked_plans"]:
                if isinstance(plan, dict) and "alias" in plan:
                    # Set default relevance score if missing
                    if "relevance_score" not in plan:
                        plan["relevance_score"] = 0.7
                    valid_plans.append(plan)

            parsed["reranked_plans"] = valid_plans

            # Set defaults for optional fields
            if "confidence" not in parsed:
                parsed["confidence"] = 0.8
            if "reasoning" not in parsed:
                parsed["reasoning"] = "LLM semantic reranking applied"

            return parsed

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing failed: {e}")
            return self._parse_fallback_response(response)
        except Exception as e:
            print(f"⚠️  Unexpected error parsing LLM response: {e}")
            return None

    def _parse_fallback_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Fallback parsing for cases where JSON parsing fails"""

        # Look for plan aliases mentioned in response (simple heuristic)
        plan_pattern = r'\b[A-Z]\d+[_\w]*\b'
        found_plans = re.findall(plan_pattern, response)

        if not found_plans:
            return None

        # Create basic reranking structure
        reranked_plans = []
        for i, alias in enumerate(found_plans[:10]):  # Limit to top 10
            relevance_score = 0.9 - (i * 0.1)  # Decreasing relevance
            reranked_plans.append({
                "alias": alias,
                "relevance_score": max(relevance_score, 0.1),
                "rationale": f"Mentioned in LLM response (position {i+1})"
            })

        return {
            "reranked_plans": reranked_plans,
            "confidence": 0.6,  # Lower confidence for fallback parsing
            "reasoning": "Fallback parsing - plan aliases extracted from response"
        }

    def _extract_balanced_json(self, text: str) -> str:
        """Extract first balanced JSON object from text."""
        start = text.find('{')
        if start == -1:
            return ""
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return ""

    def _apply_reranking(self, candidates: List[Dict], reranking_data: Dict,
                        top_k: int) -> List[Dict[str, Any]]:
        """Apply LLM reranking to candidate list"""

        if not reranking_data.get("reranked_plans"):
            return candidates[:top_k]

        # Create mapping alias -> candidate
        candidates_map = {c.get('alias', ''): c for c in candidates}

        # Build reranked list following LLM order
        reranked_results = []
        used_aliases = set()

        for plan_info in reranking_data["reranked_plans"]:
            alias = plan_info.get("alias", "")

            if alias in candidates_map and alias not in used_aliases:
                # Get original candidate and enhance with LLM insights
                candidate = candidates_map[alias].copy()

                # Add LLM reranking metadata
                candidate["llm_relevance_score"] = plan_info.get("relevance_score", 0.7)
                candidate["llm_rationale"] = plan_info.get("rationale", "LLM determined relevance")
                candidate["rerank_position"] = len(reranked_results) + 1

                reranked_results.append(candidate)
                used_aliases.add(alias)

                # Stop when we have enough results
                if len(reranked_results) >= top_k:
                    break

        # Fill remaining slots with unused candidates (preserve some vector insights)
        if len(reranked_results) < top_k:
            remaining_candidates = [
                c for c in candidates
                if c.get('alias', '') not in used_aliases
            ]

            for candidate in remaining_candidates[:top_k - len(reranked_results)]:
                candidate = candidate.copy()
                candidate["llm_relevance_score"] = 0.5  # Default score for non-reranked
                candidate["llm_rationale"] = "Not reranked by LLM, using vector score"
                candidate["rerank_position"] = len(reranked_results) + 1
                reranked_results.append(candidate)

        return reranked_results

    def _create_fallback_result(self, candidates: List[Dict], start_time: float,
                               reason: str) -> RerankingResult:
        """Create fallback result when LLM reranking fails"""

        processing_time = (time.time() - start_time) * 1000

        return RerankingResult(
            reranked_items=candidates[:10],  # Return top vector results
            confidence_score=0.6,  # Lower confidence for fallback
            reasoning=f"Fallback to vector order: {reason}",
            processing_time_ms=processing_time,
            fallback_used=True
        )

    def _create_passthrough_result(self, candidates: List[Dict],
                                  start_time: float) -> RerankingResult:
        """Create passthrough result when reranking isn't needed"""

        processing_time = (time.time() - start_time) * 1000

        return RerankingResult(
            reranked_items=candidates,
            confidence_score=0.8,  # Good confidence since no reranking needed
            reasoning="Few candidates, no reranking needed",
            processing_time_ms=processing_time,
            fallback_used=False
        )

    def set_llm_client(self, llm_client):
        """Set LLM client (dependency injection pattern)"""
        self.llm_client = llm_client

    def get_reranking_stats(self) -> Dict[str, Any]:
        """Get statistics about reranking performance (would be enhanced with tracking)"""

        return {
            "max_candidates": self.max_candidates,
            "max_tokens": self.max_tokens,
            "fallback_strategies": ["simplified_prompt", "alias_extraction"],
            "status": "operational" if self.llm_client else "no_llm_client"
        }