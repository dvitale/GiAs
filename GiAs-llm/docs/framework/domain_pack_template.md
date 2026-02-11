# Domain Pack (template monodominio, italiano)

## 1) Meta
- nome_dominio: <es. "criminalita", "finanza", "codice_strada">
- versione: <es. "1.0.0">
- lingua: it
- descrizione: <breve descrizione del dominio>

## 2) Lessico (etichette UI e report)
- entita_target: <es. "soggetto", "azienda", "conducente">
- programma: <es. "piano", "campagna", "iniziativa">
- evento_controllo: <es. "evento", "ispezione", "verifica">
- violazione: <es. "infrazione", "anomalia", "reato">
- severita_grave: <etichetta>
- severita_non_grave: <etichetta>
- giurisdizione: <es. "provincia", "regione", "distretto">
- unita_organizzativa: <es. "ufficio", "reparto">

## 3) Intents (nomi canonici + descrizione in italiano)
- ask_program_description
- ask_program_entities
- ask_program_activities
- search_programs_by_topic
- ask_priority_entities
- ask_risk_based_priority
- ask_delayed_programs
- check_if_program_delayed
- ask_entity_history
- ask_top_risk_activities

## 4) Categorie di violazione (pesi)
- categoria_1: peso (0-1)
- categoria_2: peso (0-1)
- ...

## 5) Formula rischio
- descrizione: "P(violazione) x impatto x 100"
- definizione_probabilita: "tot_violazioni / tot_controlli"
- definizione_impatto: "violazioni_gravi / tot_controlli"
- note: <eventuali varianti>

## 6) Mapping colonne (schema canonico -> colonne reali)
### programmi
- id: <colonna>
- codice: <colonna>
- descrizione: <colonna>
- sezione: <colonna>

### attivita
- macroarea: <colonna>
- aggregazione: <colonna>
- linea_attivita: <colonna>

### controlli
- entity_id: <colonna>
- program_code: <colonna>
- macroarea: <colonna>
- aggregazione: <colonna>
- linea_attivita: <colonna>
- data_evento: <colonna>
- giurisdizione: <colonna>

### violazioni
- event_id: <colonna>
- entity_id: <colonna>
- categoria: <colonna>
- severita: <colonna>
- count_gravi: <colonna>
- count_non_gravi: <colonna>
- data_evento: <colonna>

### programmazione_vs_esecuzione
- org_unit: <colonna>
- program_code: <colonna>
- planned: <colonna>
- executed: <colonna>
- year: <colonna>

### entita_target
- entity_id: <colonna>
- giurisdizione: <colonna>
- comune/localita: <colonna>
- indirizzo: <colonna>
- macroarea: <colonna>
- aggregazione: <colonna>
- linea_attivita: <colonna>

### personale
- user_id: <colonna>
- giurisdizione: <colonna>
- org_unit: <colonna>

## 7) Keyword fallback (ricerca)
- elenco_keyword: [<termine1>, <termine2>, ...]

