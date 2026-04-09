# GChat - Interfaccia Web per Chatbot GIAS

Programma Golang che fornisce un'interfaccia web per il chatbot GIAS (sistema integrato LangGraph + LLM).

## Regole di Sviluppo

- **Test vs Backend**: Quando un test evidenzia un problema del backend, correggi SEMPRE il backend — mai il test.

## Struttura del Progetto

- **app/**: Sorgenti Go
  - `main.go`: Entry point, routing HTTP (Gin), template
  - `llm_client.go`: Client HTTP backend + `ProxyChatLogAPI` + `ProxyAdminAPI`
  - `config.go`: Gestione configurazione JSON
  - `personale.go`: Lookup dati personale via API backend (tabella DB `personale`)
  - `session.go`: Session middleware cookie-based (gin-contrib/sessions), `MergeSessionParams()`
  - `transcribe.go`: Trascrizione audio (speech-to-text)
- **statics/**: Asset statici (CSS, JS, immagini, PWA: `sw.js`, `manifest.webmanifest`, `offline.html`)
- **template/**: HTML templates (index, history, debug, debug_langgraph, analytics, monitor, admin_schema, admin_rag)
- **config/**: `config.json` (server, llm_server, ui, predefined_questions)
- **data/**: (vuoto — dati personale ora dal DB PostgreSQL)
- **SDD/**: Requisiti EARS + traceability

## Comandi

```bash
./all.sh        # build + stop + run (COMANDO PRINCIPALE)
./build.sh      # solo compilazione
./run.sh        # solo avvio (nohup)
./stop.sh       # stop
./status.sh     # health check
```

## Endpoint (:8080)

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/gias/webchat/` | GET | UI chat |
| `/gias/webchat/chat` | POST | Invio messaggio |
| `/gias/webchat/chat/stream` | POST | Invio messaggio streaming (SSE) |
| `/gias/webchat/history` | GET | Cronologia chat |
| `/gias/webchat/api/chat-log/*` | GET | Proxy API chat-log (evita CORS) |
| `/gias/webchat/api/admin/*` | GET/POST/PUT/DELETE | Proxy API admin |
| `/gias/webchat/debug` | GET | Debug mode (intent/entity/slot) |
| `/gias/webchat/debug/langgraph` | GET | LangGraph workflow visualizer |
| `/gias/webchat/analytics` | GET | Dashboard analytics |
| `/gias/webchat/monitor` | GET | Monitor qualita' conversazioni |
| `/gias/webchat/admin/schema` | GET | Admin schema metadata |
| `/gias/webchat/manifest.webmanifest` | GET | PWA manifest |
| `/gias/webchat/sw.js` | GET | Service Worker PWA |

## Comunicazione Go ↔ Backend

```
Browser (:8080) → Go (Gin) → Python (:5005)
```

- **Chat**: `SendToLLMV1()` → `POST /api/v1/chat` (payload: `NativeChatMessage` con sender, message, metadata)
- **Streaming**: `HandleChatStream()` → `POST /api/v1/chat/stream` (SSE proxy)
- **CORS proxy**: `ProxyChatLogAPI()` (solo GET, `/api/chat-log/*`), `ProxyAdminAPI()` (GET/POST/PUT/DELETE, `/api/admin/*`)
- **Health check**: `CheckLLMServerHealth()` → `GET /` con cache 30s/5s

### Flusso metadata utente

```
Query String URL / POST body
    ↓
MergeSessionParams() — priorita' POST > Query > Session cookie (TTL 5 min)
    ↓
Template HTML — injection in window.queryParams
    ↓
JavaScript chat.js — read queryParams + UOC auto → POST body
    ↓
Go Handler /chat — extract JSON, build NativeUserMetadata, lookup UOC da API backend (tabella personale DB)
    ↓
Backend /api/v1/chat — metadata: {asl, asl_id, user_id, codice_fiscale, username, uoc, lat, lon}
```

## Note chiave

- **Timeout chain**: JS (75s) > Go (60s) > Backend streaming (120s). Il client deve avere timeout maggiore del server
- **Sessioni**: Cookie-based, TTL 5 min, cookie path `/gias/webchat`, HttpOnly, SameSite=Lax
- **Access control**: chatbot bloccato senza `user_id` + `asl`. Frontend: `hasRequiredMetadata()`. Backend: HTTP 403
- **PWA**: Service Worker con cache-first (statici) e network-first (API), install banner configurabile (`ui.pwa_install_message`)
- **GPS**: on-demand via `acquireGPS()`, coordinate nel payload chat (mai loggate/persistite per GDPR)
- **Markdown tables**: `chat.js` renderizza tabelle markdown (`| col | col |`) come `<table>` HTML con allineamento (`:---:`, `---:`), hover e dark theme. CSS in `new-formatting.css` (`.md-table`, `.table-wrapper`)
- **Tema**: light (oro/ambra) / dark (slate/indaco), persistenza localStorage
- **Debug API**: comandi curl auto-generati in `log/gias_api_debug.log`
- **Logging**: prefissi strutturati (CHAT_, LLM_, LLM_HEALTH_, USER_, INDEX_, HISTORY_, ANALYTICS_, MONITOR_, CHATLOG_PROXY_)

## Regole di manutenzione

Questo file e' la **fonte di verita' unica** per i dettagli frontend gchat. Vedere regole in `../CLAUDE.md`.

Aggiornare questo file se tocchi: file Go in `app/`, endpoint/route, template, session/parametri, configurazione timeout, funzionalita' JS, route proxy. Aggiornare `SDD/traceability.md` per nuovi requisiti implementati.
DISTILLED_AESTHETICS_PROMPT = """
<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration.

Motion: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context. Vary between light and dark themes, different fonts, different aesthetics. You still tend to converge on common choices (Space Grotesk, for example) across generations. Avoid this: it is critical that you think outside the box!
</frontend_aesthetics>
"""