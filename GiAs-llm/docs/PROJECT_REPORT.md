# Report di Progetto: Agente Predittore ML

**Versione:** 1.0
**Data:** 15 Gennaio 2026
**Stato:** Modello V4


# Agente Predittore ML (GiAs-llm)

Questo progetto mira a sviluppare un **Agente Predittore basato su Machine Learning** integrato nell'ecosistema GiAs-llm. L'obiettivo principale è fornire stime di rischio di non conformità (NC) per stabilimenti alimentari mai controllati o controllati raramente, ottimizzando così la pianificazione delle ispezioni ufficiali.

## Scopo del Progetto

Il sistema utilizza dati storici e caratteristiche territoriali per addestrare un modello ML (XGBoost) in grado di identificare pattern di rischio. L'agente espone un tool intelligente utilizzabile dall'orchestratore LangGraph per rispondere a query in linguaggio naturale come *"Dammi la lista degli stabilimenti a rischio alto ad Avellino"*.


---

## 1. Introduzione al Progetto

### Obiettivo
L'obiettivo del sistema "Agente Predittore ML" è supportare i veterinari e gli ispettori ASL nell'identificare gli stabilimenti a rischio di **Non Conformità (NC)** che non sono **mai stati controllati** (o non controllati da molto tempo).
Il sistema utilizza algoritmi di Machine Learning addestrati su 10 anni di storico ispezioni per assegnare un "Risk Score" a ogni stabilimento, permettendo di prioritizzare le ispezioni.

La sfida principale è predire il rischio per attività di cui non abbiamo dati storici diretti.
La soluzione adottata si basa sul principio del **"Rischio per Associazione"**: un'attività eredita il profilo di rischio della sua categoria tipologica (`linea_attivita`, `macroarea`), del contesto normativo (`norma`) e territoriale (`asl`) e della sua anzianità (`years_never_controlled`).

---

## 2. Evoluzione dello Sviluppo (Da V1 a V4)

Il progetto ha seguito un approccio iterativo data-driven.

### Phase 1: Il Prototipo (V1) 
*   **Dataset**: ~100k record (Solo 2025).
*   **Target**: Binario (Non Conformità).
*   **Features**: `macroarea`, `aggregazione`, `years_never_controlled`.
*   **Performance**: AUC 0.95 | Recall 0.84 | Precision 0.74.
*   **Analisi Critica**: I risultati eccellenti erano illusori. Il modello aveva memorizzato pattern specifici dell'anno 2025 che non si applicavano allo storico. Falliva nel generalizzare su anni diversi (AUC crollava a 0.77 su dati storici).

### Phase 2: La Baseline Storica  
*   **Dataset**: ~800k record (Storico 2016-2025).
*   **Target**: Binario.
*   **Features**: + `ASL` (Geografica).
*   **Weighting**: `scale_pos_weight=9.5` (Bilanciamento aggressivo).
*   **Performance (V2 Opt)**: AUC 0.81 | Recall 0.87 | Precision 0.18.
*   **Analisi Critica**:
    *   **Pro**: Robustissimo. Impara da 10 anni di dati. Cattura quasi tutti i rischi (Recall 87%).
    *   **Contro**: Troppi falsi positivi (Precision 18%). Per trovare 1 rischio reale, richiede 5-6 ispezioni. Inaccettabile per risorse limitate.

### Phase 3: Focus sulla Precisione  
*   **Dataset**: ~800k record (2016-2025).
*   **Features**: + `linea_attivita` (Alta cardinalità: 170 categorie).
*   **Weighting**: Moderato (`scale_pos_weight=4.0`).
*   **Performance**: AUC 0.82 | Recall 0.51 | Precision 0.30.
*   **Analisi Critica**:
    *   **Pro**: Precisione aumentata del 50%. Ogni 3 ispezioni, 1 è un successo.
    *   **Contro**: Cieco a metà dei rischi. Recall 51% significa che un'epidemia potrebbe diffondersi mentre il modello ignora i segnali deboli.

### Phase 4: Il Breakthrough  
*   **Dataset**: ~800k record (2016-2025).
*   **Features Key**: + **`norma`** (Feature Dominante).
    *   *Insight*: Ispezioni sotto *REG CE 852* hanno rischio **15.1%**. Sotto *REG CE 853* solo **1.8%**. Questo segnale è 8x più forte di ogni altro.
*   **Strategia**: Ottimizzazione su **PR-AUC** (Precision-Recall Area Check) + Tuning Soglia (0.40).
*   **Performance**: AUC 0.82+ | Recall 0.70 | Precision 0.25.
*   **Analisi Critica**:
    *   Raggiunge il "Sweet Spot": Cattura la maggioranza dei rischi (70%) senza crollare nella precisione (25%).
    *   È il modello più intelligente perché discrimina basandosi sul quadro normativo reale, non solo sulla geografia.

---

## 3. Comparazione Modelli

| Modello | Focus Strategico | Precision | Recall | Quando Usarlo |
| :--- | :--- | :--- | :--- | :--- |
| **V2 (Optimized)** | **Sicurezza Totale** | 18% | **87%** | Scenari epidemici. Trova (quasi) tutto, ma genera molti falsi allarmi. |
| **V3** | **Efficienza Costi** | **30%** | 51% | Risorse ispettive molto scarse. Ogni ispezione deve contare ("Colpo sicuro"). |
| **V4 (Recommended)** | **Bilanciato** | 25% | **70%** | **Standard Operativo**. Ottimo compromesso: trova la maggioranza dei rischi senza sprecare risorse eccessive. |

---

## 4. Raccomandazione Finale

Si raccomanda il deploy in produzione del modello **V4** con soglia di probabilità **0.40**.
Questo settaggio garantisce che:
1.  Venga intercettato il **70%** delle Non Conformità  presenti sul territorio.
2.  Il tasso di successo delle ispezioni sia **1 su 4** (25%), un miglioramento significativo rispetto alla selezione casuale (baseline rischio 9-10%).

*Per i dettagli tecnici dell'integrazione, fare riferimento alla `HANDOFF_GUIDE.md`.*
