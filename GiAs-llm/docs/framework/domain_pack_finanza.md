# Domain Pack - Finanza (monodominio, italiano)

## 1) Meta
- nome_dominio: finanza
- versione: 1.0.0
- lingua: it
- descrizione: analisi del rischio in ambito finanziario per priorita di controllo e monitoraggio.

## 2) Lessico (etichette UI e report)
- entita_target: intermediario
- programma: iniziativa di vigilanza
- evento_controllo: ispezione
- violazione: irregolarita
- severita_grave: grave
- severita_non_grave: non grave
- giurisdizione: area di vigilanza
- unita_organizzativa: ufficio

## 3) Intents (nomi canonici + descrizione in italiano)
- ask_program_description: descrizione di una iniziativa di vigilanza
- ask_program_entities: intermediari ispezionati per iniziativa
- ask_program_activities: attivita o processi associati a una iniziativa
- search_programs_by_topic: ricerca iniziative per argomento
- ask_priority_entities: priorita di ispezione basate su programmazione
- ask_risk_based_priority: priorita basate su rischio storico di irregolarita
- ask_delayed_programs: iniziative in ritardo per ufficio
- check_if_program_delayed: verifica ritardo di una iniziativa specifica
- ask_entity_history: storico ispezioni e irregolarita per intermediario
- ask_top_risk_activities: top attivita/processi piu rischiosi

## 4) Categorie di violazione (pesi)
- antiriciclaggio: 1.0
- trasparenza: 0.8
- requisiti_patrimoniali: 0.9
- governance: 0.7
- condotta_mercato: 0.8
- segnalazioni_vigilanza: 0.6
- frodi: 1.0
- continuita_operativa: 0.6

## 5) Formula rischio
- descrizione: "P(irregolarita) x impatto x 100"
- definizione_probabilita: "tot_irregolarita / tot_ispezioni"
- definizione_impatto: "irregolarita_gravi / tot_ispezioni"
- note: "pesi categoria applicati al punteggio finale"

## 6) Mapping colonne (schema canonico -> colonne reali)
### programmi
- id: id_iniziativa
- codice: codice_iniziativa
- descrizione: descrizione
- sezione: area_tematica

### attivita
- macroarea: macroarea
- aggregazione: aggregazione
- linea_attivita: processo

### controlli
- entity_id: id_intermediario
- program_code: codice_iniziativa
- macroarea: macroarea
- aggregazione: aggregazione
- linea_attivita: processo
- data_evento: data_ispezione
- giurisdizione: area_vigilanza

### violazioni
- event_id: id_ispezione
- entity_id: id_intermediario
- categoria: categoria_irregolarita
- severita: severita
- count_gravi: num_irregolarita_gravi
- count_non_gravi: num_irregolarita_non_gravi
- data_evento: data_ispezione

### programmazione_vs_esecuzione
- org_unit: ufficio
- program_code: codice_iniziativa
- planned: programmati
- executed: eseguiti
- year: anno

### entita_target
- entity_id: id_intermediario
- giurisdizione: area_vigilanza
- comune/localita: localita
- indirizzo: indirizzo
- macroarea: macroarea
- aggregazione: aggregazione
- linea_attivita: processo

### personale
- user_id: user_id
- giurisdizione: area_vigilanza
- org_unit: ufficio

## 7) Keyword fallback (ricerca)
- elenco_keyword: ["antiriciclaggio", "trasparenza", "patrimonio", "governance", "condotta", "frodi", "segnalazioni", "operativita", "vigilanza"]

