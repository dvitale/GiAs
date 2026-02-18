"""
Utility per geocodifica e calcolo distanze geografiche.

Usa Nominatim (OpenStreetMap) per geocodifica gratuita.
Include cache LRU per ottimizzare le chiamate ripetute.
"""

import logging
import time
from functools import lru_cache
from typing import Tuple, Optional, List
import pandas as pd

try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
    from geopy.point import Point
    from geopy.extra.rate_limiter import RateLimiter
    from geopy.adapters import BaseSyncAdapter, AdapterHTTPError
    import requests
    from requests.adapters import HTTPAdapter
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    Nominatim = None
    geodesic = None
    Point = None
    RateLimiter = None
    BaseSyncAdapter = None

logger = logging.getLogger(__name__)


# =============================================================================
# Adapter custom per evitare bug ssl_context con Nominatim/Varnish CDN
# Il default ssl_context di geopy causa HTTP 509 con Nominatim
# =============================================================================

class SimpleRequestsAdapter(BaseSyncAdapter if BaseSyncAdapter else object):
    """
    Adapter requests senza ssl_context custom.

    Nominatim (tramite Varnish CDN) fa TLS fingerprinting e rifiuta
    connessioni con ssl_context personalizzato (errore 509).
    Questo adapter usa il comportamento default di requests.
    """

    is_available = GEOPY_AVAILABLE

    def __init__(self, *, proxies, ssl_context, **kwargs):
        if not GEOPY_AVAILABLE:
            raise ImportError("geopy non disponibile")
        # Ignora ssl_context - causa 509 con Nominatim
        super().__init__(proxies=proxies, ssl_context=None)

        self.session = requests.Session()
        self.session.trust_env = False

        # HTTPAdapter standard senza ssl_context custom
        adapter = HTTPAdapter(max_retries=2)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def get_text(self, url, *, timeout, headers):
        resp = self._request(url, timeout=timeout, headers=headers)
        return resp.text

    def get_json(self, url, *, timeout, headers):
        resp = self._request(url, timeout=timeout, headers=headers)
        return resp.json()

    def _request(self, url, *, timeout, headers):
        try:
            resp = self.session.get(url, timeout=timeout, headers=headers)
        except requests.Timeout:
            raise GeocoderTimedOut('Service timed out')
        except requests.ConnectionError as e:
            raise GeocoderUnavailable(str(e))
        except Exception as e:
            raise GeocoderServiceError(str(e))

        if resp.status_code >= 400:
            raise AdapterHTTPError(
                f'Non-successful status code {resp.status_code}',
                status_code=resp.status_code,
                headers=resp.headers,
                text=resp.text,
            )
        return resp

    def __del__(self):
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass


# Eccezioni custom
class GeocodingError(Exception):
    """Eccezione base per errori di geocodifica."""
    pass


class AddressNotFoundError(GeocodingError):
    """Indirizzo non trovato."""
    pass


class GeocodingTimeoutError(GeocodingError):
    """Timeout durante la geocodifica."""
    pass


class GeocodingService:
    """
    Servizio geocodifica con cache LRU.

    Usa Nominatim (OSM) con user-agent personalizzato.
    Le coordinate sono sempre restituite come (latitudine, longitudine).
    """

    _instance = None
    _geolocator = None

    def __new__(cls):
        """Singleton pattern per riusare la stessa istanza."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inizializza il geolocator se non già fatto."""
        if self._initialized:
            return

        if not GEOPY_AVAILABLE:
            logger.warning("geopy non disponibile - geocodifica disabilitata")
            self._geolocator = None
            self._geocode_fn = None
        else:
            # Usa adapter custom per evitare bug ssl_context (HTTP 509)
            base_geolocator = Nominatim(
                user_agent="GIAS-VeterinaryAssistant/1.0 (gisa@regione.campania.it)",
                timeout=10,
                adapter_factory=SimpleRequestsAdapter
            )
            self._geolocator = base_geolocator
            # Rate limiter: max 1 richiesta al secondo (richiesto da Nominatim ToS)
            if RateLimiter:
                self._geocode_fn = RateLimiter(
                    base_geolocator.geocode,
                    min_delay_seconds=1.0,
                    max_retries=2,
                    error_wait_seconds=5.0
                )
                logger.info("GeocodingService inizializzato con Nominatim + SimpleAdapter + RateLimiter")
            else:
                self._geocode_fn = base_geolocator.geocode
                logger.info("GeocodingService inizializzato con Nominatim + SimpleAdapter")

        self._initialized = True

    def geocode(self, address: str) -> Tuple[float, float]:
        """
        Geocodifica un indirizzo in coordinate (lat, lon).

        Args:
            address: Indirizzo da geocodificare (es. "Via Roma 15, Napoli")

        Returns:
            Tuple (latitudine, longitudine)

        Raises:
            AddressNotFoundError: Se l'indirizzo non viene trovato
            GeocodingTimeoutError: Se il servizio non risponde
            GeocodingError: Per altri errori di geocodifica
        """
        result = self.geocode_with_address(address)
        return (result[0], result[1])

    @lru_cache(maxsize=500)
    def geocode_with_address(self, address: str) -> Tuple[float, float, str]:
        """
        Geocodifica un indirizzo e restituisce anche l'indirizzo risolto.

        Strategia "city-first":
        1. Prima geocodifica il comune/città per avere coordinate di riferimento
        2. Poi cerca l'indirizzo specifico con viewbox centrato sul comune
        3. Se non trova o risultato troppo lontano, usa centro città + warning

        Args:
            address: Indirizzo da geocodificare

        Returns:
            Tuple (latitudine, longitudine, indirizzo_risolto)
        """
        if not self._geocode_fn:
            raise GeocodingError("Servizio geocodifica non disponibile")

        if not address or not address.strip():
            raise AddressNotFoundError("Indirizzo vuoto")

        import re
        address_normalized = address.strip()
        addr_lower = address_normalized.lower()

        # Mappa capoluoghi di provincia campani
        capoluoghi = {
            'napoli': ('Napoli', 40.8518, 14.2681),
            'salerno': ('Salerno', 40.6824, 14.7681),
            'caserta': ('Caserta', 41.0725, 14.3311),
            'avellino': ('Avellino', 40.9146, 14.7906),
            'benevento': ('Benevento', 41.1297, 14.7826),
        }

        # Raggio massimo dal centro città (km) per considerare il risultato valido
        MAX_DISTANCE_FROM_CENTER_KM = 6.0

        # Estrai città e parte indirizzo
        target_city = None
        target_coords = None
        address_part = None

        for city_key, (city_name, city_lat, city_lon) in capoluoghi.items():
            if city_key in addr_lower:
                target_city = city_name
                target_coords = (city_lat, city_lon)
                # Estrai la parte indirizzo rimuovendo il nome città
                pattern = re.compile(rf',?\s*{city_key}\s*,?', re.IGNORECASE)
                address_part = pattern.sub('', address_normalized).strip().strip(',').strip()
                break

        try:
            # STEP 1: Se c'è una città, prima geocodifica la città per avere il centro di riferimento
            if target_city and target_coords:
                city_lat, city_lon = target_coords

                # STEP 2: Se c'è una parte indirizzo, cerca l'indirizzo nel comune
                if address_part:
                    # Crea viewbox stretto centrato sulla città (circa 5km)
                    radius = 0.05  # ~5km
                    city_viewbox = [
                        Point(city_lat + radius, city_lon - radius),
                        Point(city_lat - radius, city_lon + radius)
                    ] if Point else None

                    # Prova varie formulazioni dell'indirizzo
                    search_variants = [
                        f"{address_part}, {target_city}, BN, Italia",
                        f"{address_part}, {target_city}, Campania, Italia",
                        f"{address_part}, comune di {target_city}, Campania, Italia",
                    ]

                    location = None
                    for variant in search_variants:
                        if city_viewbox:
                            # Prima prova bounded
                            location = self._geocode_fn(variant, viewbox=city_viewbox, bounded=True)
                        if location is None:
                            location = self._geocode_fn(variant)

                        if location:
                            # Verifica che il risultato sia vicino al centro città
                            dist = calculate_distance_km(
                                city_lat, city_lon,
                                location.latitude, location.longitude
                            )
                            if dist <= MAX_DISTANCE_FROM_CENTER_KM:
                                # Risultato valido, dentro il comune
                                resolved = location.address if hasattr(location, 'address') else address
                                logger.debug(f"Geocodificato '{address}' -> ({location.latitude}, {location.longitude}) [{resolved}]")
                                return (location.latitude, location.longitude, resolved)
                            else:
                                # Risultato troppo lontano, scarta e prova la prossima variante
                                logger.debug(f"Risultato per '{variant}' troppo lontano ({dist:.1f} km), scarto")
                                location = None

                    # STEP 3: Indirizzo non trovato nel comune -> usa centro città + warning
                    logger.warning(f"Indirizzo '{address_part}' non trovato in {target_city}, uso centro città")
                    warning_address = (
                        f"⚠️ CENTRO CITTÀ: Indirizzo '{address_part}' non trovato in {target_city}. "
                        f"Uso il centro di {target_city} come riferimento."
                    )
                    return (city_lat, city_lon, warning_address)

                else:
                    # Solo nome città, senza indirizzo specifico
                    return (city_lat, city_lon, f"{target_city}, Campania, Italia (centro città)")

            # =================================================================
            # STEP GENERICO: city-first per comuni non capoluogo
            # Splitta "Via X, Comune Y" → geocodifica il comune, poi
            # cerca la via con viewbox centrato sul comune.
            # =================================================================
            parts = [p.strip() for p in address_normalized.split(',') if p.strip()]
            if len(parts) >= 2:
                # Ultimo segmento = comune candidato, resto = via/indirizzo
                city_candidate = parts[-1].strip()
                street_candidate = ', '.join(parts[:-1]).strip()

                # Pulisci preposizioni spurie: "in via" → "via", "in piazza" → "piazza"
                street_candidate = re.sub(
                    r'^(?:in|al|alla|allo|alle|agli|ai)\s+',
                    '', street_candidate, flags=re.IGNORECASE
                ).strip()

                try:
                    city_location = self._geocode_fn(f"{city_candidate}, Campania, Italia")
                    if city_location:
                        city_lat = city_location.latitude
                        city_lon = city_location.longitude

                        if street_candidate:
                            radius = 0.05  # ~5km
                            city_viewbox = [
                                Point(city_lat + radius, city_lon - radius),
                                Point(city_lat - radius, city_lon + radius)
                            ] if Point else None

                            search_variants = [
                                f"{street_candidate}, {city_candidate}, Campania, Italia",
                                f"{street_candidate}, comune di {city_candidate}, Campania, Italia",
                            ]

                            location = None
                            for variant in search_variants:
                                if city_viewbox:
                                    location = self._geocode_fn(variant, viewbox=city_viewbox, bounded=True)
                                if location is None:
                                    location = self._geocode_fn(variant)
                                if location:
                                    dist = calculate_distance_km(
                                        city_lat, city_lon,
                                        location.latitude, location.longitude
                                    )
                                    if dist <= MAX_DISTANCE_FROM_CENTER_KM:
                                        resolved = location.address if hasattr(location, 'address') else address
                                        logger.debug(f"Geocodificato '{address}' -> ({location.latitude}, {location.longitude}) [{resolved}]")
                                        return (location.latitude, location.longitude, resolved)
                                    else:
                                        logger.debug(f"Risultato per '{variant}' troppo lontano ({dist:.1f} km), scarto")
                                        location = None

                            # Via non trovata nel comune → usa centro comune + warning
                            logger.warning(f"Indirizzo '{street_candidate}' non trovato in {city_candidate}, uso centro comune")
                            warning_address = (
                                f"⚠️ CENTRO CITTÀ: Indirizzo '{street_candidate}' non trovato in {city_candidate}. "
                                f"Uso il centro di {city_candidate} come riferimento."
                            )
                            return (city_lat, city_lon, warning_address)
                        else:
                            # Solo comune, nessuna via
                            resolved = city_location.address if hasattr(city_location, 'address') else city_candidate
                            return (city_lat, city_lon, resolved)
                except (GeocoderTimedOut, GeocoderServiceError):
                    raise
                except Exception as e:
                    logger.debug(f"Generic city-first fallback failed for '{address}': {e}")

            # Nessun capoluogo riconosciuto e city-first non applicabile, cerca normalmente
            if "italia" not in addr_lower and "italy" not in addr_lower:
                address_normalized = f"{address_normalized}, Campania, Italia"

            location = self._geocode_fn(address_normalized)

            if location is None:
                raise AddressNotFoundError(f"Indirizzo non trovato: {address}")

            resolved_address = location.address if hasattr(location, 'address') else address
            logger.debug(f"Geocodificato '{address}' -> ({location.latitude}, {location.longitude}) [{resolved_address}]")
            return (location.latitude, location.longitude, resolved_address)

        except GeocoderTimedOut:
            raise GeocodingTimeoutError("Il servizio di geolocalizzazione non risponde. Riprova tra qualche secondo.")
        except GeocoderServiceError as e:
            raise GeocodingError(f"Errore servizio geocodifica: {str(e)}")
        except Exception as e:
            if "not found" in str(e).lower():
                raise AddressNotFoundError(f"Indirizzo non trovato: {address}")
            raise GeocodingError(f"Errore geocodifica: {str(e)}")

    def geocode_safe(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Versione safe di geocode che ritorna None invece di eccezioni.

        Args:
            address: Indirizzo da geocodificare

        Returns:
            Tuple (lat, lon) o None se fallisce
        """
        try:
            return self.geocode(address)
        except GeocodingError as e:
            logger.warning(f"Geocodifica fallita per '{address}': {e}")
            return None

    def clear_cache(self):
        """Svuota la cache delle geocodifiche."""
        self.geocode_with_address.cache_clear()
        logger.info("Cache geocodifica svuotata")

    def get_cache_info(self):
        """Ritorna statistiche della cache."""
        return self.geocode_with_address.cache_info()


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcola la distanza geodetica tra due punti in km.

    Args:
        lat1, lon1: Coordinate del primo punto
        lat2, lon2: Coordinate del secondo punto

    Returns:
        Distanza in chilometri
    """
    if not GEOPY_AVAILABLE:
        # Fallback: formula haversine approssimativa
        import math
        R = 6371  # Raggio Terra in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    return geodesic((lat1, lon1), (lat2, lon2)).kilometers


def filter_by_proximity(
    df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    lat_col: str = 'latitudine',
    lon_col: str = 'longitudine',
    address_col: str = 'indirizzo',
    comune_col: str = 'comune'
) -> pd.DataFrame:
    """
    Filtra un DataFrame per prossimità geografica.

    Se le colonne lat/lon non esistono, tenta di geocodificare
    usando indirizzo + comune.

    Args:
        df: DataFrame con dati stabilimenti
        center_lat: Latitudine centro ricerca
        center_lon: Longitudine centro ricerca
        radius_km: Raggio in km
        lat_col: Nome colonna latitudine
        lon_col: Nome colonna longitudine
        address_col: Nome colonna indirizzo (per geocodifica fallback)
        comune_col: Nome colonna comune (per geocodifica fallback)

    Returns:
        DataFrame filtrato con colonna 'distanza_km' aggiunta
    """
    if df.empty:
        return df

    result_df = df.copy()

    # Verifica se esistono coordinate
    has_coords = lat_col in result_df.columns and lon_col in result_df.columns

    if not has_coords:
        # Fallback: tenta geocodifica basata su indirizzo
        logger.info("Coordinate non presenti, tentativo geocodifica da indirizzo...")
        geocoder = GeocodingService()

        coords_cache = {}

        def get_coords(row):
            address = row.get(address_col, '')
            comune = row.get(comune_col, '')

            if not address and not comune:
                return None, None

            full_address = f"{address}, {comune}" if address and comune else (address or comune)

            if full_address in coords_cache:
                return coords_cache[full_address]

            coords = geocoder.geocode_safe(full_address)
            coords_cache[full_address] = coords if coords else (None, None)
            return coords_cache[full_address]

        # Applica geocodifica (solo se necessario, limitato per performance)
        if len(result_df) <= 100:  # Limite per evitare troppe chiamate
            coords = result_df.apply(get_coords, axis=1)
            result_df[lat_col] = coords.apply(lambda x: x[0] if x else None)
            result_df[lon_col] = coords.apply(lambda x: x[1] if x else None)
        else:
            logger.warning(f"Troppe righe ({len(result_df)}) per geocodifica batch, usa colonne coordinate")
            return pd.DataFrame()

    # Calcola distanze
    def calc_distance(row):
        lat = row.get(lat_col)
        lon = row.get(lon_col)

        if pd.isna(lat) or pd.isna(lon):
            return float('inf')

        try:
            return calculate_distance_km(center_lat, center_lon, float(lat), float(lon))
        except (ValueError, TypeError):
            return float('inf')

    result_df['distanza_km'] = result_df.apply(calc_distance, axis=1)

    # Filtra per raggio
    filtered_df = result_df[result_df['distanza_km'] <= radius_km].copy()

    # Ordina per distanza
    filtered_df = filtered_df.sort_values('distanza_km')

    logger.info(f"Filtro prossimità: {len(filtered_df)}/{len(df)} stabilimenti entro {radius_km} km")

    return filtered_df


# Istanza singleton globale
_geocoding_service = None


def get_geocoding_service() -> GeocodingService:
    """Ritorna l'istanza singleton del servizio geocodifica."""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service
