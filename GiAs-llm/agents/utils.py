"""
Utility functions for data processing
"""

from typing import List
import pandas as pd
from difflib import SequenceMatcher


def enhanced_similarity(term: str, text: str) -> float:
    """
    Calcola similarità semantica tra termine e testo.

    Args:
        term: Termine di ricerca
        text: Testo da confrontare

    Returns:
        Score di similarità (0-1)
    """
    if not term or not text:
        return 0.0

    term_lower = term.lower()
    text_lower = text.lower()

    if term_lower in text_lower:
        return 1.0

    return SequenceMatcher(None, term_lower, text_lower).ratio()


def expand_terms(keyword: str) -> List[str]:
    """
    Espande un termine di ricerca con sinonimi/varianti comuni del settore veterinario.

    Args:
        keyword: Parola chiave da espandere

    Returns:
        Lista di termini correlati
    """
    expansions = {
        'bovini': ['bovino', 'bovini', 'vacca', 'mucca', 'vitello', 'vitelli', 'bufalini', 'bufalino'],
        'suini': ['suino', 'suini', 'maiale', 'maiali', 'porco', 'suinicoli', 'suinicolo'],
        'ovicaprini': ['ovicaprino', 'ovicaprini', 'pecora', 'capra', 'ovino', 'caprino', 'ovini', 'caprini'],
        'avicoli': ['avicolo', 'avicoli', 'pollo', 'gallina', 'pollame', 'ovaiole', 'broiler'],
        'equini': ['equino', 'equini', 'cavallo', 'cavalli', 'equidi'],
        'latte': ['latte', 'lattiero', 'latticini', 'caseario', 'lattiero-caseario'],
        'carne': ['carne', 'carni', 'macello', 'macellazione'],
        'allevamenti': [
            'allevamento', 'allevamenti', 'stalla', 'stalle',
            'aziende zootecniche', 'azienda zootecnica',
            'zootecnico', 'zootecnica', 'zootecniche',
            'aziende', 'azienda', 'stabilimenti', 'stabilimento'
        ],
        'residui': ['residuo', 'residui', 'farmaco', 'farmaci', 'fitosanitari'],
        'acquacoltura': ['acquacoltura', 'ittico', 'pesci', 'pesca'],
        'apicoltura': ['apicoltura', 'api', 'miele'],
        'mangimi': ['mangime', 'mangimi', 'alimentazione', 'alimenti'],
        'benessere': ['benessere animale', 'benessere', 'biosicurezza'],
    }

    keyword_lower = keyword.lower()

    # Cerca espansione diretta
    for key, values in expansions.items():
        if keyword_lower == key or keyword_lower in values:
            return values

    # Cerca espansione parziale per parole composte
    for key, values in expansions.items():
        if keyword_lower in key or any(keyword_lower in val for val in values):
            return values + [keyword]

    return [keyword]


def filter_by_asl(df: pd.DataFrame, asl_code: str, asl_column: str = 'asl') -> pd.DataFrame:
    """
    Filtra DataFrame per codice ASL.

    Args:
        df: DataFrame da filtrare
        asl_code: Codice ASL (es. "NA1", "SA1")
        asl_column: Nome colonna contenente ASL

    Returns:
        DataFrame filtrato

    Raises:
        ValueError: Se la colonna ASL non esiste
    """
    if asl_column not in df.columns:
        raise ValueError(f"Colonna '{asl_column}' non trovata nel DataFrame")

    if not asl_code:
        return df

    return df[df[asl_column].str.upper() == asl_code.upper()].copy()
