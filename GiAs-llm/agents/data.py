"""
Data module - Configurable data loaders (CSV or PostgreSQL)

Questo modulo carica i dataset necessari per il sistema usando la sorgente
configurata (CSV o PostgreSQL).
"""

import pandas as pd
import os
from data_sources.factory import get_data_source

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

# Initialize data source and load data
try:
    _data_source = get_data_source()
    _datasets = _data_source.load_all()

    piani_df = _datasets.get("piani", pd.DataFrame())
    attivita_df = _datasets.get("attivita", pd.DataFrame())
    controlli_df = _datasets.get("controlli", pd.DataFrame())
    osa_mai_controllati_df = _datasets.get("osa_mai_controllati", pd.DataFrame())
    ocse_df = _datasets.get("ocse", pd.DataFrame())
    diff_prog_eseg_df = _datasets.get("diff_prog_eseg", pd.DataFrame())
    personale_df = _datasets.get("personale", pd.DataFrame())

    print(f"[Data] Caricati: piani={len(piani_df)}, attivita={len(attivita_df)}, controlli={len(controlli_df)}, osa={len(osa_mai_controllati_df)}, ocse={len(ocse_df)}, diff_prog_eseg={len(diff_prog_eseg_df)}, personale={len(personale_df)}")
except Exception as e:
    print(f"[Data] Errore caricamento dati: {e}")
    piani_df = pd.DataFrame()
    attivita_df = pd.DataFrame()
    controlli_df = pd.DataFrame()
    osa_mai_controllati_df = pd.DataFrame()
    ocse_df = pd.DataFrame()
    diff_prog_eseg_df = pd.DataFrame()
    personale_df = pd.DataFrame()


def load_data(data_dir: str = None):
    """
    Ricarica tutti i dati dalla sorgente configurata.

    Args:
        data_dir: (Deprecated) Directory contenente i file CSV - usare config.json invece

    Note:
        Questa funzione ricarica i dati dalla sorgente configurata.
        Per compatibilità, il parametro data_dir è mantenuto ma ignorato.
    """
    global piani_df, attivita_df, controlli_df, osa_mai_controllati_df, ocse_df, diff_prog_eseg_df, personale_df, _data_source, _datasets

    try:
        # Reload from configured data source
        _data_source = get_data_source()
        _datasets = _data_source.load_all()

        piani_df = _datasets.get("piani", pd.DataFrame())
        attivita_df = _datasets.get("attivita", pd.DataFrame())
        controlli_df = _datasets.get("controlli", pd.DataFrame())
        osa_mai_controllati_df = _datasets.get("osa_mai_controllati", pd.DataFrame())
        ocse_df = _datasets.get("ocse", pd.DataFrame())
        diff_prog_eseg_df = _datasets.get("diff_prog_eseg", pd.DataFrame())
        personale_df = _datasets.get("personale", pd.DataFrame())

        print(f"[Data] Ricaricati: piani={len(piani_df)}, controlli={len(controlli_df)}, personale={len(personale_df)}")
    except Exception as e:
        print(f"[Data] Error reloading data: {e}")


def get_uoc_from_user_id(user_id: str) -> str:
    """
    Risolve la UOC dal user_id usando personale_df.

    Args:
        user_id: ID utente

    Returns:
        Nome UOC o None
    """
    if not user_id:
        return None

    # Note: user_id di test (test_*) ritornano None - i test devono gestire UOC mancante
    # Questo riflette il comportamento reale per utenti non autenticati o senza UOC

    if personale_df.empty:
        return None

    try:
        # Normalizza user_id (rimuovi .0 se presente)
        user_id_str = str(user_id).replace('.0', '')

        # Prova match come stringa (gestisce sia "42423" che "42423.0")
        user_row = personale_df[
            personale_df['user_id'].astype(str).str.replace('.0', '', regex=False) == user_id_str
        ]
        if not user_row.empty:
            return user_row.iloc[0]['descrizione_uoc']
    except (ValueError, KeyError) as e:
        pass

    return None
