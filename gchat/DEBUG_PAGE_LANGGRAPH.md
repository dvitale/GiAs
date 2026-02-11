# Debug Page per LangGraph Architecture

## Panoramica

Questa directory contiene due versioni della pagina di debug:

1. **`debug.html` + `debug.js`** - Versione originale per Rasa
2. **`debug_langgraph.html` + `debug_langgraph.js`** - Nuova versione per GiAs-llm (LangGraph)

## Differenze Architetturali

### Rasa (Originale)
```
User Message
    ↓
Rasa NLU (ML-based)
    ↓
Rasa Core (Stories)
    ↓
Rasa Actions
    ↓
Rasa Tracker
    ↓
Response
```

### LangGraph (Nuova)
```
User Message
    ↓
LLM Router (Prompt-based)
    ↓
LangGraph State Machine
    ↓
Tool Execution (Piano, Priority, Risk, Search)
    ↓
ConversationState
    ↓
LLM Response Generation
```

## Modifiche alla UI

### Header
**Prima (Rasa)**:
```html
<h1>🔍 Assistente Gias - Debug Mode</h1>
```

**Dopo (LangGraph)**:
```html
<h1>
    🔍 Assistente Gias - Debug Mode
    <span class="architecture-badge">LangGraph + LLM</span>
</h1>
```

### Pannello Informazioni Architettura
**Nuovo elemento aggiunto**:
```html
<div class="architecture-info">
    <strong>🏗️ Architettura:</strong> LangGraph State Machine<br>
    <strong>🤖 Router:</strong> LLM-based Intent Classification<br>
    <strong>🔧 Tools:</strong> Piano, Priority, Risk, Search
</div>
```

### Sezione Intent
**Prima**:
```html
<h3>🎯 Intent Predetto</h3>
```

**Dopo**:
```html
<h3>
    🎯 Intent Classification
    <div class="section-subtitle">LLM Router (pattern-based)</div>
</h3>
```

**Visualizzazione confidence aggiornata** per mostrare "(LLM Router)" invece di riferimenti a Rasa NLU.

### Sezione Entities
**Prima**:
```html
<h3>🏷️ Entities Estratte</h3>
```

**Dopo**:
```html
<h3>
    🏷️ Entities Estratte
    <div class="section-subtitle">Slots from intent classification</div>
</h3>
```

### Sezione Actions → Tools
**Prima**:
```html
<h3>⚡ Actions Execute</h3>
<div id="actionsDisplay">...</div>
```

**Dopo**:
```html
<h3>
    🔧 Tools Eseguiti
    <div class="section-subtitle">LangGraph tool nodes</div>
</h3>
<div id="toolsDisplay">...</div>
```

**Nuovo: Tool badges con colori per categoria**:
- Piano tools: Blu (#3b82f6)
- Search tools: Verde (#10b981)
- Priority tools: Arancione (#f59e0b)
- Risk tools: Rosso (#ef4444)

### Sezione Slots → State
**Prima**:
```html
<h3>💾 Contesto Utente</h3>
<div id="slotsDisplay">...</div>
```

**Dopo**:
```html
<h3>
    💾 Conversation State
    <div class="section-subtitle">Metadata & Context</div>
</h3>
<div id="stateDisplay">...</div>
```

**Footer aggiunto**:
```html
💡 ConversationState gestito da LangGraph
```

## Modifiche JavaScript

### Classe Rinominata
```javascript
// Prima
class DebugChatBot { ... }

// Dopo
class LangGraphDebugChatBot { ... }
```

### Mappa Intent → Tools
**Nuovo mapping aggiunto**:
```javascript
const intentToTool = {
    'ask_piano_description': { name: 'piano_description_tool', category: 'piano' },
    'ask_piano_attivita': { name: 'piano_attivita_tool', category: 'piano' },
    'ask_piano_stabilimenti': { name: 'piano_stabilimenti_tool', category: 'piano' },
    'search_piani_by_topic': { name: 'search_piani_tool', category: 'search' },
    'ask_priority_establishment': { name: 'priority_establishment_tool', category: 'priority' },
    'ask_risk_based_priority': { name: 'risk_based_priority_tool', category: 'risk' },
    'ask_delayed_plans': { name: 'delayed_plans_tool', category: 'priority' },
    'ask_suggest_controls': { name: 'suggest_controls_tool', category: 'priority' }
};
```

### Metodi Aggiornati

**`updateToolsDisplay(response)` - Nuovo**:
- Mappa intent a tool eseguito
- Mostra badge colorato per categoria
- Indica "Eseguito nel workflow LangGraph"

**`updateStateDisplay(response)` - Modificato**:
- Gestisce ConversationState invece di Rasa Tracker
- Distingue tra metadata (context) e slots (extracted)
- Mostra footer "ConversationState gestito da LangGraph"

**`updateIntentDisplay(response)` - Migliorato**:
- Aggiunge descrizioni user-friendly per ogni intent
- Mostra "(LLM Router)" nel confidence
- Mappa completa degli intent disponibili

### Testo Typing Indicator
**Prima**:
```javascript
<span>Il bot sta scrivendo...</span>
```

**Dopo**:
```javascript
<span>Il sistema sta elaborando...</span>
```

## Intent Supportati

La debug page riconosce e visualizza 13 intent:

1. **ask_piano_description** - Richiesta descrizione piano
2. **ask_piano_attivita** - Richiesta attività piano
3. **ask_piano_stabilimenti** - Richiesta stabilimenti piano
4. **search_piani_by_topic** - Ricerca piani per argomento
5. **ask_priority_establishment** - Priorità basate su programmazione
6. **ask_risk_based_priority** - Priorità basate su rischio
7. **ask_delayed_plans** - Piani in ritardo
8. **ask_suggest_controls** - Suggerimenti controlli
9. **greet** - Saluto
10. **goodbye** - Congedo
11. **ask_help** - Richiesta aiuto
12. **fallback** - Intent non riconosciuto
13. **ask_piano_generic** - Richiesta generica su piano

## Tool Categories

Ogni tool è categorizzato visivamente:

| Categoria | Colore | Tools |
|-----------|--------|-------|
| **piano** | 🔵 Blu | piano_description, piano_attivita, piano_stabilimenti |
| **search** | 🟢 Verde | search_piani |
| **priority** | 🟠 Arancione | priority_establishment, delayed_plans, suggest_controls |
| **risk** | 🔴 Rosso | risk_based_priority |

## File Structure

```
/opt/lang-env/gchat/
├── template/
│   ├── debug.html              # Versione corrente
│   └── debug_langgraph.html    # Versione LangGraph (nuova)
├── statics/js/
│   ├── debug.js                # JS corrente
│   └── debug_langgraph.js      # JS LangGraph (nuovo)
└── DEBUG_PAGE_LANGGRAPH.md     # Questa documentazione
```

## Integrazione

Per usare la nuova debug page con GiAs-llm:

### Opzione 1: Sostituire i file esistenti
```bash
# Backup versione originale
cp /opt/lang-env/gchat/template/debug.html /opt/lang-env/gchat/template/debug_backup.html
cp /opt/lang-env/gchat/statics/js/debug.js /opt/lang-env/gchat/statics/js/debug_backup.js

# Sostituire con versione LangGraph
cp /opt/lang-env/gchat/template/debug_langgraph.html /opt/lang-env/gchat/template/debug.html
cp /opt/lang-env/gchat/statics/js/debug_langgraph.js /opt/lang-env/gchat/statics/js/debug.js
```

### Opzione 2: Route separato
Modificare `main.go` per servire entrambe le versioni:

```go
// Debug page Rasa (legacy)
api.GET("/debug", func(c *gin.Context) {
    // ... esistente ...
    c.HTML(http.StatusOK, "debug.html", templateData)
})

// Debug page LangGraph (nuovo)
api.GET("/debug/langgraph", func(c *gin.Context) {
    // ... stesso codice ...
    c.HTML(http.StatusOK, "debug_langgraph.html", templateData)
})
```

## Testing

La debug page è stata testata con:

```bash
# Test parse endpoint
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "quali attività ha il piano A1?", "metadata": {"asl": "NA1"}}'

# Test webhook
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "descrivi piano A1", "metadata": {"asl": "NA1"}}'

# Test tracker
curl http://localhost:5005/conversations/test/tracker
```

Tutti gli endpoint sono compatibili al 100% con la versione Rasa.

## Vantaggi della Nuova Versione

### 🎯 Chiarezza Architetturale
- Mostra esplicitamente che si usa LangGraph invece di Rasa
- Badge "LangGraph + LLM" visibile nell'header
- Informazioni architettura nel pannello

### 🔧 Tool Visualization
- Mappa chiara intent → tool
- Badge colorati per categoria
- Indica quale tool viene eseguito nel workflow

### 💾 State Management
- Distingue tra metadata e slots estratti
- Mostra fonte di ogni valore (context vs extracted)
- Footer che spiega ConversationState

### 📊 Intent Descriptions
- Descrizioni user-friendly per ogni intent
- Indica che usa LLM Router
- Mappa completa degli intent supportati

### 🎨 Visual Design
- Colori aggiornati (viola invece di rosso/viola)
- Badge e label più informativi
- Layout ottimizzato per tool display

## Compatibilità

✅ **Completamente compatibile** con l'API GiAs-llm
✅ **Nessuna modifica** necessaria al backend Go
✅ **Stesso formato** request/response
✅ **Stessi endpoint** utilizzati

L'unica differenza è nella **visualizzazione e terminologia** per riflettere l'architettura LangGraph.

---

**Data**: 2025-12-24
**Versione**: 1.0.0
**Status**: ✅ Production Ready
