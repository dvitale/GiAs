# Piano di Implementazione: Integrazione Categorie Non Conformità

**Data Creazione**: 2026-01-09
**Ultima Modifica**: 2026-01-09
**Status Generale**: 🟡 In Corso

## Architettura del Sistema Identificata

**Backend GiAs-llm**:
- Layer di dati: `agents/agents/data_agent.py`
- Tool layer: `tools/*.py`
- Router e workflow: `orchestrator/`

**Frontend gchat**:
- Interfaccia Go: `/opt/lang-env/gchat/app/`
- Configurazione: `/opt/lang-env/gchat/config/config.json`
- Template HTML: `/opt/lang-env/gchat/template/index.html`
- JavaScript: `/opt/lang-env/gchat/statics/js/chat.js`

---

## MILESTONE 1: Backend Data Layer - Supporto Categorie NC
**Status**: ✅ COMPLETATO (2026-01-09)
**Durata Stimata**: 3 giorni
**Durata Effettiva**: 0.5 giorni

### M1.1 - Estensione RiskAnalyzer
**File**: `/opt/lang-env/GiAs-llm/agents/agents/data_agent.py`
**Status**: ✅ COMPLETATO (2026-01-09)

#### Passi:
- [x] **Step 1.1.1**: ✅ Aggiungere costanti categorie NC (COMPLETATO 2026-01-09)
- [x] **Step 1.1.2**: ✅ Implementare `calculate_categorized_risk_scores()` (COMPLETATO 2026-01-09)
- [x] **Step 1.1.3**: ✅ Implementare `analyze_nc_category_trends()` (COMPLETATO 2026-01-09)
- [x] **Step 1.1.4**: ✅ Test unitari per nuove funzioni (COMPLETATO 2026-01-09)

**Test di Accettazione**:
- [x] ✅ DataFrame restituito contiene colonne categoria NC
- [x] ✅ Pesi applicati correttamente nei calcoli
- [x] ✅ Trend analysis filtra correttamente per date

### M1.2 - Estensione DataRetriever
**File**: `/opt/lang-env/GiAs-llm/agents/agents/data_agent.py`
**Status**: ✅ COMPLETATO (2026-01-09)

#### Passi:
- [x] **Step 1.2.1**: ✅ Implementare `get_nc_by_category()` (COMPLETATO 2026-01-09)
- [x] **Step 1.2.2**: ✅ Implementare `get_establishments_with_nc_category()` (COMPLETATO 2026-01-09)
- [x] **Step 1.2.3**: ✅ Test con dati OCSE reali (COMPLETATO 2026-01-09)

**Test di Accettazione**:
- [x] ✅ Filtri categoria funzionano correttamente
- [x] ✅ Filtri ASL applicati quando specificati
- [x] ✅ Limite di risultati rispettato

---

## MILESTONE 2: Backend Tool Layer - Nuovi Tool per Categorie
**Status**: 🔴 Non Iniziato
**Durata Stimata**: 2 giorni
**Dipendenze**: M1 completato

### M2.1 - Nuovi tool in risk_tools.py
**File**: `/opt/lang-env/GiAs-llm/tools/risk_tools.py`
**Status**: ✅ COMPLETATO (2026-01-09)

#### Passi:
- [x] **Step 2.1.1**: ✅ Implementare `analyze_nc_by_category` tool (COMPLETATO 2026-01-09)
- [x] **Step 2.1.2**: ✅ Implementare `predict_high_risk_categories` tool (COMPLETATO 2026-01-09)
- [x] **Step 2.1.3**: ✅ Test tool API e response format (COMPLETATO 2026-01-09)

**Test di Accettazione**:
- [x] ✅ Tool restituiscono JSON valido
- [x] ✅ Parametri ASL gestiti correttamente
- [x] ✅ Response in italiano ben formattato

### M2.2 - Aggiornamento tool esistenti
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 2.2.1**: Estendere `get_risk_based_priority` con breakdown categoria
- [ ] **Step 2.2.2**: Aggiornare `establishment_history` con dettagli NC
- [ ] **Step 2.2.3**: Test backwards compatibility

**Test di Accettazione**:
- [ ] API esistenti mantengono compatibilità
- [ ] Nuovi campi presenti negli output

---

## MILESTONE 3: Backend Orchestration - Intent e Response
**Status**: 🔴 Non Iniziato
**Durata Stimata**: 2 giorni
**Dipendenze**: M2 completato

### M3.1 - Nuovi intent per categorie NC
**File**: `/opt/lang-env/GiAs-llm/orchestrator/router.py`
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 3.1.1**: Aggiungere nuovi intent alla lista VALID_INTENTS
- [ ] **Step 3.1.2**: Aggiornare CLASSIFICATION_PROMPT con esempi
- [ ] **Step 3.1.3**: Test classification accuracy

**Test di Accettazione**:
- [ ] Classification > 90% accuracy su test set
- [ ] Slot extraction categoria funzionante
- [ ] Fallback per categorie non valide

### M3.2 - Aggiornamento workflow
**File**: `/opt/lang-env/GiAs-llm/orchestrator/graph.py`
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 3.2.1**: Implementare nuovi node methods
- [ ] **Step 3.2.2**: Aggiungere conditional edges
- [ ] **Step 3.2.3**: Test workflow end-to-end

**Test di Accettazione**:
- [ ] Workflow completa senza errori
- [ ] State management corretto
- [ ] Error handling appropriato

---

## MILESTONE 4: Frontend gchat - UI e UX
**Status**: 🔴 Non Iniziato
**Durata Stimata**: 1 giorno
**Dipendenze**: M3 completato

### M4.1 - Nuove domande pre-configurate
**File**: `/opt/lang-env/gchat/config/config.json`
**Status**: 🔴 Non Iniziato

#### Passi:
- [x] **Step 4.1.1**: ✅ Aggiungere domande categoria-specifiche al config (COMPLETATO 2026-01-09)
- [ ] **Step 4.1.2**: Test caricamento domande in UI
- [ ] **Step 4.1.3**: Verificare ordinamento e rendering

**Test di Accettazione**:
- [ ] Domande caricate correttamente nell'interfaccia
- [ ] Click e invio messaggi funzionanti
- [ ] Ordinamento rispettato

### M4.2 - Aggiornamento help e welcome
**Status**: 🔴 Non Iniziato

#### Passi:
- [x] **Step 4.2.1**: ✅ Aggiornare welcome_message con sezione NC (COMPLETATO 2026-01-09)
- [x] **Step 4.2.2**: ✅ Aggiornare help tool backend con funzionalità NC (COMPLETATO 2026-01-09)
- [ ] **Step 4.2.3**: Verificare responsiveness

**Test di Accettazione**:
- [ ] Markdown renderizzato correttamente
- [ ] UI responsive su desktop/mobile
- [ ] Testo help comprensibile

---

## MILESTONE 5: Testing e Validazione
**Status**: 🔴 Non Iniziato
**Durata Stimata**: 2 giorni
**Dipendenze**: M1-M4 completati

### M5.1 - Unit Testing
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 5.1.1**: Creare test suite per nuove funzioni DataAgent
- [ ] **Step 5.1.2**: Test per nuovi tool
- [ ] **Step 5.1.3**: Test intent classification
- [ ] **Step 5.1.4**: Raggiungere >95% coverage

### M5.2 - Integration Testing
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 5.2.1**: Test end-to-end domanda pre-configurata
- [ ] **Step 5.2.2**: Test query manuale categoria
- [ ] **Step 5.2.3**: Test con slice dati OCSE reali

### M5.3 - User Acceptance Testing
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 5.3.1**: Scenario operatore ASL cerca HACCP
- [ ] **Step 5.3.2**: Scenario analisi trend per reportistica
- [ ] **Step 5.3.3**: Scenario identificazione stabilimenti a rischio

---

## MILESTONE 6: Deployment e Monitoring
**Status**: 🔴 Non Iniziato
**Durata Stimata**: 1 giorno
**Dipendenze**: M5 completato

### M6.1 - Deployment Backend
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 6.1.1**: Update codebase GiAs-llm
- [ ] **Step 6.1.2**: Restart servizi LangGraph
- [ ] **Step 6.1.3**: Test health endpoints

### M6.2 - Deployment Frontend
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 6.2.1**: Update gchat config.json
- [ ] **Step 6.2.2**: Eseguire all.sh per rebuild
- [ ] **Step 6.2.3**: Test caricamento domande

### M6.3 - Monitoring Setup
**Status**: 🔴 Non Iniziato

#### Passi:
- [ ] **Step 6.3.1**: Setup analytics nuove domande
- [ ] **Step 6.3.2**: Monitor response time categoria NC
- [ ] **Step 6.3.3**: Alert per error rate nuovi intent

---

## Cronogramma di Implementazione

| Milestone | Durata | Dipendenze | Status | Data Inizio | Data Fine |
|-----------|--------|------------|---------|-------------|-----------|
| M1 - Data Layer | 3 giorni | - | 🔴 | - | - |
| M2 - Tool Layer | 2 giorni | M1 | 🔴 | - | - |
| M3 - Orchestration | 2 giorni | M2 | 🔴 | - | - |
| M4 - Frontend | 1 giorno | M3 | 🔴 | - | - |
| M5 - Testing | 2 giorni | M1-M4 | 🔴 | - | - |
| M6 - Deployment | 1 giorno | M5 | 🔴 | - | - |

**Totale Stimato**: 11 giorni lavorativi

---

## Log Implementazione

### 2026-01-09
- ✅ Creato documento piano implementazione
- ✅ **M1.1 COMPLETATO**: Estensione RiskAnalyzer (costanti NC, risk categorizzato, analisi trend)
- ✅ **M1.2 COMPLETATO**: Estensione DataRetriever (get_nc_by_category, get_establishments_with_nc_category)
- ✅ **M2.1 COMPLETATO**: Nuovi tool per categorie NC (analyze_nc_by_category, predict_high_risk_categories)
- ✅ **M4.1-M4.2 PARZIALE**: Aggiornamento gchat (4 nuove domande NC, welcome message, help tool backend)
- 🔄 **PROSSIMO**: M3 - Orchestration (Intent classification + workflow) o completare M4

---

## Note e Decisioni

### Categorie NC Identificate
1. RINTRACCIABILITÀ/RITIRO/RICHIAMO (16,850 casi) - 21%
2. IGIENE DEGLI ALIMENTI (16,653 casi) - 20%
3. ETICHETTATURA (10,115 casi) - 12%
4. CONDIZIONI DELLA STRUTTURA E DELLE ATTREZZATURE (9,803 casi) - 12%
5. CONDIZIONI DI PULIZIA E SANIFICAZIONE (5,109 casi) - 6%
6. RICONOSCIMENTO/REGISTRAZIONE (5,007 casi) - 6%
7. HACCP (4,283 casi) - 5%
8. IGIENE DELLE LAVORAZIONI (3,763 casi) - 5%
9. IGIENE DEL PERSONALE (2,896 casi) - 4%
10. LOTTA AGLI INFESTANTI (948 casi) - 1%
11. MOCA (244 casi) - <1%

### Pesi Categoria Decisi
- **HACCP**: 1.0 (massima criticità - sistema preventivo)
- **IGIENE DEGLI ALIMENTI**: 0.9 (alto rischio sanitario)
- **CONDIZIONI STRUTTURA**: 0.8
- **PULIZIA E SANIFICAZIONE**: 0.8
- **IGIENE LAVORAZIONI**: 0.7
- **RINTRACCIABILITÀ**: 0.6 (critico per gestione crisi)
- **IGIENE PERSONALE**: 0.5
- **REGISTRAZIONE**: 0.4 (amministrativo)
- **ETICHETTATURA**: 0.3 (meno critico per sicurezza)
- **INFESTANTI**: 0.5
- **MOCA**: 0.4