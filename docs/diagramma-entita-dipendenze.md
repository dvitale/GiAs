# Diagramma Entita e Dipendenze del Chatbot GIAS-AI

Il chatbot gestisce 21 intent che interrogano 7 dataset principali + 3 collezioni vettoriali Qdrant + tabelle di sistema. Questo documento mappa le dipendenze tra dataset per capire come i dati fluiscono attraverso i vari intent.

---

## DIAGRAMMA DELLE DIPENDENZE

```
                              ┌─────────────┐
                              │   ACCESSO    │
                              │  (Frontend)  │
                              └──────┬───────┘
                                     │ user_id
                                     ▼
                          ┌──────────────────────┐
                          │     PERSONALE         │
                          │  (~24.7K righe)       │
                          └──┬───────────┬────────┘
                             │           │
                    asl/uoc/uos    codice_fiscale
                             │           │
              ┌──────────────┼───────────┼──────────────────┐
              │              │           │                   │
              ▼              ▼           ▼                   ▼
   ┌─────────────────┐  ┌────────────────────┐  ┌──────────────────────┐
   │  CU_ESEGUITI    │  │ OSA_MAI_CONTROLLATI│  │CU_DIFF_PROGRAMMATI   │
   │  (~355K righe)  │  │  (~119K righe)     │  │   _ESEGUITI (~60K)   │
   └──┬──────┬───┬───┘  └──┬─────────┬──────┘  └──┬───────────────────┘
      │      │   │          │         │             │
      │      │   │          │         │             │ indicatore
      │      │   │          │         │             │ descrizione_indicatore
      │      │   │          │         │             ▼
      │      │   │          │         │    ┌──────────────────────┐
      │      │   │          │         │    │  PIANI_MONITORAGGIO  │
      │      │   │          │         │    │   (~3.650 righe)     │
      │      │   │          │         │    └──────────────────────┘
      │      │   │          │         │             ▲
      │      │   │          │         │             │ alias_indicatore
      │      │   │          │         │             │ (prefix match)
      │      │   └──────────┼─────────┼─────────────┘
      │      │  descrizione │         │  descrizione_indicatore
      │      │  _indicatore │         │
      │      │              │         │
      │      │  macroarea   │macroarea│
      │      │  _cu         │         │
      │      ▼              ▼         │
      │   ┌──────────────────────┐    │
      │   │    MASTERLIST        │    │
      │   │   (~2.2K righe)      │    │
      │   └──────────────────────┘    │
      │              ▲                │
      │              │ macroarea      │
      │              │ _sottoposta    │
      │              │ _a_controllo   │
      │   ┌──────────┴───────────┐    │
      │   │   OCSE_ISP_SEMP      │    │
      │   │  (NC storiche 2016-  │    │
      │   │   2025, ~807K righe) │    │
      │   └──────────────────────┘    │
      │                               │
      │   latitudine/longitudine      │ latitudine/longitudine
      ▼              ▼                ▼
   ┌─────────────────────────────────────┐
   │        PROXIMITY (GPS device)       │
   │     haversine distance filter       │
   │     (dati mai persistiti - GDPR)    │
   └─────────────────────────────────────┘


=== RISORSE VETTORIALI (Qdrant) ===

   ┌─────────────────────────────┐
   │  Qdrant: piani_monitoraggio │◄── semantic search per search_piani_by_topic
   │  730 vettori, 384-dim       │
   └─────────────────────────────┘

   ┌─────────────────────────────┐
   │  Qdrant: intent_examples    │◄── few-shot classification per Router
   │  ~150 vettori, 384-dim      │
   └─────────────────────────────┘

   ┌─────────────────────────────┐
   │  Qdrant: procedure_documents│◄── RAG per info_procedure
   │  ~500+ vettori, 384-dim     │    (NO filtro ASL - docs pubblici)
   └─────────────────────────────┘


=== TABELLE DI SISTEMA ===

   ┌─────────────────────────────┐
   │  chat_log (logging)         │◄── analytics, monitor, history
   │  + 23 viste analitiche      │
   └─────────────────────────────┘

   ┌─────────────────────────────┐
   │  intents (21 records)       │◄── metadata intent, help_tool
   │  intent_examples (FK)       │    classificazione
   │  domande_risposte           │    RAG admin
   └─────────────────────────────┘

   ┌─────────────────────────────┐
   │  schema_metadata (7 records)│◄── Schema-Aware LLM, query_data
   └─────────────────────────────┘
```

---

## DIPENDENZE PER INTENT

```
INTENT                        DATASET COINVOLTI                              CHIAVI DI JOIN
─────────────────────────────────────────────────────────────────────────────────────────────
greet/goodbye/ask_help        (nessun dataset)                               —
                              intents (solo help)

ask_piano_description         piani_monitoraggio                             alias, alias_indicatore
                              cu_eseguiti                                    descrizione_indicatore → alias_indicatore (prefix)

ask_piano_stabilimenti        piani_monitoraggio                             alias, alias_indicatore
                              cu_eseguiti                                    descrizione_indicatore → alias_indicatore (prefix)
                                                                            macroarea_cu, aggregazione_cu, attivita_cu

ask_piano_statistics          cu_eseguiti                                    descrizione_piano, descrizione_asl
                              (aggregazione per piano)

search_piani_by_topic         Qdrant:piani_monitoraggio (vector)             semantic similarity
                              piani_monitoraggio (fallback ILIKE)            descrizione, descrizione-2, sezione

ask_priority_establishment    cu_diff_programmati_eseguiti                   indicatore → alias_indicatore
                              osa_mai_controllati                            macroarea, aggregazione, attivita
                              (filtro: asl, uoc, uos)

ask_delayed_plans             cu_diff_programmati_eseguiti                   indicatore, descrizione_asl, descrizione_uoc
check_if_plan_delayed         cu_diff_programmati_eseguiti                   indicatore (specifico piano)

ask_risk_based_priority       ocse_isp_semp                                 macroarea_sottoposta_a_controllo
                              osa_mai_controllati                            macroarea, aggregazione, attivita
                              cu_eseguiti (contesto)                         macroarea_cu

ask_suggest_controls          osa_mai_controllati                            asl, macroarea, aggregazione
                              masterlist                                     macroarea, aggregazione, attivita

ask_nearby_priority           osa_mai_controllati                            latitudine_stab, longitudine_stab
                              GPS device (haversine)                         device_lat, device_lon
                              (filtro: asl, raggio km)

ask_establishment_history     cu_eseguiti                                    num_registrazione, approval_number,
                              ocse_isp_semp                                  partita_iva, ragione_sociale

ask_top_risk_activities       ocse_isp_semp                                 macroarea_sottoposta_a_controllo
                                                                            numero_nc_gravi, numero_nc_non_gravi

analyze_nc_by_category        ocse_isp_semp                                 tipo_non_conformita, oggetto_non_conformita
                              cu_eseguiti                                    macroarea_cu

info_procedure                Qdrant:procedure_documents                    vector search + BM25
                              (NO filtro ASL)

query_data                    TUTTI i 7 dataset (whitelist)                  dinamico via LLM → QueryDescriptor
                              schema_metadata                                catalogo colonne
```

---

## DETTAGLIO CAMPI PER DATASET

### 1. PERSONALE (~24.677 righe)

| Campo | Uso | Critico |
|-------|-----|---------|
| `user_id` | Autenticazione, lookup | **Obbligatorio per accesso** |
| `asl` / `descrizione_asl` | Filtro dati per ASL utente | **Obbligatorio per accesso** |
| `descrizione_uoc` | Filtro unita operativa | Opzionale, auto-risolto da user_id |
| `descrizione_uos` | Filtro unita semplice | **Filtro chiave per diversi intent (piani in ritardo, priorita, controlli)** |
| `namefirst`, `namelast` | Identificazione | **PII - blacklist query_data** |
| `codice_fiscale` | Identificazione fiscale | **PII - blacklist query_data** |

**Aspetti critici:**
- Il campo `user_id` e un intero (Atoi in Go), non una stringa
- UOC si risolve da `DescrizioneAreaStrutturaComplessa` con fallback a segmento di `Descrizione[1]`
- Senza `user_id` + `asl` il chatbot restituisce HTTP 403
- I campi PII (namefirst, namelast, codice_fiscale) sono nella blacklist di SafeQueryExecutor

---

### 2. PIANI_MONITORAGGIO (~3.650 righe)

| Campo | Uso | Critico |
|-------|-----|---------|
| `alias` | Codice piano (A1, B2, C3) | Chiave primaria logica |
| `alias_indicatore` | Codice indicatore (A1_A, B2_B) | **Join con cu_eseguiti via prefix match** |
| `sezione` | Sezione PRISCAV (A-G) | Filtro per search_piani_by_topic |
| `descrizione` | Descrizione piano | Testo ricerca semantica |
| `descrizione-2` | Descrizione aggiuntiva | **Colonna con trattino! Richiede quoting** |
| `campionamento` | Flag campionamento | Filtro strutturale |
| `rendicontazione_per_campione` | Tipo rendicontazione | Determina se campionamento |

**Aspetti critici:**
- La colonna `descrizione-2` ha un trattino nel nome → richiede quoting speciale in SQL/pandas
- Il join con `cu_eseguiti` e per **prefix match** (A1 matcha A1_A, A1_B, etc.), non per uguaglianza esatta
- Fallback "ATT " prefix per `alias_indicatore` (es. AO5_A → ATT AO5_A)
- Dati vettorizzati anche in Qdrant per ricerca semantica

---

### 3. CU_ESEGUITI (~355.448 righe) - **Dataset piu grande**

| Campo | Uso | Critico |
|-------|-----|---------|
| `descrizione_indicatore` | Codice piano/indicatore | **Join verso piani (prefix match)** |
| `macroarea_cu` | Macro-area attivita | **Join verso masterlist.macroarea** |
| `aggregazione_cu` | Aggregazione attivita | Join verso masterlist |
| `attivita_cu` | Linea attivita | Join verso masterlist |
| `descrizione_asl` | ASL del controllo | **Filtro per ASL utente** |
| `descrizione_uoc` | Unita operativa | Filtro opzionale |
| `data_inizio_controllo` | Data controllo | **Alias "anno" in query_data** |
| `num_registrazione` | Numero registrazione OSA | **PII, usato per storico stabilimento** |
| `approval_number` | Numero riconoscimento | **Alias "stabilimento" in query_data** |
| `partita_iva` | Partita IVA | **PII** |
| `ragione_sociale` | Ragione sociale | **PII** |
| `latitudine_stab` / `longitudine_stab` | Coordinate | Per proximity search |
| `descrizione_piano` | Nome piano | Aggregazione statistiche |
| `sezione` | Sezione PRISCAV | Filtro |

**Aspetti critici:**
- **355K righe**: dataset piu grande, ma gestibile in-memory
- Il campo `anno` non esiste: viene mappato a `data_inizio_controllo` con conversione date range
- Il campo `asl` non esiste: viene mappato a `descrizione_asl`
- 5 campi PII nella blacklist: partita_iva, ragione_sociale, num_registrazione, codice_fiscale, nominativo_rappresentante
- Il join con piani e per prefix match, non FK classica

---

### 4. OSA_MAI_CONTROLLATI (~118.729 righe)

| Campo | Uso | Critico |
|-------|-----|---------|
| `asl` | ASL di competenza | **Filtro per ASL utente** |
| `macroarea` | Macro-area attivita | **Join verso masterlist** |
| `aggregazione` | Aggregazione attivita | Join verso masterlist |
| `attivita` | Linea attivita | Join verso masterlist |
| `comune` | Comune stabilimento | Filtro geografico |
| `indirizzo` | Indirizzo | Visualizzazione |
| `latitudine_stab` / `longitudine_stab` | Coordinate GPS | **Proximity search (haversine)** |
| `num_riconoscimento` | Numero riconoscimento | **PII** |
| `codice_fiscale` | CF rappresentante | **PII** |
| `partita_iva` | Partita IVA | **PII** |
| `codice_fiscale_rappresentante` | CF rappresentante legale | **PII** |
| `nominativo_rappresentante` | Nome rappresentante | **PII** |
| `data_inizio_attivita` / `data_fine_attivita` | Periodo attivita | |

**Aspetti critici:**
- 5 campi PII nella blacklist
- Le coordinate sono fondamentali per `ask_nearby_priority` (haversine distance)
- La validazione GPS Campania: 39.9 <= lat <= 41.5, 13.7 <= lon <= 15.8
- Join verso masterlist per text match (non FK), possibili disallineamenti nomenclatura

---

### 5. OCSE_ISP_SEMP (~807.290 righe, NC storiche 2016-2025)

| Campo | Uso | Critico |
|-------|-----|---------|
| `macroarea_sottoposta_a_controllo` | Macro-area NC | **Join verso masterlist (nome diverso!)** |
| `aggregazione_sottoposta_a_controllo` | Aggregazione NC | |
| `linea_attivita_sottoposta_a_controllo` | Linea attivita NC | |
| `numero_nc_gravi` | Conteggio NC gravi | **Formula rischio: P(NC) x Impact** |
| `numero_nc_non_gravi` | Conteggio NC non gravi | Formula rischio |
| `anno_controllo` | Anno (2016-2025) | **Alias "anno" in query_data** |
| `numero_registrazione` | Numero registrazione | Per storico stabilimento |
| `numero_riconoscimento` | Numero riconoscimento | Per storico stabilimento |
| `asl` | ASL | Filtro |
| `tipo_non_conformita` | Tipo NC | Per analyze_nc_by_category |
| `oggetto_non_conformita` | Oggetto NC | Per analyze_nc_by_category |
| `comune` | Comune | Contesto geografico |

**Aspetti critici:**
- **Nomi colonne diversi da altri dataset!** `macroarea_sottoposta_a_controllo` vs `macroarea_cu` vs `macroarea`
- La formula rischio: Risk = P(NC) x Impact x 100, dove P(NC) = (gravi + non_gravi) / count, Impact = gravi / count
- Dati storici multi-anno (2016-2025): attenzione alla granularita temporale
- Join verso masterlist usa `macroarea_sottoposta_a_controllo` → `macroarea` (text match)

---

### 6. CU_DIFF_PROGRAMMATI_ESEGUITI (~59.799 righe)

| Campo | Uso | Critico |
|-------|-----|---------|
| `indicatore` | Codice piano/indicatore | **Join verso piani.alias_indicatore** |
| `descrizione_indicatore` | Descrizione piano | Visualizzazione |
| `programmati` | Controlli programmati | **Calcolo ritardo: programmati - eseguiti** |
| `eseguiti` | Controlli eseguiti | Calcolo ritardo |
| `anno` | Anno programmazione | Filtro temporale |
| `descrizione_asl` | ASL | Filtro per ASL utente |
| `descrizione_uoc` | Unita operativa | Filtro per UOC utente |
| `descrizione_uos` | Unita semplice | **Filtro primario per utente: individua piani in ritardo e stabilimenti prioritari** |

**Aspetti critici:**
- Il ritardo si calcola come `programmati - eseguiti > 0`
- Il campo `indicatore` matcha `piani.alias_indicatore` (stesso valore, non prefix)
- **`descrizione_uos` e il campo chiave per personalizzare i risultati**: filtra i piani in ritardo e gli stabilimenti prioritari per l'utente collegato (risolto da personale via user_id)
- Per `ask_priority_establishment`: i piani in ritardo (filtrati per UOS) vengono poi incrociati con `osa_mai_controllati` per trovare stabilimenti da controllare

---

### 7. MASTERLIST (~2.152 righe)

| Campo | Uso | Critico |
|-------|-----|---------|
| `norma` | Regolamento (Reg. CE 852, 853) | Classificazione normativa |
| `macroarea` | Macro-area | **Chiave di join principale** |
| `aggregazione` | Aggregazione attivita | Chiave di join |
| `linea_di_attivita` | Linea attivita | **Colonna con spazi nel nome!** |
| `registrati` | N. stabilimenti registrati | Contesto |
| `riconosciuti` | N. stabilimenti riconosciuti | Contesto |

**Aspetti critici:**
- **Hub di join centrale**: collegata a cu_eseguiti, osa_mai_controllati e ocse_isp_semp
- `linea_di_attivita` ha spazi nel nome colonna
- I nomi delle macroaree nei 3 dataset collegati sono **leggermente diversi**: `macroarea_cu`, `macroarea`, `macroarea_sottoposta_a_controllo` — tutti matchano per testo
- Possibili disallineamenti di nomenclatura tra i dataset (text match, non FK)

---

## ASPETTI CRITICI TRASVERSALI

### 1. Join per text match (non FK formali)
Nessun dataset ha foreign key SQL formali. Tutti i join sono per **text match** su stringhe, il che rende possibili disallineamenti (spazi, maiuscole, accenti).

### 2. Prefix match per piani
Il collegamento `cu_eseguiti.descrizione_indicatore` → `piani.alias_indicatore` e per **prefix** (startswith), non per uguaglianza. Con fallback "ATT " prefix.

### 3. Nomi colonne incoerenti tra dataset
- Macroarea: `macroarea` / `macroarea_cu` / `macroarea_sottoposta_a_controllo`
- Anno: `anno` / `anno_controllo` / `data_inizio_controllo` (timestamp)
- ASL: `asl` / `descrizione_asl` / `id_asl`
- Stabilimento: `num_registrazione` / `numero_registrazione` / `n_reg`

### 4. PII e GDPR
- 14 campi PII totali distribuiti su 3 dataset (controlli, mai_controllati, personale)
- SafeQueryExecutor blocca query su colonne PII
- Coordinate GPS mai persistite nei log

### 5. Volume dati
- cu_eseguiti (355K) e ocse_isp_semp (807K) sono i dataset piu grandi
- Tutte le operazioni sono in-memory su pandas DataFrame
- Limit max 100 righe per output query_data

### 6. Dataset procedure (Qdrant)
- `procedure_documents`: unico dataset senza filtro ASL (documenti pubblici)
- RAG con parent-child chunking, BM25 + vector search
