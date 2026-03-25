# Theme System

**Componente**: Frontend (gchat)
**Provenienza**: Reverse-engineering 2026-03-09
**File sorgente analizzati**: statics/css/style.css, statics/js/chat.js (initializeTheme, toggleTheme), statics/js/history.js (initTheme)

## Requisiti Funzionali

### TS-01 Sistema temi light/dark con CSS variables
- **Pattern EARS**: Il sistema DEVE supportare due temi: light (default, palette warm/beige con accent `#d4a574`) e dark (palette `#1a1a1a` con accent viola `#8b5cf6`), attivato dalla classe CSS `dark-theme` su body. QUANDO il tema cambia, DEVE sovrascrivere le variabili CSS root (--bg-primary, --bg-secondary, --text-primary, --accent-color, --shadow-*, etc.) tramite il selettore `body.dark-theme`.
- **Status**: IMPLEMENTATO
- **Accorpa**: TS-01, TS-02

### TS-03 Persistenza e ripristino tema da localStorage
- **Pattern EARS**: QUANDO l'utente cambia tema, il sistema DEVE salvare la preferenza in localStorage con chiave `theme` e valore `dark` o `light`. QUANDO la pagina si carica, DEVE leggere la preferenza e, se il valore e' `dark`, aggiungere la classe `dark-theme` al body.
- **Status**: IMPLEMENTATO
- **Accorpa**: TS-03, TS-04

### TS-05 Transizioni, icona toggle e header gradients
- **Pattern EARS**: Il sistema DEVE applicare transizioni di 0.3s ease su background-color, border-color e color per un cambio tema fluido. QUANDO il tema e' light, DEVE mostrare l'icona sole (sun-icon); quando dark, l'icona luna (moon-icon). QUANDO il tema e' light, l'header DEVE avere gradiente `#c49464 -> #a07850`; quando dark, gradiente `#1e1e1e -> #2d2d2d`.
- **Status**: IMPLEMENTATO
- **Accorpa**: TS-05, TS-06, TS-07

### TS-08 Tema Consistente tra Pagine
- **Pattern EARS**: Il sistema DEVE inizializzare il tema da localStorage su tutte le pagine (index, history, debug, debug_langgraph) per mantenere la preferenza utente.
- **Status**: IMPLEMENTATO

### TS-09 Admin/Analytics/Monitor Dark-Only
- **Pattern EARS**: Le pagine analytics, monitor e admin_rag DEVONO utilizzare esclusivamente il tema dark con palette dedicata (--bg-primary: #0f172a, gradiente sfondo indaco/slate).
- **Status**: IMPLEMENTATO

### TS-10 Dark Theme ASL Badge
- **Pattern EARS**: QUANDO il tema e' dark, il badge ASL nell'header DEVE usare sfondo `rgba(139, 92, 246, 0.3)` (viola) al posto dello sfondo bianco trasparente del tema light.
- **Status**: IMPLEMENTATO

## Requisiti Non Funzionali

### TS-NF01 No Flash of Unstyled Content
- **Pattern EARS**: Il sistema DEVE applicare il tema salvato il prima possibile al caricamento per evitare flash visivi del tema sbagliato.
- **Status**: IMPLEMENTATO
- **Note**: L'inizializzazione avviene nel costruttore della classe ChatBot o in un blocco script inline immediatamente dopo il body.
