## Schema Canonico Applicativo

Nomi colonna come presenti nel DB e visti dal codice Python (nessun rename applicativo).
Le tabelle originali sono archiviate nello schema `old`. Script di creazione: `sql/create_normalized_views.sql`.


### piani\_monitoraggio

DataFrame: `piani_df` | Tabella DB: `piani_monitoraggio` | ~730 righe (dedup)

| Colonna | Note |
| - | - |
| sezione | Filtro, display, ricerca (SEZIONE A..G) |
| alias\_piano\_attivita | Codice piano (A1, B2, C3) |
| descrizione\_piano | Descrizione testuale del piano |
| alias\_indicatore | Codice indicatore (A1\_A, ATT AO5\_A) |
| descrizione\_indicatore | Descrizione testuale dell'indicatore |
| campionamento | boolean: True = prelievo campioni |
| tipo\_piano\_attivita | piano / attivita |


### cu\_eseguiti

DataFrame: `controlli_df` | Tabella DB: `cu_eseguiti_nc` | ~399K righe

| Colonna | Note |
| - | - |
| id\_controllo |  |
| data\_inizio\_controllo | Filtro anno |
| tecnica\_controllo |  |
| macroarea\_cu | classificazione\_ml |
| aggregazione\_cu | classificazione\_ml |
| attivita\_cu | classificazione\_ml |
| alias\_piano\_attivita | motivo\_controllo |
| descrizione\_piano | motivo\_controllo |
| alias\_indicatore | motivo\_controllo |
| descrizione\_indicatore | motivo\_controllo |
| sezione |  |
| campionamento | arricchito da piani\_monitoraggio |
| tipo\_piano\_attivita | arricchito da piani\_monitoraggio |
| descrizione\_asl | organizzazione |
| descrizione\_uoc | organizzazione |
| descrizione\_uos | organizzazione |
| num\_registrazione | stabilimento |
| norma | stabilimento |
| num\_riconoscimento | stabilimento |
| latitudine\_stab | stabilimento |
| longitudine\_stab | stabilimento |
| ragione\_sociale | stabilimento (PII) |
| partita\_iva | stabilimento (PII) |
| codice\_fiscale | soggetto\_fisico (PII) |
| nominativo\_rappresentante | soggetto\_fisico (PII) |
| tipo\_non\_conformita | NC inline |
| numero\_nc\_gravi | NC inline |
| numero\_nc\_non\_gravi | NC inline |
| oggetto\_non\_conformita | NC inline |
| comune | stabilimento |


### cu\_diff\_programmati\_eseguiti

DataFrame: `diff_prog_eseg_df` | Tabella DB: `cu_diff_programmati_eseguiti` | ~60K righe

| Colonna | Note |
| - | - |
| alias\_indicatore | motivo\_controllo |
| descrizione\_indicatore | motivo\_controllo |
| programmati |  |
| eseguiti |  |
| anno | Filtro temporale |
| descrizione\_asl | organizzazione |
| descrizione\_uoc | organizzazione |
| descrizione\_uos | organizzazione |
| sezione | arricchito da piani\_monitoraggio |
| alias\_piano\_attivita | arricchito da piani\_monitoraggio |
| descrizione\_piano | arricchito da piani\_monitoraggio |
| tipo\_piano\_attivita | arricchito da piani\_monitoraggio |
| campionamento | arricchito da piani\_monitoraggio |


### masterlist

DataFrame: `attivita_df` | ~105K righe

| Colonna | Note |
| - | - |
| norma |  |
| macroarea | classificazione\_ml |
| aggregazione | classificazione\_ml |
| linea di attivita | classificazione\_ml |
| registrati |  |
| riconosciuti |  |


### osa\_mai\_controllati

DataFrame: `osa_mai_controllati_df` | ~643K righe

| Colonna | Note |
| - | - |
| ragione\_sociale | identificativo primario UI |
| asl | Filtro ASL |
| macroarea | classificazione\_ml |
| aggregazione | classificazione\_ml |
| attivita | classificazione\_ml |
| comune | stabilimento |
| indirizzo | stabilimento |
| latitudine\_stab | stabilimento |
| longitudine\_stab | stabilimento |
| num\_riconoscimento | stabilimento |
| n\_reg | stabilimento |
| provincia\_stab | stabilimento |
| data\_inizio\_attivita |  |
| partita\_iva | stabilimento (PII) |
| codice\_fiscale | soggetto\_fisico (PII) |
| codice\_fiscale\_rappresentante | soggetto\_fisico (PII) |
| nominativo\_rappresentante | soggetto\_fisico (PII) |


### personale

DataFrame: `personale_df` | ~100K righe

| Colonna | Note |
| - | - |
| user\_id | Filtro utente, autenticazione |
| descrizione\_asl | organizzazione |
| descrizione\_uoc | organizzazione |
| descrizione\_uos | organizzazione |
| codice\_fiscale |  |
| anno | Filtro anno corrente |
| namefirst |  |
| namelast |  |


### indicatori\_non\_catalogati

Tabella ausiliaria per indicatori orfani (presenti in cu\_eseguiti/cu\_diff ma assenti da piani\_monitoraggio).

| Colonna | Note |
| - | - |
| alias\_indicatore | PK |
| descrizione\_indicatore |  |
| fonte | cu\_eseguiti\_x o cu\_diff |
| data\_rilevamento |  |
