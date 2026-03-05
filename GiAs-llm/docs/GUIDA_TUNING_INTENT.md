# Guida operativa: migliorare il riconoscimento intent via DB

Quando il sistema classifica male un messaggio utente, e' possibile intervenire direttamente sulle tabelle `intents` e `intent_examples` nel database PostgreSQL senza modificare codice Python.

## Diagnosi: capire cosa e' andato storto

### 1. Consultare il chat_log

```sql
-- Ultime classificazioni errate (intent = fallback o intent sbagliato)
SELECT ask, intent, slots, confidence, "when"
FROM chat_log
WHERE intent = 'fallback'
   OR intent != '<intent_atteso>'
ORDER BY "when" DESC
LIMIT 20;
```

### 2. Controllare gli esempi esistenti per l'intent atteso

```sql
SELECT text, example_type, confused_with
FROM intent_examples
WHERE intent = '<intent_atteso>'
ORDER BY example_type, display_order;
```

### 3. Controllare la copertura complessiva

```sql
SELECT * FROM v_intent_example_counts;
```

Intent con pochi esempi (< 5 totali) sono candidati naturali per interventi.

---

## Intervento 1: aggiungere esempi few-shot

Questo e' l'intervento piu' comune. Se il sistema non riconosce una formulazione dell'utente, aggiungere l'esempio come tipo `few_shot`.

```sql
INSERT INTO intent_examples (intent, text, example_type)
VALUES ('ask_delayed_plans', 'ci sono piani scaduti?', 'few_shot')
ON CONFLICT (intent, text, example_type) DO NOTHING;
```

**Quando usare**: l'utente formula la domanda in modo naturale ma diverso dagli esempi esistenti. L'intent e' chiaro, manca solo la variazione linguistica.

---

## Intervento 2: aggiungere coppie di disambiguazione

Se il sistema confonde due intent simili, aggiungere coppie `disambiguation` per entrambi.

```sql
-- Il sistema confonde "OSA pericolosi" con ask_top_risk_activities
-- ma l'intent corretto e' ask_risk_based_priority

INSERT INTO intent_examples (intent, text, example_type, confused_with) VALUES
('ask_risk_based_priority', 'OSA pericolosi', 'disambiguation', 'ask_top_risk_activities'),
('ask_top_risk_activities', 'tipologie attivita pericolose', 'disambiguation', 'ask_risk_based_priority')
ON CONFLICT (intent, text, example_type) DO NOTHING;
```

**Quando usare**: due intent si confondono frequentemente. Inserire esempi per **entrambi** i lati della confusione.

---

## Intervento 3: aggiungere esempi critici per il prompt LLM

Gli esempi `prompt_critical` sono i piu' potenti: vengono iniettati direttamente nel prompt di classificazione con la risposta JSON attesa.

```sql
INSERT INTO intent_examples (intent, text, example_type, expected_json)
VALUES (
    'ask_risk_based_priority',
    'chi ha piu non conformita',
    'prompt_critical',
    '{"reasoning":"chiede stabilimenti con piu NC","intent":"ask_risk_based_priority","slots":{},"needs_clarification":false,"confidence":0.95}'
)
ON CONFLICT (intent, text, example_type) DO NOTHING;
```

**Quando usare**: una formulazione specifica viene classificata male in modo persistente e serve un esempio esplicito nel prompt.

**Attenzione**: non eccedere con i prompt_critical (max ~35-40 totali) per non appesantire il prompt di classificazione.

---

## Intervento 4: aggiungere variazioni linguistiche

Le variazioni aumentano la copertura dell'indice Qdrant per il few-shot retrieval.

```sql
INSERT INTO intent_examples (intent, text, example_type)
VALUES ('ask_establishment_history', 'voglio vedere i controlli precedenti', 'variation')
ON CONFLICT (intent, text, example_type) DO NOTHING;
```

**Quando usare**: formulazioni colloquiali o dialettali che non compaiono negli altri tipi.

---

## Intervento 5: aggiornare il menu aiuto

Per aggiungere o modificare le domande mostrate quando l'utente chiede "aiuto":

```sql
-- Aggiungere nuova domanda nel menu help
INSERT INTO intent_examples (intent, text, example_type, display_order)
VALUES ('ask_risk_based_priority', 'Quali stabilimenti hanno piu non conformita?', 'help', 9)
ON CONFLICT (intent, text, example_type) DO NOTHING;

-- Rimuovere una domanda dal menu
DELETE FROM intent_examples
WHERE text = 'Stabilimenti a rischio' AND example_type = 'help';
```

Il campo `display_order` determina l'ordine all'interno della categoria.

---

## Dopo ogni intervento: ricostruire l'indice

Dopo aver modificato gli esempi, ricostruire l'indice Qdrant e riavviare il server:

```bash
# Ricostruire l'indice few-shot (include tutti i tipi dal DB)
cd GiAs-llm && python tools/indexing/build_intent_examples_index.py

# Riavviare il backend (ricarica il prompt dal DB)
scripts/server.sh restart
```

Il server ricarica automaticamente il prompt di classificazione e il contenuto help dal DB all'avvio.

---

## Intervento 6: aggiungere un nuovo intent

Se serve un intent completamente nuovo, la procedura richiede anche codice Python. Ma la parte dati si puo' preparare in anticipo:

```sql
-- 1. Aggiungere l'intent nella tabella intents
INSERT INTO intents (intent, section_number, title, category, emoji, is_direct_response)
VALUES ('ask_new_intent', 21, 'Nuovo Intent', 'Categoria', '📋', false);

-- 2. Aggiungere almeno 3 esempi few_shot
INSERT INTO intent_examples (intent, text, example_type) VALUES
('ask_new_intent', 'esempio domanda 1', 'few_shot'),
('ask_new_intent', 'esempio domanda 2', 'few_shot'),
('ask_new_intent', 'esempio domanda 3', 'few_shot');

-- 3. Aggiungere almeno 1 esempio prompt_critical
INSERT INTO intent_examples (intent, text, example_type, expected_json) VALUES
('ask_new_intent', 'esempio critico', 'prompt_critical',
 '{"reasoning":"motivazione","intent":"ask_new_intent","slots":{},"needs_clarification":false,"confidence":0.95}');

-- 4. Aggiungere domanda help
INSERT INTO intent_examples (intent, text, example_type, display_order)
VALUES ('ask_new_intent', 'Domanda di esempio per help', 'help', 18);
```

Poi nel codice Python: aggiungere a `VALID_INTENTS`, `INTENT_REGISTRY`, creare tool, etc. (vedi sezione "Adding a New Intent" nel CLAUDE.md).

---

## Verifica rapida dello stato

```sql
-- Conteggi per tipo e intent
SELECT * FROM v_intent_example_counts;

-- Totale esempi
SELECT COUNT(*) AS totale, example_type, COUNT(DISTINCT intent) AS intent_coperti
FROM intent_examples
GROUP BY example_type;

-- Intent senza esempi help (non compaiono nel menu aiuto)
SELECT i.intent, i.title
FROM intents i
LEFT JOIN intent_examples e ON i.intent = e.intent AND e.example_type = 'help'
WHERE e.id IS NULL AND i.intent NOT IN ('greet', 'goodbye', 'fallback', 'confirm_show_details', 'decline_show_details');

-- Allineamento con VALID_INTENTS (20 intent attesi)
SELECT COUNT(*) FROM intents;
```

---

## Riepilogo tipi di esempio

| Tipo | Scopo | Dove agisce | Limite consigliato |
|------|-------|-------------|-------------------|
| `few_shot` | Training generico, Qdrant index | Indice vettoriale | Illimitato |
| `prompt_critical` | Iniettato nel prompt LLM | Classificazione diretta | Max 35-40 |
| `disambiguation` | Coppie confuse per training | Indice vettoriale | Illimitato |
| `variation` | Variazioni linguistiche | Indice vettoriale | Illimitato |
| `help` | Menu aiuto utente | UI help_tool | 1-2 per intent |
