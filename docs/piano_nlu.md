# Piano di Miglioramento NLU - GiAs-llm

## Contesto

Il sistema di classificazione intent in `orchestrator/router.py` ha accumulato troppa logica euristica ad-hoc (`_try_heuristics`: 25 regex rule con ordine fragile) e usa l'LLM (Ministral 3B) con un prompt troppo scarno (15 esempi per 20 intent). Quando l'LLM sbaglia, 3 `_SEMANTIC_CORRECTIONS` regex correggono post-hoc. Il dialogue manager lavora su confidence hardcoded (0.90/0.55/0.30) invece che su valori reali dell'LLM. Obiettivo: spostare l'intelligenza dalle regex all'LLM, migliorare il prompt, aggiungere confidence reale, e usare Qdrant per few-shot dinamico.

**Ordine di deploy**: P1 → P2 → P4 → P3 (P3 per ultimo perche' rimuove la safety net delle heuristic e richiede LLM validato)

---

## Priorita' 1: Migliorare il prompt LLM di classificazione

### File da modificare
- `GiAs-llm/orchestrator/router.py` — `CLASSIFICATION_SYSTEM_PROMPT` (righe 61-106)

### Cosa cambia

Sostituire il prompt attuale con uno ristrutturato che:

1. **Aggiunge `reasoning` e `confidence` allo schema JSON output**:
```json
{"reasoning":"breve motivo","intent":"NOME","slots":{},"needs_clarification":false,"confidence":0.85}
```

2. **Raggruppa gli intent per categoria** (aiuta il modello a navigare):
```
INTENT PER CATEGORIA:
Piani: ask_piano_description(piano_code) | ask_piano_stabilimenti(piano_code) | ask_piano_statistics | search_piani_by_topic(topic)
Priorita: ask_priority_establishment | ask_risk_based_priority | ask_suggest_controls | ask_nearby_priority(location,radius_km)
Ritardi: ask_delayed_plans | check_if_plan_delayed(piano_code)
Storico: ask_establishment_history(...) | ask_top_risk_activities | analyze_nc_by_category(categoria)
Procedure: info_procedure
Base: greet | goodbye | ask_help | confirm_show_details | decline_show_details | fallback
```

3. **Aggiunge regole di disambiguazione esplicite con negazione** (risolvono le confusioni note):
```
- STABILIMENTI a rischio/pericolosi → ask_risk_based_priority (NON ask_piano_*)
- ATTIVITÀ a rischio/classifica rischio → ask_top_risk_activities (NON ask_risk_based_priority)
- piano+codice SENZA "rischio/ritardo" → ask_piano_stabilimenti
- chi devo controllare/priorità programmazione → ask_priority_establishment (NON ask_risk_based_priority)
- confidence: 0.95 se chiaro, 0.70 se probabile, 0.40 se incerto
```

4. **Porta gli esempi da 15 a ~20** coprendo tutti gli intent, inclusi disambiguation pair:
```
"stabilimenti a rischio" → ask_risk_based_priority  (conf 0.95)
"attività più rischiose" → ask_top_risk_activities  (conf 0.95)
"chi devo controllare per primo" → ask_priority_establishment (conf 0.95)
"stabilimenti mai controllati" → ask_suggest_controls (conf 0.95)
"storico IT 2287" → ask_establishment_history (conf 0.90)
"NC categoria HACCP" → analyze_nc_by_category (conf 0.95)
"statistiche piani" → ask_piano_statistics (conf 0.95)
```
Fonti: `INTENT_REGISTRY.examples` in `intent_metadata.py` + tabella DB `intents.example_question`

5. **Budget token**: ~700-750 token per system prompt (entro il limite 800 per Ministral 3B)

### Retrocompatibilita'
- Il vecchio prompt salvato come commento `CLASSIFICATION_SYSTEM_PROMPT_V1` per rollback rapido
- I nuovi campi JSON (`reasoning`, `confidence`) vengono ignorati silenziosamente dal parser esistente fino a P2 (il FIXUP in `_parse_llm_response` riga 772 gia' gestisce campi mancanti)
- Nessun cambiamento all'interfaccia di `Router.classify()` — ritorna lo stesso dict di prima

### Test
- Tutti i test esistenti in `test_router.py` devono passare invariati (usano mock LLM, non il prompt reale)
- Aggiungere `test_parse_llm_response_with_new_fields`: verifica che `_parse_llm_response` gestisca il nuovo schema senza errori
- Test manuale con curl su 20+ messaggi reali per validare classificazione
- Aggiungere `test_prompt_token_budget`: verifica che il prompt non superi 800 token (proxy: `len(prompt.split()) < 600`)

### Rischi
- **Basso**: cambia solo il path LLM. Le heuristic (che gestiscono ~60% del traffico) sono intatte
- **Rollback**: ripristinare `CLASSIFICATION_SYSTEM_PROMPT_V1`, zero cambiamenti altrove

---

## Priorita' 2: Aggiungere confidence reale dall'LLM

### File da modificare
- `GiAs-llm/orchestrator/router.py` — `_parse_llm_response` (riga 739), `_try_heuristics` (riga 493)
- `GiAs-llm/orchestrator/graph.py` — `_classify_node` (riga 194), `_dialogue_manager_node` (riga 298)
- `GiAs-llm/orchestrator/dialogue_manager.py` — soglie (invariate inizialmente, calibrazione dopo raccolta dati)

### Cosa cambia

**1. `_parse_llm_response` in router.py** — estrarre e validare `confidence`:

Dopo il FIXUP di `needs_clarification` (riga 773), aggiungere:
```python
# Estrai confidence se presente, clamp 0-1, default None
if "confidence" in parsed:
    try:
        conf = float(parsed["confidence"])
        parsed["confidence"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        parsed["confidence"] = None
else:
    parsed["confidence"] = None
```

**2. `_try_heuristics` in router.py** — aggiungere `"confidence": 0.99` a tutti i return:

Ogni `return {"intent": ..., "slots": ..., "needs_clarification": ...}` diventa:
```python
return {"intent": ..., "slots": ..., "needs_clarification": ..., "confidence": 0.99}
```
(Sono ~12 return statement nei pattern mantenuti: confirm/decline/greet/goodbye/help/risk_type)

**3. `_classify_node` in graph.py** — propagare confidence nello state:

Dopo riga 255 (`state["error"] = classification.get("error", "")`):
```python
state["_classification_confidence"] = classification.get("confidence")
```

**4. `_dialogue_manager_node` in graph.py** — usare confidence reale:

Sostituire righe 319-321 (confidence hardcoded) con:
```python
llm_confidence = state.get("_classification_confidence")
if llm_confidence is not None:
    confidence = llm_confidence
else:
    # Fallback: compatibilita' con vecchio comportamento
    confidence = 0.90 if not needs_clarification else 0.55
    if intent == "fallback":
        confidence = 0.30
```

**5. Logging per calibrazione** — nel `_dialogue_manager_node`, dopo la confidence:
```python
logger.info(f"[DM] Intent={intent}, confidence={confidence:.3f}, source={'llm' if llm_confidence is not None else 'heuristic'}")
```

**6. Soglie nel dialogue_manager.py** — invariate inizialmente. Dopo 200+ log raccolti, calibrare `_MODEL_CONFIDENCE_THRESHOLDS["ministral"]` in base alla distribuzione reale.

### Retrocompatibilita'
- Il campo `confidence` nel dict ritornato da `classify()` e' un'aggiunta: i consumer che non lo leggono non sono impattati
- Il fallback a confidence hardcoded garantisce che il behaviour non cambi quando l'LLM non fornisce confidence

### Test
- `test_heuristic_confidence`: verifica che tutti i risultati heuristic abbiano `confidence: 0.99`
- `test_parse_confidence_valid`: mock LLM con `confidence: 0.85`, verifica parsing e clamping
- `test_parse_confidence_missing`: mock LLM senza `confidence`, verifica `None`
- `test_parse_confidence_invalid`: mock LLM con `confidence: "alta"`, verifica fallback a `None`
- `test_dm_uses_real_confidence`: candidato con confidence 0.85, verifica DM esegue (> 0.65 soglia ministral)
- `test_dm_low_confidence_fallback`: candidato con confidence 0.25, verifica DM fa fallback

### Rischi
- **Basso**: tutto additivo, fallback preserva comportamento attuale
- **Modelli overconfident**: i 3B tendono a dare sempre 0.9+. Il logging serve proprio a capire la distribuzione reale prima di toccare le soglie

---

## Priorita' 3: Ridurre le heuristic al minimo

### Dipendenza
**RICHIEDE P1 validata con 200+ messaggi reali e P4 deployata** — l'LLM deve classificare correttamente i pattern di dominio prima di rimuovere la safety net.

### File da modificare
- `GiAs-llm/orchestrator/router.py` — `_try_heuristics`, `_SEMANTIC_CORRECTIONS`, `_post_validate`, pattern regex inutilizzati
- `GiAs-llm/tests/test_router.py` — aggiornare test che verificano bypass LLM

### Cosa cambia

**1. Slim down `_try_heuristics`** — da ~120 righe a ~35, mantiene SOLO:

| Pattern mantenuto | Perche' |
|---|---|
| `CONFIRM_EXPLICIT_PATTERNS` | Deterministico, non ambiguo |
| `DECLINE_EXPLICIT_PATTERNS` | Deterministico, non ambiguo |
| `CONFIRM_SHORT_PATTERNS` (con context) | Richiede detail_context, LLM non ha questo contesto |
| `DECLINE_SHORT_PATTERNS` (con context) | Idem |
| `RE_RISK_TYPE_MAI_CONTROLLATI/CON_SANZIONI` | Risposte a disambiguazione, non classificazione iniziale |
| `GREET_PATTERNS` (< 20 char) | Triviale, risparmia una chiamata LLM |
| `GOODBYE_PATTERNS` (< 30 char) | Triviale, risparmia una chiamata LLM |
| `HELP_PATTERNS` | Triviale |

**Pattern RIMOSSI** (18 check, righe 529-606): PROCEDURE, CHECK_PLAN_DELAYED, SINGULAR_PLAN, DELAYED, NEARBY, NEVER_CONTROLLED, TOP_RISK, PRIORITY, NC_CATEGORY, RISK, STATISTICS, ESTABLISHMENT_HISTORY, PIANO_DESCRIPTION, PIANO_STABILIMENTI, SEARCH_PIANI, catch-all piano+code.

**2. Rimuovere `_SEMANTIC_CORRECTIONS`** (righe 849-856) e il loop di correzione in `_post_validate` (righe 872-878). Con il prompt migliorato, queste correzioni non servono piu'.

**3. Rimuovere regex class variable inutilizzate** — pattern usati SOLO nelle heuristic rimosse:
```
DELAYED_PATTERNS, SINGULAR_PLAN_PATTERN, CHECK_PLAN_DELAYED_PATTERNS,
NEVER_CONTROLLED_PATTERNS, RISK_PATTERNS, TOP_RISK_PATTERNS, PRIORITY_PATTERNS,
STATISTICS_PATTERNS, PROCEDURE_PATTERNS, DI_COSA_TRATTA_PATTERN, INFO_SU_PATTERN,
SEARCH_PIANI_PATTERNS, PIANO_DESCRIPTION_PATTERNS, PIANO_STABILIMENTI_PATTERNS
```
MANTENERE (usati da `_extract_slots`): `NC_CATEGORY_PATTERNS` (riga 680), `ESTABLISHMENT_HISTORY_PATTERNS` (riga 666), `NEARBY_PATTERNS` + `RE_LOCATION` + `RE_LOCATION_ENTRO` + `RE_RADIUS` (righe 697-722), tutti i `RE_*` pattern per slot.

**4. Feature flag per rollback graduale**:
```python
MINIMAL_HEURISTICS = True  # Set False per ripristinare vecchie heuristic
```

### Aggiornamento test

I test che asseriscono `mock_llm.query.assert_not_called()` per pattern di dominio **falliranno** perche' quei messaggi ora vanno all'LLM. Aggiornare:

| Test | Da | A |
|------|-----|-----|
| `test_heuristic_delayed_plans` | assert LLM not called | mock LLM response, assert intent corretto |
| `test_heuristic_check_plan_delayed` | assert LLM not called | mock LLM, assert intent+slot |
| `test_heuristic_never_controlled` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_risk` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_top_risk_activities` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_analyze_nc_by_category` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_priority` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_piano_statistics` | assert LLM not called | mock LLM, assert intent |
| `test_heuristic_nearby_priority` | assert LLM not called | mock LLM, assert intent |

Test invariati: `test_heuristic_greet`, `test_heuristic_goodbye`, `test_heuristic_help`, `test_heuristic_confirm_with_context`, `test_heuristic_decline_with_context`, tutti i post-validation/cache/slot test.

Nuovi test:
- `test_domain_patterns_go_to_llm`: verifica che "piani in ritardo", "stabilimenti a rischio" etc. chiamino `mock_llm.query`
- `test_semantic_corrections_removed`: verifica che `_SEMANTIC_CORRECTIONS` non esista piu'

### Rischi
- **Medio**: rimuove safety net. Se il prompt (P1) ha gap, messaggi verranno misclassificati
- **Performance**: messaggi prima gestiti da heuristic (~60%) ora vanno all'LLM (+500-1500ms). Cache mitiga per query ripetute
- **Rollback**: `MINIMAL_HEURISTICS = False` ripristina il vecchio comportamento
- **Mitigazione**: monitorare tasso di fallback via log. Se > 5%, rollback e aggiungere esempi al prompt

---

## Priorita' 4: Few-shot dinamico con Qdrant

### File nuovi da creare
- `GiAs-llm/tools/indexing/build_intent_examples_index.py` — script di build della collection
- `GiAs-llm/orchestrator/few_shot_retriever.py` — retriever singleton per classificazione

### File da modificare
- `GiAs-llm/orchestrator/router.py` — `classify()` (riga 417-455), `CLASSIFICATION_SYSTEM_PROMPT`

### Cosa cambia

**1. Collection Qdrant `intent_examples`** — 100-200 vettori, 384 dim (stesso modello `paraphrase-multilingual-MiniLM-L12-v2`)

Ogni punto ha payload:
```json
{
  "text": "stabilimenti a rischio non conformità",
  "intent": "ask_risk_based_priority",
  "slots": {},
  "source": "registry|db|handcrafted"
}
```

Fonti degli esempi (~150 totali):
- ~60 da `INTENT_REGISTRY.examples` (3 per intent × 20 intent)
- ~20 da DB `intents.example_question` (espandere quelli con virgola)
- ~40 disambiguation pair hand-crafted (le 4 coppie confuse + varianti)
- ~30 variazioni linguistiche (es. "quali stabilimenti sono a rischio", "gli stabilimenti piu' pericolosi", "OSA a rischio NC")

**2. Build script** (`build_intent_examples_index.py`) — segue il pattern di `build_qdrant_index.py`:
- Carica `INTENT_REGISTRY` e tabella DB `intents`
- Aggiunge disambiguation pair hardcoded
- Crea/ricrea collection `intent_examples`
- Embedding batch + upsert
- Verifica con 5 query di test

**3. `FewShotRetriever`** (`few_shot_retriever.py`) — singleton, lazy init:
- Riusa lo stesso `qdrant_storage` path e lo stesso embedding model
- `retrieve(query, top_k=6, score_threshold=0.40)` → lista di esempi
- Diversita': max 2 esempi per intent nei risultati
- Embedding cache come `DataRetriever._embedding_cache`
- `format_for_prompt(examples)` → stringa formattata per il prompt:
```
ESEMPI SIMILI:
"stabilimenti a rischio" → ask_risk_based_priority {}
"attività più rischiose" → ask_top_risk_activities {}
```

**4. Integrazione in `Router.classify()`** — nel layer 4 (LLM), prima di costruire il prompt:
```python
# Dynamic few-shot
dynamic_examples = ""
try:
    from .few_shot_retriever import FewShotRetriever
    retriever = FewShotRetriever.get_instance()
    examples = retriever.retrieve(message, top_k=6)
    if examples:
        dynamic_examples = retriever.format_for_prompt(examples)
except Exception:
    pass  # Graceful degradation
```

Iniettare `dynamic_examples` nel user prompt PRIMA del messaggio:
```
ESEMPI SIMILI:
...
SESSIONE: ...
MESSAGGIO: "..."
SLOT PRE-ESTRATTI: ...
OUTPUT:
```

**5. Ridurre esempi statici nel system prompt** da ~20 a ~10 (i core) e aggiungere:
```
Se presenti ESEMPI SIMILI nel messaggio utente, dai loro priorita'.
```

### Retrocompatibilita'
- Se Qdrant non e' disponibile o la collection non esiste, `retrieve()` torna `[]` e il prompt funziona come prima
- Nessun cambiamento all'interfaccia di `classify()`

### Test
- `test_retriever_returns_examples`: mock Qdrant, verifica formato
- `test_retriever_diversity_limit`: verifica max 2 per intent
- `test_retriever_graceful_fallback`: verifica `[]` quando Qdrant down
- `test_classify_with_dynamic_examples`: mock retriever, verifica che gli esempi appaiano nel prompt passato a `mock_llm.query`
- `test_build_script`: esecuzione build script, verifica collection creata con count atteso
- Test manuale: confronto accuracy con/senza few-shot su 50 messaggi

### Rischi
- **Basso**: completamente additivo con graceful fallback
- **Performance**: +5-15ms per query Qdrant (trascurabile vs 500-1500ms LLM)
- **Manutenzione**: collection da ricostruire quando cambiano gli intent. Aggiungere al checklist in CLAUDE.md

---

## Riepilogo file impattati

| File | P1 | P2 | P3 | P4 |
|------|----|----|----|----|
| `orchestrator/router.py` | prompt | parse+heuristic | heuristic+cleanup | classify |
| `orchestrator/graph.py` | - | DM node | - | - |
| `orchestrator/dialogue_manager.py` | - | soglie (deferred) | - | - |
| `orchestrator/few_shot_retriever.py` | - | - | - | NUOVO |
| `tools/indexing/build_intent_examples_index.py` | - | - | - | NUOVO |
| `tests/test_router.py` | estendi | estendi | aggiorna 9 test | estendi |
| `tests/test_few_shot_retriever.py` | - | - | - | NUOVO |
| `GiAs-llm/docs/CLAUDE.md` | - | - | aggiorna architettura | aggiorna |

## Verifica end-to-end

1. **Dopo P1**: `cd GiAs-llm && python -m pytest tests/test_router.py -v` + curl con 20 messaggi reali
2. **Dopo P2**: stessi test + verificare nei log `[DM] Intent=..., confidence=0.XX, source=llm`
3. **Dopo P4**: `python tools/indexing/build_intent_examples_index.py` + test retriever + curl verifica few-shot nel prompt
4. **Dopo P3**: `python -m pytest tests/test_router.py -v` (9 test aggiornati) + curl intensivo con 50+ messaggi + monitorare fallback rate per 24-48h
