from typing import Dict, Any, List

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(name):
        def decorator(func):
            return func
        return decorator

try:
    from agents.data_agent import DataRetriever
    from agents.response_agent import ResponseFormatter
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever
    from agents.response_agent import ResponseFormatter

# Import hybrid search engine
try:
    from tools.hybrid_search.hybrid_engine import HybridSearchEngine, HybridSearchConfig
    from tools.hybrid_search.smart_router import SearchStrategy
    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    print("⚠️  Hybrid search not available, using vector-only approach")
    HYBRID_SEARCH_AVAILABLE = False

# Global hybrid engine instance (singleton pattern)
_hybrid_engine = None
_hybrid_enabled = True  # Feature flag for gradual rollout


def get_hybrid_engine():
    """Get or create hybrid search engine instance"""
    global _hybrid_engine

    if not HYBRID_SEARCH_AVAILABLE or not _hybrid_enabled:
        return None

    if _hybrid_engine is None:
        try:
            # Configure hybrid engine
            config = HybridSearchConfig(
                vector_top_k=20,
                llm_rerank_top_k=10,
                max_hybrid_latency_ms=3000,
                vector_threshold=0.3,
                min_candidates_for_reranking=5
            )

            _hybrid_engine = HybridSearchEngine(config)

            # Try to inject LLM client from system
            try:
                from llm.client import LLMClient
                llm_client = LLMClient()
                _hybrid_engine.set_llm_client(llm_client)
                print("✅ Hybrid search engine initialized with LLM client")
            except Exception as e:
                print(f"⚠️  Hybrid engine initialized without LLM client: {e}")

        except Exception as e:
            print(f"❌ Failed to initialize hybrid search engine: {e}")
            _hybrid_engine = None

    return _hybrid_engine


def disable_hybrid_search():
    """Disable hybrid search (fallback to vector-only)"""
    global _hybrid_enabled
    _hybrid_enabled = False
    print("🔄 Hybrid search disabled, using vector-only mode")


def enable_hybrid_search():
    """Enable hybrid search"""
    global _hybrid_enabled
    if HYBRID_SEARCH_AVAILABLE:
        _hybrid_enabled = True
        print("✅ Hybrid search enabled")
    else:
        print("❌ Cannot enable hybrid search - components not available")


@tool("search_piani")
def search_piani_by_topic(query: str, similarity_threshold: float = 0.4) -> Dict[str, Any]:
    """
    Cerca piani di controllo usando approccio ibrido intelligente.

    Utilizza automaticamente la strategia ottimale:
    - Vector-only: Query semplici, risposta veloce richiesta
    - LLM-only: Query semantiche complesse
    - Hybrid: Approccio bilanciato con reranking LLM su candidati vector

    Args:
        query: Termine di ricerca (es. "allevamenti", "bovini", "residui")
        similarity_threshold: Soglia di similarità minima (default 0.4)

    Returns:
        Dict con piani trovati, strategia utilizzata, e metriche di performance
    """
    if not query or not query.strip():
        return {"error": "Query di ricerca non specificata"}

    search_term = query.strip()

    # Try hybrid search first
    hybrid_engine = get_hybrid_engine()
    if hybrid_engine:
        try:
            # Build metadata for smart routing
            metadata = {
                "similarity_threshold": similarity_threshold,
                "user_preference": "balanced",  # Could be dynamic
                "require_fast_response": False
            }

            # Execute hybrid search with intelligent strategy selection
            result = hybrid_engine.search(search_term, metadata)

            # Ensure backward compatibility with existing response format
            if result and not result.get("error"):
                return result
            else:
                print(f"⚠️  Hybrid search failed, falling back to legacy vector search")

        except Exception as e:
            print(f"⚠️  Hybrid search error: {e}, falling back to legacy vector search")

    # Legacy vector search fallback
    return _legacy_vector_search(search_term, similarity_threshold)


def _legacy_vector_search(search_term: str, similarity_threshold: float) -> Dict[str, Any]:
    """
    Legacy vector search implementation (original code) used as fallback.
    """
    try:
        matches = DataRetriever.search_piani_semantic(
            query=search_term,
            top_k=15,
            score_threshold=similarity_threshold
        )

        if not matches:
            print(f"⚠️  Semantic search returned 0 results, trying keyword fallback...")

            veterinary_keywords = [
                "bovini", "bovino", "vacche", "vitelli", "bufalini",
                "suini", "suino", "maiali", "porci",
                "ovini", "ovino", "pecore", "agnelli",
                "caprini", "caprino", "capre",
                "avicoli", "avicolo", "polli", "pollame", "galline",
                "equini", "equino", "cavalli",
                "latte", "lattiero", "caseario", "latticini",
                "carne", "macellazione", "macello", "carni",
                "mangimi", "mangime", "alimentazione",
                "allevamenti", "allevamento", "zootecniche", "zootecnia", "zootecnico",
                "benessere", "biosicurezza",
                "salmonella", "residui", "farmaco", "farmaci",
                "api", "apicoltura", "miele",
                "acquacoltura", "ittico", "pesca", "pesci"
            ]

            found_keywords = [kw for kw in veterinary_keywords if kw in search_term.lower()]
            if found_keywords:
                search_term_fallback = " ".join(found_keywords)
            else:
                search_term_fallback = search_term

            matches = DataRetriever.search_piani_by_keyword(
                search_term_fallback,
                similarity_threshold=similarity_threshold
            )

        if not matches:
            return {
                "error": f"Nessun piano trovato per '{search_term}'",
                "search_term": search_term,
                "total_found": 0,
                "search_strategy": "legacy_vector",
                "formatted_response": f"Non ho trovato piani di monitoraggio che corrispondono a **'{search_term}'**.\n\nProva con termini più specifici come:\n- Bovini, suini, avicoli\n- Latte, carne, mangimi\n- Allevamenti\n- Nome specifico del piano (es. A1, B2)"
            }

        # Remove duplicates
        unique_piani = {}
        for match in matches:
            alias = match['alias']
            if alias not in unique_piani or match['similarity'] > unique_piani[alias]['similarity']:
                unique_piani[alias] = match

        matches_list = list(unique_piani.values())

        # Format response
        response = ResponseFormatter.format_search_results(
            search_term=search_term,
            matches=matches_list,
            max_display=10
        )

        return {
            "search_term": search_term,
            "total_found": len(matches_list),
            "matches": matches_list[:10],
            "search_strategy": "legacy_vector",
            "formatted_response": response
        }

    except Exception as e:
        return {
            "error": f"Errore durante la ricerca: {str(e)}",
            "search_strategy": "legacy_vector_failed"
        }


def search_tool(query: str = None) -> Dict[str, Any]:
    """
    Router per funzionalità di ricerca.

    Args:
        query: Termine di ricerca

    Returns:
        Dict con risultati ricerca
    """
    try:
        search_func = search_piani_by_topic.func if hasattr(search_piani_by_topic, 'func') else search_piani_by_topic
        return search_func(query)
    except Exception as e:
        return {"error": f"Errore in search_tool: {str(e)}"}
