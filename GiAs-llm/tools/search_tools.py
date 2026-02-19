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


@tool("search_piani")
def search_piani_by_topic(query: str, similarity_threshold: float = 0.4) -> Dict[str, Any]:
    """
    Cerca piani di controllo per argomento sul database in memoria.

    Esegue ricerca testuale (ILIKE) sulle colonne descrizione e descrizione-2
    del DataFrame piani_monitoraggio gia' caricato in RAM al startup.

    Args:
        query: Termine di ricerca (es. "scrofe", "bovini", "residui")
        similarity_threshold: Non usato, mantenuto per compatibilita'

    Returns:
        Dict con piani trovati e risposta formattata
    """
    if not query or not query.strip():
        return {"error": "Query di ricerca non specificata"}

    search_term = query.strip()

    try:
        matches = DataRetriever.search_piani_by_db(search_term)

        if not matches:
            return {
                "error": f"Nessun piano trovato per '{search_term}'",
                "search_term": search_term,
                "total_found": 0,
                "search_strategy": "db_ilike",
                "formatted_response": f"Non ho trovato piani di monitoraggio che corrispondono a **'{search_term}'**.\n\nProva con termini più specifici come:\n- Bovini, suini, avicoli\n- Latte, carne, mangimi\n- Allevamenti\n- Nome specifico del piano (es. A1, B2)"
            }

        # Format response
        response = ResponseFormatter.format_search_results(
            search_term=search_term,
            matches=matches,
            max_display=10
        )

        return {
            "search_term": search_term,
            "total_found": len(matches),
            "matches": matches[:10],
            "search_strategy": "db_ilike",
            "formatted_response": response
        }

    except Exception as e:
        return {
            "error": f"Errore durante la ricerca: {str(e)}",
            "search_strategy": "db_ilike_failed"
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
