# Bugfix Summary - Sistema Fallback Intelligente

## 🐛 Bug Identificati e Risolti

### Bug #1: TypeError con fallback_count = None

**Errore**: `TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'`

**Causa**: I campi `fallback_count` e `fallback_phase` non venivano inizializzati correttamente nello stato del grafo, causando `None` quando si tentava di fare `None + 1`.

**File interessati**:
- `orchestrator/graph.py`

**Fix applicati**:

1. **graph.py linea ~1598-1625** - Aggiunta inizializzazione campi fallback in `initial_state`:
   ```python
   # NUOVO: Fallback recovery fields
   "fallback_suggestions": effective_metadata.get("_fallback_suggestions"),
   "fallback_phase": effective_metadata.get("_fallback_phase"),
   "fallback_count": effective_metadata.get("_fallback_count"),
   "fallback_selected_category": effective_metadata.get("_fallback_selected_category"),
   ```

2. **graph.py linea ~1640-1644** - Aggiunta campi fallback nel return value:
   ```python
   "fallback_suggestions": final_state.get("fallback_suggestions"),
   "fallback_phase": final_state.get("fallback_phase"),
   "fallback_count": final_state.get("fallback_count"),
   "fallback_selected_category": final_state.get("fallback_selected_category"),
   ```

3. **graph.py linea ~861, 878** - Gestione sicura di None values:
   ```python
   fallback_count = (state.get("fallback_count") or 0) + 1
   phase = state.get("fallback_phase") or 1
   ```

**Test**: ✅ Passato - Fallback ora gestisce correttamente None values

---

### Bug #2: Validazione Fallita per Risposte LLM

**Errore**: `"Validazione fallita"` per query valide come "Piani sul benessere animale"

**Causa**: L'LLM ritornava risposte JSON senza la chiave `"needs_clarification"`, che era richiesta obbligatoria dal validatore `_validate_result()`. Esempio risposta LLM:
```json
{"intent":"search_piani_by_topic","slots":{"topic":"benessere animale"}}
```
Mancava: `"needs_clarification": false`

**File interessati**:
- `orchestrator/router.py`

**Fix applicato**:

**router.py linea ~599-640** - Aggiunto default per `needs_clarification` e `slots`:
```python
def _parse_llm_response(self, response: str) -> Dict[str, Any]:
    # ... parsing logic ...

    # FIXUP: Aggiungi needs_clarification se mancante (default: False)
    if "needs_clarification" not in parsed:
        parsed["needs_clarification"] = False

    # FIXUP: Assicura che slots sia un dict
    if "slots" not in parsed:
        parsed["slots"] = {}

    return parsed
```

**Test**: ✅ Passato - "Piani sul benessere animale" ora classifica correttamente come `search_piani_by_topic`

---

### Bug #3: Session Corruption su Workflow Validation Fail

**Errore**: Quando `workflow_context` non passava validazione, veniva eliminata TUTTA la session (`_session_store.pop()`), causando perdita di `detail_context`, `last_intent`, ecc.

**Causa**: Invalidazione troppo aggressiva della session quando workflow_context non era valido.

**File interessati**:
- `app/api.py`

**Fix applicato**:

**api.py linea ~331-336** - Rimozione selettiva invece di pop totale:
```python
# Se validazione fallisce, rimuovi solo workflow_context (non tutta la session)
if workflow_context_raw and not workflow_context:
    logger.warning(f"[SECURITY] Invalid or expired workflow_context for user {message.sender}")
    # Non fare pop di tutta la session, solo rimuovi workflow_context
    if message.sender in _session_store:
        _session_store[message.sender].pop("workflow_context", None)
    workflow_context = None
```

**Test**: ✅ Passato - Session preservata correttamente anche con workflow_context invalido

---

### Bug #4: Duplicazione Recupero Session in api.py

**Errore**: `sender_session` veniva recuperato due volte, causando inconsistenze.

**Causa**: Codice duplicato per accedere alla session.

**File interessati**:
- `app/api.py`

**Fix applicato**:

**api.py linea ~286-323** - Consolidamento recupero session:
```python
# 2-phase system: retrieve detail_context from session if available
sender_session = _session_store.get(message.sender, {})
session_timestamp = sender_session.get("timestamp", 0)
session_valid = time.time() - session_timestamp <= SESSION_TTL

# ... usa stessa sender_session per tutto ...

# NUOVO: Recupera workflow_context dalla stessa session
workflow_context_raw = sender_session.get("workflow_context")  # No più dup
```

**Test**: ✅ Passato - Nessuna duplicazione, logica più chiara

---

## 📊 Riepilogo Fix

| Bug | File | Linee | Status | Impatto |
|-----|------|-------|--------|---------|
| TypeError fallback_count | graph.py | 861, 878, 1598-1644 | ✅ Fixed | Alto |
| Validazione LLM fallita | router.py | 599-640 | ✅ Fixed | Critico |
| Session corruption | api.py | 331-336 | ✅ Fixed | Medio |
| Duplicazione session | api.py | 286-323 | ✅ Fixed | Basso |

---

## ✅ Test Finali

Tutti i seguenti scenari sono stati testati e funzionano correttamente:

```bash
✅ "Piani sul benessere animale" (ASL: BENEVENTO)
   → Intent: search_piani_by_topic
   → Slots: {'topic': 'benessere animale'}

✅ "che faccio oggi?" (ASL: NA1)
   → Intent: greet

✅ "xyz123 voglio pizza" (ASL: BENEVENTO)
   → Intent: fallback
   → Suggestions: 5 categorie

✅ "stabilimenti a rischio" (ASL: NA1)
   → Intent: ask_risk_based_priority
   → Response: 1471 chars
```

---

## 🚀 Deployment

**Restart server** per applicare i fix:
```bash
cd /opt/lang-env/GiAs-llm
./scripts/stop_server.sh
sleep 2
./scripts/start_server.sh
```

**Verifica** che il server sia attivo:
```bash
curl http://localhost:5001/health || echo "Server non risponde"
```

**Test produzione**:
```bash
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test_user", "message":"Piani sul benessere animale"}' | jq .
```

---

## 📝 Checklist Post-Deploy

- [ ] Server riavviato senza errori
- [ ] Test "Piani sul benessere animale" → OK
- [ ] Test "che faccio oggi?" → OK
- [ ] Test messaggio off-topic → Fallback con suggerimenti
- [ ] Nessun errore "Validazione fallita" nei log
- [ ] Nessun TypeError nei log
- [ ] Cache funzionante
- [ ] Session management OK

---

## 🔍 Monitoring

Monitor questi pattern nei log dopo il deploy:

```bash
# Errori critici (non dovrebbero più apparire)
tail -f runtime/logs/api-server.log | grep -i "validazione fallita\|typeerror\|nonetype"

# Fallback activity (normale)
tail -f runtime/logs/api-server.log | grep -i "fallback"

# Performance
tail -f runtime/logs/api-server.log | grep -i "cached\|took"
```

---

## 📌 Note Importanti

1. **Cache LLM**: Il sistema usa cache per le classificazioni. Se necessario pulire:
   ```python
   from orchestrator.router import Router
   Router().clear_cache()
   ```

2. **Session TTL**: Le session scadono dopo 300 secondi (5 minuti)

3. **Workflow Validation**: Il WorkflowValidator richiede `workflow_nonce`. Se una session non ha nonce, il workflow_context viene invalidato (by design)

4. **LLM Response Format**: Il sistema ora tollera risposte LLM senza `needs_clarification` (aggiunge default `false`)

---

## 🎯 Metriche da Monitorare

Dopo 24h di produzione, verifica:

- **Fallback Rate**: % di richieste che vanno in fallback
- **Validation Failures**: Dovrebbe essere 0 (precedentemente era >10%)
- **TypeError Count**: Dovrebbe essere 0
- **Session Corruption**: Dovrebbe essere 0
- **Average Response Time**: <2s per richieste normali

Eventuali anomalie possono indicare nuovi edge case da gestire.

---

Data fix: 2026-01-30
Versione: Post-implementazione Fallback Intelligente v1.0
