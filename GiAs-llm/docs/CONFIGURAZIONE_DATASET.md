# Configurazione Dataset GiAs-llm

**Data Creazione**: 2026-01-09
**Ultima Modifica**: 2026-01-09

## Panoramica

Il sistema GiAs-llm supporta due tipi di sorgenti dati configurabili: **CSV** e **PostgreSQL**. La configurazione avviene tramite un file JSON centralizzato che permette di specificare sia il tipo di sorgente che i nomi specifici dei file/tabelle.

## Architettura del Sistema

### Factory Pattern

Il sistema utilizza il pattern Factory per creare istanze di data source appropriate:

```
config.json → ConfigLoader → DataSourceFactory → CSVDataSource | PostgreSQLDataSource
```

**File coinvolti**:
- `/opt/lang-env/GiAs-llm/config.json` - Configurazione principale
- `/opt/lang-env/GiAs-llm/config_loader.py` - Caricamento configurazione
- `/opt/lang-env/GiAs-llm/data_sources/factory.py` - Factory per data source
- `/opt/lang-env/GiAs-llm/data_sources/base.py` - Interfaccia astratta
- `/opt/lang-env/GiAs-llm/data_sources/csv_source.py` - Implementazione CSV
- `/opt/lang-env/GiAs-llm/data_sources/postgresql_source.py` - Implementazione PostgreSQL

### Utilizzo nel Sistema

Il data source viene inizializzato automaticamente in:
- `/opt/lang-env/GiAs-llm/agents/data.py` (linea 17-18)

```python
_data_source = get_data_source()
_datasets = _data_source.load_all()
```

## File di Configurazione

### Struttura del config.json

```json
{
  "data_source": {
    "type": "csv",          // Tipo: "csv" o "postgresql"
    "csv": { ... },         // Configurazione CSV
    "postgresql": { ... }   // Configurazione PostgreSQL
  }
}
```

### Configurazione CSV (Attuale)

```json
"csv": {
  "directory": "dataset",
  "files": {
    "piani": "piani_monitoraggio.csv",
    "attivita": "Master list rev 11_filtered.csv",
    "controlli": "vw_2025_eseguiti_filtered.csv",
    "osa_mai_controllati": "osa_mai_controllati_con_linea_852-3_filtered.csv",
    "ocse": "OCSE_ISP_SEMP_2025_filtered_v2.csv",
    "diff_prog_eseg": "vw_diff_programmmati_eseguiti.csv",
    "personale": "personale_filtered.csv"
  },
  "personale_separator": "|"
}
```

**Parametri CSV**:
- `directory`: Directory relativa contenente i file CSV (default: "dataset")
- `files`: Mappatura chiavi logiche → nomi file fisici
- `personale_separator`: Separatore speciale per il file personale (default: "|")

### Configurazione PostgreSQL (Preparata)

```json
"postgresql": {
  "enabled": false,
  "host": "localhost",
  "port": 5432,
  "database": "gias_db",
  "user": "gias_user",
  "password": "gias_password",
  "tables": {
    "piani": "piani_monitoraggio",
    "attivita": "attivita_master",
    "controlli": "vw_2025_eseguiti",
    "osa_mai_controllati": "osa_mai_controllati",
    "ocse": "ocse_isp_semp_2025",
    "diff_prog_eseg": "vw_diff_programmati_eseguiti",
    "personale": "personale"
  }
}
```

**Parametri PostgreSQL**:
- `enabled`: Flag abilitazione PostgreSQL
- `host`, `port`, `database`, `user`, `password`: Parametri connessione
- `tables`: Mappatura chiavi logiche → nomi tabelle fisiche

## Mappatura Dataset

### Chiavi Logiche Standardizzate

Il sistema utilizza **7 chiavi logiche** che rimangono invariate indipendentemente dalla sorgente dati:

| Chiave Logica | Descrizione | CSV Attuale | Tabella PostgreSQL |
|---------------|-------------|-------------|-------------------|
| `piani` | Piani di monitoraggio | `piani_monitoraggio.csv` | `piani_monitoraggio` |
| `attivita` | Master list attività | `Master list rev 11_filtered.csv` | `attivita_master` |
| `controlli` | Controlli eseguiti 2025 | `vw_2025_eseguiti_filtered.csv` | `vw_2025_eseguiti` |
| `osa_mai_controllati` | OSA mai controllati | `osa_mai_controllati_con_linea_852-3_filtered.csv` | `osa_mai_controllati` |
| `ocse` | Dati OCSE con NC | `OCSE_ISP_SEMP_2025_filtered_v2.csv` | `ocse_isp_semp_2025` |
| `diff_prog_eseg` | Differenza prog/eseg | `vw_diff_programmmati_eseguiti.csv` | `vw_diff_programmati_eseguiti` |
| `personale` | Anagrafica personale | `personale_filtered.csv` | `personale` |

### Utilizzo nel Codice

Il codice del sistema accede ai dati sempre tramite le **chiavi logiche**:

```python
# In agents/data.py e tools/*.py
ocse_df = _datasets.get("ocse", pd.DataFrame())
piani_df = _datasets.get("piani", pd.DataFrame())
```

Questo garantisce che tutto il codice di analisi (incluso il nuovo sistema di categorie NC) funzioni identicamente con CSV o PostgreSQL.

## Procedimenti di Configurazione

### 1. Cambiare Tipo di Sorgente Dati

**Da CSV a PostgreSQL**:

```bash
# 1. Modificare config.json
"type": "postgresql"
"postgresql.enabled": true

# 2. Riavviare il sistema
# Il sistema caricherà automaticamente da PostgreSQL
```

**Da PostgreSQL a CSV**:
```bash
# 1. Modificare config.json
"type": "csv"
"postgresql.enabled": false

# 2. Riavviare il sistema
```

### 2. Cambiare Nomi File CSV

```json
"csv": {
  "files": {
    "ocse": "OCSE_ISP_SEMP_2026_v3.csv",
    "controlli": "controlli_aggiornati_2026.csv"
  }
}
```

### 3. Cambiare Nomi Tabelle PostgreSQL

```json
"postgresql": {
  "tables": {
    "ocse": "ocse_completa_2026",
    "controlli": "vw_controlli_storici"
  }
}
```

### 4. Aggiungere Nuovi Dataset

Per aggiungere un nuovo dataset (es. "sanzioni"):

1. **Aggiornare DataSource base** (`data_sources/base.py`):
```python
@abstractmethod
def load_sanzioni(self) -> pd.DataFrame:
    """Load sanzioni data."""
    pass

def load_all(self) -> Dict[str, pd.DataFrame]:
    return {
        # ... dataset esistenti ...
        "sanzioni": self.load_sanzioni()
    }
```

2. **Implementare in CSV/PostgreSQL sources**:
```python
# csv_source.py
def load_sanzioni(self) -> pd.DataFrame:
    return self._load_csv("sanzioni")

# postgresql_source.py
def load_sanzioni(self) -> pd.DataFrame:
    return self._load_table("sanzioni")
```

3. **Aggiornare config.json**:
```json
"files": {
  // ... altri file ...
  "sanzioni": "sanzioni_2025.csv"
},
"tables": {
  // ... altre tabelle ...
  "sanzioni": "sanzioni"
}
```

4. **Utilizzare in agents/data.py**:
```python
sanzioni_df = _datasets.get("sanzioni", pd.DataFrame())
```

## Configurazione di Default

Se il file `config.json` non esiste o è corrotto, il sistema utilizza configurazione di default definita in `config_loader.py:_get_default_config()`:

- **Tipo**: CSV
- **Directory**: `dataset`
- **File**: Quelli attualmente configurati
- **PostgreSQL**: Disabilitato

## Gestione Errori

### Errori di Caricamento CSV
- File non trovato → DataFrame vuoto + log di errore
- Errore di parsing → DataFrame vuoto + log di errore
- Directory non esistente → Utilizza configurazione di default

### Errori di Connessione PostgreSQL
- Connessione fallita → Eccezione sollevata
- psycopg2 non installato → ImportError con istruzioni installazione
- Tabella non esistente → DataFrame vuoto + log di errore

## Note di Sicurezza

- **Password PostgreSQL**: Memorizzate in plain text in config.json
- **Raccomandazione**: Utilizzare variabili ambiente o vault per credenziali in produzione
- **Separazione**: CSV non richiede credenziali

## Compatibilità

- **Python**: ≥3.8
- **Dipendenze CSV**: pandas
- **Dipendenze PostgreSQL**: pandas + psycopg2-binary
- **Retrocompatibilità**: Il sistema mantiene compatibilità con il codice esistente tramite le chiavi logiche standardizzate

## Log e Monitoraggio

Il sistema fornisce log dettagliati per:
- Caricamento configurazione: `[Config]` prefix
- Selezione data source: `[DataSource Factory]` prefix
- Caricamento CSV: `[CSVDataSource]` prefix
- Connessioni PostgreSQL: `[PostgreSQLDataSource]` prefix

Esempio log:
```
[Config] Loaded configuration from config.json
[DataSource Factory] Creating CSV data source
[CSVDataSource] Loaded ocse: 82749 rows from OCSE_ISP_SEMP_2025_filtered_v2.csv
[Data] Caricati: piani=78, attivita=5982, controlli=9865, osa=4637, ocse=82749, diff_prog_eseg=1169, personale=2847
```

## Considerazioni di Performance

### CSV
- **Vantaggio**: Nessuna dipendenza esterna, caricamento rapido per dataset ≤100MB
- **Svantaggio**: Tutto in memoria, lento su dataset >1GB

### PostgreSQL
- **Vantaggio**: Query efficienti, gestione dataset grandi, indicizzazione
- **Svantaggio**: Richiede setup DB, dipendenze aggiuntive, latenza di rete

## Migrazione

Per migrare da CSV a PostgreSQL:

1. **Setup PostgreSQL** con schema corrispondente
2. **Importare dati** CSV nelle tabelle
3. **Aggiornare config.json** con parametri PostgreSQL
4. **Testare** caricamento e funzionalità
5. **Switchare** `type` da "csv" a "postgresql"

Il sistema è stato progettato per **zero-downtime migration**: tutti i tool e l'analisi delle categorie NC continuano a funzionare identicamente dopo la migrazione.