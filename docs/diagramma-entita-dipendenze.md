# Diagramma Entita e Dipendenze del Chatbot GIAS-AI

Il chatbot gestisce 20 intent (registry DB-driven via tabella intents + IntentMetadataService) che interrogano 6 dataset principali in PostgreSQL + 3 collezioni vettoriali Qdrant + tabelle di sistema. Questo documento mappa le dipendenze tra dataset per capire come i dati fluiscono attraverso i vari intent.

> **Nota schema**: lo schema PostgreSQL e' stato normalizzato — le tabelle in public usano nomi colonna canonici (alias\_piano\_attivita, descrizione\_piano\_attivita, alias\_indicatore, descrizione\_indicatore, tipo\_piano\_attivita, campionamento). Le tabelle originali sono archiviate in schema old. Le NC storiche sono ora **inline** in cu\_eseguiti\_nc (la vecchia tabella ocse\_isp\_semp e' stata rimossa).


## DIAGRAMMA DELLE DIPENDENZE


```
                              ┌──────────────┐  
                              │   ACCESSO    │  
                              │  (Frontend)  │  
                              └──────┬───────┘  
                                     │ user\_id  
                                     ▼  
                          ┌───────────────────────┐  
                          │     PERSONALE         │  
                          │  (~24.7K righe)       │  
                          └──┬───────────┬────────┘  
                             │           │  
                    asl/uoc/uos    codice\_fiscale  
                             │           │  
              ┌──────────────┼───────────┼───────────────────┐  
              │              │           │                   │  
              ▼              ▼           ▼                   ▼  
   ┌─────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  
   │  CU\_ESEGUITI\_NC │  │ OSA\_MAI\_CONTROLLATI│  │CU\_DIFF\_PROGRAMMATI   │  
   │  (~400K righe)  │  │  (~119K righe)     │  │   \_ESEGUITI (~60K)   │  
   │  controlli + NC │  └──┬─────────┬───────┘  └──┬───────────────────┘  
   │      inline     │     │         │             │  
   └──┬──────┬───┬───┘     │         │             │ alias\_piano\_attivita  
      │      │   │         │         │             │ alias\_indicatore  
      │      │   │         │         │             ▼  
      │      │   │         │         │    ┌──────────────────────┐  
      │      │   │         │         │    │  PIANI\_MONITORAGGIO  │  
      │      │   │         │         │    │   (~3.650 righe)     │  
      │      │   │         │         │    └──────────────────────┘  
      │      │   │         │         │             ▲  
      │      │   │         │         │             │ alias\_indicatore  
      │      │   │         │         │             │ (prefix match)  
      │      │   └─────────┼─────────┼─────────────┘  
      │      │ descrizione │         │ descrizione\_indicatore  
      │      │  \_indicatore│         │  
      │      │             │         │  
      │      │  macroarea  │macroarea│  
      │      │  \_cu        │         │  
      │      ▼             ▼         │  
      │   ┌──────────────────────┐   │  
      │   │    MASTERLIST        │   │  
      │   │   (~2.2K righe)      │   │  
      │   └──────────────────────┘   │  
      │                              │  
      │   latitudine/longitudine     │ latitudine/longitudine  
      ▼              ▼               ▼  
   ┌─────────────────────────────────────┐  
   │        PROXIMITY (GPS device)       │  
   │     haversine distance filter       │  
   │     (dati mai persistiti - GDPR)    │  
   └─────────────────────────────────────┘  
  
  
=== RISORSE VETTORIALI (Qdrant) ===  
  
   ┌─────────────────────────────┐  
   │  Qdrant: piani\_monitoraggio │◄── semantic search per search\_piani\_by\_topic  
   │  730 vettori, 384-dim       │  
   └─────────────────────────────┘  
  
   ┌─────────────────────────────┐  
   │  Qdrant: intent\_examples    │◄── few-shot classification per Router  
   │  ~150 vettori, 384-dim      │  
   └─────────────────────────────┘  
  
   ┌─────────────────────────────┐  
   │  Qdrant: procedure\_documents│◄── RAG per info\_procedure  
   │  ~500+ vettori, 384-dim     │    (NO filtro ASL - docs pubblici)  
   └─────────────────────────────┘  
  
  
=== TABELLE DI SISTEMA ===  
  
   ┌─────────────────────────────┐  
   │  chat\_log (logging)         │◄── analytics, monitor, history  
   │  + 23 viste analitiche      │  
   └─────────────────────────────┘  
  
   ┌─────────────────────────────┐  
   │  intents (20 records)       │◄── IntentMetadataService (DB-first):  
   │  intent\_examples (FK)       │    VALID\_INTENTS, REQUIRED\_SLOTS,  
   │  domande\_risposte           │    INTENT\_TO\_TOOL, soglie two-phase,  
   │                             │    self\_sufficient, keywords, ...  
   └─────────────────────────────┘  
  
   ┌─────────────────────────────┐  
   │  schema\_metadata (6 records)│◄── Schema-Aware LLM, query\_data  
   └─────────────────────────────┘
```


## DIPENDENZE PER INTENT

Il registry e' DB-driven (tabella intents); il fallback Python in router.py definisce 20 intent.

```
INTENT                        DATASET COINVOLTI                              CHIAVI DI JOIN  
─────────────────────────────────────────────────────────────────────────────────────────────  
greet/goodbye/ask\_help        (nessun dataset)                               —  
                              intents (solo help)  
  
confirm\_show\_details          (nessun dataset — gestisce conferma/rifiuto    —  
decline\_show\_details          two-phase nel dialogue manager)  
fallback                      (nessun dataset — recovery / clarify)  
  
ask\_piano\_description         piani\_monitoraggio                             alias\_piano\_attivita, alias\_indicatore  
                              cu\_eseguiti\_nc                                 descrizione\_indicatore → alias\_indicatore (prefix)  
  
ask\_piano\_stabilimenti        piani\_monitoraggio                             alias\_piano\_attivita, alias\_indicatore  
                              cu\_eseguiti\_nc                                 descrizione\_indicatore → alias\_indicatore (prefix)  
                                                                            macroarea\_cu, aggregazione\_cu, attivita\_cu  
  
ask\_piano\_statistics          cu\_eseguiti\_nc                                 descrizione\_piano, descrizione\_asl  
                              (aggregazione per piano)  
  
search\_piani\_by\_topic         Qdrant:piani\_monitoraggio (vector)             semantic similarity  
                              piani\_monitoraggio (fallback ILIKE)            descrizione\_piano\_attivita, sezione  
  
ask\_priority\_establishment    cu\_diff\_programmati\_eseguiti                   alias\_indicatore  
                              osa\_mai\_controllati                            macroarea, aggregazione, attivita  
                              (filtro: asl, uoc, uos)  
  
ask\_delayed\_plans             cu\_diff\_programmati\_eseguiti                   alias\_indicatore, descrizione\_asl, descrizione\_uoc  
check\_if\_plan\_delayed         cu\_diff\_programmati\_eseguiti                   alias\_piano\_attivita / alias\_indicatore (specifico piano)  
                              + sub-flow "controlli programmati":  
                                SUM(programmati/eseguiti) per  
                                alias\_piano\_attivita + ASL + UOS  
  
ask\_risk\_based\_priority       cu\_eseguiti\_nc (NC inline)                     macroarea\_cu, aggregazione\_cu, attivita\_cu  
                              osa\_mai\_controllati                            macroarea, aggregazione, attivita  
                              MLRiskPredictor (XGBoost)                      per stabilimento (strategia "ml")  
  
ask\_suggest\_controls          osa\_mai\_controllati                            asl, macroarea, aggregazione  
                              masterlist                                     macroarea, aggregazione, attivita  
  
ask\_nearby\_priority           osa\_mai\_controllati                            latitudine\_stab, longitudine\_stab  
                              GPS device (haversine)                         device\_lat, device\_lon  
                              (filtro: asl, raggio km)  
  
ask\_establishment\_history     cu\_eseguiti\_nc                                 num\_registrazione, approval\_number,  
                                                                            partita\_iva, ragione\_sociale  
  
ask\_top\_risk\_activities       cu\_eseguiti\_nc (NC inline,                     macroarea\_cu / aggregazione\_cu  
                              via risk\_score\_view)                           numero\_nc\_gravi, numero\_nc\_non\_gravi  
  
info\_procedure                Qdrant:procedure\_documents                    vector search + BM25  
                              (NO filtro ASL)  
  
query\_data                    TUTTI i 6 dataset (whitelist)                  dinamico via LLM → QueryDescriptor  
                              schema\_metadata                                catalogo colonne
```

## DETTAGLIO CAMPI PER DATASET

### 1. PERSONALE (~24.677 righe)

| Campo | Uso | Critico |
| - | - | - |
| user\_id | Autenticazione, lookup | **Obbligatorio per accesso** |
| asl / descrizione\_asl | Filtro dati per ASL utente | **Obbligatorio per accesso** |
| descrizione\_uoc | Filtro unita operativa | Opzionale, auto-risolto da user\_id |
| descrizione\_uos | Filtro unita semplice | **Filtro chiave per piani in ritardo, priorita, controlli** |
| namefirst, namelast | Identificazione | **PII - blacklist query\_data** |
| codice\_fiscale | Identificazione fiscale | **PII - blacklist query\_data** |


**Aspetti critici:**

- Il campo user\_id e un intero (Atoi in Go), non una stringa

- UOC si risolve da DescrizioneAreaStrutturaComplessa con fallback a segmento di Descrizione\[1\]

- Senza user\_id + asl il chatbot restituisce HTTP 403

- I campi PII (namefirst, namelast, codice\_fiscale) sono nella blacklist di SafeQueryExecutor


### 2. PIANI\_MONITORAGGIO (~3.650 righe) — schema normalizzato

| Campo (canonico) | Uso | Critico |
| - | - | - |
| alias\_piano\_attivita | Codice piano (A1, B2, C3) | Chiave primaria logica del piano |
| descrizione\_piano\_attivita | Descrizione piano | Testo per ricerca semantica |
| alias\_indicatore | Codice indicatore (A1\_A, B2\_B) | **Join con cu\_eseguiti\_nc via prefix match** |
| descrizione\_indicatore | Descrizione indicatore | Testo |
| tipo\_piano\_attivita | Tipo (Piano / Attivita) | **Discrimina entita: usato per warning di mismatch** |
| sezione | Sezione PRISCAV (A-G) | Filtro per search\_piani\_by\_topic |
| campionamento | Flag campionamento | Filtro strutturale |
| anno | Anno di programmazione | Filtro temporale |


**Aspetti critici:**

- Le colonne sono **canoniche dopo normalizzazione**: i vecchi nomi (alias, descrizione, descrizione-2) sono solo nello schema old

- Il join con cu\_eseguiti\_nc e per **prefix match** su alias\_indicatore (A1 matcha A1\_A, A1\_B, etc.), con fallback "ATT " (es. AO5\_A → ATT AO5\_A)

- L'aggregazione "piano" usa alias\_piano\_attivita (A14 aggrega A14\_A, A14\_B...), distinta dal singolo alias\_indicatore

- Dati vettorizzati anche in Qdrant per ricerca semantica


### 3. CU\_ESEGUITI\_NC (~400.000 righe stimato) — **Dataset piu grande, NC inline**

Sostituisce sia il vecchio cu\_eseguiti sia ocse\_isp\_semp: contiene i controlli ufficiali eseguiti **arricchiti** con le non conformita rilevate (NC inline) e con campionamento / tipo provenienti da piani\_monitoraggio.

| Campo | Uso | Critico |
| - | - | - |
| descrizione\_indicatore | Codice piano/indicatore | **Join verso piani (prefix match)** |
| descrizione\_piano | Nome piano | Aggregazione statistiche (NB: qui ancora non descrizione\_piano\_attivita) |
| macroarea\_cu | Macro-area attivita | **Join verso masterlist.macroarea** |
| aggregazione\_cu | Aggregazione attivita | Join verso masterlist |
| attivita\_cu | Linea attivita | Join verso masterlist |
| descrizione\_asl | ASL del controllo | **Filtro per ASL utente** |
| descrizione\_uoc / descrizione\_uos | Unita operative | Filtro UOC/UOS |
| data\_inizio\_controllo | Data controllo | **Alias "anno" in query\_data** |
| numero\_nc\_gravi, numero\_nc\_non\_gravi | NC inline | **Formula rischio: P(NC) x Impact** |
| tipo\_non\_conformita, oggetto\_non\_conformita | Dettaglio NC | Per analisi NC ad-hoc |
| num\_registrazione | Numero registrazione OSA | **PII** |
| approval\_number | Numero riconoscimento | **Alias "stabilimento" in query\_data** |
| partita\_iva / ragione\_sociale | Identificativi OSA | **PII** |
| latitudine\_stab / longitudine\_stab | Coordinate | Per proximity search |
| sezione | Sezione PRISCAV | Filtro |
| campionamento, tipo | Da join con piani | Arricchimento |


**Aspetti critici:**

- Dataset piu grande, gestito in-memory su pandas DataFrame (controlli\_df)

- Il campo anno non esiste: viene mappato a data\_inizio\_controllo con conversione date range

- Il campo asl non esiste: viene mappato a descrizione\_asl

- 5 campi PII nella blacklist: partita\_iva, ragione\_sociale, num\_registrazione, codice\_fiscale, nominativo\_rappresentante

- Le NC storiche (2016-2025) sono **inline** qui: risk\_score\_view e tutta la logica rischio leggono direttamente da cu\_eseguiti\_nc

- Il join con piani e per prefix match, non FK classica


### 4. OSA\_MAI\_CONTROLLATI (~118.729 righe)

Sincronizzata da mdgm (chatbot.osa\_mai\_controllati) tramite scripts/sync\_osa\_mai\_controllati.py.

| Campo | Uso | Critico |
| - | - | - |
| asl | ASL di competenza | **Filtro per ASL utente** |
| macroarea | Macro-area attivita | **Join verso masterlist** |
| aggregazione | Aggregazione attivita | Join verso masterlist |
| attivita | Linea attivita | Join verso masterlist |
| comune | Comune stabilimento | Filtro geografico |
| indirizzo | Indirizzo | Visualizzazione |
| latitudine\_stab / longitudine\_stab | Coordinate GPS | **Proximity search (haversine)** |
| ragione\_sociale | Ragione sociale OSA | **Identificativo primario nelle risposte** di ask\_priority/ask\_risk |
| num\_riconoscimento | Numero riconoscimento | **PII** |
| codice\_fiscale / partita\_iva | Identificativi fiscali | **PII** |
| codice\_fiscale\_rappresentante / nominativo\_rappresentante | Rappresentante legale | **PII** |
| data\_inizio\_attivita / data\_fine\_attivita | Periodo attivita |  |


**Aspetti critici:**

- 5 campi PII nella blacklist

- Le coordinate sono fondamentali per ask\_nearby\_priority (haversine distance)

- Validazione GPS Campania: 39.9 \<= lat \<= 41.5, 13.7 \<= lon \<= 15.8

- Whitelist KEEP\_COLUMNS in data\_sources/base.py per caricamento selettivo

- Join verso masterlist per text match (non FK), possibili disallineamenti nomenclatura


### 5. CU\_DIFF\_PROGRAMMATI\_ESEGUITI (~59.799 righe)

| Campo | Uso | Critico |
| - | - | - |
| alias\_piano\_attivita | Codice piano (aggregato) | **Aggregazione SUM per piano (controlli programmati)** |
| alias\_indicatore | Codice indicatore | **Join verso piani.alias\_indicatore (specifico)** |
| descrizione\_indicatore | Descrizione indicatore | Visualizzazione |
| programmati | Controlli programmati | **Calcolo ritardo: programmati - eseguiti** |
| eseguiti | Controlli eseguiti | Calcolo ritardo |
| anno | Anno programmazione | Filtro temporale (con warning su mismatch anno richiesto) |
| descrizione\_asl | ASL | Filtro per ASL utente |
| descrizione\_uoc | Unita operativa | Filtro per UOC utente |
| descrizione\_uos | Unita semplice | **Filtro primario per personalizzare i risultati per utente** |


**Aspetti critici:**

- Due livelli di identificatore: alias\_piano\_attivita per aggregazione SUM (es. A14 aggrega A14\_A, A14\_B), alias\_indicatore per il singolo indicatore

- Il ritardo si calcola come programmati - eseguiti \> 0

- descrizione\_uos e il campo chiave per personalizzare i risultati: filtra piani in ritardo e stabilimenti prioritari per l'utente collegato (risolto da personale via user\_id)

- Sub-flow "controlli programmati": query del tipo controlli programmati per il piano A14 vengono routate (regex \\bprogramm(?:at\[oiae\]|azione)\\b) verso get\_programmed\_controls\_summary, che fa SUM su programmati/eseguiti per alias\_piano\_attivita + ASL + UOS senza richiedere UOC


### 6. MASTERLIST (~2.152 righe)

| Campo | Uso | Critico |
| - | - | - |
| norma | Regolamento (Reg. CE 852, 853) | Classificazione normativa |
| macroarea | Macro-area | **Chiave di join principale** |
| aggregazione | Aggregazione attivita | Chiave di join |
| linea\_di\_attivita | Linea attivita | **Colonna con spazi nel nome!** |
| registrati | N. stabilimenti registrati | Contesto |
| riconosciuti | N. stabilimenti riconosciuti | Contesto |


**Aspetti critici:**

- **Hub di join centrale**: collegata a cu\_eseguiti\_nc e osa\_mai\_controllati

- linea\_di\_attivita ha spazi nel nome colonna

- I nomi delle macroaree nei dataset collegati sono leggermente diversi: macroarea\_cu (cu\_eseguiti\_nc) vs macroarea (osa\_mai\_controllati e masterlist) — match per testo

- Possibili disallineamenti di nomenclatura (text match, non FK)


## ASPETTI CRITICI TRASVERSALI

### 1. Join per text match (non FK formali)

Nessun dataset ha foreign key SQL formali. Tutti i join sono per **text match** su stringhe, il che rende possibili disallineamenti (spazi, maiuscole, accenti). Il fix di whitespace normalization e' applicato in fase di aggregazione per evitare duplicati.

### 2. Prefix match per piani

Il collegamento cu\_eseguiti\_nc.descrizione\_indicatore → piani.alias\_indicatore e per **prefix** (startswith), non per uguaglianza. Con fallback "ATT " prefix.

### 3. Due livelli di identificatore piano

- alias\_piano\_attivita → aggregazione di piano (A14 = A14\_A + A14\_B + ...)

- alias\_indicatore → singolo indicatore La distinzione e cruciale per le query "controlli programmati per il piano A14" (somma) vs "indicatore A14\_A" (singolo).

### 4. Nomi colonne incoerenti tra dataset

- Macroarea: macroarea (osa\_mai, masterlist) / macroarea\_cu (cu\_eseguiti\_nc)

- Anno: anno / data\_inizio\_controllo (timestamp in cu\_eseguiti\_nc)

- ASL: asl (osa\_mai) / descrizione\_asl (cu\_eseguiti\_nc, diff\_prog\_eseg) / id\_asl

- Stabilimento: num\_registrazione / numero\_riconoscimento / n\_reg

- Piano: alias\_piano\_attivita / descrizione\_piano\_attivita (piani) vs descrizione\_piano (cu\_eseguiti\_nc)

### 5. PII e GDPR

- PII distribuiti su cu\_eseguiti\_nc, osa\_mai\_controllati, personale

- SafeQueryExecutor blocca query su colonne PII

- Coordinate GPS device mai persistite nei log (intent ask\_nearby\_priority)

### 6. Volume dati

- cu\_eseguiti\_nc (~~400K) e osa\_mai\_controllati (~~119K) sono i dataset piu grandi

- Tutte le operazioni sono in-memory su pandas DataFrame

- Limit max 100 righe per output query\_data

### 7. Schema normalizzato (refactor)

- Le tabelle in public usano nomi colonna canonici

- Le tabelle originali sono archiviate in schema old

- Le NC storiche (2016-2025) sono **inline** in cu\_eseguiti\_nc — la vecchia ocse\_isp\_semp e' stata rimossa

- Definizione viste: sql/create\_normalized\_views.sql

- Vista rischio: sql/risk\_score\_view.sql (legge da cu\_eseguiti\_nc)

### 8. Intent registry DB-driven

- Tabella intents (20 record) e' la **singola fonte di verita** per i metadati intent

- IntentMetadataService (singleton DB-first) espone: VALID\_INTENTS, REQUIRED\_SLOTS, INTENT\_TO\_TOOL, soglie two-phase, self\_sufficient, is\_direct\_response, followup\_excluded, keywords

- Ogni modulo Python ha un fallback hardcoded per il boot senza DB

### 9. Dataset procedure (Qdrant)

- procedure\_documents: unico dataset senza filtro ASL (documenti pubblici)

- RAG con parent-child chunking, BM25 + vector search

