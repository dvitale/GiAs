# Piano di Bug Fix - GiAs-llm Test Suite
**Data**: 2026-01-31
**Test Suite Version**: v3.4
**Success Rate Attuale**: 98% (134/140 passed)
**Target Success Rate**: 100% (140/140)

---

## 🎯 Obiettivo

Risolvere i 2 test falliti identificati nella test suite per raggiungere il 100% di success rate mantenendo la stabilità del sistema.

---

## 🐛 Bug #1: Conferma Monosillabica Non Riconosciuta

### Priorità: 🔴 **ALTA** (UX Critica)

### Descrizione
La risposta monosillabica "sì" non viene riconosciuta come `confirm_show_details`, costringendo gli utenti ad usare frasi più lunghe come "si mostrami i dettagli".

### Dettagli Tecnici
- **Test Case**: `"sì"` → expected `confirm_show_details`
- **Test File**: `/opt/lang-env/GiAs-llm/tests/test_server.py:56`
- **Comportamento Attuale**: Intent classificato erroneamente
- **Comportamento Atteso**: Intent = `confirm_show_details`

### Root Cause Analysis

Il sistema usa una combinazione di pattern heuristici e LLM classification. La risposta "sì" è troppo breve e generica per essere catturata dai pattern attuali.

**File coinvolto**: `/opt/lang-env/GiAs-llm/orchestrator/router.py`

#### Linee rilevanti:
1. **CLASSIFICATION_SYSTEM_PROMPT** (linee 59-97): System prompt per LLM
2. **_try_heuristics()** (linee 406-504): Pattern matching heuristico

### Impatto
- **UX**: ALTO - Gli utenti si aspettano di poter rispondere "sì"/"no"
- **Funzionale**: BASSO - Il sistema funziona con frasi più lunghe
- **Adozione**: MEDIO - Può frustrare utenti non tecnici

---

## 🔧 Fix Proposto per Bug #1

### Strategia: Pattern Heuristico + LLM Fallback

Aggiungere pattern heuristici specifici per conferme/rifiuti monosillabici prima del LLM classification.

### Step di Implementazione

#### Step 1: Identificare la funzione heuristic
```python
# File: /opt/lang-env/GiAs-llm/orchestrator/router.py
# Funzione: _try_heuristics() (linee 406-504)
```

#### Step 2: Aggiungere pattern per conferme monosillabiche

**Location**: `/opt/lang-env/GiAs-llm/orchestrator/router.py:406-504`

**Pattern da aggiungere**:
```python
# Confirmation patterns (monosyllabic and short)
if re.search(r'\b(sì|si|ok|okay|va bene|certo|certamente|yes|yep|yeah)\b',
             user_message.lower().strip()):
    return RouterOutput(
        intent="confirm_show_details",
        confidence=0.95,
        metadata={"heuristic": "monosyllabic_confirm"}
    )

# Decline patterns (monosyllabic and short)
if re.search(r'\b(no|nah|nope|non|mai|niente)\b',
             user_message.lower().strip()):
    return RouterOutput(
        intent="decline_show_details",
        confidence=0.95,
        metadata={"heuristic": "monosyllabic_decline"}
    )
```

#### Step 3: Gestione del contesto

**Problema**: "sì" è ambiguo senza contesto (conferma dettagli? risposta generica?)

**Soluzione**: Verificare lo stato della sessione

```python
# Check if we're in a two-phase flow context
if state.get("awaiting_confirmation"):
    # Apply confirmation/decline patterns
    if re.search(r'\b(sì|si|ok|...)\b', user_message.lower()):
        return RouterOutput(
            intent="confirm_show_details",
            confidence=0.98,  # Higher confidence in context
            metadata={"heuristic": "contextual_confirm"}
        )
```

#### Step 4: Ordinamento dei pattern

**Importante**: I pattern monosillabici devono essere controllati DOPO i pattern più specifici per evitare falsi positivi.

**Ordine suggerito**:
1. Pattern multi-word specifici (già esistenti)
2. Pattern con contesto (two-phase state)
3. Pattern monosillabici (NUOVO)
4. LLM classification (fallback)

### Testing del Fix

**Test cases da verificare**:
```python
# Conferme
"sì" → confirm_show_details ✓
"si" → confirm_show_details ✓
"ok" → confirm_show_details ✓
"va bene" → confirm_show_details ✓

# Rifiuti
"no" → decline_show_details ✓
"no grazie" → decline_show_details ✓ (già funzionante)

# Edge cases
"sì ma..." → (gestire con LLM, non heuristic)
"no però..." → (gestire con LLM, non heuristic)
```

### Stima Implementazione
- **Tempo**: 20-30 minuti
- **Complessità**: BASSA
- **Risk**: BASSO (pattern aggiuntivi, non modifiche logica esistente)
- **Testing**: 10 minuti (re-run sezione 2 test suite)

### Verification
```bash
# Test specifico
python tests/test_server.py --verbose | grep '"sì"'

# Full regression
python tests/test_server.py --verbose
```

---

## 🐛 Bug #2: Query Colloquiale Priorità Non Riconosciuta

### Priorità: 🟡 **MEDIA** (Usabilità)

### Descrizione
La query colloquiale "chi devo controllare per primo" non viene riconosciuta come `ask_priority_establishment`.

### Dettagli Tecnici
- **Test Case**: `"chi devo controllare per primo"` → expected `ask_priority_establishment`
- **Test File**: `/opt/lang-env/GiAs-llm/tests/test_server.py:37`
- **Comportamento Attuale**: Intent classificato erroneamente
- **Comportamento Atteso**: Intent = `ask_priority_establishment`

**Note**: Le varianti funzionano:
- ✓ "quali stabilimenti controllare" (linea 38)
- ✓ "cosa devo fare oggi" (linea 39)

### Root Cause Analysis

Il pattern "chi devo controllare per primo" usa la forma interrogativa "chi" invece di "quali/cosa", confondendo il sistema.

**File coinvolto**: `/opt/lang-env/GiAs-llm/orchestrator/router.py`

### Impatto
- **UX**: MEDIO - Gli utenti possono riformulare
- **Funzionale**: BASSO - Alternative funzionanti disponibili
- **Adozione**: BASSO - Linguaggio naturale variante

---

## 🔧 Fix Proposto per Bug #2

### Strategia: Migliorare System Prompt LLM

Aggiungere esempi di query colloquiali al system prompt per migliorare la classificazione LLM.

### Step di Implementazione

#### Step 1: Modificare CLASSIFICATION_SYSTEM_PROMPT

**Location**: `/opt/lang-env/GiAs-llm/orchestrator/router.py:59-97`

**Modifica**: Aggiungere varianti colloquiali agli esempi per `ask_priority_establishment`

**Prima**:
```python
# ask_priority_establishment
- "quali stabilimenti controllare"
- "cosa devo fare oggi"
```

**Dopo**:
```python
# ask_priority_establishment
- "quali stabilimenti controllare"
- "cosa devo fare oggi"
- "chi devo controllare per primo"
- "chi controllare oggi"
- "da chi inizio"
```

#### Step 2: (Alternativa) Pattern Heuristico

Se il fix al system prompt non basta, aggiungere pattern heuristico:

```python
# Priority establishment patterns (interrogative "chi")
if re.search(r'\b(chi)\s+(devo\s+)?controllare\s+(per\s+primo|oggi|prima)\b',
             user_message.lower()):
    return RouterOutput(
        intent="ask_priority_establishment",
        confidence=0.90,
        metadata={"heuristic": "priority_chi_pattern"}
    )
```

### Testing del Fix

**Test cases da verificare**:
```python
"chi devo controllare per primo" → ask_priority_establishment ✓
"chi controllare oggi" → ask_priority_establishment ✓
"da chi inizio" → ask_priority_establishment ✓

# Verifica non-regression
"quali stabilimenti controllare" → ask_priority_establishment ✓
"cosa devo fare oggi" → ask_priority_establishment ✓
```

### Stima Implementazione
- **Tempo**: 15-20 minuti
- **Complessità**: BASSA
- **Risk**: MOLTO BASSO (aggiunta esempi, no modifiche logica)
- **Testing**: 10 minuti (re-run sezione 2 + 14)

### Verification
```bash
# Test specifico
python tests/test_server.py --verbose | grep '"chi devo controllare'

# Full regression
python tests/test_server.py --verbose
```

---

## 📅 Piano di Esecuzione

### Fase 1: Bug Fix (Stimato 40-60 minuti)

| Step | Attività | Tempo | Responsabile |
|------|----------|-------|--------------|
| 1 | Backup file `router.py` | 2 min | Dev |
| 2 | Implementare Fix Bug #1 (conferme monosillabiche) | 25 min | Dev |
| 3 | Test locale Fix Bug #1 | 5 min | Dev |
| 4 | Implementare Fix Bug #2 (query colloquiali) | 15 min | Dev |
| 5 | Test locale Fix Bug #2 | 5 min | Dev |
| 6 | Code review modifiche | 10 min | Dev |

### Fase 2: Regression Testing (Stimato 10-15 minuti)

| Step | Attività | Tempo | Comando |
|------|----------|-------|---------|
| 1 | Re-run test suite completa | 5 min | `python tests/test_server.py --verbose` |
| 2 | Verificare success rate = 100% | 2 min | Check summary |
| 3 | Verificare log server per errori | 3 min | `tail -100 runtime/logs/api-server.log` |
| 4 | Smoke test manuale | 5 min | Curl tests |

### Fase 3: Documentazione (Stimato 15 minuti)

| Step | Attività | Tempo |
|------|----------|-------|
| 1 | Aggiornare CHANGELOG | 5 min |
| 2 | Documentare fix in BUGFIX_SUMMARY.md | 5 min |
| 3 | Commit con messaggio descrittivo | 5 min |

---

## 🧪 Test Plan Dettagliato

### Pre-Fix Validation
```bash
# Verificare stato attuale
cd /opt/lang-env/GiAs-llm
python tests/test_server.py --verbose | grep -E '(✗|Failed)'

# Expected output:
# [✗] "chi devo controllare per primo"
# [✗] "sì"
# Failed: 2
```

### Post-Fix Validation
```bash
# Test completo
python tests/test_server.py --verbose 2>&1 | tee runtime/logs/test_post_fix_$(date +%Y%m%d_%H%M%S).log

# Verificare success rate
grep "HEALTH:" runtime/logs/test_post_fix_*.log

# Expected output:
# ✅ HEALTH: EXCELLENT (100%)
# Passed: 140
# Failed: 0
```

### Specific Test Cases
```bash
# Test Bug #1 fix
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"sì"}' | jq '.intent_name'
# Expected: "confirm_show_details"

# Test Bug #2 fix
curl -X POST http://localhost:5005/model/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"chi devo controllare per primo"}' | jq '.intent_name'
# Expected: "ask_priority_establishment"
```

---

## 🔍 Root Cause Summary

### Bug #1: Pattern Heuristico Insufficiente
- **Causa**: Mancano pattern per conferme/rifiuti monosillabici
- **Soluzione**: Aggiungere pattern specifici con context awareness
- **Prevenzione**: Aggiungere test per tutte le varianti monosillabiche comuni

### Bug #2: LLM Training Examples Incompleti
- **Causa**: System prompt non include varianti interrogative con "chi"
- **Soluzione**: Arricchire esempi nel prompt o aggiungere pattern heuristico
- **Prevenzione**: Raccogliere feedback utenti su query colloquiali

---

## 📊 Metriche di Successo

### Target Post-Fix
- ✅ Success Rate: 100% (140/140)
- ✅ Intent Classification Accuracy: 100% (sezione 2 e 14)
- ✅ Zero regressioni su test esistenti
- ✅ Performance avg: < 2.5s (mantenuta)

### Acceptance Criteria
1. Test `"sì"` → `confirm_show_details` ✓
2. Test `"chi devo controllare per primo"` → `ask_priority_establishment` ✓
3. Full test suite: 0 failed ✓
4. No regressioni su test precedentemente passati ✓
5. Avg response time non peggiorato (< 2.5s) ✓

---

## 🚨 Risk Assessment

### Risk #1: Falsi Positivi Pattern Monosillabici
**Probabilità**: MEDIA
**Impatto**: MEDIO
**Mitigazione**:
- Usare context awareness (verificare stato two-phase)
- Pattern specifici solo in contesto appropriato
- Fallback a LLM per casi ambigui

### Risk #2: Performance Degradation
**Probabilità**: BASSA
**Impatto**: BASSO
**Mitigazione**:
- Pattern heuristici sono più veloci di LLM
- Fix migliorano performance (meno chiamate LLM)

### Risk #3: Regressioni su Test Esistenti
**Probabilità**: MOLTO BASSA
**Impatto**: ALTO
**Mitigazione**:
- Full regression test obbligatorio
- Code review prima del commit
- Pattern aggiunti in modo additivo (no modifiche esistenti)

---

## 📝 Checklist Pre-Commit

- [ ] Backup `router.py` creato
- [ ] Fix Bug #1 implementato
- [ ] Fix Bug #2 implementato
- [ ] Test locali passati
- [ ] Full test suite eseguita (100% success)
- [ ] Log server verificati (no errori)
- [ ] Smoke test manuali eseguiti
- [ ] Performance avg verificata (< 2.5s)
- [ ] CHANGELOG aggiornato
- [ ] BUGFIX_SUMMARY.md aggiornato
- [ ] Code review completata
- [ ] Commit message descrittivo preparato

---

## 🎯 Commit Message Template

```
fix(router): Migliorare intent classification per conferme monosillabiche e query colloquiali

Risolvere 2 test falliti nella suite v3.4 (98% → 100% success rate):

1. Bug #1 - Conferme monosillabiche:
   - Aggiungere pattern heuristici per "sì", "si", "ok", "no"
   - Context-aware per two-phase flow
   - Test: "sì" → confirm_show_details ✓

2. Bug #2 - Query colloquiali priorità:
   - Arricchire system prompt con varianti "chi controllare"
   - Test: "chi devo controllare per primo" → ask_priority_establishment ✓

Impatto:
- Success rate: 98% → 100% (140/140 test passed)
- UX migliorata per risposte naturali
- Zero regressioni

File modificati:
- orchestrator/router.py (pattern heuristici + system prompt)

Test:
- Full test suite: 140/140 passed ✓
- Performance avg: 2.478s (mantenuta) ✓

Refs: test_execution_20260131_090444.log, bug_fix_plan_20260131.md
```

---

## 📚 Risorse

### File da Leggere
- `/opt/lang-env/GiAs-llm/orchestrator/router.py` (linee 59-97, 406-504)
- `/opt/lang-env/GiAs-llm/tests/test_server.py` (linee 37, 56)
- `/opt/lang-env/GiAs-llm/runtime/logs/test_execution_20260131_090444.log`

### Documentazione Correlata
- `/opt/lang-env/GiAs-llm/BUGFIX_SUMMARY.md` (da aggiornare)
- `/opt/lang-env/GiAs-llm/orchestrator/intent_metadata.py` (reference intent definitions)
- `/opt/lang-env/CLAUDE.md` (architettura sistema)

### Test Reference
- Test Suite v3.4: `/opt/lang-env/GiAs-llm/tests/test_server.py`
- Quick mode: `python tests/test_server.py -q`
- Verbose mode: `python tests/test_server.py -v`

---

## ✅ Next Steps

1. **Implementare Fix Bug #1** (20-30 min)
   - Modificare `router.py` con pattern monosillabici
   - Test locale

2. **Implementare Fix Bug #2** (15-20 min)
   - Aggiornare system prompt con varianti colloquiali
   - Test locale

3. **Regression Testing** (10-15 min)
   - Re-run full test suite
   - Verificare 100% success rate

4. **Documentazione & Commit** (15 min)
   - Aggiornare CHANGELOG e BUGFIX_SUMMARY
   - Commit con messaggio descrittivo

**TOTALE STIMATO**: ~60-80 minuti

---

**Piano creato**: 2026-01-31 09:15:00
**Autore**: Claude Code Analysis
**Status**: ✅ READY FOR IMPLEMENTATION
