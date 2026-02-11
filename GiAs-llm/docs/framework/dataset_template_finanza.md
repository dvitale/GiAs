# Template dataset - Finanza (schema canonico monodominio)

## programmi.csv
Colonne minime:
- id_iniziativa
- codice_iniziativa
- area_tematica
- descrizione
Opzionali:
- descrizione_2

## attivita.csv
Colonne minime:
- macroarea
- aggregazione
- processo

## controlli.csv
Colonne minime:
- id_intermediario
- codice_iniziativa
- macroarea
- aggregazione
- processo
- data_ispezione
- area_vigilanza

## violazioni.csv
Colonne minime:
- id_ispezione
- id_intermediario
- categoria_irregolarita
- severita
- num_irregolarita_gravi
- num_irregolarita_non_gravi
- data_ispezione

## programmazione_esecuzione.csv
Colonne minime:
- ufficio
- codice_iniziativa
- programmati
- eseguiti
- anno

## entita_target.csv
Colonne minime:
- id_intermediario
- area_vigilanza
- localita
- indirizzo
- macroarea
- aggregazione
- processo

## personale.csv
Colonne minime:
- user_id
- area_vigilanza
- ufficio

