Analizza la richiesta fornita e segui questi step:

1. Determina quali componenti sono coinvolti dalla richiesta:
   - Backend Python → `GiAs-llm/SDD/requirements/` (prefissi: LG-, IC-, DM-, TE-, FR-, CF-, RA-, RC-, QE-, WS-, WV-, RG-, SM-, RP-, DL-, AP-, GP-, SQ-, HS-, API-)
   - Frontend Go → `gchat/SDD/requirements/` (prefissi: SR-, LP-, CU-, CN-, TH-, HP-, DT-, AM-, ST-, PD-, PG-)
2. Leggi i CLAUDE.md dei componenti coinvolti per comprendere l'architettura
3. Leggi i file in SDD/requirements/ dei componenti coinvolti
4. Consulta SDD/traceability.md per verificare cosa e' gia' tracciato
5. Fai una impact analysis: quali requisiti esistenti vengono toccati?
6. Proponi le modifiche/aggiunte in notazione EARS, usando questo formato:

   ### PREFIX-NNN Titolo requisito
   - **Pattern EARS**: WHEN/IF/WHILE/WHERE/ubiquitous + testo del requisito
   - **Status**: DA IMPLEMENTARE

   Regole:
   - Assegna ID progressivi rispetto all'ultimo presente nel file di destinazione
   - Usa il prefisso corretto per il file di destinazione (es. SQ- per schema-query-data.md)
   - Scegli il pattern EARS corretto (WHEN/IF/WHILE/WHERE/ubiquitous)
   - Marca gli assunti con [ASSUNTO - DA CONFERMARE]
   - Segnala separatamente tutto cio' che e' ambiguo
   - Indica in quale file requirements/ va inserito ogni requisito
7. NON modificare i file. Mostra solo la proposta e aspetta approvazione.

Richiesta: $ARGUMENTS
