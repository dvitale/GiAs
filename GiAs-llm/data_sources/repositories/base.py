"""
Interfacce base per i repository.

Ogni repository è un Protocol (structural typing) così le concrezioni
pandas/sql non devono ereditare esplicitamente — basta che implementino
i metodi della firma.

Regola fondamentale di contratto:
    Le due implementazioni (pandas e sql) di uno stesso repository
    DEVONO restituire strutture dati con la stessa forma (stesse colonne,
    stesso tipo di wrapper DataFrame/dict/list). Il codice chiamante non
    deve accorgersi di quale implementazione stia usando.

Questo è garantito dai "contract test" in tests/integration/db/.
"""

from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
import pandas as pd


@runtime_checkable
class PianoRepository(Protocol):
    """
    Repository per query su piani/attività di monitoraggio.

    Copre gli accessi a `piani_monitoraggio` (piani_df in-memory o tabella/MV SQL).
    NON copre i controlli eseguiti (`cu_eseguiti_nc`) — quelli vanno nel
    ControlliRepository di Fase 2.

    Tutti i metodi ritornano strutture `pandas` o primitive Python standard,
    per mantenere compatibilità con il codice pre-esistente che si aspetta
    DataFrame dal DataRetriever.
    """

    def find_by_alias(self, piano_id: str) -> Optional[pd.DataFrame]:
        """
        Recupera tutte le righe di un piano/attività per alias.

        Replica il comportamento di `DataRetriever.get_piano_by_id`, incluso il
        triplo fallback:
          1. Match diretto su `alias_piano_attivita` o `alias_indicatore`
          2. Prefix "ATT " automatico (es. "AO5_A" → "ATT AO5_A")
          3. Prefix pattern con normalizzazione spazio/underscore
             (es. "B47" → "ATT B47" o "ATT_B47")

        Args:
            piano_id: Codice alfanumerico (case-insensitive)

        Returns:
            DataFrame con le righe del piano, o None se nessun match.
            Colonne minime: {sezione, alias_piano_attivita, alias_indicatore,
                             descrizione_piano_attivita, descrizione_indicatore,
                             campionamento, tipo_piano_attivita}
        """
        ...

    def search(
        self,
        query: str,
        sezione: Optional[str] = None,
        campionamento: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca full-text su descrizioni piani (equivalente SQL ILIKE '%query%').

        Replica `DataRetriever.search_piani_by_db`.

        Args:
            query: Termine di ricerca (es. "scrofe", "bovini")
            sezione: Lettera sezione (es. "A", "B") per filtrare su colonna sezione
            campionamento: Filtro booleano su tipo piano

        Returns:
            Lista di dict con chiavi {sezione, alias_piano_attivita,
            alias_indicatore, descrizione_piano_attivita,
            descrizione_indicatore, campionamento}.
            Lista vuota se nessun match.
        """
        ...

    def count_attivita(self, piano_id: str) -> int:
        """
        Conta le righe "attività" associate a un piano.

        Usato da BusinessLogic.compare_plans_metrics. Conta:
          - +1 per ogni `descrizione_piano_attivita` non-NULL
          - +1 per ogni `descrizione_indicatore` non-NULL
        """
        ...


@runtime_checkable
class ControlliRepository(Protocol):
    """
    Repository per query su `cu_eseguiti_nc` (controlli ufficiali eseguiti
    con NC inline).

    Tabella più grande del sistema (~3.3M righe). I metodi devono SEMPRE
    filtrare il più stretto possibile a livello SQL per evitare scaricare
    intere tabelle.
    """

    def get_by_piano(self, piano_id: str) -> Optional[pd.DataFrame]:
        """
        Recupera controlli eseguiti per un piano/attività.

        Replica `DataRetriever.get_controlli_by_piano`, inclusa la
        distinzione piano/attività (prefix "ATT ") e il fallback regex.

        Returns:
            DataFrame non vuoto o None. Colonne minime:
            {id_controllo, alias_indicatore, descrizione_indicatore,
             descrizione_piano, macroarea_cu, aggregazione_cu, attivita_cu,
             descrizione_uos, descrizione_asl, data_inizio_controllo,
             numero_nc_gravi, numero_nc_non_gravi, tipo_piano_attivita}
        """
        ...

    def count_stabilimenti_by_piano(self, piano_id: str) -> int:
        """
        Conta tipologie distinte di stabilimenti per un piano.
        Usato da BusinessLogic._count_stabilimenti.
        """
        ...

    def get_by_asl(self, asl: str) -> pd.DataFrame:
        """
        Recupera controlli filtrati per ASL (substring match case-insensitive
        su `descrizione_asl`).

        Usato da tool di prossimità/geo per evitare scaricare l'intera
        tabella (3.3M righe) quando l'ASL è nota.
        """
        ...


@runtime_checkable
class DiffRepository(Protocol):
    """
    Repository per `cu_diff_programmati_eseguiti`.

    Le query sono sempre filtrate per UOC (almeno) + opzionalmente ASL/UOS/anno.
    """

    def get_for_struttura(
        self,
        uoc_name: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Recupera differenze programmati/eseguiti filtrate per struttura.

        Replica `DataRetriever.get_diff_programmati_eseguiti`.

        Args:
            uoc_name: Nome UOC (substring match, case-insensitive)
            asl: Filtro ASL (substring match)
            uos: Filtro UOS (substring match, soft fallback se 0 risultati)

        Returns:
            DataFrame con colonne minime {alias_indicatore, alias_piano_attivita,
            descrizione_indicatore, descrizione_uoc, descrizione_uos,
            descrizione_asl, anno, programmati, eseguiti}.
        """
        ...

    def get_programmati_for_piano(
        self,
        piano_code: str,
        asl: Optional[str] = None,
        uos: Optional[str] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Recupera righe programmati/eseguiti per un piano (su alias_piano_attivita)
        con filtri opzionali ASL/UOS/anno.

        Usato da `get_programmed_controls_summary` per la query SUM aggregata.
        """
        ...


@runtime_checkable
class OsaRepository(Protocol):
    """
    Repository per `osa_mai_controllati` — stabilimenti mai controllati.
    """

    def get_all(
        self,
        asl: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Recupera stabilimenti mai controllati, opzionalmente filtrati per ASL.

        Replica `DataRetriever.get_osa_mai_controllati`.

        Returns:
            DataFrame con colonne minime: {ragione_sociale, asl, macroarea,
            aggregazione, attivita, comune, num_riconoscimento, n_reg,
            codice_fiscale, partita_iva, indirizzo, data_inizio_attivita,
            latitudine_stab, longitudine_stab}
        """
        ...


@runtime_checkable
class RiskRepository(Protocol):
    """
    Repository per calcoli di rischio per tipologia di attività.

    Contract invariant: il DataFrame ritornato deve avere le colonne:
      {macroarea, aggregazione, linea_attivita, tot_nc_gravi,
       tot_nc_non_gravi, tot_nc_totali, numero_controlli_totali,
       prob_nc, impatto, punteggio_rischio_totale}

    Le due impl (pandas/sql) devono produrre strutture identiche.
    La versione SQL legge da `v_risk_score_per_attivita` (vedi
    sql/risk_score_view.sql) e rinomina `risk_score` →
    `punteggio_rischio_totale` per mantenere il contract con il codice
    consumer (risk_tools, RiskAnalyzer).
    """

    def get_risk_scores(self) -> pd.DataFrame:
        """
        Ritorna il DataFrame dei risk score per tutte le attività con rischio > 0.
        Replica `RiskAnalyzer.calculate_risk_scores`.
        """
        ...
