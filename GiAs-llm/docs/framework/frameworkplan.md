# Piano di generalizzazione a piattaforma di risk management (monodominio, solo italiano)

## Sintesi
Il sistema attuale e fortemente specializzato sul dominio veterinario (ASL, OSA, piani, NC). La generalizzazione richiede un livello di configurazione di dominio (terminologia, mapping colonne, scoring) senza cambiare l'architettura a 3 layer (data, tools, response) e la pipeline LLM + tools. Il target e monodominio: una installazione per un solo settore alla volta, con interfaccia solo in italiano.

## Vincoli confermati dal committente
- Lingua: italiano soltanto.
- Dominio: monodominio (una istanza = un settore).

## Dipendenze di dominio attuali (punti di lock-in)
- Prompt e routing: terminologia veterinaria hard-coded in `orchestrator/router.py` e `orchestrator/graph.py`.
- Dataset e colonne: schema specifico in `agents/agents/data_agent.py` e `agents/data.py` (piani, controlli, OCSE/NC, OSA, diff programmati/eseguiti).
- Tools e formattazione: concetti veterinari in `tools/*.py` e `agents/agents/response_agent.py`.
- Ricerca: fallback keyword veterinarie in `tools/search_tools.py`.

## Requisiti dati (schema minimo e vincoli)
Ogni dominio deve fornire dataset coerenti con un modello canonico. I nomi possono cambiare, ma devono essere mappati.

### 1) Programmi (equivalente di piani)
- Campi minimi: `code/id`, `title/name`, `description`, `category/section`.
- Opzionale: sotto-indicatori o varianti.
- Deve essere indicizzabile per ricerca semantica.

### 2) Tassonomia attivita
- Campi minimi: `macroarea`, `aggregazione`, `linea_attivita` (o equivalenti).
- Deve consentire join con eventi e violazioni.

### 3) Eventi/controlli
- Campi minimi: `entity_id`, `program_code`, `activity_taxonomy`, `date`, `jurisdiction`.
- Serve per conteggi aggregati per attivita, programma e ente.

### 4) Violazioni/incidenti (equivalente OCSE/NC)
- Campi minimi: `event_id` o `entity_id`, `severity`, `category`, `count`, `date`.
- Necessaria distinzione di severita (es. grave/non grave o scala).

### 5) Programmazione vs esecuzione
- Campi minimi: `org_unit`, `program_code`, `planned`, `executed`, `year`.

### 6) Entita target (equivalente OSA mai controllati)
- Campi minimi: `entity_id`, `location`, `activity_taxonomy`, `jurisdiction`.

### 7) Organizzazione/personale
- `user_id` e mapping verso `org_unit` e `jurisdiction`.

### Vincoli di qualita dati
- Chiavi normalizzate e coerenti tra dataset (program_code, taxonomy).
- Date parseabili e coerenti.
- Valori numerici affidabili per severita e conteggi.
- Terminologia unica per dominio (niente mix di etichette non mappate).

## Piano di generalizzazione (monodominio)

### Fase 1: Definire Domain Pack (configurazione dominio)
- Dizionario termini: etichette italiane per entita, programmi, violazioni, categorie.
- Mapping colonne: dal dataset reale al modello canonico.
- Parametri di scoring: formula rischio, pesi severita, soglie.
- Keyword fallback per ricerca (specifiche di dominio).

### Fase 2: Adattamento dati
- Introdurre un adapter che applica il mapping colonne e normalizza i dataset in memoria.
- Mantenere la data source attuale (CSV/PostgreSQL) ma aggiungere mapping per dominio.

### Fase 3: Generalizzare tools e business logic
- Rendere parametrico il calcolo rischio e le etichette di risposta.
- Spostare costanti veterinarie (NC_CATEGORY_WEIGHTS) in configurazione dominio.
- Aggiungere interfaccia di accesso ai nomi canonici per tool e formatter.

### Fase 4: Prompt e intent
- Parametrizzare i prompt di classificazione e generazione risposta usando Domain Pack.
- Aggiornare esempi e descrizioni intent con lessico di dominio.

### Fase 5: Search e indicizzazione
- Indici Qdrant separati per dominio (una sola istanza per installazione).
- Fallback keywords dal Domain Pack.

### Fase 6: Test e benchmark
- Rimuovere assunzioni veterinarie dai test generici.
- Aggiungere fixture di dominio (dataset minimo valido + intent sample).

## Nuovi sviluppi necessari
- Modulo `domain_config` (schema, validazione, loader).
- Adapter di normalizzazione dataset.
- Parametrizzazione formatter (etichette, descrittori, legenda rischio).
- Strumento di validazione dataset contro schema minimo.
- Documentazione di onboarding per nuovo dominio.

## Assunzioni finali
- Lingua unica: italiano.
- Monodominio per installazione.
- Formula rischio configurabile, ma unica per dominio.

## Checklist operativa (milestone e stime)
- M1 (1-2 settimane): definizione Domain Pack, schema minimo e mapping colonne
- M2 (1-2 settimane): adapter dati + validatore dataset
- M3 (2-3 settimane): refactor tools/formatter con etichette e scoring configurabili
- M4 (1-2 settimane): aggiornamento prompt intent/risposte e keyword search
- M5 (1-2 settimane): test suite monodominio + fixture dati + benchmark

## Esempio concreto (finanza) senza perdita di generalita
Questo esempio mostra come istanziare il framework mantenendo la struttura generale invariata.

- Lessico: entita_target=intermediario, programma=iniziativa di vigilanza, evento_controllo=ispezione, violazione=irregolarita
- Categorie con pesi: antiriciclaggio=1.0, trasparenza=0.8, requisiti_patrimoniali=0.9, governance=0.7, frodi=1.0
- Mapping colonne tipico: programmi(id_iniziativa, codice_iniziativa, area_tematica, descrizione), controlli(id_intermediario, codice_iniziativa, processo, data_ispezione, area_vigilanza), violazioni(id_ispezione, categoria_irregolarita, num_irregolarita_gravi)
- Keyword fallback: antiriciclaggio, frodi, condotta, governance, vigilanza
- Nota: l'implementazione resta identica; cambia solo il Domain Pack e il mapping dei dataset.

## Riferimenti ai template finanza
- Domain Pack compilato: `doc/domain_pack_finanza.md`
- Dataset template compilato: `doc/dataset_template_finanza.md`

## How-to (finanza) per compilare i template con dati reali
1) Compilare `doc/domain_pack_finanza.md` con:
   - Etichette effettive usate dall'organizzazione (intermediario, iniziativa, ufficio, area di vigilanza).
   - Categorie reali di irregolarita e relativi pesi.
   - Mapping colonne reale per ogni dataset disponibile.
2) Allineare i dataset reali a `doc/dataset_template_finanza.md`:
   - Verificare che ogni colonna minima sia presente o mappabile.
   - Normalizzare codici iniziativa e tassonomie di processo.
3) Validare la coerenza:
   - Programmi e controlli devono condividere lo stesso codice iniziativa.
   - Violazioni devono riferirsi allo stesso id_ispezione o id_intermediario usato nei controlli.
4) Verificare la qualita:
   - Date in formato coerente.
   - Severita valorizzata su scala definita (grave/non grave o livelli).
5) Iterare sui pesi:
   - Eseguire analisi preliminare e regolare i pesi categoria per ottenere ranking plausibili.
