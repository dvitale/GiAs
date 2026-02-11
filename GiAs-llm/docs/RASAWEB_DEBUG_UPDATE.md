# Aggiornamento Debug Page GChat per LangGraph

## Completato ✅

Aggiornata la pagina di debug di GChat per riflettere l'architettura LangGraph eliminando i riferimenti a Rasa.

## File Creati

### 1. Template HTML Aggiornato
**Location**: `/opt/lang-env/gchat/template/debug_langgraph.html`

**Modifiche principali**:
- ✅ Badge "LangGraph + LLM" nell'header
- ✅ Pannello info architettura (LangGraph, LLM Router, Tools)
- ✅ Sezione "Intent Classification" invece di "Intent Predetto"
- ✅ Sezione "Tools Eseguiti" invece di "Actions Execute"
- ✅ Sezione "Conversation State" invece di "Contesto Utente"
- ✅ Sottotitoli esplicativi per ogni sezione

### 2. JavaScript Aggiornato
**Location**: `/opt/lang-env/gchat/statics/js/debug_langgraph.js`

**Modifiche principali**:
- ✅ Classe rinominata: `LangGraphDebugChatBot`
- ✅ Mappa Intent → Tools (13 intent supportati)
- ✅ Tool badges colorati per categoria (Piano, Search, Priority, Risk)
- ✅ Gestione ConversationState invece di Rasa Tracker
- ✅ Descrizioni user-friendly per ogni intent
- ✅ Indicatori "LLM Router" e "LangGraph workflow"

### 3. Documentazione
**Location**: `/opt/lang-env/gchat/DEBUG_PAGE_LANGGRAPH.md`

**Contenuto**:
- Confronto architetture Rasa vs LangGraph
- Dettagli di tutte le modifiche UI e JavaScript
- Intent supportati e tool categories
- Guida all'integrazione (2 opzioni)
- Testing e compatibilità

## Differenze Visuali

### Architettura Rasa → LangGraph

| Elemento | Prima (Rasa) | Dopo (LangGraph) |
|----------|--------------|------------------|
| **Header** | "Debug Mode" | "Debug Mode" + badge "LangGraph + LLM" |
| **Info box** | Nessuno | Architettura: LangGraph, Router: LLM, Tools |
| **Intent** | "Intent Predetto" | "Intent Classification (LLM Router)" |
| **Entities** | "Entities Estratte" | "Entities Estratte (Slots from intent)" |
| **Actions** | "Actions Execute" | "Tools Eseguiti (LangGraph tool nodes)" |
| **Slots** | "Contesto Utente" | "Conversation State (Metadata & Context)" |
| **Typing** | "Il bot sta scrivendo..." | "Il sistema sta elaborando..." |

### Tool Visualization

Nuova sezione con badge colorati:

```
🔧 Tools Eseguiti

┌─────────────────────────────────────┐
│ piano_description_tool    [piano]   │  🔵 Blu
│ search_piani_tool         [search]  │  🟢 Verde
│ priority_establishment    [priority]│  🟠 Arancione
│ risk_based_priority       [risk]    │  🔴 Rosso
└─────────────────────────────────────┘

→ Eseguito nel workflow LangGraph
```

### Intent Descriptions

Ogni intent ora mostra una descrizione chiara:

```
🎯 Intent Classification

ask_piano_description
Richiesta descrizione piano

━━━━━━━━━━━━━━━━━━━━━━━━━ 95%
Confidence: 95.0% (LLM Router)
```

## Integrazione in GChat

### Opzione 1: Sostituire File Esistenti (Consigliato)

```bash
# Backup Rasa version
cd /opt/lang-env/gchat
cp template/debug.html template/debug_rasa.html.bak
cp statics/js/debug.js statics/js/debug_rasa.js.bak

# Deploy LangGraph version
cp template/debug_langgraph.html template/debug.html
cp statics/js/debug_langgraph.js statics/js/debug.js

# Restart GChat
systemctl restart rasaweb
```

### Opzione 2: Route Separato

Mantenere entrambe le versioni con route separati:

```go
// In main.go
api.GET("/debug", serveDebugRasa)           // Versione Rasa (legacy)
api.GET("/debug/langgraph", serveDebugLangGraph)  // Versione LangGraph (nuova)
```

Accesso:
- Rasa: `http://localhost:8080/debug`
- LangGraph: `http://localhost:8080/debug/langgraph`

## Testing Completato

✅ **Tutti gli endpoint funzionanti**:
- `/model/parse` - Intent classification
- `/webhooks/rest/webhook` - Main webhook
- `/conversations/{id}/tracker` - Conversation state

✅ **Compatibilità 100%**:
- Stesso formato request/response
- Nessuna modifica backend necessaria
- Funziona con GiAs-llm API su porta 5005

✅ **UI verificata**:
- Layout responsive
- Tool badges visualizzati correttamente
- Intent descriptions chiare
- State display con metadata/slots

## Terminologia Aggiornata

| Rasa | LangGraph |
|------|-----------|
| Rasa NLU | LLM Router |
| Intent prediction | Intent classification |
| Rasa Core | LangGraph State Machine |
| Rasa Actions | Tool execution |
| Rasa Tracker | ConversationState |
| Action name | Tool name |
| Bot | Sistema |

## Intent Supportati (13 totali)

### Piano Tools (3)
1. `ask_piano_description` - Richiesta descrizione piano
2. `ask_piano_attivita` - Richiesta attività piano
3. `ask_piano_stabilimenti` - Richiesta stabilimenti piano

### Search Tools (1)
4. `search_piani_by_topic` - Ricerca piani per argomento

### Priority Tools (3)
5. `ask_priority_establishment` - Priorità basate su programmazione
6. `ask_delayed_plans` - Piani in ritardo
7. `ask_suggest_controls` - Suggerimenti controlli

### Risk Tools (1)
8. `ask_risk_based_priority` - Priorità basate su rischio storico

### System (5)
9. `greet` - Saluto
10. `goodbye` - Congedo
11. `ask_help` - Richiesta aiuto
12. `ask_piano_generic` - Richiesta generica su piano
13. `fallback` - Intent non riconosciuto

## Screenshot Conceptual

### Prima (Rasa)
```
┌──────────────────────────────────────┐
│ 🔍 Assistente Gias - Debug Mode     │
│ ───────────────────────────────────  │
│ Chat Area                            │
│                                      │
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│ 🎯 Intent Predetto                  │
│ ask_piano_description                │
│ ━━━━━━━━━━ 95%                      │
│                                      │
│ ⚡ Actions Execute                   │
│ action_piano_description             │
│                                      │
│ 💾 Contesto Utente                  │
│ asl: NA1                             │
└──────────────────────────────────────┘
```

### Dopo (LangGraph)
```
┌──────────────────────────────────────┐
│ 🔍 Debug Mode [LangGraph + LLM]     │
│ ───────────────────────────────────  │
│ Chat Area                            │
│                                      │
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│ 🏗️ Architettura: LangGraph          │
│ 🤖 Router: LLM-based                 │
│ 🔧 Tools: Piano, Priority, Risk      │
│ ───────────────────────────────────  │
│ 🎯 Intent Classification             │
│    (LLM Router)                      │
│ ask_piano_description                │
│ Richiesta descrizione piano          │
│ ━━━━━━━━━━ 95% (LLM Router)        │
│                                      │
│ 🔧 Tools Eseguiti                    │
│    (LangGraph tool nodes)            │
│ piano_description_tool [piano]🔵     │
│ → Eseguito nel workflow LangGraph    │
│                                      │
│ 💾 Conversation State                │
│    (Metadata & Context)              │
│ asl: NA1 (context)                   │
│ piano_code: A1 (extracted)           │
│ 💡 ConversationState da LangGraph    │
└──────────────────────────────────────┘
```

## Vantaggi

### 🎯 Chiarezza
- Mostra esplicitamente l'architettura LangGraph
- Elimina confusione con riferimenti a Rasa
- Descrizioni chiare per ogni componente

### 🔧 Trasparenza
- Visualizza quale tool viene eseguito
- Mappa chiara intent → tool → categoria
- Badge colorati per identificazione rapida

### 📊 Informazioni
- Distingue metadata da slots estratti
- Mostra fonte di ogni valore
- Spiega il workflow LangGraph

### 🎨 Design
- UI moderna e pulita
- Colori consistenti con brand
- Layout ottimizzato per debug

## Compatibilità Futura

✅ **Pronto per LLM reale**: Quando si implementerà LLaMA 3.1, l'UI già mostra "(LLM Router)"
✅ **Tool extensibility**: Facile aggiungere nuovi tools alla mappa
✅ **State evolution**: ConversationState può essere esteso senza modifiche UI
✅ **Multi-language**: Terminologia pronta per internazionalizzazione

## Conclusione

La debug page è stata completamente aggiornata per riflettere l'architettura LangGraph mantenendo 100% di compatibilità con l'API esistente.

**Nessuna modifica** richiesta al backend Go o all'API GiAs-llm.

---

**Data aggiornamento**: 2025-12-24
**Versione**: 1.0.0
**Compatibilità**: ✅ GiAs-llm API v1.0.0
**Status**: ✅ Production Ready
