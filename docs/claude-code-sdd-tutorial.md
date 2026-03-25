# Claude Code + Spec-Driven Development v2.0
## Guida completa: dal "vibe coding" allo sviluppo strutturato con AI

---

## Indice

1. [Cos'e' Claude Code?](#1-cose-claude-code)
2. [Cos'e' lo Spec-Driven Development?](#2-cose-lo-spec-driven-development)
3. [Perche' SDD + Claude Code?](#3-perche-sdd--claude-code)
4. [Installazione e Setup](#4-installazione-e-setup)
5. [La struttura template del progetto](#5-la-struttura-template-del-progetto)
6. [Fondamenta: il file CLAUDE.md](#6-fondamenta-il-file-claudemd)
7. [Il workflow SDD in 5 fasi](#7-il-workflow-sdd-in-5-fasi)
8. [Il workflow EARS: requisiti formali con /req e /implement](#8-il-workflow-ears-requisiti-formali-con-req-e-implement)
9. [Esempio pratico end-to-end](#9-esempio-pratico-end-to-end)
10. [Strumenti pronti all'uso](#10-strumenti-pronti-alluso)
11. [Livello intermedio: Slash Commands e Subagents](#11-livello-intermedio-slash-commands-e-subagents)
12. [Livello avanzato: Hooks e pipeline automatizzate](#12-livello-avanzato-hooks-e-pipeline-automatizzate)
13. [Risorse e documentazione](#13-risorse-e-documentazione)
14. [Riepilogo: quando usare SDD e quando no](#14-riepilogo-quando-usare-sdd-e-quando-no)

---

## 1. Cos'e' Claude Code?

Claude Code e' un assistente AI per lo sviluppo software che gira **nel terminale**, progettato per lo sviluppo **agentico** — cioe' non si limita a suggerire frammenti di codice, ma puo' pianificare, orchestrare workflow complessi, eseguire comandi bash, leggere l'intera codebase, aprire branch, fare commit e molto altro.

A differenza di Cursor o GitHub Copilot (che *augmentano* il workflow del developer), Claude Code mira a **sostituire intere porzioni del processo** di sviluppo in autonomia, lasciando all'umano il ruolo di *orchestratore* e *revisore*.

### Caratteristiche chiave

| Feature | Descrizione |
|---|---|
| **CLAUDE.md** | File di memoria persistente: la "costituzione" del progetto |
| **Subagents** | Istanze isolate di Claude per task paralleli o specializzati |
| **Slash Commands** | Shortcut testuali per workflow ripetibili (`/spec`, `/review`, `/req`, `/implement`) |
| **Hooks** | Script che si attivano a eventi del ciclo di vita (pre-commit, post-edit...) |
| **Skills** | Directory di istruzioni caricate automaticamente per contesto |
| **MCP Servers** | Integrazione con sistemi esterni (Slack, GitHub, database...) |
| **Task tool** | Meccanismo nativo per spawnare subagenti e gestire lavoro parallelo |

---

## 2. Cos'e' lo Spec-Driven Development?

Lo **Spec-Driven Development (SDD)** e' una metodologia che separa nettamente la **fase di pianificazione** dalla **fase di implementazione**.

L'idea di fondo: invece di dire all'AI "scrivi questa funzione", prima si produce una *specifica* — un documento strutturato che descrive cosa si sta costruendo, perche', come e con quali vincoli — e solo dopo si delega l'implementazione.

```
PRIMA (vibe coding)
  umano -> "fai X" -> Claude -> codice

DOPO (SDD)
  umano -> spec.md -> Claude -> requirements.md -> design.md -> tasks.md -> Claude -> codice
                      ^ review umano in ogni fase
```

### Le 3 domande che una spec deve rispondere

1. **COSA** si costruisce? (requisiti funzionali e non)
2. **COME** si costruisce? (architettura, tecnologie, pattern)
3. **QUANDO** e' fatto? (criteri di accettazione verificabili)

### Due livelli di formalismo

Questa guida presenta **due workflow complementari** che convivono nello stesso progetto:

| Workflow | Quando usarlo | Artefatti |
|----------|---------------|-----------|
| **SDD Specs** (`/spec`) | Feature nuove, componenti complessi | `docs/specs/` (spec, requirements, design, tasks) |
| **EARS Requirements** (`/req` + `/implement`) | Requisiti puntuali, bug fix strutturati, incrementi | `SDD/requirements/` + `SDD/traceability.md` |

Lo Spec workflow produce documentazione di progetto. Il workflow EARS produce requisiti formali tracciabili fino al codice sorgente.

---

## 3. Perche' SDD + Claude Code?

### Il problema del "vibe coding"

Il vibe coding — dare prompt vaghi e aspettarsi magia — funziona per progetti piccoli. Sui progetti reali crea:

- **Approvazione fatigue**: si finisce ad approvare ogni modifica senza capirla davvero
- **Context drift**: Claude "dimentica" l'architettura man mano che la conversazione si allunga
- **Debito tecnico silenzioso**: il codice funziona ma non e' manutenibile
- **Regressioni inspiegabili**: le modifiche si contraddicono a vicenda

### Come SDD risolve il problema

- **Review ai gate, non ad ogni micro-edit**: si approva la spec, non ogni singolo file
- **Memoria strutturata**: CLAUDE.md + doc di spec = Claude ricorda sempre il contesto
- **Parallelismo sicuro**: subagenti separati lavorano su task isolati senza contaminarsi
- **Artefatti vivi**: i documenti di spec restano nella repo come documentazione reale
- **Tracciabilita'**: ogni riga di codice e' collegata a un requisito formale tramite tag `# REQ: [ID]`

---

## 4. Installazione e Setup

### Prerequisiti

- **Node.js** >= 18 (verifica con `node --version`)
- Un account Anthropic con accesso a Claude Code (piano Pro o API key)
- Git installato e configurato

### Installazione

```bash
# Installazione globale via npm
npm install -g @anthropic-ai/claude-code

# Verifica
claude --version
```

> **Nota WSL/Debian**: se usi WSL come ambiente primario, assicurati che Node.js sia installato nel layer Linux (non Windows). Usa `nvm` per gestire le versioni:
>
> ```bash
> curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
> nvm install --lts
> npm install -g @anthropic-ai/claude-code
> ```

### Primo avvio

```bash
# Naviga nel tuo progetto
cd /path/to/mio-progetto

# Avvia Claude Code
claude
```

Al primo avvio ti verra' chiesto di autenticarti. Segui le istruzioni nel browser.

### Comandi essenziali da terminale

```bash
claude                  # Avvia una nuova sessione interattiva
claude --continue       # Riprende l'ultima sessione
claude --resume         # Mostra sessioni precedenti da scegliere
claude -p "prompt"      # Esegue un prompt non interattivo (utile per script)
claude --model opus     # Usa Claude Opus (piu' potente, piu' lento)
```

---

## 5. La Struttura Template del Progetto

Il template `project-template/` fornisce una struttura completa e pronta all'uso per qualsiasi nuovo progetto gestito con Claude Code + SDD.

### Albero della directory

```
project-template/
├── .claude/
│   └── commands/
│       ├── req.md              # Slash command /req — propone requisiti EARS
│       ├── implement.md        # Slash command /implement — implementa requisiti
│       ├── spec.md             # Slash command /spec — workflow SDD completo
│       └── review.md           # Slash command /review — code review strutturata
├── CLAUDE.md                   # Memoria persistente del progetto (personalizzare!)
├── .gitignore                  # Gitignore generico multi-linguaggio
├── SDD/
│   ├── README.md               # Guida alla directory SDD
│   ├── traceability.md         # Matrice requisito -> codice sorgente
│   └── requirements/
│       └── TEMPLATE.md         # Template per file di requisiti EARS
├── docs/
│   └── specs/
│       ├── README.md           # Guida ai template di specifica
│       ├── TEMPLATE-spec.md    # Template Fase 1: specifica iniziale
│       ├── TEMPLATE-requirements.md  # Template Fase 2: requisiti
│       ├── TEMPLATE-design.md  # Template Fase 3: design architetturale
│       └── TEMPLATE-tasks.md   # Template Fase 4: task breakdown
├── src/                        # Codice sorgente (struttura libera)
├── tests/
│   ├── unit/                   # Test unitari
│   ├── integration/            # Test di integrazione
│   ├── e2e/                    # Test end-to-end
│   └── fixtures/               # Dati di test
├── scripts/                    # Script di build, deploy, utility
└── configs/                    # File di configurazione
```

### Come usare il template

1. **Copia** la directory `project-template/` nella root del nuovo progetto
2. **Rinomina** e **personalizza** `CLAUDE.md` con le informazioni specifiche del progetto
3. **Adatta i prefissi** nella tabella dei componenti in CLAUDE.md ai moduli reali
4. **Aggiorna** `.claude/commands/req.md` con i prefissi personalizzati
5. **Inizializza** git e fai il primo commit

```bash
cp -r project-template/ /path/to/nuovo-progetto
cd /path/to/nuovo-progetto
git init
# Personalizza CLAUDE.md
claude  # Avvia Claude Code e inizia a lavorare
```

### Cosa contiene ogni componente

| Componente | Scopo | Quando si usa |
|------------|-------|---------------|
| `CLAUDE.md` | Memoria persistente di Claude per il progetto | Sempre — e' il primo file che Claude legge |
| `.claude/commands/` | Slash commands per automatizzare i workflow | `/spec`, `/req`, `/implement`, `/review` |
| `SDD/requirements/` | Requisiti formali EARS tracciabili | Ogni volta che si aggiunge/modifica una feature |
| `SDD/traceability.md` | Mappa requisito -> file:riga nel codice | Aggiornata ad ogni `/implement` |
| `docs/specs/` | Documenti di specifica per feature complesse | Quando si usa il workflow `/spec` |

---

## 6. Fondamenta: il file CLAUDE.md

Il `CLAUDE.md` e' il file piu' importante di tutto il setup. E' la **memoria persistente** di Claude per il tuo progetto: viene letto automaticamente all'inizio di ogni sessione.

### Dove metterlo

```
mio-progetto/
├── CLAUDE.md           <- root: istruzioni globali di progetto
├── src/
│   └── CLAUDE.md       <- opzionale: istruzioni specifiche per src/
└── tests/
    └── CLAUDE.md       <- opzionale: istruzioni specifiche per test
```

Esiste anche un `~/.claude/CLAUDE.md` **globale**, valido per tutti i progetti (utile per preferenze personali).

### Struttura consigliata

Il template in `project-template/CLAUDE.md` contiene tutte le sezioni consigliate:

- **Panoramica del Progetto** — cosa fa, per chi
- **Stack Tecnologico** — linguaggi, framework, database
- **Architettura** — layer principali e path della codebase
- **Convenzioni di Codice** — naming, lingua, formattazione
- **Workflow Git** — branch strategy, formato commit
- **Dipendenze Chiave** — librerie importanti e regole d'uso
- **Regole Importanti** — i "non fare" del progetto
- **Metodologia SDD** — comandi, prefissi requisiti, workflow
- **Stato Attuale** — ultima sessione, prossimi passi, known issues

### Best practice per CLAUDE.md

- **Aggiornalo attivamente**: alla fine di ogni sessione importante, chiedi a Claude di aggiornare il CLAUDE.md con cio' che e' cambiato
- **Non esagerare**: un CLAUDE.md da 25KB e' gestibile, da 100KB diventa controproducente
- **Includi "non fare"**: le regole negative sono spesso le piu' utili
- **Stato corrente**: la sezione sullo stato attuale evita che Claude riparta da zero ogni volta
- **Non duplicare**: se il progetto ha piu' CLAUDE.md (root + sotto-directory), ogni informazione va in un solo file

---

## 7. Il Workflow SDD in 5 Fasi

Questa e' la struttura centrale dello Spec-Driven Development. Ogni fase produce un artefatto in `docs/specs/` che diventa input della successiva, e **ogni artefatto viene revisionato dall'umano** prima di procedere.

```
Fase 1: SPEC INIZIALE     -> docs/specs/[feature]-spec.md
    | [review umano]
Fase 2: REQUIREMENTS      -> docs/specs/[feature]-requirements.md
    | [review umano]
Fase 3: DESIGN            -> docs/specs/[feature]-design.md
    | [review umano]
Fase 4: TASKS             -> docs/specs/[feature]-tasks.md
    | [review umano]
Fase 5: IMPLEMENTATION    -> codice in src/ + test in tests/
```

Per avviare il workflow completo, usa il comando:

```
/spec [nome-feature]
```

Il comando e' definito in `.claude/commands/spec.md` e guida Claude attraverso tutte le fasi, fermandosi ad ogni gate per la tua approvazione.

---

### Fase 1 — Spec Iniziale

**Obiettivo**: catturare in modo strutturato cosa si vuole costruire, prima ancora che Claude analizzi il codice.

**Template**: `docs/specs/TEMPLATE-spec.md`

**Sezioni chiave**:
- Problema da risolvere
- Obiettivo
- Scope (in scope / out of scope)
- Criteri di accettazione (verificabili e misurabili)
- Vincoli (tecnici, business, temporali)

**Prompt utile dopo la generazione**:
```
Leggi questo spec.md e dimmi:
1. Cosa non e' chiaro o potrebbe essere interpretato in modi diversi?
2. Ci sono assunzioni rischiose?
3. Hai domande prima di procedere?
```

---

### Fase 2 — Requirements

**Obiettivo**: trasformare la spec in requisiti formali, separando funzionali da non-funzionali.

**Template**: `docs/specs/TEMPLATE-requirements.md`

**Prompt**:
```
Analizza la spec approvata e genera un documento requirements strutturato.
Dividi in:
- Requisiti Funzionali (con ID tipo RF-001, RF-002...)
- Requisiti Non Funzionali (performance, sicurezza, scalabilita')
- Assunzioni esplicite
- Dipendenze esterne
```

---

### Fase 3 — Design

**Obiettivo**: definire *come* si implementa, a livello architetturale.

**Template**: `docs/specs/TEMPLATE-design.md`

**Prompt**:
```
Basandoti sui requirements approvati e sull'architettura descritta in CLAUDE.md,
crea un documento design che include:
- Architettura dei componenti coinvolti
- Schema del database (se applicabile)
- Definizione delle API (endpoint, payload, risposte)
- Diagramma di sequenza per i flussi principali (formato Mermaid)
- Decisioni architetturali e loro motivazione
- Alternative considerate e scartate (con perche')
```

---

### Fase 4 — Task Breakdown

**Obiettivo**: scomporre il design in task atomici, ordinati per dipendenze, assegnabili a singoli subagenti o sessioni.

**Template**: `docs/specs/TEMPLATE-tasks.md`

**Prompt**:
```
Basandoti sul design approvato, crea la lista completa dei task di implementazione.
Per ogni task:
- ID univoco (T-001, T-002...)
- Titolo breve
- Descrizione
- Dipendenze (altri task che devono essere completati prima)
- Criteri di completamento (come verifico che e' fatto)
- Stima dimensione: S/M/L
Ordina i task per poterli eseguire in sequenza o in parallelo dove possibile.
```

---

### Fase 5 — Implementazione

Con i task pronti, l'implementazione diventa istruttiva invece che creativa. Claude sa esattamente cosa fare.

**Prompt esempio per un task**:
```
Implementa il task T-002 come descritto in tasks.md.
Prima di iniziare, leggi il design per il contratto dell'API
e i requirements per i criteri di accettazione.
Dopo ogni file modificato, aggiorna lo status in tasks.md.
Non procedere al task successivo senza conferma.
```

---

## 8. Il Workflow EARS: Requisiti Formali con /req e /implement

Accanto al workflow per feature complesse (capitolo 7), il template include un sistema di **requisiti formali EARS** per gestire incrementi puntuali con piena tracciabilita'.

### Cos'e' la notazione EARS?

EARS (Easy Approach to Requirements Syntax) e' un metodo per scrivere requisiti non ambigui usando pattern predefiniti:

| Tipo | Pattern | Esempio |
|------|---------|---------|
| **Ubiquitous** | Il sistema deve [azione] | Il sistema deve loggare ogni errore con timestamp |
| **Event-Driven** | Quando [evento], il sistema deve [azione] | Quando l'utente fa login, il sistema deve creare una sessione |
| **State-Driven** | Mentre [stato], il sistema deve [azione] | Mentre offline, il sistema deve usare la cache locale |
| **Optional** | Dove [feature attiva], il sistema deve [azione] | Dove il modulo email e' attivo, il sistema deve notificare |
| **Unwanted** | Se [condizione indesiderata], il sistema deve [mitigazione] | Se il DB non risponde in 5s, il sistema deve fare fallback |

### Il flusso /req -> /implement

```
/req "descrizione informale"
    |
    v
Claude propone requisiti EARS formali (NON modifica file)
    |
    v
Umano approva / corregge
    |
    v
Requisiti salvati in SDD/requirements/[componente].md
    |
    v
/implement [ID-001, ID-002]
    |
    v
Claude implementa + aggiunge tag # REQ: [ID] nel codice
    |
    v
SDD/traceability.md aggiornata automaticamente
```

### Struttura SDD

```
SDD/
├── README.md                # Guida alla directory SDD
├── traceability.md          # Mappa: requisito -> file:riga -> status
└── requirements/
    ├── TEMPLATE.md          # Template per nuovi componenti
    ├── api-endpoints.md     # Requisiti del componente API (esempio)
    ├── database.md          # Requisiti del componente DB (esempio)
    └── ...                  # Un file per componente
```

### Prefissi requisiti

Ogni componente ha un prefisso univoco per gli ID. I prefissi vanno definiti nel CLAUDE.md del progetto e nel comando `/req`. Il template include prefissi generici:

| Prefisso | Componente |
|----------|------------|
| `GEN-` | Generale |
| `API-` | API / Endpoints |
| `UI-` | Interfaccia utente |
| `DB-` | Database / Modelli |
| `SEC-` | Sicurezza |
| `PERF-` | Performance |
| `INFRA-` | Infrastruttura |

Personalizzali in base ai componenti reali del tuo progetto.

### Tracciabilita'

Il file `SDD/traceability.md` mantiene la matrice completa:

```markdown
| ID       | Descrizione          | File:Riga              | Status          |
|----------|----------------------|------------------------|-----------------|
| API-001  | Endpoint di login    | src/api/auth.py:42     | IMPLEMENTATO    |
| API-002  | Rate limiting        | src/middleware/rate.py:8| IMPLEMENTATO   |
| DB-001   | Schema utenti        | src/models/user.py:15  | IMPLEMENTATO    |
| SEC-001  | Validazione input    |                        | DA IMPLEMENTARE |
```

Regole:
- Gli ID non vanno mai riutilizzati
- I requisiti rimossi vanno marcati come `RIMOSSO`, mai cancellati
- La traceability si aggiorna contestualmente al codice

---

## 9. Esempio Pratico End-to-End

Scenario: vuoi aggiungere **un modulo di notifiche email** a un'applicazione esistente.

### Step 1 — Setup iniziale (una tantum)

```bash
# Se il progetto non ha ancora la struttura SDD
cp -r project-template/.claude /path/to/progetto/
cp -r project-template/SDD /path/to/progetto/
cp -r project-template/docs/specs /path/to/progetto/docs/
# Personalizza CLAUDE.md
```

### Step 2 — Avvia il workflow spec

```bash
claude
```

```
/spec notifiche-email
```

Claude ti chiede dettagli. Tu descrivi:
```
Voglio un sistema di notifiche email transazionali. Deve inviare email
automaticamente in risposta a eventi di sistema (es. approvazione pratica,
rifiuto, promemoria scadenza). Template HTML per ogni tipo. Log dell'invio
nel DB con retry automatico in caso di errore.
```

Claude genera `docs/specs/notifiche-email-spec.md` e si ferma per la tua revisione.

### Step 3 — Genera requirements

Dopo aver approvato la spec:
```
Spec approvata. Procedi con i requirements.
```

Claude genera `docs/specs/notifiche-email-requirements.md`. Tu verifichi che i requisiti funzionali e non funzionali siano corretti.

### Step 4 — Design

```
Requirements approvati. Procedi con il design.
Tieni conto che usiamo gia' Redis nel progetto (vedi CLAUDE.md)
e potremmo usarlo come queue per le email.
```

Claude propone un'architettura con Redis come job queue e un worker asincrono. Tu rivedi, magari chiedi di semplificare, poi approvi.

### Step 5 — Task breakdown

```
Design approvato. Genera i task.
```

Claude genera `docs/specs/notifiche-email-tasks.md` con task atomici e dipendenze.

### Step 6 — Implementazione controllata

```
Implementa T-001 (modello EmailLog) e T-002 (servizio email base).
Usa il design come riferimento.
Dopo ogni task, aspetta la mia conferma prima di continuare.
Aggiorna tasks.md con lo status.
```

### Step 7 — Requisiti EARS per incrementi futuri

Mesi dopo, serve aggiungere un tipo di notifica. Invece di rifare tutto il workflow spec:

```
/req "Aggiungere notifica email per scadenza certificato. Deve partire 30 giorni
prima della scadenza e ripetersi ogni 7 giorni fino al rinnovo."
```

Claude propone un requisito EARS formale, tu approvi, poi:

```
/implement API-015
```

Il codice viene implementato con tag `# REQ: API-015` e la traceability aggiornata.

---

## 10. Strumenti Pronti all'Uso

### Il template di questo progetto (zero configurazione)

La directory `project-template/` di questo repository e' pronta all'uso:

```bash
cp -r project-template/ /path/to/nuovo-progetto
cd /path/to/nuovo-progetto
# Personalizza CLAUDE.md con i dettagli del tuo progetto
claude
```

Include gia': CLAUDE.md, slash commands (`/req`, `/implement`, `/spec`, `/review`), template SDD e template specifiche.

### Pacchetti npm alternativi

#### `claude-code-spec-workflow` (npm)

Installa un workflow SDD con slash commands predefiniti:

```bash
npx @pimzino/claude-code-spec-workflow

# Poi in Claude Code:
/spec-steering-setup    # Crea product.md, tech.md, structure.md
/spec feature-name      # Avvia il workflow completo
/bug-create issue       # Workflow dedicato ai bug fix
```

#### `cc-sdd` (npm) — stile Kiro

Ispirato all'approccio di AWS Kiro, supporta anche Cursor, Gemini CLI e altri:

```bash
npx cc-sdd

# Poi in Claude Code:
/kiro:spec-init "Feature con upload e tagging"
/kiro:spec-requirements feature-name
/kiro:spec-design feature-name -y
/kiro:spec-tasks feature-name -y
```

### Repository GitHub di riferimento

| Repository | Descrizione |
|---|---|
| `hesreallyhim/awesome-claude-code` | Lista curata di skills, hooks, commands, plugins |
| `disler/claude-code-hooks-mastery` | Esempi pratici di hooks per ogni evento |
| `shanraisshan/claude-code-best-practice` | Best practice documentate con esempi |
| `Pimzino/claude-code-spec-workflow` | Workflow SDD completo con dashboard |
| `gotalab/cc-sdd` | SDD multi-agent compatibile con vari tool |
| `swingerman/atdd` | Acceptance Test Driven Development per Claude Code |

---

## 11. Livello Intermedio: Slash Commands e Subagents

### Slash Commands

I **Slash Commands** sono prompt salvati che puoi richiamare con `/nome-comando`. Vivono in:

```
.claude/commands/          <- comandi di progetto (versionati nel repo)
~/.claude/commands/        <- comandi personali (tutti i progetti)
```

Il template include quattro comandi pronti:

| Comando | File | Scopo |
|---------|------|-------|
| `/req` | `.claude/commands/req.md` | Propone requisiti EARS da una descrizione informale |
| `/implement` | `.claude/commands/implement.md` | Implementa requisiti approvati con tag e traceability |
| `/spec` | `.claude/commands/spec.md` | Avvia il workflow SDD completo in 4 fasi con gate |
| `/review` | `.claude/commands/review.md` | Code review strutturata dell'ultimo commit |

#### Creare comandi personalizzati

Crea un file `.md` in `.claude/commands/`. Il nome del file diventa il nome del comando.

Esempio — `.claude/commands/test-coverage.md`:

```markdown
Analizza la copertura dei test per i file modificati negli ultimi 3 commit.
Per ogni file senza test corrispondente:
1. Identifica le funzioni pubbliche
2. Genera test unitari in tests/unit/
3. Verifica che tutti i test passino
```

Uso: `/test-coverage`

#### Parametri nei comandi

I comandi supportano il placeholder `$ARGUMENTS` che riceve il testo dopo il nome del comando:

```
/req Aggiungere supporto per l'export in CSV
      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      Questo testo finisce in $ARGUMENTS
```

### Subagents

I **Subagents** sono istanze isolate di Claude con il proprio system prompt, tool permissions e context window. Ideali per:

- **Ricerca parallela** su piu' aspetti di un problema
- **Task isolati** che non devono "contaminare" il contesto principale
- **Ruoli specializzati** (es. un agente che fa solo code review, uno che gestisce solo il DB)

#### Approccio 1: Master-Clone (consigliato per iniziare)

Metti tutto il contesto in CLAUDE.md e lascia che Claude spawni copie di se stesso con il `Task tool` quando serve. Nessuna configurazione richiesta.

```
Analizza il design.md e identifica task che possono essere eseguiti in parallelo.
Per ognuno, usa il Task tool per spawnare un subagente separato.
Aspetta che tutti completino e riportami un summary.
```

#### Approccio 2: Subagents specializzati

Crea file in `.claude/agents/`. Esempio — `.claude/agents/spec-writer.md`:

```yaml
---
name: spec-writer
description: Usa questo agente per scrivere specifiche tecniche
tools: Read, Write
model: sonnet
---
Sei un esperto di specifiche tecniche per sistemi software.
Il tuo compito e' trasformare descrizioni informali in documenti di specifica strutturati.

Quando ti viene assegnato un task:
1. Chiedi chiarimenti se la descrizione e' ambigua
2. Produci una spec nel formato standard del progetto (vedi docs/specs/TEMPLATE-spec.md)
3. Esplicita sempre gli assunti che stai facendo
4. Segnala i rischi tecnici che vedi

Non scrivere mai codice. Il tuo output e' solo documentazione.
```

Invocazione:
```
Usa il subagente spec-writer per trasformare questa richiesta in una spec formale:
"Voglio un sistema che invii promemoria automatici quando una pratica
e' in attesa di firma da piu' di 48 ore"
```

---

## 12. Livello Avanzato: Hooks e Pipeline Automatizzate

Gli **Hooks** sono script che si eseguono automaticamente in risposta a eventi del ciclo di vita di Claude Code.

Vivono in `.claude/settings.json` (progetto) o `~/.claude/settings.json` (globale).

### Tipi di Hook

| Hook | Quando si attiva | Puo' bloccare? |
|---|---|---|
| `PreToolUse` | Prima che Claude usi uno strumento | si' |
| `PostToolUse` | Dopo che Claude usa uno strumento | no |
| `Stop` | Quando Claude termina la risposta | si' |
| `SubagentStop` | Quando un subagente termina | si' |
| `SessionStart` | All'inizio di ogni sessione | no |

### Esempio: auto-lint dopo ogni modifica

Crea `.claude/hooks/post-edit-lint.sh`:

```bash
#!/bin/bash
# Riceve il contesto dello strumento da stdin (JSON)
FILE=$(echo $1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('path',''))")

if [[ "$FILE" == *.py ]]; then
    ruff check "$FILE" --fix
    echo "Lint completato per $FILE"
elif [[ "$FILE" == *.js || "$FILE" == *.ts ]]; then
    npx eslint "$FILE" --fix
    echo "Lint completato per $FILE"
fi
```

Configura in `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/post-edit-lint.sh"
          }
        ]
      }
    ]
  }
}
```

### Esempio: bloccare commit senza test

Crea `.claude/hooks/pre-commit-check.sh`:

```bash
#!/bin/bash
# Verifica che esistano test per i file sorgente modificati

STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|js|ts)$' | grep -v 'test')

if [ -n "$STAGED" ]; then
    for f in $STAGED; do
        # Adatta il pattern al tuo progetto
        TESTDIR="tests/unit"
        BASENAME=$(basename "$f" | sed 's/\.[^.]*$//')
        if ! find "$TESTDIR" -name "*${BASENAME}*" | grep -q .; then
            echo "Mancano test per: $f"
            exit 2  # Exit code 2 = blocca e mostra errore a Claude
        fi
    done
fi
```

### Pipeline SDD completa con Hooks e Subagents

Per team o progetti complessi, si puo' costruire una vera pipeline:

```
[Hook: SessionStart] -> carica contesto progetto
         |
/spec comando -> spec-writer subagent produce spec.md
         |
[Hook: PostToolUse Write] -> valida formato spec
         |
requirements-analyst subagent -> requirements.md
         |
architect subagent -> design.md
         |
task-planner subagent -> tasks.md
         |
implementer subagent (per ogni task)
         |
[Hook: PreToolUse Bash(git commit)] -> blocca se test non passano
         |
code-reviewer subagent -> review finale
```

---

## 13. Risorse e Documentazione

### Documentazione Ufficiale

| Risorsa | URL |
|---|---|
| Claude Code Docs | `https://docs.claude.ai/en/docs/claude-code` |
| Best Practices (Anthropic) | `https://anthropic.com/engineering` |
| Subagents Docs | `https://code.claude.com/docs/en/sub-agents` |

### Articoli Fondamentali

| Titolo | Autore | Perche' leggerlo |
|---|---|---|
| "Spec-Driven Development with Claude Code in Action" | Alex Opalic (alexop.dev) | Esempio pratico reale, workflow completo |
| "How I Use Every Claude Code Feature" | Shrivu Shankar (blog.sshh.io) | Overview esaustiva di tutti i tool |
| "Best Practices for Claude Code Subagents" | PubNub Blog | Pipeline subagent per team |
| "Spec-Driven Development: The Waterfall Strikes Back" | Marmelab | Critica bilanciata: quando SDD NON conviene |
| "Understanding Claude Code's Full Stack" | Alex Opalic (alexop.dev) | MCP, Skills, Subagents, Hooks spiegati insieme |

### Repository GitHub da bookmarkare

```
hesreallyhim/awesome-claude-code     -> la lista piu' completa di risorse
disler/claude-code-hooks-mastery     -> hooks con esempi per ogni evento
Pimzino/claude-code-spec-workflow    -> workflow SDD pronto all'uso
gotalab/cc-sdd                       -> SDD multi-agente stile Kiro
shanraisshan/claude-code-best-practice -> best practice documentate
```

---

## 14. Riepilogo: Quando Usare SDD e Quando No

### SDD vale la pena quando...

- Il progetto dura **piu' di qualche giorno**
- Lavori su una **codebase esistente** con vincoli architetturali
- **Piu' persone** usano Claude Code sullo stesso progetto
- I requisiti sono **complessi o soggetti a revisioni**
- Hai bisogno di **documentazione** come output del processo (audit, compliance, ecc.)
- Stai costruendo qualcosa che andra' in **produzione**
- Serve **tracciabilita'** tra requisiti e codice

### SDD e' overkill quando...

- Stai esplorando un'idea in un **prototipo usa-e-getta**
- Il progetto e' piccolissimo (< 1 giorno di lavoro)
- I requisiti sono **banali e stabili** ("aggiungi un campo al form")
- Stai imparando una nuova tecnologia e vuoi **sperimentare liberamente**

### La via di mezzo: SDD leggero

Anche senza il workflow completo, puoi adottare i principi chiave:

1. **Scrivi sempre un CLAUDE.md** — anche minimo, aiuta enormemente
2. **Prima la spec, poi il codice** — anche solo 5 righe di contesto
3. **Usa `/req` per i requisiti importanti** — anche senza fare `/spec` completo
4. **Committa in piccoli passi** — ogni task completato = un commit
5. **Aggiorna CLAUDE.md** — a ogni sessione importante
6. **Tieni la traceability** — sapere quale codice implementa quale requisito e' sempre utile

---

### Differenze rispetto alla v1.0

| Aspetto | v1.0 | v2.0 |
|---------|------|------|
| Template | Solo esempi inline | Directory `project-template/` completa e pronta all'uso |
| Workflow | Solo spec -> req -> design -> tasks | Due workflow: SDD Specs (`/spec`) + EARS Requirements (`/req` + `/implement`) |
| Tracciabilita' | Non presente | `SDD/traceability.md` con matrice requisito -> codice |
| Slash Commands | Esempi da copiare manualmente | 4 comandi pronti in `.claude/commands/` |
| Notazione requisiti | Informale | EARS (Easy Approach to Requirements Syntax) |
| Scope | Legato a un progetto specifico | Template generalizzato per qualsiasi progetto |

---

*Tutorial v2.0 — Marzo 2026*
*Basato su: documentazione Anthropic, alexop.dev, blog.sshh.io, PubNub Engineering, marmelab.com e community GitHub*
