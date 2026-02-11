# Template dataset (schema canonico monodominio)

## programmi.csv
Colonne minime:
- id
- codice
- sezione
- descrizione
Opzionali:
- descrizione_2 (varianti)

## attivita.csv
Colonne minime:
- macroarea
- aggregazione
- linea_attivita

## controlli.csv
Colonne minime:
- entity_id
- program_code
- macroarea
- aggregazione
- linea_attivita
- data_evento
- giurisdizione

## violazioni.csv
Colonne minime:
- event_id
- entity_id
- categoria
- severita
- count_gravi
- count_non_gravi
- data_evento

## programmazione_esecuzione.csv
Colonne minime:
- org_unit
- program_code
- planned
- executed
- year

## entita_target.csv
Colonne minime:
- entity_id
- giurisdizione
- comune
- indirizzo
- macroarea
- aggregazione
- linea_attivita

## personale.csv
Colonne minime:
- user_id
- giurisdizione
- org_unit

