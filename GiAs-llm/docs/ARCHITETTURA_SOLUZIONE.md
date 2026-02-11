# GiAs-llm: Assistente Intelligente per il Monitoraggio Veterinario

## Panoramica

GiAs-llm è un sistema di assistenza conversazionale basato su Intelligenza Artificiale, progettato per supportare le Autorità Competenti della Regione Campania nelle attività di pianificazione e indirizzamento dei controlli ufficiali veterinari.

---

## Obiettivi

### 1. Supporto Decisionale ai Controlli Ufficiali

Il sistema utilizza tecnologie di **Intelligenza Artificiale (AI)** e **Machine Learning (ML)** per:

- **Analizzare i dati storici** dei controlli eseguiti e delle non conformità rilevate
- **Calcolare indici di rischio** per stabilimenti e attività produttive
- **Identificare priorità di intervento** basate su criteri oggettivi e misurabili
- **Evidenziare ritardi nella programmazione** rispetto agli obiettivi pianificati
- **Suggerire gli stabilimenti da controllare** in base a correlazioni statistiche tra piani e tipologie di attività

### 2. Interfaccia Conversazionale Unificata

Il sistema fornisce un'**interfaccia in linguaggio naturale** che permette agli operatori di:

- **Consultare informazioni** provenienti dai diversi sottosistemi dell'ecosistema GISA
- **Ottenere risposte immediate** senza necessità di navigare tra applicativi diversi
- **Formulare domande in italiano** senza conoscere query tecniche o strutture dati
- **Ricevere informazioni contestualizzate** in base alla propria ASL e struttura organizzativa

---

## Architettura del Sistema

### Componenti Principali

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTERFACCIA UTENTE                           │
│                  (Chat conversazionale)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ORCHESTRATORE CONVERSAZIONE                     │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  Comprensione│───▶│  Esecuzione │───▶│ Generazione │        │
│  │   Richiesta  │    │    Azione   │    │  Risposta   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MOTORE INTELLIGENZA                          │
│                                                                 │
│  ┌───────────────────┐    ┌───────────────────┐                │
│  │   Analisi Rischio │    │  Ricerca Semantica │                │
│  │   (ML/Statistico) │    │    (AI/Vettoriale) │                │
│  └───────────────────┘    └───────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     STRATO DATI                                 │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Piani   │ │ Controlli│ │   OSA    │ │    NC    │          │
│  │Monitorag.│ │ Eseguiti │ │(Stabili.)│ │(Storiche)│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Flusso Operativo

1. **Ricezione della Richiesta**: L'operatore formula una domanda in linguaggio naturale attraverso l'interfaccia chat

2. **Comprensione dell'Intento**: Il sistema AI interpreta la richiesta, identificando cosa l'utente vuole sapere e quali parametri sono stati specificati

3. **Esecuzione dell'Azione**: In base all'intento riconosciuto, il sistema:
   - Interroga le basi dati appropriate
   - Applica algoritmi di analisi del rischio
   - Effettua correlazioni statistiche
   - Esegue ricerche semantiche sui piani di controllo

4. **Generazione della Risposta**: I risultati vengono elaborati e presentati in italiano, con spiegazioni operative e suggerimenti contestuali

---

## Funzionalità Principali

### Analisi del Rischio

Il sistema calcola un **punteggio di rischio** per ogni tipologia di attività basandosi su:

- Frequenza storica delle non conformità (gravi e non gravi)
- Numero di controlli effettuati
- Impatto potenziale delle violazioni

Questo permette di **indirizzare i controlli** verso gli stabilimenti statisticamente più a rischio.

### Gestione Priorità

Il sistema identifica **priorità di intervento** attraverso:

- Analisi degli scostamenti tra controlli programmati ed eseguiti
- Individuazione degli stabilimenti mai controllati
- Correlazione tra piani in ritardo e tipologie di attività correlate

### Ricerca Intelligente

Gli operatori possono **cercare piani di controllo** per argomento utilizzando:

- Ricerca semantica che comprende sinonimi e concetti correlati
- Navigazione per macro-aree e categorie
- Filtri contestuali per ASL e struttura organizzativa

### Consultazione Dati

Il sistema permette di **consultare** in modo conversazionale:

- Descrizioni e dettagli dei piani di monitoraggio
- Elenchi di stabilimenti controllati per piano
- Storico controlli per singolo stabilimento
- Stato di avanzamento della programmazione

---

## Integrazione con l'Ecosistema GISA

GiAs-llm si integra con i sottosistemi esistenti fungendo da **punto di accesso unificato** alle informazioni:

| Fonte Dati | Informazioni |
|------------|--------------|
| Anagrafe OSA | Stabilimenti, attività, localizzazione |
| Controlli Ufficiali | Ispezioni eseguite, esiti, non conformità |
| Programmazione | Piani, obiettivi, scadenze |
| Personale | Strutture organizzative, competenze territoriali |

Il sistema **non sostituisce** gli applicativi esistenti ma li **complementa**, offrendo una modalità di accesso immediata e intuitiva.

---

## Benefici Attesi

### Per gli Operatori

- **Riduzione dei tempi** di consultazione delle informazioni
- **Accesso semplificato** senza necessità di formazione su sistemi complessi
- **Supporto decisionale** basato su dati oggettivi

### Per l'Organizzazione

- **Ottimizzazione delle risorse** indirizzando i controlli dove più necessari
- **Maggiore efficacia** nell'individuazione delle criticità
- **Tracciabilità** delle logiche decisionali

### Per il Cittadino

- **Controlli più mirati** sulle attività a maggior rischio
- **Maggiore tutela** della salute pubblica e del benessere animale

---

## Evoluzione Futura

Il sistema è progettato per evoluzioni incrementali:

- **Modelli predittivi avanzati** per anticipare le non conformità
- **Integrazione con ulteriori fonti dati** dell'ecosistema regionale
- **Estensione delle capacità conversazionali** a nuovi domini applicativi
