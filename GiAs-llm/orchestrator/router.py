import json
import logging
import re
import time
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

try:
    from llm.client import LLMClient
    from configs.config import AppConfig
    from .intent_cache import IntentCache
    from .few_shot_retriever import get_few_shot_retriever
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from llm.client import LLMClient
    from configs.config import AppConfig
    from orchestrator.intent_cache import IntentCache
    from orchestrator.few_shot_retriever import get_few_shot_retriever


class Router:
    """
    Router ibrido per classificazione intent.

    Architettura a 3 livelli:
    1. Heuristics: pattern matching per intent comuni (saluti, aiuto, conferme)
    2. Pre-parsing: estrazione slot deterministici via regex
    3. LLM: classificazione per casi ambigui con prompt compatto
    """

    # P3: Feature flag per heuristics minimali
    # Quando True, solo heuristics essenziali (confirm/decline, disambiguazione rischio, greet/goodbye/help)
    # Richiede validazione con 200+ messaggi prima di attivare in produzione
    MINIMAL_HEURISTICS = True

    # VALID_INTENTS e REQUIRED_SLOTS: caricati da DB via IntentMetadataService al __init__.
    # Valori di classe come fallback (usati se il servizio non è disponibile).
    VALID_INTENTS = [
        "greet", "goodbye", "ask_help",
        "ask_piano_stabilimenti", "ask_piano_description", "ask_piano_statistics", "search_piani_by_topic",
        "ask_priority_establishment", "ask_risk_based_priority", "ask_suggest_controls",
        "ask_nearby_priority",
        "ask_delayed_plans", "check_if_plan_delayed", "ask_establishment_history",
        "ask_top_risk_activities",
        "info_procedure", "query_data",
        "confirm_show_details", "decline_show_details", "fallback"
    ]

    VALID_SLOT_KEYS = {
        "piano_code", "asl", "topic", "num_registrazione", "numero_riconoscimento",
        "partita_iva", "ragione_sociale", "categoria",
        "location", "radius_km",
        "sezione", "macroarea", "aggregazione", "anno", "comune",
        "table", "operation", "filters", "group_by", "order_by", "limit",
    }

    REQUIRED_SLOTS = {
        "ask_piano_description": ["piano_code"],
        "ask_piano_stabilimenti": ["piano_code"],
        "check_if_plan_delayed": ["piano_code"],
        "search_piani_by_topic": ["topic"],
        "ask_establishment_history": ["num_registrazione", "numero_riconoscimento", "partita_iva", "ragione_sociale"],
        "ask_nearby_priority": ["location"],
    }

    _metadata_loaded = False

    # =========================================================================
    # PROMPT V2 - Template semi-dinamico
    # Struttura e regole formato restano costanti Python.
    # Contenuti variabili (catalogo, esempi critici) iniettati da IntentMetadataService.
    # =========================================================================

    _CLASSIFICATION_PROMPT_TEMPLATE = """Classificatore intent veterinario GIAS. Output JSON esatto:
{{"reasoning":"breve motivazione","intent":"NOME","slots":{{}},"needs_clarification":false,"confidence":0.85,"alternatives":[]}}

Se sei incerto (confidence < 0.85), aggiungi fino a 2 alternative:
"alternatives":[{{"intent":"ALTRO","confidence":0.70,"reasoning":"perché"}}]

INTENT PER CATEGORIA:
{intent_catalog}

SLOT: piano_code(A1,B2), topic, num_registrazione(IT...), partita_iva(11cifre), ragione_sociale, categoria(HACCP,IGIENE,STRUTTURE), location, radius_km, sezione(A-G), macroarea, aggregazione, anno(2019-2026), comune

DATI DISPONIBILI:
{schema_catalog}

Quando l'utente filtra per colonne strutturate (sezione, macroarea, anno, comune), estrai il valore come slot.

REGOLE DISAMBIGUAZIONE:
{disambiguation_rules}

ESEMPI CRITICI (coppie confuse):
{critical_examples}

ESEMPI CON ALTERNATIVES (intent ambigui):
"come funziona il rischio" → {{"reasoning":"potrebbe essere procedura o analisi rischio","intent":"info_procedure","slots":{{}},"needs_clarification":false,"confidence":0.60,"alternatives":[{{"intent":"ask_risk_based_priority","confidence":0.55,"reasoning":"potrebbe chiedere stabilimenti a rischio"}}]}}
"controlli recenti" → {{"reasoning":"potrebbe essere storico o priorità","intent":"ask_establishment_history","slots":{{}},"needs_clarification":true,"confidence":0.55,"alternatives":[{{"intent":"ask_priority_establishment","confidence":0.50,"reasoning":"potrebbe chiedere chi controllare"}}]}}

CAMBIO TOPIC (ignora sessione precedente):
SESSIONE: intent=ask_delayed_plans, slots={{"piano_code":"A1"}}
"attività più rischiose" → {{"reasoning":"nuovo topic, ignoro sessione piani","intent":"ask_top_risk_activities","slots":{{}},"needs_clarification":false,"confidence":0.95}}

Output: SOLO JSON valido, niente altro."""

    # =========================================================================
    # PROMPT V2 - Fallback hardcoded (usato se IntentMetadataService non disponibile)
    # =========================================================================

    _CLASSIFICATION_PROMPT_FALLBACK = """Classificatore intent veterinario GIAS. Output JSON esatto:
{"reasoning":"breve motivazione","intent":"NOME","slots":{},"needs_clarification":false,"confidence":0.85,"alternatives":[]}

Se sei incerto (confidence < 0.85), aggiungi fino a 2 alternative:
"alternatives":[{"intent":"ALTRO","confidence":0.70,"reasoning":"perché"}]

INTENT PER CATEGORIA:

[Piani]
ask_piano_description(piano_code) - descrizione/info piano
ask_piano_stabilimenti(piano_code) - stabilimenti controllati da piano
ask_piano_statistics - statistiche/frequenza PIANI (top piani per controlli, quanti indicatori ha un piano). Richiede contesto piano, NON per conteggi generici di controlli per ASL/macroarea.
search_piani_by_topic(topic) - cerca piani per argomento

[Priorità]
ask_priority_establishment - chi controllare oggi/priorità generica
ask_risk_based_priority - STABILIMENTI a rischio (score, non conformità)
ask_top_risk_activities - classifica ATTIVITÀ più rischiose
ask_suggest_controls - stabilimenti MAI controllati
ask_nearby_priority(location,radius_km) - stabilimenti MAI CONTROLLATI vicino a INDIRIZZO FISICO specifico (richiede location geocodificabile, NON per aggregazioni/conteggi)

[Monitoraggio]
ask_cu_statistics - conteggio/statistiche CONTROLLI ESEGUITI o PROGRAMMATI, con filtri per piano, anno, ASL, macroarea. Slot: piano_code, anno, asl, macroarea, tipo_conteggio(eseguiti|programmati). NON per ritardi (→ ask_delayed_plans) né per ranking piani (→ ask_piano_statistics).
ask_delayed_plans - LISTA piani/attività in ritardo (plurale/generico)
check_if_plan_delayed(piano_code) - verifica ritardo UN piano specifico

[Storico]
ask_establishment_history(num_registrazione|partita_iva|ragione_sociale) - storico controlli stabilimento

[Procedure]
info_procedure - procedure operative, come si fa, passi per, definizioni termini GISA/Matrix (cos'e X)

[Dati]
query_data - interrogazione dati su misura NON coperta dagli intent sopra (usa SOLO se nessun intent specifico corrisponde). Confidence MAI > 0.80.

[Base]
greet - saluti e convenevoli (ciao, salve, buongiorno, buonasera, buonanotte, buon pomeriggio, ehilà, come stai, ecc.), MAI domande operative
goodbye - commiato (arrivederci, tanti saluti, alla prossima, ci vediamo, a domani, ecc.)
ask_help - aiuto, cosa puoi fare
confirm_show_details - sì/ok/mostrami (in risposta a offerta dettagli)
decline_show_details - no/basta (in risposta a offerta dettagli)
fallback - fuori dominio

SLOT: piano_code(A1,B2), topic, num_registrazione(IT...), partita_iva(11cifre), ragione_sociale, categoria(HACCP,IGIENE,STRUTTURE), location, radius_km, sezione(A-G), macroarea, aggregazione, anno(2019-2026), comune

DATI DISPONIBILI:
- piani_monitoraggio ~730 righe: Piani di controllo veterinario per sezione PRISCAV
  Filtri: sezione(SEZIONE A,SEZIONE B,SEZIONE C), alias(A1,A22,B2), alias_indicatore, campionamento
  Valori: sezione: SEZIONE A=Sicurezza Alimentare, SEZIONE B=Sanità Animale, SEZIONE C=Igiene Allevamenti, SEZIONE D=Alimentazione Animale, SEZIONE E=Farmacosorveglianza, SEZIONE F=Benessere Animale, SEZIONE G=Sottoprodotti
- masterlist ~105,000 righe: Tassonomia attività (norma, macroarea, aggregazione, linea_di_attivita)
- cu_eseguiti_nc ~400,000 righe: Controlli eseguiti 2019-2025 con NC inline (ASL, UOC, piano, macroarea, comune, tipo_non_conformita, numero_nc_gravi, numero_nc_non_gravi, oggetto_non_conformita, alias_piano_attivita, alias_indicatore)
- osa_mai_controllati ~643,000 righe: Stabilimenti mai controllati (ASL, comune, macroarea)
- cu_diff_programmati_eseguiti: Programmati vs eseguiti per indicatore, ASL, UOC
- personale ~100,000 righe: Struttura organizzativa (user_id, ASL, UOC)

Quando l'utente filtra per colonne strutturate (sezione, macroarea, anno, comune), estrai il valore come slot.

REGOLE DISAMBIGUAZIONE:
1. "STABILIMENTI a rischio" → ask_risk_based_priority (NON ask_top_risk_activities)
2. "LINEE DI ATTIVITÀ rischiose" / "classifica linee di attività" → ask_top_risk_activities (NON ask_risk_based_priority)
3. "piani in ritardo" / "attività in ritardo" (plurale/generico) → ask_delayed_plans
4. "il piano X è in ritardo" (specifico) → check_if_plan_delayed
5. greet se messaggio è saluto/convenevole SENZA domande operative; goodbye se è commiato
6. Slot mancante per intent che lo richiede → needs_clarification:true
7. confidence: 0.95+ per match esatto, 0.70-0.90 per inferenza, <0.70 se incerto
8. CAMBIO TOPIC: Se il messaggio è chiaramente un NUOVO ARGOMENTO (es. "linee di attività rischiose" dopo aver parlato di "piani"), IGNORA la sessione precedente e classifica il messaggio in isolamento
9. "PIANI controllare per primi" → ask_delayed_plans (priorità PIANI); "STABILIMENTI controllare per primi" → ask_priority_establishment (priorità STABILIMENTI)
10. Se la domanda potrebbe corrispondere a 2+ intent con confidence simile, restituisci il migliore come intent principale e gli altri in "alternatives". NON indovinare: è meglio chiedere all'utente che classificare male.
11. "piani della sezione X" con X in (A-G) → search_piani_by_topic con slot sezione=X
12. Filtro per MACROAREA/AGGREGAZIONE → estrai come slot per filtrare i risultati dell'intent più vicino
13. "quanti controlli nell'ASL X" / "controlli eseguiti a BENEVENTO" / "controlli totali quest'anno" / "controlli fatti per il piano AO1" / "controlli eseguiti per il benessere animale" → ask_cu_statistics (conteggio aggregato su cu_eseguiti_nc). NON è query_data (riservato a domande non coperte da intent specifici) né ask_piano_statistics (che riguarda ranking/overview dei PIANI).
14. query_data per domande su dati tabulari NON coperte dagli intent specifici. Confidence MAI > 0.80.
15. "più controllati"/"quanti controlli per stabilimento"/"quanti controlli per comune" = aggregazione PER ENTITA' → query_data. MA "quanti controlli" senza "per stabilimento"/"per comune" → ask_cu_statistics.
16. "nelle mie vicinanze"/"vicino a me" SENZA indirizzo fisico → se la domanda è aggregazione dati, usa query_data con filtro ASL/comune dai metadata. ask_nearby_priority richiede un indirizzo geocodificabile (es. "Via Roma 15, Napoli").
17. "controlli per l'attività/piano X" con codice specifico → se chiede "quanti"/"conteggio"/"eseguiti"/"fatti" → ask_cu_statistics. Se chiede "quali stabilimenti"/"elenco"/"lista" → ask_piano_stabilimenti.
18. "controlli programmati per il 2026" / "programmazione per piano X" → ask_cu_statistics con tipo_conteggio="programmati". NON è ask_delayed_plans (che analizza ritardi programmati-eseguiti) né check_if_plan_delayed.

ESEMPI CRITICI (coppie confuse):
"stabilimenti a rischio" → {"reasoning":"chiede stabilimenti con alto rischio","intent":"ask_risk_based_priority","slots":{},"needs_clarification":false,"confidence":0.95}
"linee di attività più rischiose" → {"reasoning":"chiede classifica linee di attività per rischio","intent":"ask_top_risk_activities","slots":{},"needs_clarification":false,"confidence":0.95}
"piani in ritardo" → {"reasoning":"lista piani ritardo generico","intent":"ask_delayed_plans","slots":{},"needs_clarification":false,"confidence":0.95}
"attività in ritardo" → {"reasoning":"lista attività ritardo generico","intent":"ask_delayed_plans","slots":{},"needs_clarification":false,"confidence":0.95}
"il piano B2 è in ritardo?" → {"reasoning":"verifica ritardo piano specifico B2","intent":"check_if_plan_delayed","slots":{"piano_code":"B2"},"needs_clarification":false,"confidence":0.95}
"voglio verificare se un piano è in ritardo" → {"reasoning":"manca piano_code","intent":"check_if_plan_delayed","slots":{},"needs_clarification":true,"confidence":0.85}
"piano A1" → {"reasoning":"info piano A1","intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.90}
"di cosa si occupa il piano A1" → {"reasoning":"descrizione piano","intent":"ask_piano_description","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.95}
"piani su latte" → {"reasoning":"cerca piani tema latte","intent":"search_piani_by_topic","slots":{"topic":"latte"},"needs_clarification":false,"confidence":0.95}
"chi devo controllare" → {"reasoning":"priorità generica","intent":"ask_priority_establishment","slots":{},"needs_clarification":false,"confidence":0.90}
"chi devo controllare secondo la programmazione" → {"reasoning":"priorità per programmazione","intent":"ask_priority_establishment","slots":{},"needs_clarification":false,"confidence":0.95}
"quali piani devo controllare per primi" → {"reasoning":"priorità PIANI, non stabilimenti","intent":"ask_delayed_plans","slots":{},"needs_clarification":false,"confidence":0.95}
"quali stabilimenti devo controllare per primi" → {"reasoning":"priorità STABILIMENTI","intent":"ask_priority_establishment","slots":{},"needs_clarification":false,"confidence":0.95}
"mai controllati" → {"reasoning":"stabilimenti mai controllati","intent":"ask_suggest_controls","slots":{},"needs_clarification":false,"confidence":0.90}
"vicino a Napoli" → {"reasoning":"controlli vicino indirizzo","intent":"ask_nearby_priority","slots":{"location":"Napoli"},"needs_clarification":false,"confidence":0.90}
"entro 5 km da Via Roma" → {"reasoning":"raggio specifico","intent":"ask_nearby_priority","slots":{"location":"Via Roma","radius_km":5},"needs_clarification":false,"confidence":0.95}
"NC categoria HACCP" → {"reasoning":"filtra controlli per oggetto_non_conformita HACCP","intent":"query_data","slots":{},"needs_clarification":false,"confidence":0.75}
"controlli eseguiti per l'attività B47" → {"reasoning":"controlli eseguiti per attività specifica - ambiguo tra conteggio e lista stabilimenti","intent":"ask_cu_statistics","slots":{"piano_code":"ATT B47","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.70,"alternatives":[{"intent":"ask_piano_stabilimenti","confidence":0.60,"reasoning":"potrebbe chiedere lista stabilimenti"}]}
"quali stabilimenti sono stati controllati per il piano A1" → {"reasoning":"chiede esplicitamente stabilimenti","intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.90}
"quanti controlli sono stati fatti per AO1" → {"reasoning":"conteggio controlli eseguiti per piano specifico","intent":"ask_cu_statistics","slots":{"piano_code":"AO1","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}
"procedura ispezione" → {"reasoning":"come si fa ispezione","intent":"info_procedure","slots":{},"needs_clarification":false,"confidence":0.90}
"cos'e il borsellino in Matrix" → {"reasoning":"definizione termine Matrix","intent":"info_procedure","slots":{},"needs_clarification":false,"confidence":0.95}
"piani della sezione A" → {"reasoning":"cerca piani sezione A=Sicurezza Alimentare","intent":"search_piani_by_topic","slots":{"topic":"sezione A","sezione":"A"},"needs_clarification":false,"confidence":0.95}
"piani sezione B su bovini" → {"reasoning":"cerca piani sezione B con keyword bovini","intent":"search_piani_by_topic","slots":{"topic":"bovini","sezione":"B"},"needs_clarification":false,"confidence":0.95}
"stabilimenti mai controllati a Benevento" → {"reasoning":"OSA mai controllati filtro comune","intent":"ask_suggest_controls","slots":{"comune":"Benevento"},"needs_clarification":false,"confidence":0.95}
"quanti controlli per macroarea?" → {"reasoning":"interrogazione dati aggregati su controlli","intent":"query_data","slots":{"table":"controlli","operation":"group_count","group_by":["macroarea_cu"]},"needs_clarification":false,"confidence":0.75}
"quanti controlli sono stati eseguiti nell'ASL Benevento?" → {"reasoning":"conteggio controlli per ASL","intent":"ask_cu_statistics","slots":{"asl":"BENEVENTO","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}
"quanti controlli ha fatto l'ASL Napoli nel 2025?" → {"reasoning":"conteggio controlli ASL+anno","intent":"ask_cu_statistics","slots":{"asl":"NAPOLI","anno":2025,"tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}
"controlli eseguiti per il benessere animale" → {"reasoning":"conteggio controlli filtrato per macroarea","intent":"ask_cu_statistics","slots":{"macroarea":"BENESSERE ANIMALE","tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}
"controlli programmati per il 2026" → {"reasoning":"somma controlli programmati anno futuro","intent":"ask_cu_statistics","slots":{"anno":2026,"tipo_conteggio":"programmati"},"needs_clarification":false,"confidence":0.90}
"controlli totali eseguiti quest'anno" → {"reasoning":"conteggio totale controlli anno corrente","intent":"ask_cu_statistics","slots":{"tipo_conteggio":"eseguiti"},"needs_clarification":false,"confidence":0.90}
"distribuzione NC per anno" → {"reasoning":"aggregazione NC storiche per anno","intent":"query_data","slots":{"table":"nc_storiche","operation":"group_count","group_by":["anno"]},"needs_clarification":false,"confidence":0.75}
"stabilimenti più controllati nelle mie vicinanze" → {"reasoning":"aggregazione: ranking stabilimenti per numero controlli, vicinanze=filtro ASL da metadata, NON ask_nearby_priority","intent":"query_data","slots":{"table":"controlli","operation":"group_count","group_by":["attivita_cu","comune"]},"needs_clarification":false,"confidence":0.75}
"stabilimenti con più controlli nella mia zona" → {"reasoning":"classifica stabilimenti per controlli, zona=ASL utente","intent":"query_data","slots":{"table":"controlli","operation":"group_count","group_by":["attivita_cu"]},"needs_clarification":false,"confidence":0.75}
"statistiche piani" → {"reasoning":"statistiche aggregate sui piani di controllo","intent":"ask_piano_statistics","slots":{},"needs_clarification":false,"confidence":0.90}
"quanti indicatori ha il piano A1" → {"reasoning":"statistiche di un piano specifico","intent":"ask_piano_statistics","slots":{"piano_code":"A1"},"needs_clarification":false,"confidence":0.95}
"storico IT 2287" → {"reasoning":"storico stabilimento","intent":"ask_establishment_history","slots":{"num_registrazione":"IT 2287"},"needs_clarification":false,"confidence":0.95}
"ciao" → {"reasoning":"saluto","intent":"greet","slots":{},"needs_clarification":false,"confidence":0.99}
"buonanotte" → {"reasoning":"saluto serale","intent":"greet","slots":{},"needs_clarification":false,"confidence":0.99}
"come stai" → {"reasoning":"convenevole","intent":"greet","slots":{},"needs_clarification":false,"confidence":0.95}
"tanti saluti" → {"reasoning":"commiato","intent":"goodbye","slots":{},"needs_clarification":false,"confidence":0.95}
"alla prossima" → {"reasoning":"commiato","intent":"goodbye","slots":{},"needs_clarification":false,"confidence":0.95}
"ciao cosa puoi fare" → {"reasoning":"non solo saluto, chiede help","intent":"ask_help","slots":{},"needs_clarification":false,"confidence":0.95}
"sì mostrami" → {"reasoning":"conferma offerta dettagli","intent":"confirm_show_details","slots":{},"needs_clarification":false,"confidence":0.95}
"no grazie" → {"reasoning":"rifiuto dettagli","intent":"decline_show_details","slots":{},"needs_clarification":false,"confidence":0.95}
"pizza?" → {"reasoning":"fuori dominio","intent":"fallback","slots":{},"needs_clarification":false,"confidence":0.99}

ESEMPI CON ALTERNATIVES (intent ambigui):
"come funziona il rischio" → {"reasoning":"potrebbe essere procedura o analisi rischio","intent":"info_procedure","slots":{},"needs_clarification":false,"confidence":0.60,"alternatives":[{"intent":"ask_risk_based_priority","confidence":0.55,"reasoning":"potrebbe chiedere stabilimenti a rischio"}]}
"controlli recenti" → {"reasoning":"potrebbe essere storico o priorità","intent":"ask_establishment_history","slots":{},"needs_clarification":true,"confidence":0.55,"alternatives":[{"intent":"ask_priority_establishment","confidence":0.50,"reasoning":"potrebbe chiedere chi controllare"}]}

CAMBIO TOPIC (ignora sessione precedente):
SESSIONE: intent=ask_delayed_plans, slots={"piano_code":"A1"}
"linee di attività più rischiose" → {"reasoning":"nuovo topic, ignoro sessione piani","intent":"ask_top_risk_activities","slots":{},"needs_clarification":false,"confidence":0.95}

Output: SOLO JSON valido, niente altro."""

    # =========================================================================
    # PROMPT V1 (backup per rollback)
    # =========================================================================
    # CLASSIFICATION_SYSTEM_PROMPT_V1 = """Classificatore intent veterinario. Rispondi SOLO con JSON.
    # {"intent":"NOME","slots":{},"needs_clarification":false}
    #
    # INTENT:
    # ask_piano_description(piano_code) | ask_piano_stabilimenti(piano_code) | ask_piano_statistics
    # search_piani_by_topic(topic) | ask_priority_establishment | ask_risk_based_priority | ask_suggest_controls
    # ask_nearby_priority(location,radius_km) | ask_delayed_plans | check_if_plan_delayed(piano_code)
    # ask_establishment_history(num_registrazione|partita_iva|ragione_sociale)
    # ask_top_risk_activities | info_procedure
    # greet | goodbye | ask_help | confirm_show_details | decline_show_details | fallback
    #
    # SLOT: piano_code(A1,B2), asl(NA1), topic, num_registrazione(IT...), partita_iva(10-11cifre), ragione_sociale, categoria, location(indirizzo), radius_km(5)
    #
    # REGOLE:
    # - sì/si/ok/certo/mostrami → confirm_show_details
    # - no/no grazie → decline_show_details
    # - Slot mancante → needs_clarification:true
    # - Fuori dominio → fallback
    # - greet = SOLO saluti (ciao/salve/buongiorno), NON domande generiche
    # - STABILIMENTI a rischio → ask_risk_based_priority
    # - ATTIVITA' a rischio (classifica) → ask_top_risk_activities
    # - LISTA piani in ritardo → ask_delayed_plans
    # - Verifica UN piano in ritardo → check_if_plan_delayed
    # - procedura/come si fa/passi per/istruzioni per → info_procedure
    # - vicino a/nei dintorni/nei pressi/zona di/entro X km → ask_nearby_priority
    # - SE c'è CONTESTO RISPOSTA PRECEDENTE, risolvi riferimenti ("le varianti"→varianti del piano, "quelli"→elementi citati)
    #
    # ESEMPI:
    # "piano A1" → {"intent":"ask_piano_stabilimenti","slots":{"piano_code":"A1"},"needs_clarification":false}
    # "piani su latte" → {"intent":"search_piani_by_topic","slots":{"topic":"latte"},"needs_clarification":false}
    # "piani che trattano di igiene" → {"intent":"search_piani_by_topic","slots":{"topic":"igiene"},"needs_clarification":false}
    # "stabilimenti a rischio" → {"intent":"ask_risk_based_priority","slots":{},"needs_clarification":false}
    # "attività più rischiose" → {"intent":"ask_top_risk_activities","slots":{},"needs_clarification":false}
    # "piani in ritardo" → {"intent":"ask_delayed_plans","slots":{},"needs_clarification":false}
    # "il piano B2 è in ritardo?" → {"intent":"check_if_plan_delayed","slots":{"piano_code":"B2"},"needs_clarification":false}
    # "voglio verificare se un piano è in ritardo" → {"intent":"check_if_plan_delayed","slots":{},"needs_clarification":true}
    # "dimmi del piano" → {"intent":"ask_piano_stabilimenti","slots":{},"needs_clarification":true}
    # "di cosa si occupa il piano A1" → {"intent":"ask_piano_description","slots":{"piano_code":"A1"},"needs_clarification":false}
    # "chi devo controllare per primo" → {"intent":"ask_priority_establishment","slots":{},"needs_clarification":false}
    # "procedura ispezione semplice" → {"intent":"info_procedure","slots":{},"needs_clarification":false}
    # "stabilimenti vicino a Piazza Garibaldi Napoli" → {"intent":"ask_nearby_priority","slots":{"location":"Piazza Garibaldi Napoli"},"needs_clarification":false}
    # "controlli entro 3 km da Via Roma, Benevento" → {"intent":"ask_nearby_priority","slots":{"location":"Via Roma, Benevento","radius_km":3},"needs_clarification":false}
    # "pizza?" → {"intent":"fallback","slots":{},"needs_clarification":false}
    # [con CONTESTO: "info piano - piano A2 - 5 varianti"] "quali sono le varianti?" → {"intent":"ask_piano_stabilimenti","slots":{"piano_code":"A2"},"needs_clarification":false}
    #
    # Rispondi SOLO JSON."""

    CLASSIFICATION_USER_TEMPLATE = """MESSAGGIO: "{message}"
METADATA: {metadata}
SLOT PRE-ESTRATTI: {extracted_slots}
OUTPUT:"""

    # =========================================================================
    # REGEX PATTERNS per pre-parsing slot
    # =========================================================================

    # Piano code: pattern GIAS reali (A1, B2, C3, A22, C3_F, etc.)
    # Formato: 1-2 lettere + 1-3 numeri + opzionale suffisso _LETTERE
    # NON matcha pattern casuali come XYZ123, ABC999, etc.
    RE_PIANO_CODE = re.compile(r'\b([A-Z]{1,2}[0-9]{1,3}(?:_[A-Z]+)?)\b', re.IGNORECASE)

    # Parole chiave dominio GIAS per rilevare query significative
    # Se un messaggio non contiene NESSUNA di queste e non è saluto/aiuto, è probabilmente gibberish
    DOMAIN_KEYWORDS = re.compile(
        r'\b(piano|piani|controllo|controlli|stabilimento|stabilimenti|'
        r'rischio|ritardo|ritardi|priorit[àa]|verificare|verifica|'
        r'asl|uoc|osa|nc|non\s*conformit[àa]|ispezione|ispezion[ie]|'
        r'storico|storia|attivit[àa]|categoria|bovini|suini|latte|carni|'
        r'allevament[io]|macellazione|igiene|sicurezza|alimentare|'
        r'descrizione|informazioni|descrivimi|dimmi|mostrami|cerca|'
        r'vicino|dintorni|zona|controllare|controllato|controllati|'
        r'sanzion[ie]|procedura|procedure|chi|quali|quanti|cosa|come|'
        r'cos[\'\'`\u2019]?[eè]|perch[eé]|quando|dove|quanto|'
        r'matrix|borsellino|preaccettazione|checklist|aiuto|help)\b',
        re.IGNORECASE
    )

    # ASL: NA1, NA2, AV1, CE1, etc.
    RE_ASL = re.compile(r'\b([A-Z]{2}[0-9])\b', re.IGNORECASE)

    # Numero riconoscimento UE: inizia con "UE IT" (es. "UE IT 15 273")
    RE_NUM_RIC = re.compile(r'\b(UE\s+IT\s*[\d\s]+[A-Z]?)\b', re.IGNORECASE)

    # Numero registrazione: contiene IT ma NON "UE IT" (es. "IT 123", "IT 2287 M")
    RE_NUM_REG = re.compile(r'\b(?<!UE\s)(IT\s*[\d\s]+[A-Z]?)\b', re.IGNORECASE)

    # Partita IVA: 10-11 cifre, opzionalmente preceduto da "p.iva" o "partita iva"
    RE_PARTITA_IVA = re.compile(r'(?:p\.?\s*iva|partita\s*iva)?\s*(\d{10,11})\b', re.IGNORECASE)

    # Topic: estrae argomento dopo "piani su/per/riguardanti/che trattano"
    RE_TOPIC = re.compile(
        r"\bpiani\s+(?:su|per|riguardant[io]|(?:che\s+)?riguardano|(?:che\s+)?trattano\s+(?:di\s+)?)\s*(?:la\s+|il\s+|i\s+|le\s+|gli\s+|l['\u2019])?(.+)",
        re.IGNORECASE
    )

    # Sezione piani: "sezione A", "della sezione B", "sez. C"
    RE_SEZIONE = re.compile(
        r'\bsez(?:ione|\.)\s+([A-Z])\b',
        re.IGNORECASE
    )

    # Tipo analisi rischio: disambiguazione tra mai controllati e con sanzioni
    # Pattern TESTUALI: matchano sempre (sono espliciti)
    RE_RISK_TYPE_MAI_CONTROLLATI_TEXT = re.compile(
        r'^\s*(?:mai\s*controllat[io]|non\s*controllat[io])\s*$',
        re.IGNORECASE
    )
    RE_RISK_TYPE_CON_SANZIONI_TEXT = re.compile(
        r'^\s*(?:con\s*(?:pi[uù]\s*)?sanzion[ie]|con\s*(?:pi[uù]\s*)?nc|pi[uù]\s*sanzionat[io])\s*$',
        re.IGNORECASE
    )
    # Pattern NUMERICI: matchano solo con contesto rischio pendente (evita conflitto con disambiguazione intent)
    RE_RISK_TYPE_NUMERIC_1 = re.compile(r'^\s*1\s*$')
    RE_RISK_TYPE_NUMERIC_2 = re.compile(r'^\s*2\s*$')
    # Pattern combinato per _extract_slots (include tutto)
    RE_RISK_TYPE_MAI_CONTROLLATI = re.compile(
        r'^\s*(?:1|mai\s*controllat[io]|non\s*controllat[io])\s*$',
        re.IGNORECASE
    )
    RE_RISK_TYPE_CON_SANZIONI = re.compile(
        r'^\s*(?:2|con\s*(?:pi[uù]\s*)?sanzion[ie]|con\s*(?:pi[uù]\s*)?nc|pi[uù]\s*sanzionat[io])\s*$',
        re.IGNORECASE
    )

    # =========================================================================
    # HEURISTICS per intent comuni
    # =========================================================================

    GREET_PATTERNS = re.compile(
        r'^(ciao|salve|buongiorno|buonasera|buondì|buon\s*pomeriggio|buonanotte|'
        r'hey|hi|hello|aloha|saluti|ehilà|ehi|ben\s*trovato|ben\s*tornato|eccomi)\b',
        re.IGNORECASE
    )

    GOODBYE_PATTERNS = re.compile(
        r'\b(arrivederci|bye|addio|a\s*presto|buon\s*lavoro|'
        r'alla\s*prossima|ci\s*vediamo|a\s*domani|tanti\s*saluti|stammi?\s*bene)\b',
        re.IGNORECASE
    )

    HELP_PATTERNS = re.compile(
        r'\b(aiuto|help|cosa\s*(puoi|sai)\s*fare|come\s*funziona|che\s*domande|'
        r'cosa\s*(ti\s*)?posso\s*(chiedere|chiederti|chiederle|domandare|fare)|'
        r'quali\s*domande\s*(posso|ti\s*posso))\b',
        re.IGNORECASE
    )

    # Confirm - explicit confirm with verb (non richiedono detail_context)
    CONFIRM_EXPLICIT_PATTERNS = re.compile(
        r'^(sì|si|s[iì])[\s,]*(mostrami|vediamo|dammi|fammi vedere)(\s+(i\s+)?dettagli|\s+tutti)?|'
        r'^(mostrami|vediamo|dammi|fammi vedere)(\s+(i\s+)?dettagli|\s+tutti)|'
        r'^vediamo\s+tutti\s*[.!]?\s*$',
        re.IGNORECASE
    )

    # Confirm - pattern per conferme brevi (richiedono detail_context)
    # Include bare "sì"/"si" which now requires active detail_context
    CONFIRM_SHORT_PATTERNS = re.compile(
        r'^(sì|si|s[iì]|ok|okay|certo|vai|procedi|mostrami|vediamo)\s*[.!]?\s*$',
        re.IGNORECASE
    )

    # Decline - pattern per rifiuti espliciti (non richiedono detail_context)
    DECLINE_EXPLICIT_PATTERNS = re.compile(
        r'^no[\s,]*grazie|'
        r'^(basta|non\s*serve|stop)\s*[.!]?\s*$|'
        r'^va\s*bene\s*cos[iì]\s*[.!]?\s*$',
        re.IGNORECASE
    )

    # Decline - pattern per rifiuti brevi (richiedono detail_context)
    DECLINE_SHORT_PATTERNS = re.compile(
        r'^no\s*[.!]?\s*$',
        re.IGNORECASE
    )

    # Piani in ritardo (generico PLURALE, senza piano specifico)
    # Match solo forme plurali/generiche: "piani in ritardo", "quali piani", "ritardo piani"
    # NOTE: "piani controllare per primi" NON è qui - disambiguato dall'LLM (regola 9)
    DELAYED_PATTERNS = re.compile(
        r'\b(piani\s+(in\s*|sono\s+(in\s*)?)?ritardo|ritardo\s+piani|quali\s+piani\s+(sono\s+)?(in\s+)?ritardo)\b',
        re.IGNORECASE
    )

    # Pattern per singolare "un piano" / "il piano" che richiede chiarimento
    # Se questo matcha senza piano_code, deve passare all'LLM per needs_clarification
    SINGULAR_PLAN_PATTERN = re.compile(
        r'\b(un\s+piano|il\s+piano|questo\s+piano|quel\s+piano)\b',
        re.IGNORECASE
    )

    # Ritardo piano specifico: "ritardo del piano A1", "piano A1 in ritardo", "il piano B2 è in ritardo?"
    CHECK_PLAN_DELAYED_PATTERNS = re.compile(
        r'\britard',
        re.IGNORECASE
    )

    # Mai controllati - allow "stati" between "mai" and "controllati"
    # "da controllare per primi/primo" è priorità, NON mai controllati → escluso con lookahead
    NEVER_CONTROLLED_PATTERNS = re.compile(
        r'\b(mai\s*(stati\s*)?controllat[io]|non\s*(sono\s*(stati\s*)?)?controllat[io]|da\s*controllare(?!\s+per\s+prim))\b',
        re.IGNORECASE
    )

    # Rischio generico (stabilimenti a rischio) - MIGLIORATO per maggiore accuratezza
    RISK_PATTERNS = re.compile(
        r'\b(stabiliment[io]|OSA)\s+.*\s*(a|ad|ai|più|alto|elevato)\s*rischio\b|'
        r'\bstabiliment[io]\s+(molto\s+)?rischios[io]\b|'
        r'\b(più|alto|elevato)\s+rischio\b.*\bstabiliment[io]\b|'
        r'\bOSA\s+(a|ad|ai)\s*rischio\b|'
        r'\bstabiliment[io]\s+.*\bnon\s*conformit[àa]\b|'
        r'\brischios[io]\b.*\bstabiliment[io]\b|'
        r'\bpi[uù]\s+rischios[io]\b',
        re.IGNORECASE
    )

    # Top attività/linee di attività rischiose
    TOP_RISK_PATTERNS = re.compile(
        r'\b((?:line[ae]\s+di\s+)?attivit[aà]\s*(pi[uù]\s*)?rischios[ae]|'
        r'top\s*(10\s*)?(?:line[ae]\s+di\s+)?attivit[aà]|'
        r'classifica\s*(?:line[ae]\s+di\s+)?attivit[aà]\s*(per\s*rischio)?)\b',
        re.IGNORECASE
    )

    # Priorità controlli (solo pattern con soggetto esplicito)
    # "controllare per primi" SENZA soggetto è ambiguo → delegato all'LLM (regola 9)
    PRIORITY_PATTERNS = re.compile(
        r'\b(chi\s*(devo\s*)?(controllare|ispezionare)(\s*per\s*prim[oia])?|'
        r'priorit[aà]|'
        r'cosa\s*(devo\s*)?fare\s*oggi|'
        r'da\s*chi\s*inizi[oa]|'
        r'quali\s*stabiliment[io]\s*(devo\s+)?controllare(\s+per\s+prim[oia])?)\b',
        re.IGNORECASE
    )

    # NC per categoria - DEVE essere controllato PRIMA di RISK_PATTERNS - MIGLIORATO
    NC_CATEGORY_PATTERNS = re.compile(
        r'\b(NC|non\s*conformit[àa])\s+(categoria|per|di\s*tipo|HACCP|IGIENE|STRUTTUR[AE]|PULIZIA|SANIFICAZIONE|ETICHETTATURA|MOCA|RINTRACCIABILIT[ÀA])\b|'
        r'\banalizza\s*(le\s*)?(NC|non\s*conformit[àa])|'
        r'\bproblemi?\s+(di\s+)?(HACCP|igiene|struttur[ae]|pulizia|sanificazione|etichettatura|MOCA)\b|'
        r'\bnon\s*conformit[àa]\s+.*\b(HACCP|igiene|struttur[ae]|pulizia|sanificazione|etichettatura|MOCA)\b',
        re.IGNORECASE
    )

    # Statistiche piani - broadened
    STATISTICS_PATTERNS = re.compile(
        r'\b(statistic[ah]e?\s*(sui\s*|dei\s*)?piani|'
        r'piani\s*pi[uù]\s*(usat[io]|frequent[io]?)|'
        r'quanti\s*piani|'
        r'frequenz[ae]\s*piani|'
        r'quale\s*piano\s*[eè]\s*pi[uù]\s*frequente|'
        r'quali\s*(sono\s*)?(i\s*)?piani\s*pi[uù])\b',
        re.IGNORECASE
    )

    # Procedure operative (RAG)
    # Include "come funziona [argomento specifico]" per domande su procedure GISA
    # Include domande su provvedimenti, azioni, gestione in contesti specifici
    # Include domande di definizione "cos'è X" per termini GISA (preaccettazione, checklist, matrix, etc.)
    # Include "di cosa tratta X", "dammi informazioni su X", "cosa sono X"
    # La logica per escludere "piano" è in _try_heuristics
    PROCEDURE_PATTERNS = re.compile(
        r'\b(procedura|procedimento|come\s+si\s+(fa|procede|esegue|effettua|registra|inserisce|gestisce)|'
        r'passi\s+per|step\s+per|guida\s+per|istruzioni\s+per|'
        r'come\s+procedere|'
        r'quali\s+sono\s+(i\s+passi|le\s+fasi|gli\s+step)|'
        r'come\s+funziona\s+(la|il|lo|l[\'\']\s*)?\w+|'
        r'quali\s+provvediment[io]|quali\s+azioni|cosa\s+(si\s+)?pu[oò]\s+fare|'
        r'come\s+gestire|come\s+trattare|'
        r'cos[\'\'`]?[eè]\s+(la|il|lo|l[\'\']\s*)?\w+|'
        r'cosa\s+significa\s+\w+|definizione\s+di\s+\w+|'
        r'di\s+cosa\s+tratta|'
        r'(che\s+)?cosa\s+sono\s+(gli|i|le|l[\'\']\s*)?\w+|'
        r'(dammi|vorrei|voglio)\s+info(rmazioni)?\s+(su|sugl[io]|sull[aoe\'\']\s*)\w+)\b',
        re.IGNORECASE
    )

    # Pattern per "di cosa tratta" generico (per esclusione piano in heuristics)
    DI_COSA_TRATTA_PATTERN = re.compile(r'\bdi\s+cosa\s+tratta\b', re.IGNORECASE)

    # Pattern per "dammi informazioni su X" generico (per esclusione piano in heuristics)
    INFO_SU_PATTERN = re.compile(r'\b(dammi|vorrei|voglio)\s+info(rmazioni)?\s+(su|sugl[io]|sull[aoe\'\']\s*)', re.IGNORECASE)

    # Cerca piani per topic
    SEARCH_PIANI_PATTERNS = re.compile(
        r'\b(cerca\s*piani|piani\s*(su|per|riguardant[io]|(?:che\s*)?riguardano|(?:che\s*)?trattano))\b',
        re.IGNORECASE
    )

    # Piano description: richieste generiche di informazioni/descrizione del piano
    # "di cosa tratta", "cosa prevede", "descrizione", "informazioni", "parlami", "dimmi"
    PIANO_DESCRIPTION_PATTERNS = re.compile(
        r'\b(di\s*cosa\s*tratta\s*(il\s*)?piano|di\s*cosa\s*si\s+occupa\s*(il\s*)?piano|'
        r'cosa\s*prevede\s*(il\s*)?piano|cosa\s*riguarda\s*(il\s*)?piano|'
        r'descrizione\s*(del\s*)?piano|descrivi\s*(il\s*)?piano|'
        r'piano\s+[A-Z]\d+\s*(di\s*cosa|cosa)\s*(tratta|prevede|riguarda)|'
        r'dimmi\s*(del\s*)?piano|parlami\s*(del\s*)?piano|'
        r'info(rmazioni)?\s*(sul\s*|del\s*)?piano|'
        r'(dammi|vorrei|voglio)\s*(info(rmazioni)?|dettagli)\s*(sul\s*|del\s*)?piano)\b',
        re.IGNORECASE
    )

    # Piano stabilimenti: richieste specifiche sugli stabilimenti/OSA controllati per un piano
    # "stabilimenti controllati", "dove è stato applicato", "quali stabilimenti", "OSA controllati"
    PIANO_STABILIMENTI_PATTERNS = re.compile(
        r'\b(stabiliment[io]\s*controllat[io]|dove\s*[eè]\s*stato\s*applicato|'
        r'stabiliment[io]\s*(del\s*)?piano|quali\s*stabiliment[io]|'
        r'stabiliment[io].{0,30}controll[io]|controll[io].{0,30}stabiliment[io]|'
        r'OSA\s*controllat[io]|quali\s*OSA|'
        r'attivit[aà]\s*(del\s*)?piano|quali\s*attivit[aà]\s*(riguarda|prevede))\b',
        re.IGNORECASE
    )

    # Establishment history: "storico controlli", "storia dei controlli", "controlli per partita iva"
    ESTABLISHMENT_HISTORY_PATTERNS = re.compile(
        r'\b(storic[ao]\s*(dei\s*)?(controll[io]?|stabilimento)|'
        r'storia\s*(dei\s*)?(controll[io]?|stabilimento)|'
        r'controll[io]\s*(per|dello)\s*(stabilimento|partita\s*iva))\b',
        re.IGNORECASE
    )

    # Pattern sociali ampi: saluti, commiati e convenevoli che NON devono essere bloccati dal gibberish detector.
    # Questi messaggi passano all'LLM per classificazione corretta (greet, goodbye, o fallback).
    SOCIAL_PATTERNS = re.compile(
        r'\b(buonanotte|buondì|buon\s*pomeriggio|tanti\s*saluti|'
        r'ben\s*trovato|ben\s*tornato|come\s*(stai|va|andiamo)|'
        r'ehilà|ehi|eccomi|alla\s*prossima|ci\s*vediamo|a\s*domani|'
        r'stammi?\s*bene|grazie|piacere|bentornato|bentrovato|'
        r'buona\s*(giornata|serata|notte)|a\s*dopo|ciao\s*ciao)\b',
        re.IGNORECASE
    )

    # Prossimità geografica: "vicino a", "vicino", "nei dintorni di", "nei pressi di", "zona di", "intorno a", "entro X km", "vicinanze"
    NEARBY_PATTERNS = re.compile(
        r'\b(vicino(\s+a)?|nei\s+dintorni(\s+di)?|nei\s+pressi(\s+di)?|zona\s+di|intorno\s+a|entro\s+\d+\s*km(\s+da)?|(?:nelle?\s+(?:mie\s+)?)?vicinanz[ae])\b',
        re.IGNORECASE
    )

    # Estrazione location: testo dopo "vicino a", "vicino", "nei dintorni di", etc.
    # Usa greedy matching per catturare l'intera location fino a fine stringa
    # Il post-processing rimuove "entro X km" e caratteri finali
    RE_LOCATION = re.compile(
        r'(?:vicino\s*(?:a)?|nei\s+dintorni\s*(?:di)?|nei\s+pressi\s*(?:di)?|zona\s*(?:di)?|intorno\s+a)\s+(.+)',
        re.IGNORECASE
    )

    # Pattern alternativo per "entro X km da [location]"
    RE_LOCATION_ENTRO = re.compile(
        r'entro\s+\d+(?:\.\d+)?\s*km\s+(?:da|di)\s+(.+)',
        re.IGNORECASE
    )

    # Estrazione raggio: "entro X km", "X km"
    RE_RADIUS = re.compile(r'(\d+(?:\.\d+)?)\s*km', re.IGNORECASE)

    # Pattern per pulizia location da messaggi naturali (slot fill)
    _LOCATION_PREFIXES = re.compile(
        r'^(?:mi\s+trovo\s+(?:a|in|ad|al|alla|presso|all[\'\']\s*)|'
        r'sono\s+(?:a|in|ad|al|alla|presso|all[\'\']\s*)|'
        r'sto\s+(?:a|in|ad|al|alla|presso|all[\'\']\s*))\s*',
        re.IGNORECASE
    )
    _LOCATION_PROX_PREFIX = re.compile(
        r'^(?:vicino\s+(?:a\s+)?|nei\s+pressi\s+di\s+|nei\s+dintorni\s+di\s+|'
        r'dalle\s+parti\s+di\s+|nella\s+zona\s+di\s+)',
        re.IGNORECASE
    )
    _LOCATION_VICINO_SPLIT = re.compile(
        r'^(.+?),?\s+vicino\s+(?:a\s+)?(.+)$',
        re.IGNORECASE
    )

    def _clean_location_from_message(self, message: str) -> str:
        """
        Estrae un indirizzo pulito da un messaggio in linguaggio naturale.

        Gestisce frasi come:
        - "mi trovo a Montesarchio, vicino Piazza Croce" → "Piazza Croce, Montesarchio"
        - "sono in Via Roma 15, Napoli" → "Via Roma 15, Napoli"
        - "vicino a Piazza Garibaldi" → "Piazza Garibaldi"
        - "Piazza Croce, Montesarchio" → "Piazza Croce, Montesarchio" (invariato)
        """
        text = message.strip().rstrip('?.!')

        # Rimuovi prefissi tipo "mi trovo a", "sono in"
        text = self._LOCATION_PREFIXES.sub('', text).strip()

        # Gestisci "X, vicino (a) Y" → "Y, X" (es. "Montesarchio, vicino Piazza Croce" → "Piazza Croce, Montesarchio")
        vicino_match = self._LOCATION_VICINO_SPLIT.match(text)
        if vicino_match:
            before = vicino_match.group(1).strip().rstrip(',')
            after = vicino_match.group(2).strip().rstrip(',')
            if before and after:
                return f"{after}, {before}"
            return after or before

        # Rimuovi "vicino a" semplice all'inizio (senza contesto prima)
        text = self._LOCATION_PROX_PREFIX.sub('', text).strip()

        # Pulisci preposizioni spurie: "in via Roma" → "Via Roma", "in piazza" → "Piazza"
        text = re.sub(
            r'\bin\s+(via|piazza|viale|corso|largo|vicolo|contrada|strada|localit[àa])\b',
            lambda m: m.group(1).capitalize(),
            text,
            flags=re.IGNORECASE
        )

        return text

    def _extract_location_with_llm(self, message: str) -> str:
        """
        Estrae indirizzo/location da messaggio naturale usando LLM.
        Fallback a _clean_location_from_message se LLM fallisce.
        """
        system_prompt = (
            "Estrai l'indirizzo o posizione geografica dal messaggio utente.\n"
            "Formato: \"via/piazza/luogo, comune\" oppure solo \"comune\".\n"
            "Ignora frasi conversazionali (mi trovo, sono, sto, vicino a, nei pressi di).\n"
            "Se ci sono piu' riferimenti geografici, combinali (luogo + comune).\n"
            "Se non c'e' un indirizzo identificabile, address = null.\n"
            "Output: solo JSON {\"address\": \"...\"}"
        )
        try:
            response = self.llm_client.query(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.0,
                max_tokens=150,
                json_mode=True,
                timeout=10.0
            )
            if response:
                parsed = None
                try:
                    parsed = json.loads(response)
                except json.JSONDecodeError:
                    extracted = self._extract_balanced_json(response)
                    if extracted:
                        try:
                            parsed = json.loads(extracted)
                        except json.JSONDecodeError:
                            pass
                if parsed and isinstance(parsed, dict):
                    address = parsed.get("address")
                    if address and isinstance(address, str) and len(address.strip()) > 2:
                        logger.info(f"[Router] LLM location: '{address.strip()}' <- '{message[:50]}'")
                        return address.strip()
        except Exception as e:
            logger.warning(f"[Router] LLM location fallback a regex: {e}")

        # Fallback: regex
        return self._clean_location_from_message(message)

    def __init__(self, llm_client: Optional["LLMClient"] = None, enable_cache: bool = True, cache_ttl: int = 3600):
        self.llm_client = llm_client or LLMClient()
        self.enable_cache = enable_cache
        self.intent_cache = IntentCache(ttl_seconds=cache_ttl) if enable_cache else None
        self._load_metadata_from_service()
        self._build_system_prompt()
        logger.info(f"Router configurato con modello: {self.llm_client.model}")
        if enable_cache:
            logger.info(f"Intent cache attivata (TTL: {cache_ttl}s)")

    @classmethod
    def _load_metadata_from_service(cls):
        """Carica VALID_INTENTS e REQUIRED_SLOTS da IntentMetadataService (DB-first)."""
        if cls._metadata_loaded:
            return
        try:
            from .intent_metadata_service import get_intent_metadata_service
            svc = get_intent_metadata_service()
            valid = svc.get_valid_intents()
            required = svc.get_required_slots()
            if valid:
                cls.VALID_INTENTS = valid
            if required:
                cls.REQUIRED_SLOTS = required
            cls._metadata_loaded = True
            logger.info(f"[Router] Metadati caricati da IntentMetadataService: {len(valid)} intent")
        except Exception as e:
            logger.warning(f"[Router] Fallback a metadati hardcoded: {e}")

    def _build_system_prompt(self):
        """Costruisce il prompt di classificazione dal servizio DB o fallback hardcoded."""
        # Carica schema catalog (indipendente dal servizio intent)
        schema_catalog = ""
        try:
            from .schema_catalog import get_schema_catalog
            schema_catalog = get_schema_catalog().get_compact_catalog()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Router] Schema catalog non disponibile: {e}")

        try:
            from .intent_metadata_service import get_intent_metadata_service
            service = get_intent_metadata_service()
            if service.source == 'database':
                catalog = service.get_intent_catalog_for_prompt()
                rules = service.get_disambiguation_rules_for_prompt()
                examples = service.get_critical_examples_for_prompt()
                if catalog and examples:
                    self.CLASSIFICATION_SYSTEM_PROMPT = self._CLASSIFICATION_PROMPT_TEMPLATE.format(
                        intent_catalog=catalog,
                        disambiguation_rules=rules,
                        critical_examples=examples,
                        schema_catalog=schema_catalog or self._static_schema_fallback(),
                    )
                    logger.info(f"Prompt classificazione costruito da DB ({service.source})")
                    return
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Router] Prompt dinamico fallito: {e}")

        # Fallback al prompt hardcoded
        self.CLASSIFICATION_SYSTEM_PROMPT = self._CLASSIFICATION_PROMPT_FALLBACK
        logger.info("Prompt classificazione: fallback hardcoded")

    @staticmethod
    def _static_schema_fallback() -> str:
        """Schema statico minimo per il prompt quando DB non disponibile."""
        from .schema_catalog import SchemaCatalog
        return SchemaCatalog()._static_fallback()

    def classify(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Classifica il messaggio con approccio ibrido:
        0. Gibberish detection per messaggi senza senso
        1. Heuristics per intent comuni
        2. Pre-parsing per slot
        3. LLM per casi ambigui
        4. Post-validation per needs_clarification
        """
        if not message or not message.strip():
            return self._fallback_response("Messaggio vuoto")

        message = message.strip()
        metadata = metadata or {}
        has_detail_context = bool(metadata.get("detail_context"))

        # =====================================================================
        # LAYER 0: Gibberish detection (bypass LLM per nonsense)
        # Skip se c'è un confirmed_intent con missing_slots pendenti
        # (es. l'utente risponde con un indirizzo puro a "Dove ti trovi?")
        # =====================================================================
        dialogue_state = metadata.get("_dialogue_state") or {}
        has_pending_slots = (
            dialogue_state.get("confirmed_intent")
            and dialogue_state.get("missing_slots")
        )
        logger.debug(f"[Router] message='{message[:50]}', has_pending_slots={has_pending_slots}, confirmed_intent={dialogue_state.get('confirmed_intent')}, missing_slots={dialogue_state.get('missing_slots')}")
        if not has_pending_slots and self._is_gibberish(message):
            return self._fallback_response("Messaggio non riconosciuto")

        # =====================================================================
        # LAYER 1: Pending slot fill (PRIMA delle heuristics)
        # =====================================================================
        if has_pending_slots:
            slot_result = self._fill_pending_slots(message, dialogue_state, has_detail_context)
            if slot_result is not None:
                return slot_result
            # slot_result is None → topic change o slot non estratti, prosegui

        # =====================================================================
        # LAYER 2: Heuristics (bypass LLM per casi ovvi)
        # =====================================================================
        heuristic_result = self._try_heuristics(message, has_detail_context, dialogue_state)
        if heuristic_result:
            # Pre-parse slots anche per heuristics
            slots = self._extract_slots(message)
            heuristic_result["slots"] = slots
            # Post-validation
            heuristic_result = self._post_validate(heuristic_result, message=message)
            return heuristic_result

        # =====================================================================
        # LAYER 3: Pre-parsing slot (passa al LLM come suggerimento)
        # =====================================================================
        extracted_slots = self._extract_slots(message)

        # =====================================================================
        # LAYER 4: Cache check
        # =====================================================================
        cache_key = self._build_cache_key(message, has_detail_context)
        if self.enable_cache and self.intent_cache is not None:
            cached_result = self.intent_cache.get(cache_key)
            if cached_result:
                logger.info(f"[Router] Cache HIT for: {message[:50]}...")
                self.intent_cache.record_time_saved(24000)
                # Usa SOLO slot estratti dalla query corrente (quelli cached potrebbero essere di sessioni diverse)
                cached_result["slots"] = extracted_slots
                return self._post_validate(cached_result, message=message)

        # =====================================================================
        # LAYER 5+6: LLM classification con fallback locale
        # =====================================================================
        return self._llm_classify(message, metadata, extracted_slots, cache_key)

    def _fill_pending_slots(
        self, message: str, dialogue_state: Dict[str, Any], has_detail_context: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Layer 1: gestione slot pendenti.

        Se c'e' un confirmed_intent con missing_slots, tenta di estrarre
        i valori dal messaggio corrente senza ri-classificare.

        Returns:
            Dict risultato se slot riempiti, None se topic change o slot non estratti.
        """
        pending_missing = dialogue_state.get("missing_slots", [])
        confirmed_intent = dialogue_state.get("confirmed_intent")

        # Verifica topic change: se l'heuristic matcha un intent diverso, bypass
        heuristic_check = self._try_heuristics(message, has_detail_context=False)
        if heuristic_check and heuristic_check.get("intent") != confirmed_intent:
            return None  # prosegui con LAYER 2+

        extracted_slots = self._extract_slots(message)

        if "location" in pending_missing:
            cleaned_location = self._extract_location_with_llm(message)
            if cleaned_location and len(cleaned_location) > 2:
                extracted_slots["location"] = cleaned_location
        elif "location" not in extracted_slots:
            for slot_name in pending_missing:
                if slot_name not in extracted_slots:
                    slot_value = message.strip().rstrip('?.!')
                    if slot_value and len(slot_value) > 2:
                        extracted_slots[slot_name] = slot_value

        if extracted_slots and confirmed_intent:
            filled_pending = [s for s in pending_missing if extracted_slots.get(s)]
            if filled_pending:
                return {
                    "intent": confirmed_intent,
                    "slots": self._normalize_slots(extracted_slots),
                    "needs_clarification": False,
                    "confidence": 0.95,
                }

        return None

    def _llm_classify(
        self, message: str, metadata: Dict[str, Any],
        extracted_slots: Dict[str, Any], cache_key: str
    ) -> Dict[str, Any]:
        """
        Layer 5+6: classificazione LLM con fallback locale.

        Costruisce il prompt, chiama l'LLM, merge slot, post-valida.
        Se l'LLM fallisce, usa fallback minimale (greet/goodbye/help).
        """
        classification_start = time.time()

        # Few-shot dinamici
        few_shot_examples = ""
        try:
            retriever = get_few_shot_retriever()
            if retriever.is_available():
                examples = retriever.retrieve(message, top_k=6, score_threshold=0.40, max_per_intent=2)
                if examples:
                    few_shot_examples = retriever.format_for_prompt(examples)
                    logger.info(f"[Router] Few-shot: {len(examples)} esempi recuperati")
        except Exception as e:
            logger.warning(f"[Router] Few-shot fallback: {e}")

        # Serializza metadata e slots
        metadata_str = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'))
        extracted_slots_str = json.dumps(extracted_slots, ensure_ascii=False, separators=(',', ':')) if extracted_slots else "{}"

        # Session context (~150 token max)
        session_context = self._build_session_context(metadata)

        user_prompt = self.CLASSIFICATION_USER_TEMPLATE.format(
            message=message,
            metadata=metadata_str,
            extracted_slots=extracted_slots_str
        )
        if few_shot_examples:
            user_prompt = few_shot_examples + "\n\n" + user_prompt
        if session_context:
            user_prompt = session_context + "\n" + user_prompt

        messages = [
            {"role": "system", "content": self.CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.llm_client.query(
                messages=messages, temperature=AppConfig.CLASSIFICATION_TEMPERATURE, json_mode=True
            )

            if response:
                result = self._parse_llm_response(response)

                if self._validate_result(result):
                    # Merge pre-parsed slots (LLM ha priorita' se fornisce valori)
                    llm_slots = result.get("slots", {})
                    merged_slots = {**extracted_slots, **llm_slots}
                    # Preserva prefisso ATT da _extract_slots
                    pre_piano = extracted_slots.get("piano_code", "")
                    if isinstance(pre_piano, str) and pre_piano.startswith("ATT "):
                        merged_slots["piano_code"] = pre_piano
                    result["slots"] = self._normalize_slots(merged_slots)

                    result = self._post_validate(result, message=message)

                    # Candidati per il dialogue_manager
                    alternatives = result.pop("alternatives", [])
                    candidates = [{"intent": result["intent"], "confidence": result.get("confidence", 0.70), "slots": result.get("slots", {})}]
                    for alt in alternatives[:2]:
                        alt_intent = alt.get("intent")
                        if alt_intent and alt_intent in self.VALID_INTENTS:
                            candidates.append({"intent": alt_intent, "confidence": alt.get("confidence", 0.50), "slots": alt.get("slots", {})})
                    result["_candidates"] = candidates

                    # Cache
                    classification_time = (time.time() - classification_start) * 1000
                    if self.enable_cache and self.intent_cache is not None and result.get("intent") != "fallback":
                        self.intent_cache.set(cache_key, result)
                        logger.info(f"[Router] Cached: {message[:50]}... ({classification_time:.0f}ms)")

                    return result

        except Exception as e:
            logger.error(f"[Router] LLM classification error: {e}")

        # Fallback locale per LLM-down
        msg_lower = message.lower().strip()
        if len(msg_lower) < 30 and self.GREET_PATTERNS.match(message):
            return {"intent": "greet", "slots": {}, "needs_clarification": False, "confidence": 0.90}
        if len(msg_lower) < 30 and self.GOODBYE_PATTERNS.search(message):
            return {"intent": "goodbye", "slots": {}, "needs_clarification": False, "confidence": 0.90}
        if self.HELP_PATTERNS.search(message):
            return {"intent": "ask_help", "slots": {}, "needs_clarification": False, "confidence": 0.90}

        result = self._fallback_response("LLM non disponibile")
        result["slots"] = self._normalize_slots(extracted_slots)
        return self._post_validate(result, message=message)

    def _build_session_context(self, metadata: Dict[str, Any]) -> str:
        """Costruisce contesto sessione per il prompt LLM (~150 token max)."""
        session_last_intent = metadata.get("_session_last_intent")
        session_last_slots = metadata.get("_session_last_slots")
        session_last_response_context = metadata.get("_session_last_response_context")

        if not session_last_intent and not session_last_response_context:
            return ""

        context = "\nSESSIONE:"
        if session_last_intent:
            context += f" intent={session_last_intent}"
        if session_last_slots:
            slots_compact = {k: v for k, v in (session_last_slots or {}).items() if v}
            if slots_compact:
                context += f", slots={json.dumps(slots_compact, ensure_ascii=False, separators=(',',':'))}"
        if session_last_response_context:
            context += f"\nCONTESTO RISPOSTA PRECEDENTE: {session_last_response_context}"
        return context

    def _try_heuristics(self, message: str, has_detail_context: bool, dialogue_state: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Heuristiche minimali: solo conferme/rifiuti e risposte a menu.

        Tutto il resto è delegato all'LLM che ha esempi e regole nel prompt.
        Queste heuristiche gestiscono contesto conversazionale che l'LLM non vede.
        """

        # Conferme/Rifiuti ESPLICITI (non richiedono detail_context)
        if self.CONFIRM_EXPLICIT_PATTERNS.match(message):
            return {"intent": "confirm_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.99}
        if self.DECLINE_EXPLICIT_PATTERNS.match(message):
            return {"intent": "decline_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.99}

        # Conferme/Rifiuti BREVI (richiedono detail_context per disambiguare)
        if has_detail_context:
            if self.CONFIRM_SHORT_PATTERNS.match(message):
                return {"intent": "confirm_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.99}
            if self.DECLINE_SHORT_PATTERNS.match(message):
                return {"intent": "decline_show_details", "slots": {}, "needs_clarification": False, "confidence": 0.99}

        # Risposte disambiguazione rischio
        # Pattern TESTUALI: matchano sempre (sono inequivocabili)
        if self.RE_RISK_TYPE_MAI_CONTROLLATI_TEXT.match(message):
            return {"intent": "ask_risk_based_priority", "slots": {"tipo_analisi_rischio": "mai_controllati"}, "needs_clarification": False, "confidence": 0.99}
        if self.RE_RISK_TYPE_CON_SANZIONI_TEXT.match(message):
            return {"intent": "ask_risk_based_priority", "slots": {"tipo_analisi_rischio": "con_sanzioni"}, "needs_clarification": False, "confidence": 0.99}

        # Pattern NUMERICI ("1"/"2"): solo se contesto di disambiguazione rischio pendente
        # Evita conflitto con disambiguazione intent generica gestita dal DM
        _has_risk_disambiguation = False
        if dialogue_state:
            _last = dialogue_state.get("confirmed_intent") or dialogue_state.get("last_tool_intent")
            _last_slots = dialogue_state.get("slots") or {}
            _has_risk_disambiguation = (
                _last == "ask_risk_based_priority"
                and not _last_slots.get("tipo_analisi_rischio")
            )
        if _has_risk_disambiguation:
            if self.RE_RISK_TYPE_NUMERIC_1.match(message):
                return {"intent": "ask_risk_based_priority", "slots": {"tipo_analisi_rischio": "mai_controllati"}, "needs_clarification": False, "confidence": 0.99}
            if self.RE_RISK_TYPE_NUMERIC_2.match(message):
                return {"intent": "ask_risk_based_priority", "slots": {"tipo_analisi_rischio": "con_sanzioni"}, "needs_clarification": False, "confidence": 0.99}

        # Tutto il resto → LLM
        return None

    def _extract_slots(self, message: str) -> Dict[str, Any]:
        """
        Estrazione deterministica degli slot via regex.
        """
        slots = {}

        # Attività code: "attività B5" o "attività B5_A" → piano_code con prefisso ATT
        attivita_match = re.search(
            r'\battivit[aà]\s+([A-Z]{1,2}[0-9]{1,3}(?:_[A-Z0-9]+)?)\b', message, re.IGNORECASE
        )
        if attivita_match:
            slots["piano_code"] = f"ATT {attivita_match.group(1).upper()}"
            slots["entity_hint"] = "attivita"
        else:
            # Piano code
            piano_match = self.RE_PIANO_CODE.search(message)
            if piano_match:
                slots["piano_code"] = piano_match.group(1).upper()
                # Hint esplicito "piano X" (l'utente qualifica il codice come piano)
                if re.search(
                    rf'\bpiano\s+{re.escape(piano_match.group(1))}\b',
                    message, re.IGNORECASE
                ):
                    slots["entity_hint"] = "piano"

        # ASL
        # Nota: il pattern RE_ASL `[A-Z]{2}[0-9]` collide con pattern piano/attività
        # (es. "AO1" è un piano, non una ASL). Se il token estratto coincide con
        # `piano_code` già rilevato, non sovrascrivere lo slot — è un piano.
        # Stessa cosa se il token contiene underscore (piani come A1_A) o se
        # l'utente ha usato la parola "piano"/"attività" come hint.
        asl_match = self.RE_ASL.search(message)
        if asl_match:
            asl_candidate = asl_match.group(1).upper()
            piano_already = (slots.get("piano_code") or "").upper().replace("ATT ", "")
            # Skip se il candidato coincide col piano già estratto
            if asl_candidate != piano_already:
                # Skip anche se l'utente ha qualificato il token come piano/attività
                entity_hint = slots.get("entity_hint")
                has_piano_hint = bool(re.search(
                    rf'\b(?:piano|attivit[àa])\s+{re.escape(asl_candidate)}\b',
                    message, re.IGNORECASE
                ))
                if not (entity_hint or has_piano_hint):
                    slots["asl"] = asl_candidate

        # Numero riconoscimento UE (priorità su numero registrazione)
        num_ric_match = self.RE_NUM_RIC.search(message)
        if num_ric_match:
            slots["numero_riconoscimento"] = num_ric_match.group(1).strip().upper()
        else:
            # Numero registrazione (senza UE, solo IT)
            num_reg_match = self.RE_NUM_REG.search(message)
            if num_reg_match:
                slots["num_registrazione"] = num_reg_match.group(1).strip().upper()

        # Partita IVA solo se esplicitamente menzionata
        if "p.iva" in message.lower() or "partita iva" in message.lower():
            piva_match = self.RE_PARTITA_IVA.search(message)
            if piva_match:
                slots["partita_iva"] = piva_match.group(1)

        # Sezione piani: "sezione A", "della sezione B"
        sezione_match = self.RE_SEZIONE.search(message)
        if sezione_match:
            slots["sezione"] = sezione_match.group(1).upper()

        # Topic: estrai argomento dopo "piani su/per/riguardanti"
        topic_match = self.RE_TOPIC.search(message)
        if topic_match:
            topic = topic_match.group(1).strip().rstrip('?.!')
            if topic:
                slots["topic"] = topic

        # Ragione sociale: parola(e) dopo "stabilimento" (non IT/UE/piano)
        if "stabilimento" in message.lower() and "num_registrazione" not in slots and "numero_riconoscimento" not in slots:
            ragione_match = re.search(
                r'\bstabilimento\s+(?!IT\b|UE\b|piano\b)([A-Z][A-Za-z0-9\s]*)',
                message, re.IGNORECASE
            )
            if ragione_match:
                ragione = ragione_match.group(1).strip()
                if ragione and len(ragione) > 1:
                    slots["ragione_sociale"] = ragione

        # Ragione sociale fallback: in contesto "storico/storia controlli per/di [nome]"
        # quando "stabilimento" non è presente nel messaggio
        if ("ragione_sociale" not in slots and
            "num_registrazione" not in slots and
            "numero_riconoscimento" not in slots and
            "partita_iva" not in slots and
            self.ESTABLISHMENT_HISTORY_PATTERNS.search(message)):
            ragione_ctx_match = re.search(
                r'(?:storic[ao]|storia)\s+(?:dei\s+)?(?:controll[io]?|stabilimento)\s+'
                r'(?:(?:per|di|del(?:lo|la)?)\s+)?'
                r'(?!partita\s*iva\b|p\.?\s*iva\b|IT\s|UE\s|stabilimento\b)'
                r'([A-Za-z][A-Za-z0-9\s\.\']*)',
                message, re.IGNORECASE
            )
            if ragione_ctx_match:
                ragione = ragione_ctx_match.group(1).strip().rstrip('?.!')
                if ragione and len(ragione) > 1:
                    slots["ragione_sociale"] = ragione

        # Categoria NC: parole chiave note di categorie
        if self.NC_CATEGORY_PATTERNS.search(message):
            cat_match = re.search(
                r'\b(HACCP|IGIENE\s+DEGLI\s+ALIMENTI|IGIENE|STRUTTUR[AE]|GENERALI|'
                r'PULIZIA|SANIFICAZIONE|ETICHETTATURA|MOCA|RINTRACCIABILIT[ÀA])\b',
                message, re.IGNORECASE
            )
            if cat_match:
                # Normalizza la categoria estratta
                categoria = cat_match.group(1).upper()
                # Converti varianti in forma standard
                if 'STRUTTUR' in categoria:
                    categoria = 'STRUTTURE'
                elif 'RINTRACCIABILIT' in categoria:
                    categoria = 'RINTRACCIABILITA'
                slots["categoria"] = categoria

        # Location: estrai indirizzo dopo pattern prossimità
        if self.NEARBY_PATTERNS.search(message):
            location_match = self.RE_LOCATION.search(message)
            if location_match:
                location = location_match.group(1).strip().rstrip('?.!')
                # Rimuovi eventuale "entro X km" dalla fine
                location = re.sub(r'\s+entro\s+\d+.*$', '', location, flags=re.IGNORECASE)
                if location and len(location) > 2:
                    slots["location"] = location

            # Fallback: prova pattern "entro X km da [location]"
            if "location" not in slots:
                location_entro_match = self.RE_LOCATION_ENTRO.search(message)
                if location_entro_match:
                    location = location_entro_match.group(1).strip().rstrip('?.!')
                    if location and len(location) > 2:
                        slots["location"] = location

            # Raggio: estrai "X km"
            radius_match = self.RE_RADIUS.search(message)
            if radius_match:
                try:
                    radius = float(radius_match.group(1))
                    # Limita raggio tra 1 e 50 km
                    slots["radius_km"] = max(1.0, min(50.0, radius))
                except ValueError:
                    pass

        # Tipo analisi rischio: disambiguazione stabilimenti a rischio
        if self.RE_RISK_TYPE_MAI_CONTROLLATI.match(message):
            slots["tipo_analisi_rischio"] = "mai_controllati"
        elif self.RE_RISK_TYPE_CON_SANZIONI.match(message):
            slots["tipo_analisi_rischio"] = "con_sanzioni"

        return slots

    def _build_cache_key(self, message: str, has_detail_context: bool) -> str:
        """Costruisce chiave cache normalizzata considerando il contesto."""
        base_key = message.lower().strip()
        # Rimuovi punteggiatura finale
        base_key = base_key.rstrip("?!.,;:")
        # Collassa spazi multipli
        base_key = re.sub(r'\s+', ' ', base_key)
        if has_detail_context:
            base_key = f"__ctx__:{base_key}"
        return base_key

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse risposta LLM estraendo JSON con chain di fallback."""
        response = response.strip()

        parsed = None

        # 1. Tentativo diretto (json_mode dovrebbe produrre JSON pulito)
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            pass

        # 2. Estrai JSON da blocchi code ```json ... ```
        if not parsed:
            json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_block_match:
                try:
                    parsed = json.loads(json_block_match.group(1))
                except json.JSONDecodeError:
                    pass

        # 3. Parser a parentesi bilanciate per estrarre il primo JSON valido
        if not parsed:
            extracted = self._extract_balanced_json(response)
            if extracted:
                try:
                    parsed = json.loads(extracted)
                except json.JSONDecodeError:
                    pass

        if not parsed:
            raise ValueError(f"JSON parsing fallito per risposta: {response[:200]}")

        # FIXUP: Aggiungi needs_clarification se mancante (default: False)
        if "needs_clarification" not in parsed:
            parsed["needs_clarification"] = False

        # FIXUP: Assicura che slots sia un dict
        if "slots" not in parsed:
            parsed["slots"] = {}

        # FIXUP: Parsing confidence con clamp 0-1
        if "confidence" in parsed:
            try:
                conf = float(parsed["confidence"])
                parsed["confidence"] = max(0.0, min(1.0, conf))
            except (TypeError, ValueError):
                parsed["confidence"] = 0.70  # fallback se non numerico
        else:
            parsed["confidence"] = 0.70  # default se non presente

        # FIXUP: Estrai alternatives (lista di candidati alternativi)
        if "alternatives" in parsed:
            alts = parsed["alternatives"]
            if not isinstance(alts, list):
                parsed["alternatives"] = []
        else:
            parsed["alternatives"] = []

        return parsed

    def _extract_balanced_json(self, text: str) -> str:
        """Estrai il primo oggetto JSON bilanciato dal testo."""
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

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Valida struttura risposta LLM."""
        if not isinstance(result, dict):
            return False

        intent = result.get("intent")
        if intent not in self.VALID_INTENTS:
            return False

        if "slots" not in result or not isinstance(result["slots"], dict):
            return False

        if "needs_clarification" not in result or not isinstance(result["needs_clarification"], bool):
            return False

        # Filtra slot non consentiti
        result["slots"] = {
            k: v for k, v in result["slots"].items()
            if k in self.VALID_SLOT_KEYS
        }

        return True

    def _normalize_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizza valori slot (uppercase per piano_code, asl)."""
        normalized = {}
        for key, value in slots.items():
            if value is None or value == "":
                continue
            if key == "piano_code" and isinstance(value, str):
                normalized[key] = value.upper()
            elif key == "asl" and isinstance(value, str):
                normalized[key] = value.upper()
            elif key == "categoria" and isinstance(value, str):
                normalized[key] = value.upper()
            else:
                normalized[key] = value
        return normalized

    # Pattern semantici per correzione intent
    _SEMANTIC_CORRECTIONS = [
        # Se il messaggio contiene "piano" + piano_code ma l'intent è rischio → riclassifica
        (r'\bpiano\b.*\b[A-Z]\d', {"ask_risk_based_priority", "ask_top_risk_activities"}, "ask_piano_stabilimenti"),
        # Se il messaggio chiede "stabilimenti" ma classificato come piano → riclassifica
        (r'\bstabiliment[io]\b.*\brischio\b', {"ask_piano_stabilimenti", "ask_piano_description"}, "ask_risk_based_priority"),
        # Se il messaggio chiede "attività" + "rischio" ma classificato come piano → riclassifica
        (r'\battivit[aà]\b.*\brischi[eo]\b', {"ask_piano_stabilimenti", "ask_piano_description"}, "ask_top_risk_activities"),
    ]

    def _post_validate(self, result: Dict[str, Any], message: str = "") -> Dict[str, Any]:
        """
        Post-validation: forza needs_clarification basandosi sulla presenza slot.
        Aggiunge correzioni semantiche per intent classificati erroneamente.

        P3: Quando MINIMAL_HEURISTICS=True, skip correzioni semantiche
        (l'LLM con prompt V2 dovrebbe già fare la disambiguazione corretta).
        """
        intent = result.get("intent", "fallback")
        slots = result.get("slots", {})

        # Filtra slot con valori nulli/invalidi (LLM a volte restituisce "NULL", "null", etc.)
        invalid_values = {"NULL", "null", "undefined", "none", "None", "", "N/A", "n/a"}
        slots = {k: v for k, v in slots.items() if v not in invalid_values}
        result["slots"] = slots

        # =====================================================================
        # CORREZIONI SEMANTICHE DETERMINISTICHE
        # =====================================================================

        # Fix 1: search_piani_by_topic con piano_code
        # Se l'LLM classifica "attività del piano B2" come search_piani_by_topic
        # ma c'è un piano_code, l'utente vuole info SU quel piano, non cerca piani
        if intent == "search_piani_by_topic" and slots.get("piano_code"):
            result["intent"] = "ask_piano_stabilimenti"
            intent = "ask_piano_stabilimenti"
            # Rimuovi topic se presente (era una falsa estrazione)
            if "topic" in result["slots"]:
                del result["slots"]["topic"]

        # Fix 2: ask_priority_establishment con "rischio"
        # Se la query menziona "rischio" ma l'LLM classifica come priority_establishment
        # l'utente vuole priorità basata sul rischio, non sulla programmazione
        if intent == "ask_priority_establishment" and message:
            if re.search(r'\brischio\b', message, re.IGNORECASE):
                result["intent"] = "ask_risk_based_priority"
                intent = "ask_risk_based_priority"

        # Fix 3: "più controllati" / aggregazione dati misclassificata come nearby/priority
        # "stabilimenti più controllati" è una aggregazione (ranking per numero controlli),
        # NON ask_nearby_priority (che cerca mai controllati vicino a indirizzo) né
        # ask_priority_establishment (priorità per ritardi programmazione)
        if intent in ("ask_nearby_priority", "ask_priority_establishment") and message:
            if re.search(r'\bpi[uù]\s+controllat[ie]\b', message, re.IGNORECASE):
                result["intent"] = "query_data"
                intent = "query_data"
                result["confidence"] = 0.75
                result["needs_clarification"] = False

        # Fix 4: query_data con piano_code → ask_piano_stabilimenti
        # "controlli per l'attività B47" / "controlli per il piano A1" con codice specifico
        # non è un conteggio generico ma una richiesta di dettagli su piano/attività
        if intent == "query_data" and slots.get("piano_code"):
            result["intent"] = "ask_piano_stabilimenti"
            intent = "ask_piano_stabilimenti"
            result["confidence"] = 0.90
            result["needs_clarification"] = False

        # Fix 5: "attività in ritardo" generico → ask_delayed_plans
        # Se classificato come check_if_plan_delayed ma senza piano_code e messaggio
        # contiene "attività" + ritardo → è una lista, non una verifica specifica
        if intent == "check_if_plan_delayed" and not slots.get("piano_code") and message:
            if re.search(r'\battivit[aà]\b.*\b(ritard[oi]|scadut[eiao])\b', message, re.IGNORECASE):
                result["intent"] = "ask_delayed_plans"
                intent = "ask_delayed_plans"
                result["confidence"] = 0.95
                result["needs_clarification"] = False

        # Fix 6: "controlli programmati per piano X" → check_if_plan_delayed
        # Gli intent ask_piano_stabilimenti / ask_piano_statistics / query_data
        # lavorano sugli ESEGUITI. Quando l'utente chiede esplicitamente i
        # controlli "programmati" (o il confronto programmati vs eseguiti),
        # la fonte è cu_diff_programmati_eseguiti gestita da check_if_plan_delayed,
        # che mostra programmati/eseguiti/ritardo per un piano specifico.
        _programmed_intents = {
            "ask_piano_stabilimenti", "ask_piano_statistics",
            "query_data", "ask_piano_description",
        }
        if intent in _programmed_intents and slots.get("piano_code") and message:
            if re.search(r'\bprogramm(?:at[oiae]|azione)\b', message, re.IGNORECASE):
                result["intent"] = "check_if_plan_delayed"
                intent = "check_if_plan_delayed"
                result["confidence"] = 0.90
                result["needs_clarification"] = False

        # Fix 7: "controlli fatti/eseguiti per [codice]" — ambiguo tra stabilimenti e statistiche
        # "controlli fatti per AO1" puo' significare:
        #   - "fammi vedere gli stabilimenti controllati" → ask_piano_stabilimenti
        #   - "quanti controlli sono stati fatti" → ask_piano_statistics
        # Se il messaggio NON contiene parole disambiguanti, inietta alternativa
        if intent == "ask_piano_stabilimenti" and slots.get("piano_code") and message:
            msg_lower = message.lower()
            has_controlli = re.search(r'\bcontroll[ioa]\b', msg_lower)
            has_stab_keywords = re.search(
                r'\b(stabiliment[io]|elenco|lista|quali\s+stabiliment|dove)\b', msg_lower
            )
            has_stat_keywords = re.search(
                r'\b(quant[ie]|statistic[ah]e|numer[io]|conteggio|frequenz[ae]|totale)\b', msg_lower
            )
            if has_controlli and not has_stab_keywords and not has_stat_keywords:
                result["confidence"] = 0.65
                result["alternatives"] = [
                    {"intent": "ask_piano_statistics", "confidence": 0.55,
                     "slots": {"piano_code": slots["piano_code"]}}
                ]

        # Correzioni semantiche (deterministiche, no LLM cost)
        # P3: Skip quando MINIMAL_HEURISTICS=True - deleghiamo all'LLM
        if message and not self.MINIMAL_HEURISTICS:
            msg_lower = message.lower()
            for pattern, wrong_intents, correct_intent in self._SEMANTIC_CORRECTIONS:
                if intent in wrong_intents and re.search(pattern, msg_lower):
                    result["intent"] = correct_intent
                    intent = correct_intent
                    break

        # Intent senza slot obbligatori - sempre clarification=false
        self_sufficient = [
            "greet", "goodbye", "ask_help", "ask_priority_establishment",
            "ask_risk_based_priority", "ask_suggest_controls", "ask_delayed_plans",
            "ask_piano_statistics", "ask_top_risk_activities",
            "confirm_show_details", "decline_show_details", "fallback"
        ]

        if intent in self_sufficient:
            result["needs_clarification"] = False
            return result

        # Verifica slot obbligatori
        required = self.REQUIRED_SLOTS.get(intent, [])

        if intent == "ask_establishment_history":
            # Almeno uno tra num_registrazione, partita_iva, ragione_sociale
            has_identifier = any(slots.get(k) for k in required)
            if has_identifier:
                result["needs_clarification"] = False
            else:
                result["needs_clarification"] = True
                result["slots"] = {}
        elif intent == "search_piani_by_topic" and slots.get("sezione"):
            # "piani della sezione A": la sezione e' un filtro strutturato
            # valido, il topic testuale non e' piu' richiesto.
            result["needs_clarification"] = False
        else:
            # Tutti i required devono essere presenti
            missing = [r for r in required if not slots.get(r)]
            if missing:
                result["needs_clarification"] = True
                result["slots"] = {}
            else:
                # Slot presenti - forza clarification=false
                result["needs_clarification"] = False

        return result

    def _fallback_response(self, reason: str = "") -> Dict[str, Any]:
        return {
            "intent": "fallback",
            "slots": {},
            "needs_clarification": False,
            "confidence": 0.99,
            "error": reason
        }

    def _is_gibberish(self, message: str) -> bool:
        """
        Rileva messaggi senza senso (gibberish) per evitare LLM call inutili.

        Approccio permissivo: blocca solo messaggi brevi senza keyword.
        Messaggi >15 char passano all'LLM che sa distinguere pertinenza.
        """
        if len(message) < 3:
            return False

        msg_lower = message.lower().strip()

        # Conferme/rifiuti brevi sono OK
        if self.CONFIRM_SHORT_PATTERNS.match(message) or self.DECLINE_SHORT_PATTERNS.match(message):
            return False
        if self.CONFIRM_EXPLICIT_PATTERNS.match(message) or self.DECLINE_EXPLICIT_PATTERNS.match(message):
            return False

        # Risposte numeriche sono OK (selezione da menu)
        if re.match(r'^\s*[0-9]+\s*$', message):
            return False

        # Se contiene parole del dominio, non è gibberish
        if self.DOMAIN_KEYWORDS.search(message):
            return False

        # Espressioni sociali → lasciali passare all'LLM
        if self.SOCIAL_PATTERNS.search(message):
            return False

        # Saluti/commiati/help → lasciali passare all'LLM
        if self.GREET_PATTERNS.match(message):
            return False
        if self.GOODBYE_PATTERNS.search(message):
            return False
        if self.HELP_PATTERNS.search(message):
            return False

        # Se il messaggio è lungo abbastanza (>15 char), lascialo passare all'LLM
        # L'LLM capirà se è pertinente o meno
        if len(msg_lower) > 15:
            return False

        # Messaggi brevi composti da parole reali (solo lettere/spazi/accenti) →
        # potrebbero essere saluti in altre lingue (hola, bonjour, namaste, yo).
        # Lasciamo decidere all'LLM invece di bloccarli come gibberish,
        # MA filtriamo pattern che non sono parole reali:
        # - nessuna vocale (asdfghjkl)
        # - caratteri ripetuti 3+ volte (xxxyyy, aaabbb)
        if re.match(r'^[a-zà-öø-ÿ\s]+$', msg_lower) and len(msg_lower) >= 2:
            chars_only = msg_lower.replace(' ', '')
            vowels = len(re.findall(r'[aeiouyàèéìòùäëïöü]', msg_lower))
            vowel_ratio = vowels / len(chars_only) if chars_only else 0
            has_char_repetition = bool(re.search(r'(.)\1{2,}', msg_lower))
            # Parole ripetute ("bla bla bla", "no no no")
            words = msg_lower.split()
            has_word_repetition = len(words) >= 3 and len(set(words)) == 1
            if vowel_ratio >= 0.2 and not has_char_repetition and not has_word_repetition:
                return False

        # Messaggi brevi senza keyword, senza vocali o con pattern ripetitivi → gibberish
        return True

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get intent cache statistics."""
        if not self.enable_cache or self.intent_cache is None:
            return {"cache_enabled": False}

        stats = self.intent_cache.get_stats()
        stats["cache_enabled"] = True
        return stats

    def reload(self) -> None:
        """Hot-reload: ricarica metadati intent da DB, ricostruisce prompt, svuota cache."""
        try:
            from .intent_metadata_service import get_intent_metadata_service
            service = get_intent_metadata_service()
            service.reload()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Router] Reload IntentMetadataService fallito: {e}")

        self._build_system_prompt()
        self.clear_cache()
        logger.info("[Router] Reload completato")

    def clear_cache(self) -> None:
        """Clear all cached intent classifications."""
        if self.enable_cache and self.intent_cache is not None:
            self.intent_cache.clear_all()
            logger.info("[Router] Cache cleared")

    # =========================================================================
    # WORKFLOW-AWARE CLASSIFICATION (Fase 2: Router Enhancement)
    # =========================================================================

    def classify_with_context(
        self,
        message: str,
        metadata: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classificazione context-aware che considera workflow attivo.

        Questo metodo estende classify() standard con supporto per:
        - Risposte a pending_question (strategy choice, param collection)
        - Richieste "oppure?" per alternative
        - Raffinamento query progressivo

        Args:
            message: Messaggio utente
            metadata: Metadata sessione
            workflow_context: Context workflow validato (opzionale)

        Returns:
            Classification result con intent speciali (__choose_strategy__, etc.)
        """
        # 1. Se workflow attivo, controlla se è risposta a pending_question
        if workflow_context and workflow_context.get("pending_question"):
            return self._classify_response_to_question(message, workflow_context)

        # 2. Controlla se è richiesta "oppure?" per alternative
        if workflow_context and self._is_oppure_request(message):
            return self._handle_oppure_request(workflow_context)

        # 3. Controlla se è raffinamento query
        if workflow_context and self._is_refinement_request(message):
            filters = self._extract_refinement_filters(message)
            return {
                "intent": "__refine__",  # Intent speciale
                "slots": filters,
                "needs_clarification": False,
                "is_refinement": True
            }

        # 4. Altrimenti usa classificazione standard
        return self.classify(message, metadata)

    def _classify_response_to_question(
        self,
        message: str,
        workflow_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classifica risposta a domanda del sistema con validazione nonce.

        SECURITY: Valida workflow freshness prima di routing.

        Args:
            message: Risposta utente
            workflow_context: Context workflow con pending_question

        Returns:
            Classification result
        """
        from .workflow_validator import WorkflowValidator

        pending = workflow_context.get("pending_question", {})
        workflow_nonce = workflow_context.get("workflow_nonce")

        # CRITICAL: Valida nonce per prevenire cross-turn spoofing
        if not WorkflowValidator.validate_pending_question(pending, workflow_nonce):
            # Nonce mismatch o pending_question non valido
            return {"intent": "fallback", "slots": {}, "needs_clarification": False}

        question_type = pending.get("type")

        if question_type == "strategy_choice":
            # Estrai scelta utente tra le opzioni disponibili
            available_opts = workflow_context.get("available_options", [])
            choice = self._match_user_choice(message, available_opts)
            return {
                "intent": "__choose_strategy__",
                "slots": {"strategy_choice": choice},
                "needs_clarification": choice is None
            }

        elif question_type == "param_collection":
            # Estrai parametro richiesto
            param_name = pending.get("param_name")
            value = self._extract_param_value(message, param_name)
            return {
                "intent": "__provide_param__",
                "slots": {param_name: value},
                "needs_clarification": value is None
            }

        elif question_type == "oppure_confirmation":
            # FIXED: Gestione esplicita "oppure?" confirmation
            # Riconosce "sì", "ok", "procedi"
            if self._is_positive_response(message):
                return {
                    "intent": "__choose_strategy__",
                    "slots": {"strategy_choice": pending.get("strategy_id")},
                    "needs_clarification": False
                }
            # Riconosce "no", "altro"
            elif self._is_negative_response(message):
                return {
                    "intent": "__oppure__",  # Mostra prossima strategia
                    "slots": {},
                    "needs_clarification": False
                }

        return {"intent": "fallback", "slots": {}, "needs_clarification": False}

    def _is_positive_response(self, message: str) -> bool:
        """Riconosce risposte affermative."""
        positive_patterns = [
            r"^\s*s[ìi]\s*$", r"^\s*ok\s*$", r"^\s*va\s+bene\s*$",
            r"^\s*procedi\s*$", r"^\s*d[\'']?accordo\s*$"
        ]
        return any(re.match(p, message.lower()) for p in positive_patterns)

    def _is_negative_response(self, message: str) -> bool:
        """Riconosce risposte negative."""
        negative_patterns = [
            r"^\s*no\s*$", r"^\s*altro\s*$", r"^\s*oppure\s*$"
        ]
        return any(re.match(p, message.lower()) for p in negative_patterns)

    def _is_oppure_request(self, message: str) -> bool:
        """Riconosce richieste di alternative."""
        oppure_patterns = [
            r"^\s*oppure\s*\??$",
            r"^\s*alternative?\??$",
            r"^\s*altro\??$",
            r"^\s*cos[\'']?altro\??$"
        ]
        return any(re.match(p, message.lower()) for p in oppure_patterns)

    def _handle_oppure_request(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gestisce richiesta "oppure?" per mostrare prossima strategia.

        Args:
            workflow_context: Context workflow corrente

        Returns:
            Intent speciale __oppure__
        """
        return {
            "intent": "__oppure__",
            "slots": {},
            "needs_clarification": False
        }

    def _is_refinement_request(self, message: str) -> bool:
        """Riconosce richieste di raffinamento."""
        refinement_patterns = [
            r"rifare\s+(?:la\s+)?ricerca",
            r"rifai\s+(?:la\s+)?ricerca",
            r"stessa\s+ricerca",
            r"solo\s+(?:nel|in|per|con)",
            r"filtra\s+per",
            r"limita\s+a"
        ]
        return any(re.search(p, message.lower()) for p in refinement_patterns)

    def _extract_refinement_filters(self, message: str) -> Dict[str, Any]:
        """
        Estrae filtri da richiesta raffinamento con validazione.

        SECURITY: Valida filtri estratti contro whitelist domain.

        Args:
            message: Messaggio utente con filtri

        Returns:
            Filtri validati
        """
        from .workflow_strategies import FILTER_PATTERNS
        from .workflow_validator import WorkflowValidator

        filters = {}
        for filter_name, pattern in FILTER_PATTERNS.items():
            if isinstance(pattern, dict):
                # Filtro composito (tipo_attivita)
                for subkey, subpattern in pattern.items():
                    match = re.search(subpattern, message, re.IGNORECASE)
                    if match:
                        if filter_name not in filters:
                            filters[filter_name] = {}
                        filters[filter_name][subkey] = match.group(1)
            else:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    filters[filter_name] = match.group(1)

        # CRITICAL: Valida e sanitizza filtri estratti
        return WorkflowValidator.validate_filters(filters)

    def _match_user_choice(
        self,
        message: str,
        available_options: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Estrae scelta utente con matching numerico + sinonimi.

        Migliora UX permettendo:
        - Match numerico: "1", "2", "3"
        - Label esatto o parziale
        - Sinonimi comuni

        Args:
            message: Risposta utente
            available_options: Opzioni disponibili

        Returns:
            ID opzione scelta o None se non match
        """
        message_clean = message.strip().lower()

        # Match numerico: "1", "2", "3"
        if message_clean.isdigit():
            idx = int(message_clean) - 1
            if 0 <= idx < len(available_options):
                return available_options[idx]["id"]

        # Match label esatto o parziale
        for opt in available_options:
            label = opt.get("label", "").lower()
            if label in message_clean or message_clean in label:
                return opt["id"]

        # Match sinonimi comuni
        synonyms = {
            "pianificazione": ["planning", "piani", "ritardo"],
            "rischio": ["risk", "nc", "non conformit"],
            "primo": ["1", "prima", "opzione 1"],
            "secondo": ["2", "seconda", "opzione 2"],
        }

        for opt in available_options:
            for syn_list in synonyms.values():
                if any(syn in message_clean for syn in syn_list):
                    if any(syn in opt.get("label", "").lower() for syn in syn_list):
                        return opt["id"]

        return None

    def _extract_param_value(self, message: str, param_name: str) -> Optional[Any]:
        """
        Estrae valore parametro con type checking.

        Args:
            message: Messaggio utente
            param_name: Nome parametro da estrarre

        Returns:
            Valore parametro o None
        """
        from .workflow_strategies import FILTER_PATTERNS

        if param_name == "limit":
            match = re.search(FILTER_PATTERNS["limit"], message)
            if match:
                try:
                    return max(1, min(int(match.group(1)), 500))  # Cap a 500
                except ValueError:
                    return None

        elif param_name == "comune":
            match = re.search(FILTER_PATTERNS["comune"], message, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()

        elif param_name == "asl":
            match = re.search(FILTER_PATTERNS["asl"], message, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()

        return None
