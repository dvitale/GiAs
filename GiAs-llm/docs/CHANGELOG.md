# Changelog - GiAs-llm

Tutte le modifiche notevoli a questo progetto saranno documentate in questo file.

Il formato si basa su [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] - 2025-12-25

### Aggiunto
- **Domande help cliccabili**: Le domande di esempio nell'help ora usano la sintassi `[testo]` che GChat rende automaticamente cliccabile
- **Gestione errori formattata**: Tutti i tool ora restituiscono `formatted_response` anche per gli errori, mostrando messaggi user-friendly in italiano invece di raw dict
- **Test validazione domande predefinite**: Tutte le 8 domande predefinite da `/opt/lang-env/gchat/config/config.json` validate e funzionanti

### Modificato
- `orchestrator/graph.py`: Domande di esempio nell'help cambiate da `"testo"` a `[testo]` (righe 138-141)
- `tools/piano_tools.py`: Aggiunti `formatted_response` a tutti i path di errore (9 modifiche)
  - Piano code non specificato
  - Piano non trovato
  - Nessun controllo trovato
  - Nessuno stabilimento trovato
  - Nessuna attività correlata trovata
  - Codici piano mancanti per confronto
  - Azione non riconosciuta
  - Errori generici in piano_tool

### Documentazione
- Aggiornato `README.md` versione 1.1.0
- Aggiornato `BUGFIX_REPORT.md` con nuovi bug risolti (§7 Help non cliccabile, §8 Errori raw dict)
- Creato `CHANGELOG.md` per tracciamento modifiche

### Test
- ✅ Test help cliccabile: domande `[...]` funzionano in GChat
- ✅ Test errore A1_M: messaggio formattato invece di `{'error': '...', 'piano_code': '...'}`
- ✅ 8/8 domande predefinite passano i test

---

## [1.0.0] - 2025-12-24

### Aggiunto
- Migrazione completa da Rasa a LangGraph
- FastAPI server con endpoint Rasa-compatible (webhook, parse, tracker, status)
- LangGraph workflow con 13 intent supportati
- 4 categorie di tool: piano, priority, risk, search
- Risoluzione automatica UOC da user_id usando personale.csv (1880 record)
- Caricamento dataset CSV: 323,146 record totali
- Debug page integrata con GChat

### Risolto
- **Bug critico**: Tutte le query restituivano fallback universale
  - Causa: API richiedeva `final_response`, graph restituiva `response`
  - Soluzione: Allineata chiave in `app/api.py:95`
- **StructuredTool non callable**: Decorator LangChain non gestito
  - Soluzione: Accesso a `.func` in search_tools, priority_tools, risk_tools
- **Intent misclassification**: Pattern matching su prompt completo
  - Soluzione: Estrazione corretta user_message in `llm/client.py`
- **UOC non specificata**: Metadata GChat senza campo UOC
  - Soluzione: `get_uoc_from_user_id()` in `agents/data.py`
- **Help pattern mancante**: "Cosa posso chiederti?" non riconosciuto
  - Soluzione: Aggiunti pattern "cosa posso", "come posso", "come puoi"
- **Piano con underscore**: A11_F non matchato da regex
  - Soluzione: Regex modificato per supportare `_[A-Z0-9]+`

### Modificato
- Architettura 3-layer: DataRetriever → BusinessLogic → ResponseFormatter
- Tool decorati con `@tool` LangChain
- ConversationState TypedDict per state management
- LLM stub con mock classification e response generation

### Documentazione
- Creato `README.md` completo
- Creato `BUGFIX_REPORT.md` con analisi dettagliata bug
- Creato `INTEGRATION_GCHAT.md` per integrazione frontend
- Creato `CLAUDE.md` per istruzioni Claude Code

### Test
- Test suite manuale: 6/6 query passate
- Test integrazione GChat: UOC risolta correttamente
- Test 8 domande predefinite: 8/8 passate

---

## Convenzioni Versioning

Questo progetto usa [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes (es. cambio API, rimozione funzionalità)
- **MINOR** (1.X.0): Nuove funzionalità backward-compatible
- **PATCH** (1.0.X): Bug fix backward-compatible

---

## Link Utili

- [README.md](./README.md) - Documentazione principale
- [BUGFIX_REPORT.md](./BUGFIX_REPORT.md) - Report bug risolti
- [INTEGRATION_GCHAT.md](./INTEGRATION_GCHAT.md) - Guida integrazione frontend
- [CLAUDE.md](./CLAUDE.md) - Istruzioni per Claude Code
