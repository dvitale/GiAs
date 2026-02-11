"""
Establishment History Tools

Tool per consultare lo storico controlli di stabilimenti specifici.
"""

try:
    from langchain_core.tools import tool
except ImportError:
    try:
        from langchain.tools import tool
    except ImportError:
        # Fallback if neither is available
        def tool(name: str):
            """Fallback decorator if langchain is not available"""
            def decorator(func):
                func.name = name
                return func
            return decorator
from typing import Dict, Any, Optional

try:
    from agents.data_agent import DataRetriever
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever


@tool("get_establishment_history")
def get_establishment_history(
    num_registrazione: Optional[str] = None,
    partita_iva: Optional[str] = None,
    ragione_sociale: Optional[str] = None
) -> Dict[str, Any]:
    """
    Recupera storico controlli e non conformità per uno stabilimento.

    Lo stabilimento può essere identificato tramite:
    - num_registrazione: numero di registrazione (es. "IT 123", "UE IT 2287 M")
    - partita_iva: partita IVA (solo numeri)
    - ragione_sociale: parte della ragione sociale (ricerca parziale)

    Almeno uno dei parametri deve essere specificato.

    Restituisce:
    - Storico controlli ordinati per data (più recenti primi)
    - Informazioni stabilimento
    - Riepilogo statistico controlli

    Args:
        num_registrazione: Numero registrazione stabilimento
        partita_iva: Partita IVA stabilimento
        ragione_sociale: Parte ragione sociale stabilimento

    Returns:
        Dict con:
        - formatted_response: Storico formattato
        - total_controls: Numero totale controlli
        - establishment_info: Info stabilimento
    """
    try:
        # Validazione: almeno un parametro
        if not any([num_registrazione, partita_iva, ragione_sociale]):
            return {
                "formatted_response": "❌ **Errore**: Specifica almeno uno dei seguenti parametri:\n"
                                     "- Numero di registrazione (es. 'IT 123')\n"
                                     "- Partita IVA\n"
                                     "- Ragione sociale (anche parziale)\n\n"
                                     "Esempio: 'storico controlli stabilimento IT 2287'",
                "error": "missing_parameters"
            }

        # Recupera storico da DataRetriever
        history_df = DataRetriever.get_establishment_history(
            num_registrazione=num_registrazione,
            partita_iva=partita_iva,
            ragione_sociale=ragione_sociale,
            limit=50  # Limita a 50 controlli più recenti
        )

        # Import formatter inline per evitare caching issues
        from agents.response_agent import ResponseFormatter

        # Gestione nessun risultato
        if history_df is None or history_df.empty:
            formatted_response = ResponseFormatter.format_establishment_history(
                history_df if history_df is not None else __import__('pandas').DataFrame(),
                num_registrazione=num_registrazione,
                partita_iva=partita_iva,
                ragione_sociale=ragione_sociale
            )

            return {
                "formatted_response": formatted_response,
                "total_controls": 0,
                "establishment_info": None
            }

        # Estrai info stabilimento
        first_row = history_df.iloc[0]
        establishment_info = {
            "ragione_sociale": first_row.get('ragione_sociale', 'N.D.'),
            "num_registrazione": first_row.get('num_registrazione', 'N.D.'),
            "partita_iva": first_row.get('partita_iva', 'N.D.'),
            "asl": first_row.get('descrizione_asl', 'N.D.')
        }

        # Formatta risposta
        formatted_response = ResponseFormatter.format_establishment_history(
            history_df,
            num_registrazione=num_registrazione,
            partita_iva=partita_iva,
            ragione_sociale=ragione_sociale
        )

        return {
            "formatted_response": formatted_response,
            "total_controls": len(history_df),
            "establishment_info": establishment_info,
            "history": history_df.to_dict('records'),
            "success": True
        }

    except Exception as e:
        print(f"❌ [get_establishment_history] Errore: {e}")
        import traceback
        traceback.print_exc()

        return {
            "formatted_response": f"❌ **Errore** durante il recupero dello storico controlli.\n\n"
                                 f"Dettaglio: {str(e)}\n\n"
                                 f"Verifica i parametri e riprova.",
            "error": str(e)
        }
