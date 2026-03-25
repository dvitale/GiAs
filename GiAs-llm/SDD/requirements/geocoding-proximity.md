# Geocoding e Prossimita'

**Componente**: Backend (GiAs-llm)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: `tools/geo_utils.py`, `tools/proximity_tools.py`

## Requisiti Funzionali

### GP-01 Geocodifica Nominatim
- **Pattern EARS**: Il sistema DEVE geocodificare indirizzi utilizzando il servizio Nominatim (OpenStreetMap) con user-agent "GIAS-VeterinaryAssistant/1.0 (gisa@regione.campania.it)" e timeout 10 secondi.
- **Status**: IMPLEMENTATO

### GP-02 SimpleRequestsAdapter fix SSL
- **Pattern EARS**: Il sistema DEVE utilizzare un adapter requests custom (SimpleRequestsAdapter) che ignora ssl_context personalizzato, poiche' Nominatim tramite Varnish CDN effettua TLS fingerprinting e rifiuta connessioni con ssl_context custom (errore HTTP 509).
- **Status**: IMPLEMENTATO

### GP-03 Strategia city-first con fallback centro citta'
- **Pattern EARS**: QUANDO l'indirizzo contiene un capoluogo di provincia campano (Napoli, Salerno, Caserta, Avellino, Benevento con coordinate hardcoded), il sistema DEVE prima geocodificare il comune, poi cercare l'indirizzo specifico con viewbox centrato (raggio ~5km), verificando che il risultato sia entro MAX_DISTANCE_FROM_CENTER_KM (6.0 km). QUANDO l'indirizzo contiene una virgola (formato "Via X, Comune Y"), il sistema DEVE estrarre il comune dall'ultimo segmento, geocodificarlo in Campania, e cercare la via con viewbox centrato, con pulizia preposizioni spurie. SE l'indirizzo specifico non viene trovato o il risultato e' troppo lontano (> 6 km), il sistema DEVE utilizzare le coordinate del centro citta' come riferimento con warning.
- **Status**: IMPLEMENTATO
- **Accorpa**: GP-03, GP-04, GP-05

### GP-06 Cache LRU e rate limiting Nominatim
- **Pattern EARS**: Il sistema DEVE mantenere una cache LRU con maxsize=500 entries per le geocodifiche (decoratore @lru_cache). Il sistema DEVE limitare le chiamate a Nominatim a massimo 1 richiesta al secondo (min_delay_seconds=1.0) tramite RateLimiter di geopy, con max_retries=2 e error_wait_seconds=5.0, come richiesto dai ToS di Nominatim.
- **Status**: IMPLEMENTATO
- **Accorpa**: GP-06, GP-07

### GP-08 Validazione territorio ASL
- **Pattern EARS**: QUANDO l'utente ha un'ASL assegnata, il sistema DEVE verificare che l'indirizzo cercato sia nel territorio di competenza dell'ASL, utilizzando un mapping ASL -> province (7 ASL campane). SE l'indirizzo e' fuori territorio, il sistema DEVE restituire un errore "location_outside_asl" con suggerimenti.
- **Status**: IMPLEMENTATO

### GP-09 Coordinate da database
- **Pattern EARS**: QUANDO il DataFrame contiene colonne latitudine_stab e longitudine_stab, il sistema DEVE utilizzare le coordinate esistenti per il filtro di prossimita' senza geocodifica aggiuntiva.
- **Status**: IMPLEMENTATO

### GP-10 Limite batch geocodifica
- **Pattern EARS**: QUANDO le coordinate non sono presenti e serve geocodifica da indirizzo, il sistema DEVE limitare il batch a 100 righe massimo per evitare troppe chiamate al servizio esterno. SE le righe superano 100, il sistema DEVE restituire un DataFrame vuoto.
- **Status**: IMPLEMENTATO

### GP-11 Ordinamento distanza + rischio
- **Pattern EARS**: QUANDO vengono trovati stabilimenti vicini, il sistema DEVE ordinarli per distanza crescente (primaria) e punteggio rischio decrescente (secondaria), arricchendo i risultati con risk scores da RiskAnalyzer se disponibili.
- **Status**: IMPLEMENTATO

### GP-12 Clamping raggio
- **Pattern EARS**: Il sistema DEVE accettare un raggio di ricerca in km con default 5.0 km. Il filtro filter_by_proximity applica il raggio senza clamping esplicito nel codice, ma il tool nearby_priority accetta radius_km come parametro.
- **Status**: IMPLEMENTATO
- **Note**: Il clamping 1-50 km non e' implementato esplicitamente nel codice letto; il raggio e' usato direttamente.

### GP-13 GPS device integration (coordinate dirette, skip geocoding)
- **Pattern EARS**: QUANDO i metadata contengono `latitude`/`longitude` E l'intent e' `ask_nearby_priority`, il tool `nearby_priority` DEVE usare le coordinate GPS del device direttamente, SENZA invocare il GeocodingService. Lo slot `location` DEVE essere comunque estratto dal messaggio per display, ma la ricerca di prossimita' DEVE usare le coordinate GPS. SE le coordinate GPS sono fuori dal territorio della Campania (lat 39.9-41.5, lon 13.7-15.8), il sistema DEVE ignorare le coordinate e richiedere una localizzazione testuale.
- **Status**: IMPLEMENTATO
- **Accorpa**: GP-13, GP-14, GP-15

## Requisiti Non Funzionali

### GP-NF01 Singleton e gestione eccezioni custom
- **Pattern EARS**: Il sistema DEVE mantenere un'istanza singleton di GeocodingService tramite pattern __new__. Il sistema DEVE definire eccezioni custom gerarchiche (GeocodingError base, AddressNotFoundError, GeocodingTimeoutError) e fornire un metodo geocode_safe() che ritorna None invece di propagare eccezioni.
- **Status**: IMPLEMENTATO
- **Accorpa**: GP-NF01, GP-NF02

### GP-NF03 Fallback haversine e pulizia warning
- **Pattern EARS**: SE geopy non e' disponibile, il sistema DEVE calcolare le distanze con la formula haversine approssimativa (R=6371 km). QUANDO l'indirizzo risolto contiene un warning interno ("CENTRO CITTA'"), il sistema DEVE pulire il testo prima di mostrarlo all'utente, estraendo indirizzo e comune dal warning.
- **Status**: IMPLEMENTATO
- **Accorpa**: GP-NF03, GP-NF04
