Implementa i requisiti indicati.

1. Determina i componenti coinvolti dal prefisso degli ID:
   - Backend Python (GiAs-llm/): LG-, IC-, DM-, TE-, FR-, CF-, RA-, RC-, QE-, WS-, WV-, RG-, SM-, RP-, DL-, AP-, GP-, SQ-, HS-, API-
   - Frontend Go (gchat/): SR-, LP-, CU-, CN-, TH-, HP-, DT-, AM-, ST-, PD-, PG-
2. Leggi i requisiti specificati in SDD/requirements/ del componente corretto
3. Leggi il codice esistente e i pattern del progetto (CLAUDE.md del componente)
4. Per ogni requisito:
   - Individua i file da creare o modificare
   - Segui i pattern architetturali esistenti (3-layer separation, decoratori @tool, etc.)
   - Aggiungi `# REQ: [ID]` sulla prima riga di ogni funzione che lo implementa
   - Scrivi i test corrispondenti
5. Aggiorna Status da `DA IMPLEMENTARE` a `IMPLEMENTATO` in SDD/requirements/
6. Aggiorna SDD/traceability.md con le nuove righe, usando il formato tabella:

   | ID | Descrizione | File | Funzione/Classe | Status |
   |----|-------------|------|-----------------|--------|
   | XX-NNN | Breve descrizione | `path/file.py` | `funzione()` | ✅ |

7. Esegui verifiche:
   - Backend: `cd GiAs-llm && python -m pytest tests/unit/ -v`
   - Frontend: `cd gchat && go build -o /dev/null ./app/`
8. Se l'implementazione tocca intent, endpoint, tool registry o stato LangGraph, aggiorna anche il CLAUDE.md del componente
9. Non implementare nulla che non sia coperto dai requisiti indicati

Requisiti da implementare: $ARGUMENTS
