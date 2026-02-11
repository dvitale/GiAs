"""
Tool per ricerca stabilimenti per prossimità geografica.

Risponde a: "Quali stabilimenti controllare vicino a [indirizzo]?"
"""

from typing import Dict, Any, Optional
import pandas as pd

from langchain_core.tools import tool

try:
    from agents.data_agent import DataRetriever, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
    from tools.geo_utils import (
        GeocodingService,
        AddressNotFoundError,
        GeocodingTimeoutError,
        GeocodingError,
        get_geocoding_service
    )
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.data_agent import DataRetriever, RiskAnalyzer
    from agents.response_agent import ResponseFormatter
    from tools.geo_utils import (
        GeocodingService,
        AddressNotFoundError,
        GeocodingTimeoutError,
        GeocodingError,
        get_geocoding_service
    )


@tool("nearby_priority")
def get_nearby_priority(
    location: str,
    radius_km: float = 5.0,
    asl: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Trova stabilimenti mai controllati vicino a una posizione geografica.

    Geocodifica l'indirizzo, filtra stabilimenti per prossimità,
    e li ordina per distanza + rischio.

    Args:
        location: Indirizzo da geocodificare (es. "Via Roma 15, Napoli")
        radius_km: Raggio di ricerca in km (default 5)
        asl: Filtra per ASL specifica (opzionale)
        limit: Numero massimo di risultati (default 50)

    Returns:
        Dict con stabilimenti trovati e metadati ricerca
    """
    if not location or not location.strip():
        return {
            "error": "location_missing",
            "formatted_response": "Per favore specifica un indirizzo. Esempio: 'stabilimenti vicino a Piazza Garibaldi, Napoli'"
        }

    location = location.strip()

    # Geocodifica l'indirizzo
    try:
        geocoder = get_geocoding_service()
        geocode_result = geocoder.geocode_with_address(location)
        center_lat, center_lon, resolved_address = geocode_result
    except AddressNotFoundError:
        return {
            "error": "address_not_found",
            "location": location,
            "formatted_response": (
                f"Non ho trovato l'indirizzo **{location}**. "
                f"Prova a specificare meglio (es. aggiungi città o provincia)."
            )
        }
    except GeocodingTimeoutError:
        return {
            "error": "geocoding_timeout",
            "location": location,
            "formatted_response": "Il servizio di geolocalizzazione non risponde. Riprova tra qualche secondo."
        }
    except GeocodingError as e:
        return {
            "error": "geocoding_error",
            "location": location,
            "formatted_response": f"Errore durante la geolocalizzazione: {str(e)}"
        }

    # Verifica se la location è nel territorio dell'ASL dell'utente
    # Mapping ASL -> province di competenza
    if asl:
        asl_province_map = {
            'NAPOLI 1 CENTRO': ['napoli'],
            'NAPOLI 2 NORD': ['napoli'],
            'NAPOLI 3 SUD': ['napoli'],
            'SALERNO': ['salerno'],
            'CASERTA': ['caserta'],
            'AVELLINO': ['avellino'],
            'BENEVENTO': ['benevento'],
        }

        # Estrai la provincia dall'indirizzo risolto
        # Formato tipico: "Via X, Comune, Provincia, Campania, CAP, Italia"
        location_province = None
        if resolved_address:
            # Pulisci eventuali warning dall'indirizzo
            clean_address = resolved_address
            if "⚠️" in clean_address:
                import re
                clean_address = re.sub(r'⚠️ ATTENZIONE:\s*', '', clean_address)
                clean_address = re.sub(r'\s*\(NON è nel comune di[^)]+\)', '', clean_address)

            parts = [p.strip().lower() for p in clean_address.split(',')]
            # Cerca la provincia (parte prima di "campania")
            for i, part in enumerate(parts):
                if 'campania' in part and i > 0:
                    location_province = parts[i - 1]
                    break

        # Verifica se la provincia della location è nell'ASL dell'utente
        asl_upper = asl.upper()
        asl_provinces = asl_province_map.get(asl_upper, [])

        if location_province and asl_provinces:
            location_in_asl = any(prov in location_province for prov in asl_provinces)

            if not location_in_asl:
                # La location è fuori dal territorio dell'ASL
                location_province_display = location_province.title()
                return {
                    "error": "location_outside_asl",
                    "location": location,
                    "resolved_address": resolved_address,
                    "center_coords": (center_lat, center_lon),
                    "user_asl": asl,
                    "location_province": location_province_display,
                    "formatted_response": (
                        f"**📍 Posizione fuori dal territorio ASL**\n\n"
                        f"L'indirizzo **{location}** si trova in provincia di **{location_province_display}**, "
                        f"che non rientra nel territorio dell'**ASL {asl}**.\n\n"
                        f"La ricerca per prossimità mostra solo stabilimenti della tua ASL di competenza.\n\n"
                        f"**Suggerimenti:**\n"
                        f"- Cerca un indirizzo nella tua area di competenza\n"
                        f"- Oppure contatta l'ASL {location_province_display} per informazioni su quella zona"
                    )
                }

    # Recupera stabilimenti mai controllati
    osa_df = DataRetriever.get_osa_mai_controllati(asl=asl)

    if osa_df.empty:
        asl_msg = f" per l'ASL {asl}" if asl else ""
        return {
            "error": "no_osa_data",
            "location": location,
            "center_coords": center_coords,
            "radius_km": radius_km,
            "formatted_response": f"Non ci sono stabilimenti mai controllati disponibili{asl_msg}."
        }

    # Filtra per prossimità usando le coordinate già presenti nel database
    try:
        from tools.geo_utils import filter_by_proximity

        # Verifica che ci siano coordinate valide
        has_coords = 'latitudine_stab' in osa_df.columns and 'longitudine_stab' in osa_df.columns

        if has_coords:
            # Usa le coordinate esistenti
            nearby_df = filter_by_proximity(
                df=osa_df,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                lat_col='latitudine_stab',
                lon_col='longitudine_stab',
                address_col='indirizzo',
                comune_col='comune'
            )
        else:
            # Fallback: geocodifica da indirizzo+comune (limitato per performance)
            osa_with_address = osa_df[
                (osa_df['indirizzo'].notna()) &
                (osa_df['indirizzo'] != '') &
                (osa_df['comune'].notna()) &
                (osa_df['comune'] != '')
            ].copy()

            if osa_with_address.empty:
                return {
                    "error": "no_geocodable_addresses",
                    "location": location,
                    "center_coords": center_coords,
                    "radius_km": radius_km,
                    "formatted_response": (
                        f"Gli stabilimenti nel database non hanno coordinate o indirizzi geocodificabili. "
                        f"Impossibile calcolare la prossimità."
                    )
                }

            # Limita a 100 per geocodifica batch
            osa_sample = osa_with_address.head(100)

            nearby_df = filter_by_proximity(
                df=osa_sample,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                address_col='indirizzo',
                comune_col='comune'
            )

    except Exception as e:
        return {
            "error": "proximity_filter_error",
            "location": location,
            "center_coords": center_coords,
            "formatted_response": f"Errore durante il filtro per prossimità: {str(e)}"
        }

    if nearby_df.empty:
        return {
            "error": "no_nearby_establishments",
            "location": location,
            "center_coords": center_coords,
            "radius_km": radius_km,
            "total_found": 0,
            "formatted_response": (
                f"Nessun stabilimento mai controllato trovato entro {radius_km} km "
                f"da **{location}**. Prova ad aumentare il raggio."
            )
        }

    # Arricchisci con punteggio rischio se disponibile
    try:
        risk_scores = RiskAnalyzer.calculate_risk_scores()

        if not risk_scores.empty:
            # Join con risk scores per attività
            nearby_df = nearby_df.merge(
                risk_scores[['macroarea', 'aggregazione', 'linea_attivita', 'punteggio_rischio_totale']],
                left_on=['macroarea', 'aggregazione', 'attivita'],
                right_on=['macroarea', 'aggregazione', 'linea_attivita'],
                how='left'
            )

            # Fillna per stabilimenti senza risk score
            nearby_df['punteggio_rischio_totale'] = nearby_df['punteggio_rischio_totale'].fillna(0)

            # Ordina per distanza (primaria) + rischio (secondaria, decrescente)
            nearby_df = nearby_df.sort_values(
                by=['distanza_km', 'punteggio_rischio_totale'],
                ascending=[True, False]
            )
    except Exception as e:
        # Se fallisce il join con rischio, continua senza
        print(f"[nearby_priority] Warning: impossibile aggiungere risk scores: {e}")

    total_found = len(nearby_df)

    # Limita risultati
    nearby_df_display = nearby_df.head(limit)

    # Converti in lista di dict per serializzazione
    nearby_list = []
    for row in nearby_df_display.itertuples(index=False):
        num_ric = getattr(row, 'num_riconoscimento', '') or getattr(row, 'n_reg', '')
        if not num_ric or str(num_ric) == 'nan':
            num_ric = 'N/D'

        comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'

        risk_score = getattr(row, 'punteggio_rischio_totale', 0)
        try:
            risk_score = int(risk_score) if pd.notna(risk_score) else 0
        except (ValueError, TypeError):
            risk_score = 0

        nearby_list.append({
            'macroarea': str(getattr(row, 'macroarea', '')),
            'aggregazione': str(getattr(row, 'aggregazione', '')),
            'attivita': str(getattr(row, 'attivita', '')),
            'comune': comune,
            'indirizzo': str(getattr(row, 'indirizzo', '')),
            'num_riconoscimento': str(num_ric),
            'distanza_km': round(float(getattr(row, 'distanza_km', 0)), 2),
            'punteggio_rischio_totale': risk_score
        })

    # Formatta risposta con indirizzo pulito (senza warning interno)
    center_coords = (center_lat, center_lon)

    # Pulisci l'indirizzo dal warning per il formatter
    import re
    display_address = resolved_address
    display_address = re.sub(r'⚠️ ATTENZIONE:\s*', '', display_address)
    display_address = re.sub(r'\s*\(NON è nel comune di[^)]+\)', '', display_address)
    display_address = display_address.strip()

    formatted_response = ResponseFormatter.format_nearby_priority(
        location=display_address,
        center_coords=center_coords,
        radius_km=radius_km,
        nearby_df=nearby_df_display,
        total_found=total_found
    )

    # Se l'indirizzo risolto contiene un warning (centro città usato come fallback)
    if resolved_address and "⚠️ CENTRO CITTÀ:" in resolved_address:
        # Estrai l'indirizzo non trovato dal warning
        import re
        match = re.search(r"Indirizzo '([^']+)' non trovato in (\w+)", resolved_address)
        if match:
            addr_not_found = match.group(1)
            city_name = match.group(2)
            warning_msg = (
                f"**⚠️ Indirizzo non trovato**\n\n"
                f"L'indirizzo \"{addr_not_found}\" non è stato trovato in **{city_name}**.\n"
                f"Uso il **centro di {city_name}** come riferimento per la ricerca.\n\n"
                f"---\n\n"
            )
            formatted_response = warning_msg + formatted_response

    return {
        "location": location,
        "resolved_address": resolved_address,
        "center_coords": center_coords,
        "radius_km": radius_km,
        "total_found": total_found,
        "nearby_establishments": nearby_list,
        "asl": asl,
        "formatted_response": formatted_response
    }
