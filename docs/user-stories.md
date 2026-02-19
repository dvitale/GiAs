# User Stories - GISA-AI 
Documento delle user story per ogni intent risocnosciuto dal sistema GISA-AI.
Sono esclusi gli intent di servizio: `greet`, `goodbye`, `ask_help`, `confirm_show_details`, `decline_show_details`, `fallback`.

---

# Contesto informativo: i dataset del sistema

Questa sezione descrive i dataset da cui GISA-AI attinge le informazioni per rispondere alle domande degli operatori. Ogni dataset rappresenta un aspetto specifico delle attivita' di controllo veterinario e, insieme agli altri, compone il quadro informativo completo su cui si basano le risposte dell'assistente.

---

## Piani di monitoraggio

Il dataset dei **piani di monitoraggio** contiene l'elenco ufficiale dei piani di controllo sanitario previsti dalla normativa regionale e nazionale. Per ogni piano sono disponibili:

- Il **codice piano** : codice alfanumerico univoco (es. A1, B2, C3, A11_F, AO24_B) che permette di citare il piano in modo univoco
- La **descrizione** principale che spiega gli obiettivi e l'ambito del piano (es. "Controllo della Trichinella nei suini macellati")
- La **sezione di appartenenza** che raggruppa i piani  
- L'**codice sottopiano** : codice aggiuntivo che identifica l'indicatore di performance associato al piano
- La **descrizione sottopiano** (`descrizione_2`): dettagli aggiuntivi o note operative sul piano
- Il **flag campionamento** (`campionamento`): booleano che indica se il piano prevede attivita' di prelievo campioni per analisi di laboratorio (true/false)

**Struttura tabella PostgreSQL:**
```
piani_monitoraggio (
    id, sezione, alias, descrizione,
    alias_indicatore, descrizione_2, campionamento
)
```

Questo dataset viene consultato quando l'utente chiede informazioni su un piano specifico, cerca piani per argomento, o vuole capire a quale piano afferisce una determinata attivita' ispettiva. Il flag campionamento e' particolarmente utile per distinguere i piani che richiedono CU senza campione da quelli che prevedono prelievi per campioni.

---

## Controlli ufficiali eseguiti

Il dataset dei **controlli ufficiali eseguiti** e' il registro delle ispezioni effettivamente svolte nel corso dell'anno corrente. Per ogni controllo sono registrati:

- Lo **stabilimento ispezionato** (ragione sociale, numero di registrazione, indirizzo)
- La **data del controllo** e l'ASL di competenza
- Il **piano di riferimento** nell'ambito del quale e' stato eseguito il controllo
- La **tipologia di attivita'** dello stabilimento (macroarea, aggregazione, linea di attivita')

Questo dataset e' fondamentale per sapere quanti controlli sono stati eseguiti per un piano, quali stabilimenti sono stati visitati, e per costruire lo storico ispettivo di un operatore.

---

## Stabilimenti mai controllati

Il dataset degli **stabilimenti mai controllati** elenca tutti gli operatori del settore alimentare (OSA) presenti nel territorio dell'ASL che non hanno mai ricevuto una visita ispettiva. Per ogni stabilimento sono disponibili:

- I **dati identificativi** (numero di registrazione/riconoscimento, ragione sociale)
- La **localizzazione** (comune, indirizzo, coordinate geografiche quando disponibili)
- La **tipologia di attivita'** (macroarea, aggregazione, linea di attivita')

Questo dataset viene utilizzato per identificare gli stabilimenti da ispezionare con priorita', in particolare quando l'utente chiede suggerimenti su "cosa controllare" o cerca stabilimenti nelle vicinanze di una posizione geografica.

---

## Esiti e non conformita' 

Il dataset **ispezioni** contiene il registro storico delle non conformita' rilevate durante i controlli. Per ogni rilievo sono documentati:

- Il **tipo di non conformita'** (grave o non grave)
- La **categoria** del problema riscontrato (HACCP, igiene degli alimenti, condizioni delle strutture, etichettatura, etc.)
- Lo **stabilimento** presso cui e' stata rilevata la non conformita'
- L'**anno di riferimento** per l'analisi dei trend temporali

Questo dataset alimenta tutti i calcoli di rischio: dalla classifica delle attivita' piu' problematiche, all'identificazione degli stabilimenti con storico di non conformita', fino alla previsione del rischio per stabilimenti mai controllati basata sulla tipologia di attivita'.

---

## Programmazione vs esecuzione controlli

Il dataset del **confronto programmati/eseguiti** mette a confronto, per ogni Unita' Operativa (UOC), il numero di controlli pianificati per l'anno con quelli effettivamente eseguiti. I dati includono:

- Il **piano** con il relativo codice
- I **controlli programmati** secondo la pianificazione annuale
- I **controlli eseguiti** alla data di estrazione
- La **struttura organizzativa** (UOC) responsabile

Questo dataset permette di identificare i "piani in ritardo", cioe' quei piani per cui il numero di ispezioni effettuate e' inferiore a quanto programmato. E' la base per le domande sulla priorita' dei controlli e sullo stato di avanzamento della programmazione.

---

## Organigramma del Personale

Il dataset del **personale** contiene l'anagrafica degli operatori veterinari delle ASL. Per ogni utente sono registrati:

- L'**identificativo utente** utilizzato per l'autenticazione al sistema
- L'**ASL di appartenenza**
- La **struttura organizzativa** (UOC - Unita' Operativa Complessa)

Questo dataset viene consultato automaticamente quando un utente accede al sistema per personalizzare le risposte: i piani in ritardo mostrati saranno quelli della sua UOC, gli stabilimenti suggeriti saranno quelli del territorio della sua ASL, e cosi' via.

---

## Anagrafica attivita' (Masterlist)

Il dataset della **masterlist** contiene la classificazione ufficiale di tutte le tipologie di attivita' economiche soggette a controllo veterinario. La classificazione e' gerarchica:

- **Macroarea**: il settore principale (es. "Produzione primaria", "Trasformazione", "Distribuzione")
- **Aggregazione**: la sottocategoria (es. "Lattiero-caseario", "Carni", "Pesca")
- **Linea di attivita'**: la specifica attivita' (es. "Caseificio artigianale", "Macello avicolo")

Questa classificazione standard garantisce che i dati sui controlli, gli stabilimenti e le non conformita' siano sempre catalogati in modo uniforme e confrontabile tra le diverse ASL della regione.

---

## Come i dataset lavorano insieme

L'assistente GISA-AI non interroga mai un solo dataset in isolamento. Le risposte piu' utili nascono dall'incrocio di piu' fonti:

- Per suggerire **stabilimenti prioritari**, il sistema incrocia i piani in ritardo (programmazione) con gli stabilimenti mai controllati (OSA), filtrandoli per tipologia di attivita' correlata al piano
- Per calcolare il **rischio** di uno stabilimento mai controllato, il sistema usa lo storico delle non conformita' (OCSE) aggregate per tipologia di attivita', applicando la stessa probabilita' agli stabilimenti della stessa categoria
- Per mostrare lo **storico** di uno stabilimento, il sistema unisce i controlli eseguiti con le eventuali non conformita' rilevate in ciascuna visita
- Per la ricerca **geografica**, il sistema filtra gli stabilimenti mai controllati per prossimita', arricchendoli con il punteggio di rischio calcolato dalla tipologia

---

# User Stories

---

## US-01: Descrizione di un piano di controllo

**Intent:** `ask_piano_description`

**Come** veterinario ASL della Regione Campania,
**voglio** ottenere la descrizione dettagliata di un piano di controllo specificandone il codice,
**in modo da** comprendere obiettivi, ambito e contenuto del piano prima di pianificare le attivita' ispettive.

### Dettagli funzionali

- **Input richiesto:** codice piano (es. `A1`, `B2`, `C3`, `AO24_B`)
- **Slot:** `piano_code` (estratto via regex `[A-Za-z]+[0-9]+(?:_[A-Za-z]+)?`)
- **Fonte dati:** tabella `piani_monitoraggio` (PostgreSQL)
- **Output:** descrizione testuale del piano, numero di varianti presenti nel database
- **Gestione errori:** se il codice non esiste, il sistema avvisa e suggerisce di verificare il codice

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Di cosa tratta il piano A1?" | Descrizione completa del piano A1 con varianti |
| "Cosa prevede il piano A32?" | Descrizione del piano A32 |
| "Descrizione piano B2" | Dettaglio piano B2 |

### Criteri di accettazione

- [ ] Il sistema estrae correttamente il codice piano dalla domanda
- [ ] La descrizione include tutte le varianti del piano nel database
- [ ] Se il piano non esiste, viene mostrato un messaggio di errore comprensibile
- [ ] La risposta non richiede ulteriori interazioni (single-phase)

---

## US-02: Stabilimenti coinvolti in un piano

**Intent:** `ask_piano_stabilimenti`

**Come** veterinario ASL,
**voglio** sapere quali stabilimenti sono stati controllati nell'ambito di un piano specifico,
**in modo da** avere una visione d'insieme delle attivita' ispettive svolte e degli operatori coinvolti.

### Dettagli funzionali

- **Input richiesto:** codice piano
- **Slot:** `piano_code`
- **Fonte dati:** tabella `cu_eseguiti` (controlli ufficiali eseguiti 2025)
- **Output:** lista top 10 stabilimenti per numero controlli, con macroarea, aggregazione e attivita'
- **Two-phase:** se il numero di stabilimenti supera la soglia (3), viene prima mostrato un riepilogo sintetico. L'utente puo' chiedere i dettagli completi.

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Quali stabilimenti per piano A1?" | Top stabilimenti controllati per il piano A1 |
| "OSA del piano C3" | Lista operatori controllati nel piano C3 |
| "Dove si applica piano B2?" | Stabilimenti e territori coinvolti nel piano B2 |

### Criteri di accettazione

- [ ] Vengono mostrati i top 10 stabilimenti ordinati per numero di controlli
- [ ] Il riepilogo include: totale controlli, stabilimenti unici, descrizione piano
- [ ] Se ci sono piu' di 3 stabilimenti, scatta il two-phase (riepilogo + conferma dettagli)
- [ ] Se nessun controllo e' registrato nel 2025, il sistema lo comunica chiaramente

---

## US-03: Statistiche sui piani di controllo

**Intent:** `ask_piano_statistics`

**Come** responsabile veterinario ASL,
**voglio** consultare le statistiche aggregate sui piani di controllo (controlli eseguiti, distribuzione, confronti),
**in modo da** valutare l'andamento della programmazione sanitaria e identificare aree di miglioramento.

### Dettagli funzionali

- **Input richiesto:** opzionale `piano_code` (se specificato: statistiche puntuali; se assente: panoramica top 10 piani)
- **Slot:** `piano_code` (opzionale)
- **Metadata utilizzati:** `asl` (per filtrare o confrontare dati ASL vs regionale)
- **Fonte dati:** `cu_eseguiti`
- **Output:**
  - Con piano specifico e keyword conteggio: totale controlli regionale, controlli ASL utente, periodo (primo/ultimo controllo)
  - Senza piano: top 10 piani per numero controlli con statistiche

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Statistiche piano A1" | Dettaglio numerico del piano A1 |
| "Quanti controlli nel piano B2?" | Conteggio controlli regionale e ASL |
| "Statistiche sui piani" | Top 10 piani piu' utilizzati con numeri |

### Criteri di accettazione

- [ ] Con piano specifico: mostra totale regionale + totale ASL utente + periodo temporale
- [ ] Senza piano: mostra classifica top 10 piani per controlli
- [ ] I numeri sono formattati con separatori delle migliaia
- [ ] Il confronto regionale/ASL e' presente solo se l'utente e' autenticato con ASL

---

## US-04: Ricerca piani per argomento

**Intent:** `search_piani_by_topic`

**Come** veterinario ASL,
**voglio** cercare piani di controllo per argomento o settore (es. "benessere animale", "latte", "mangimi"),
**in modo da** trovare rapidamente i piani pertinenti alla mia area di competenza senza conoscerne i codici.

### Dettagli funzionali

- **Input richiesto:** argomento/topic di ricerca
- **Slot:** `topic` (estratto dal testo dopo "piani su/per/riguardanti")
- **Motore di ricerca:** ibrido (ricerca vettoriale + re-ranking LLM)
  - Vector search su Qdrant (embeddings sentence-transformers)
  - LLM re-ranking per pertinenza semantica
  - Fallback a keyword search se la ricerca semantica non produce risultati
- **Two-phase:** se i risultati superano la soglia (3), viene mostrato un riepilogo; l'utente puo' chiedere i dettagli
- **Output:** lista piani con codice, descrizione e punteggio di similarita'

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Piani sul benessere animale" | Lista piani correlati al benessere animale |
| "Cerca piani sulla sicurezza alimentare" | Piani pertinenti alla sicurezza alimentare |
| "Piani riguardanti il latte" | Piani del settore lattiero-caseario |

### Criteri di accettazione

- [ ] La ricerca semantica trova piani rilevanti anche con terminologia non esatta
- [ ] Se la ricerca vettoriale fallisce, scatta il fallback a keyword
- [ ] I risultati sono ordinati per rilevanza (similarity score)
- [ ] Con piu' di 3 risultati scatta il two-phase
- [ ] Se nessun risultato trovato, vengono suggeriti termini alternativi

---

## US-05: Stabilimenti prioritari da controllare

**Intent:** `ask_priority_establishment`

**Come** veterinario ASL che deve pianificare la giornata lavorativa,
**voglio** sapere quali stabilimenti sono prioritari da controllare,
**in modo da** concentrare le ispezioni sugli operatori piu' critici, cioe' quelli mai controllati che ricadono in piani in ritardo.

### Dettagli funzionali

- **Input richiesto:** nessuno (usa ASL e UOC dalla sessione utente)
- **Metadata utilizzati:** `asl`, `uoc` (UOC = Unita' Operativa Complessa, la struttura organizzativa del veterinario)
- **Logica:**
  1. Recupera i piani in ritardo per la UOC dell'utente (programmati vs eseguiti)
  2. Recupera gli stabilimenti mai controllati per l'ASL dell'utente
  3. Incrocia: stabilimenti mai controllati le cui attivita' ricadono nei piani in ritardo
  4. Ordina per priorita' (stabilimenti in settori con maggiore ritardo)
- **Two-phase:** se i risultati superano 3, riepilogo + conferma
- **Output:** lista stabilimenti prioritari con piano di riferimento, macroarea, comune

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Cosa devo fare oggi?" | Lista stabilimenti prioritari per la mia UOC |
| "Chi devo controllare per primo?" | Stabilimenti mai controllati in piani in ritardo |
| "Stabilimenti prioritari" | Top 15 stabilimenti prioritari |

### Criteri di accettazione

- [ ] L'utente deve essere autenticato (ASL + UOC necessari)
- [ ] La priorita' si basa sull'incrocio piani in ritardo + stabilimenti mai controllati
- [ ] Se nessun piano e' in ritardo: messaggio positivo ("programmazione in linea")
- [ ] Se nessuno stabilimento mai controllato: segnala il numero di piani in ritardo comunque
- [ ] Con piu' di 3 risultati scatta il two-phase

---

## US-06: Stabilimenti ad alto rischio (predizione NC)

**Intent:** `ask_risk_based_priority`

**Come** veterinario ASL,
**voglio** conoscere gli stabilimenti mai controllati che hanno il piu' alto rischio storico di non conformita',
**in modo da** dirigere i controlli verso gli operatori statisticamente piu' problematici.

### Dettagli funzionali

- **Input richiesto:** nessuno (usa ASL dalla sessione)
- **Metadata utilizzati:** `asl`
- **Predittore configurabile:**
  - **ML (XGBoost v4):** modello addestrato su storico NC 2016-2025 con feature importance e SHAP values
  - **Statistico (rule-based):** formula `Risk Score = P(NC) x Impatto x 100` dove P(NC) = NC totali / controlli e Impatto = NC gravi / controlli
  - Fallback automatico: ML -> rule-based -> emergenza
- **Logica:**
  1. Calcola risk score per ogni tipologia di attivita' (dati regionali OCSE)
  2. Recupera stabilimenti mai controllati dell'ASL
  3. Associa ogni stabilimento al risk score della sua tipologia
  4. Ordina per punteggio di rischio decrescente
- **Two-phase:** se i risultati superano 3, riepilogo + conferma
- **Output:** lista stabilimenti con punteggio rischio, NC gravi/non gravi storiche, comune, indirizzo

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Stabilimenti a rischio" | Top 20 stabilimenti mai controllati ad alto rischio |
| "Quali stabilimenti hanno piu' NC?" | Classifica stabilimenti per rischio storico |
| "OSA piu' rischiosi" | Lista operatori con maggiore probabilita' NC |

### Criteri di accettazione

- [ ] Il sistema sceglie automaticamente il predittore in base alla configurazione
- [ ] Se il modello ML fallisce, il fallback rule-based si attiva trasparentemente
- [ ] Il punteggio di rischio e' basato su dati aggregati regionali per tipologia attivita'
- [ ] La risposta include una legenda per interpretare i punteggi
- [ ] Con piu' di 3 risultati scatta il two-phase

---

## US-07: Stabilimenti mai controllati

**Intent:** `ask_suggest_controls`

**Come** veterinario ASL,
**voglio** ottenere un elenco di stabilimenti che non sono mai stati ispezionati,
**in modo da** pianificare controlli su operatori che non hanno mai ricevuto visite ispettive.

### Dettagli funzionali

- **Input richiesto:** nessuno (usa ASL dalla sessione)
- **Metadata utilizzati:** `asl`
- **Fonte dati:** tabella `osa_mai_controllati`
- **Two-phase:** se il totale supera 5, riepilogo + conferma
- **Output:** campione di stabilimenti mai controllati con macroarea, aggregazione, comune

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Stabilimenti mai controllati" | Lista stabilimenti senza controlli registrati |
| "OSA da ispezionare" | Suggerimento operatori da visitare |
| "Da controllare" | Elenco stabilimenti non ancora ispezionati |

### Criteri di accettazione

- [ ] La lista e' filtrata per ASL dell'utente
- [ ] Vengono mostrati fino a 20 stabilimenti (con indicazione del totale)
- [ ] Se nessuno stabilimento risulta mai controllato: messaggio positivo
- [ ] Con piu' di 3 risultati scatta il two-phase

---

## US-08: Classifica attivita' piu' rischiose

**Intent:** `ask_top_risk_activities`

**Come** dirigente del servizio veterinario,
**voglio** conoscere la classifica delle tipologie di attivita' con il piu' alto rischio di non conformita',
**in modo da** orientare le politiche di controllo e allocare le risorse ispettive sui settori piu' critici.

### Dettagli funzionali

- **Input richiesto:** nessuno (opzionale: `limit` per il numero di risultati, default 10)
- **Fonte dati:** dataset OCSE (storico NC aggregato regionale)
- **Logica:**
  1. Calcola risk score per tutte le tipologie di attivita'
  2. Classifica: alto rischio (score > 20), medio rischio (5 < score <= 20), basso rischio
  3. Restituisce top N con dettaglio: macroarea, aggregazione, linea attivita', risk score, NC gravi/non gravi, controlli totali, P(NC), impatto
- **Output:** classifica con statistiche generali (totale attivita' analizzate, media score, distribuzione rischio)

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Attivita' piu' rischiose" | Top 10 tipologie attivita' per risk score |
| "Top tipologie a rischio" | Classifica attivita' con piu' NC |
| "Classifica attivita' pericolose" | Ranking settori per probabilita' NC |

### Criteri di accettazione

- [ ] La classifica copre tutte le tipologie di attivita' con dati sufficienti
- [ ] Ogni voce include: macroarea, aggregazione, risk score, NC gravi, NC non gravi, controlli totali
- [ ] Vengono mostrate statistiche generali (quante attivita' ad alto/medio rischio)
- [ ] Il risk score medio regionale e' calcolato e mostrato come riferimento
- [ ] Risposta single-phase (nessun two-phase)

---

## US-09: Piani di controllo in ritardo

**Intent:** `ask_delayed_plans`

**Come** veterinario ASL,
**voglio** vedere l'elenco dei piani di controllo in ritardo per la mia struttura organizzativa,
**in modo da** sapere dove la programmazione e' carente e intervenire per colmare il gap.

### Dettagli funzionali

- **Input richiesto:** nessuno (usa ASL e UOC dalla sessione)
- **Metadata utilizzati:** `asl`, `uoc`
- **Logica:**
  1. Recupera dati programmati vs eseguiti per la UOC dell'utente
  2. Calcola il ritardo: `ritardo = programmati - eseguiti` (dove ritardo > 0)
  3. Aggrega per piano (indicatore)
  4. Ordina per ritardo decrescente
- **Output:** lista top 10 piani in ritardo con: codice, descrizione, programmati, eseguiti, ritardo. Include dettaglio del piano con maggiore ritardo.

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Piani in ritardo" | Elenco piani in ritardo per la mia UOC |
| "Quali piani sono scaduti?" | Lista piani con ritardo positivo |
| "Elenco ritardi" | Panoramica ritardi programmazione |

### Criteri di accettazione

- [ ] L'utente deve essere autenticato (ASL + UOC necessari)
- [ ] Il ritardo e' calcolato come differenza tra programmati ed eseguiti
- [ ] I piani sono ordinati per ritardo decrescente
- [ ] Il piano con maggiore ritardo ha un dettaglio aggiuntivo
- [ ] Se nessun piano e' in ritardo: messaggio positivo
- [ ] Senza UOC: messaggio che spiega la necessita' di autenticazione

---

## US-10: Verifica ritardo di un piano specifico

**Intent:** `check_if_plan_delayed`

**Come** veterinario ASL,
**voglio** verificare se un piano specifico e' in ritardo per la mia struttura,
**in modo da** controllare puntualmente lo stato di avanzamento di un piano di cui sono responsabile.

### Dettagli funzionali

- **Input richiesto:** codice piano
- **Slot:** `piano_code`
- **Metadata utilizzati:** `asl`, `uoc`
- **Logica:**
  1. Recupera dati programmati vs eseguiti per la UOC
  2. Filtra per il piano specificato (match esatto o sottopiani, es. `AO24` matcha `AO24_A`, `AO24_B`)
  3. Calcola ritardo aggregato sui sottopiani
- **Output:** stato del piano (in ritardo / non in ritardo) con numeri: programmati, eseguiti, ritardo. Se ci sono sottopiani, li elenca.

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Il piano A1 e' in ritardo?" | Stato ritardo specifico del piano A1 |
| "Controlla ritardo piano B47" | Verifica se B47 e' in ritardo |
| "Piano AO24 scaduto?" | Stato AO24 con dettaglio sottopiani |

### Criteri di accettazione

- [ ] Il sistema distingue questo intent da `ask_delayed_plans` per la presenza del codice piano
- [ ] Se il piano ha sottopiani (es. AO24_A, AO24_B), li aggrega correttamente
- [ ] Se il piano non e' in ritardo: conferma positiva
- [ ] Se il piano non esiste nei dati della UOC: messaggio appropriato
- [ ] Risposta single-phase (nessun two-phase)

---

## US-11: Storico controlli di uno stabilimento

**Intent:** `ask_establishment_history`

**Come** veterinario ASL,
**voglio** consultare lo storico dei controlli e delle non conformita' di uno stabilimento specifico,
**in modo da** preparare un'ispezione avendo chiaro il quadro delle visite precedenti e delle criticita' emerse.

### Dettagli funzionali

- **Input richiesto:** almeno uno tra:
  - `num_registrazione` (es. "IT 2287", "UE IT 2287 M")
  - `partita_iva` (10-11 cifre)
  - `ragione_sociale` (ricerca parziale)
- **Slot:** `num_registrazione`, `partita_iva`, `ragione_sociale`
- **Fonte dati:** `cu_eseguiti` (join con anagrafica stabilimenti)
- **Two-phase:** se i controlli superano 3, riepilogo + conferma dettagli
- **Output:** storico controlli ordinato dal piu' recente, con: data, piano, esito, NC trovate, informazioni stabilimento (ragione sociale, ASL, registrazione)

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Storico controlli stabilimento IT 2287" | Lista controlli per lo stabilimento IT 2287 |
| "Controlli per partita iva 12345678901" | Storico per partita IVA |
| "Storia NC stabilimento Caseificio Rossi" | Controlli e NC per ragione sociale |

### Criteri di accettazione

- [ ] Lo stabilimento e' identificabile per registrazione, P.IVA o ragione sociale
- [ ] I controlli sono ordinati dal piu' recente al piu' vecchio
- [ ] Il riepilogo include: info stabilimento, totale controlli, statistiche NC
- [ ] Con piu' di 3 controlli scatta il two-phase
- [ ] Se lo stabilimento non e' trovato: messaggio di errore con suggerimenti

---

## US-12: Analisi non conformita' per categoria

**Intent:** `analyze_nc_by_category`

**Come** responsabile veterinario ASL,
**voglio** analizzare le non conformita' aggregate per una specifica categoria (es. HACCP, IGIENE, STRUTTURE),
**in modo da** capire quali ambiti di controllo presentano le maggiori criticita' e dove concentrare la formazione o le ispezioni tematiche.

### Dettagli funzionali

- **Input richiesto:** categoria NC (default: "HACCP" se non specificata)
- **Slot:** `categoria`
- **Categorie valide:** HACCP, IGIENE DEGLI ALIMENTI, IGIENE, STRUTTURE, PULIZIA, SANIFICAZIONE, ETICHETTATURA, MOCA, RINTRACCIABILITA
- **Metadata utilizzati:** `asl` (opzionale, per filtrare per ASL)
- **Fonte dati:** `cu_eseguiti` con dati NC
- **Output:** totale controlli nella categoria, NC gravi, NC non gravi, stabilimenti coinvolti, top 3 stabilimenti critici (quelli con piu' NC nella categoria)

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Analisi NC per categoria" | Analisi NC per HACCP (default) |
| "Non conformita' HACCP" | Statistiche NC HACCP |
| "Problemi di strutture" | Analisi NC categoria STRUTTURE |
| "Analizza le NC IGIENE" | Distribuzione NC nella categoria IGIENE |

### Criteri di accettazione

- [ ] Le categorie sono validate contro la lista delle categorie ammesse
- [ ] Se la categoria non e' valida: mostra la lista delle categorie disponibili
- [ ] Le statistiche includono: totale controlli, NC gravi, NC non gravi, stabilimenti coinvolti
- [ ] I top 3 stabilimenti critici sono mostrati con codice, ASL e numero NC
- [ ] Se l'utente inserisce un codice piano al posto di una categoria, il sistema suggerisce la domanda corretta
- [ ] Il filtro per ASL funziona se l'utente e' autenticato

---

## US-13: Informazioni su procedure operative

**Intent:** `info_procedure`

**Come** veterinario ASL,
**voglio** consultare le procedure operative documentate nei manuali (es. come eseguire un'ispezione semplice, come registrare una NC),
**in modo da** seguire correttamente i protocolli stabiliti senza dover cercare manualmente nei documenti cartacei o digitali.

### Dettagli funzionali

- **Input richiesto:** domanda in linguaggio naturale sulla procedura
- **Slot:** nessuno (la query intera viene usata per la ricerca semantica)
- **Architettura RAG (Retrieval-Augmented Generation):**
  1. La domanda viene trasformata in embedding vettoriale (sentence-transformers, 384 dim)
  2. Ricerca semantica nella collection Qdrant `procedure_documents` (top 5 chunk, soglia 0.30)
  3. I chunk recuperati vengono assemblati come contesto per il prompt LLM
  4. L'LLM (Ollama) genera una risposta sintetizzata basata esclusivamente sul contesto
  5. Le fonti documentali vengono citate in fondo alla risposta
- **Fonte dati:** documenti indicizzati da `data/documents/` (PDF, DOCX, TXT) tramite script `tools/indexing/build_docs_index.py`
- **Chunking:** documenti spezzati in chunk da ~600 caratteri con overlap di 100 caratteri, preservando header di sezione come metadata
- **Output:** risposta sintetizzata dall'LLM con citazione delle fonti documentali

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Qual e' la procedura per ispezione semplice?" | Passaggi della procedura estratti dal manuale |
| "Come si esegue un controllo ufficiale?" | Procedura di controllo ufficiale dal manuale operativo |
| "Quali sono i passi per registrare una NC?" | Istruzioni per la registrazione di non conformita' |
| "Come procedere con un audit?" | Procedura di audit dalla documentazione |

### Criteri di accettazione

- [ ] Il sistema classifica correttamente le domande procedurali (pattern: "procedura", "come si fa", "passi per", "istruzioni per")
- [ ] La ricerca semantica recupera chunk pertinenti dalla documentazione indicizzata
- [ ] La risposta e' generata dall'LLM basandosi esclusivamente sui chunk recuperati (no hallucination)
- [ ] Le fonti documentali sono citate in fondo alla risposta (nome file, sezione)
- [ ] Se nessun documento pertinente viene trovato, il sistema lo comunica chiaramente con suggerimenti
- [ ] La risposta e' concisa e formattata con liste numerate per i passaggi procedurali
- [ ] Il sistema richiede che i documenti siano stati preventivamente indicizzati con `build_docs_index.py`
- [ ] Risposta single-phase (nessun two-phase, la risposta LLM e' gia' sintetizzata)

### Note tecniche

- **Dipendenze:** PyMuPDF (PDF), python-docx (DOCX), sentence-transformers, qdrant-client
- **Collection Qdrant:** `procedure_documents` (separata da `piani_monitoraggio`)
- **Embedding model:** `paraphrase-multilingual-MiniLM-L12-v2` (condiviso con ricerca piani)
- **Latenza aggiuntiva:** ~1-3s per la generazione LLM rispetto ai tool con formatted_response pre-costruita
- **Configurazione:** sezione `rag_documents` in `configs/config.json`

---

## US-14: Stabilimenti da controllare per prossimita' geografica

**Intent:** `ask_nearby_priority`

**Come** veterinario ASL che si trova sul territorio,
**voglio** sapere quali stabilimenti mai controllati si trovano nelle vicinanze di un indirizzo specifico,
**in modo da** ottimizzare gli spostamenti e controllare gli operatori piu' vicini alla mia posizione attuale.

### Dettagli funzionali

- **Input richiesto:** indirizzo o localita' (es. "Piazza Garibaldi, Napoli", "centro Benevento")
- **Slot:**
  - `location` (obbligatorio): indirizzo da geocodificare
  - `radius_km` (opzionale, default 5): raggio di ricerca in km
- **Metadata utilizzati:** `asl` (per verificare che la location sia nel territorio di competenza)
- **Geocodifica:** Nominatim (OpenStreetMap) con:
  - Cache LRU per ottimizzare chiamate ripetute
  - Viewbox bounded sui capoluoghi di provincia per disambiguare omonimi
  - Riconoscimento quartieri/frazioni dei capoluoghi campani
- **Logica:**
  1. Geocodifica l'indirizzo fornito -> coordinate (lat, lon)
  2. Verifica che la location sia nel territorio dell'ASL dell'utente (matching provincia)
  3. Se fuori territorio: restituisce messaggio informativo (non risultati errati)
  4. Recupera stabilimenti mai controllati dell'ASL con coordinate valide
  5. Filtra per prossimita' geografica (distanza <= radius_km)
  6. Arricchisce con punteggio rischio per tipologia attivita'
  7. Ordina per distanza (primaria) + rischio (secondaria, decrescente)
- **Two-phase:** se i risultati superano 10, viene mostrato un riepilogo sintetico
- **Output:** lista stabilimenti con: macroarea, attivita', comune, indirizzo, distanza in km, risk score

### Esempi di interazione

| Domanda utente | Risposta attesa |
|---|---|
| "Stabilimenti vicino a Piazza Garibaldi, Napoli" | Lista stabilimenti entro 5 km da Piazza Garibaldi |
| "Cosa controllare nei dintorni di Via Roma, Benevento?" | Stabilimenti prioritari vicino a Via Roma |
| "Stabilimenti entro 3 km da Piazza Risorgimento, Benevento" | Lista con raggio personalizzato |
| "Vicino centro Salerno" | Stabilimenti vicini al centro di Salerno |

### Gestione casi particolari

| Caso | Comportamento |
|---|---|
| Indirizzo non trovato | Messaggio: "Non ho trovato l'indirizzo X. Prova a specificare meglio." |
| Location fuori territorio ASL | Messaggio informativo: "L'indirizzo X si trova in provincia di Y, fuori dal territorio dell'ASL Z." |
| Geocoding ambiguo (omonimo in altro comune) | Warning con indirizzo risolto e suggerimenti per query piu' precise |
| Nessun stabilimento nel raggio | Suggerimento di aumentare il raggio di ricerca |
| Timeout geocodifica | Messaggio di riprovare tra qualche secondo |

### Criteri di accettazione

- [ ] L'indirizzo viene geocodificato correttamente usando Nominatim con viewbox per i capoluoghi
- [ ] Se la location e' in una provincia diversa dall'ASL utente, viene mostrato un messaggio informativo invece di risultati errati
- [ ] Gli stabilimenti sono filtrati per prossimita' geografica usando le coordinate nel database
- [ ] L'ordinamento e' per distanza crescente, con risk score come criterio secondario
- [ ] Con piu' di 10 risultati scatta il two-phase (riepilogo + conferma dettagli)
- [ ] Se l'indirizzo viene risolto in un comune diverso dal capoluogo richiesto, viene mostrato un warning
- [ ] Il raggio di default e' 5 km, ma puo' essere personalizzato nella query (es. "entro 3 km")

### Note tecniche

- **Dipendenze:** geopy (Nominatim, geodesic distance)
- **Cache:** LRU cache con 500 entry per le geocodifiche
- **Viewbox:** delimitato sui capoluoghi campani per disambiguare omonimi
- **Coordinate stabilimenti:** colonne `latitudine_stab`, `longitudine_stab` nella tabella `osa_mai_controllati`
- **Formula distanza:** geodesic (geopy) con fallback a haversine se non disponibile
- **Pattern riconosciuti:** "vicino a", "vicino", "nei dintorni di", "nei pressi di", "intorno a", "entro X km da"

---

## Riepilogo intent e dipendenze

| # | Intent | Slot richiesti | Metadata richiesti | Two-phase | Predittore |
|---|--------|---------------|-------------------|-----------|------------|
| 01 | `ask_piano_description` | `piano_code` | - | No | - |
| 02 | `ask_piano_stabilimenti` | `piano_code` | - | Si (>3) | - |
| 03 | `ask_piano_statistics` | `piano_code` (opz.) | `asl` | No | - |
| 04 | `search_piani_by_topic` | `topic` | - | Si (>3) | Hybrid search |
| 05 | `ask_priority_establishment` | - | `asl`, `uoc` | Si (>3) | - |
| 06 | `ask_risk_based_priority` | - | `asl` | Si (>3) | ML / Rule-based |
| 07 | `ask_suggest_controls` | - | `asl` | Si (>3) | - |
| 08 | `ask_top_risk_activities` | - | - | No | Risk scores |
| 09 | `ask_delayed_plans` | - | `asl`, `uoc` | No | - |
| 10 | `check_if_plan_delayed` | `piano_code` | `asl`, `uoc` | No | - |
| 11 | `ask_establishment_history` | almeno 1 tra: `num_registrazione`, `partita_iva`, `ragione_sociale` | - | Si (>3) | - |
| 12 | `analyze_nc_by_category` | `categoria` | `asl` (opz.) | No | - |
| 13 | `info_procedure` | - | - | No | RAG (Qdrant + LLM) |
| 14 | `ask_nearby_priority` | `location`, `radius_km` (opz.) | `asl` | Si (>10) | Geocoding + Risk scores |
