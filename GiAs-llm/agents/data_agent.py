"""
Data/Reasoning Agent - Layer 2

Responsabilità:
- Recupero dati dai CSV
- Logica di business (filtering, aggregation, correlations)
- Analisi statistiche, ranking
- NO generazione testo "umano"
- Output: strutture dati pure (dict, list, DataFrame)
"""

import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import os
import re

try:
    from agents.data import (
        piani_df,
        attivita_df,
        controlli_df,
        osa_mai_controllati_df,
        ocse_df,
        diff_prog_eseg_df
    )
    from agents.utils import enhanced_similarity, expand_terms, filter_by_asl
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agents.data import (
        piani_df,
        attivita_df,
        controlli_df,
        osa_mai_controllati_df,
        ocse_df,
        diff_prog_eseg_df
    )
    from agents.utils import enhanced_similarity, expand_terms, filter_by_asl


# Costanti per l'analisi delle categorie di non conformità
NC_CATEGORY_WEIGHTS = {
    'HACCP': 1.0,  # Massima criticità - sistema preventivo
    'IGIENE DEGLI ALIMENTI': 0.9,  # Alto rischio sanitario
    'CONDIZIONI DELLA STRUTTURA E DELLE ATTREZZATURE': 0.8,
    'CONDIZIONI DI PULIZIA E SANIFICAZIONE': 0.8,
    'IGIENE DELLE LAVORAZIONI': 0.7,
    'RINTRACCIABILITÀ/RITIRO/RICHIAMO': 0.6,  # Critico per gestione crisi
    'IGIENE DEL PERSONALE': 0.5,
    'RICONOSCIMENTO/REGISTRAZIONE': 0.4,  # Amministrativo
    'ETICHETTATURA': 0.3,  # Meno critico per sicurezza
    'LOTTA AGLI INFESTANTI': 0.5,
    'MOCA': 0.4
}

# Lista delle categorie valide per validazione
VALID_NC_CATEGORIES = list(NC_CATEGORY_WEIGHTS.keys())


class DataRetriever:
    """
    Recupero dati puro dai CSV senza logica di presentazione.
    """

    _qdrant_client = None
    _embedding_model = None
    _qdrant_available = False

    @staticmethod
    def get_piano_by_id(piano_id: str) -> Optional[pd.DataFrame]:
        """
        Recupera piano per ID (alias o alias_indicatore).

        Returns:
            DataFrame con righe del piano o None se non trovato
        """
        if piani_df.empty or not piano_id:
            return None

        piano_rows = piani_df[
            (piani_df["alias"].str.upper() == piano_id.upper()) |
            (piani_df["alias_indicatore"].str.upper() == piano_id.upper())
        ]

        return piano_rows if not piano_rows.empty else None

    @staticmethod
    def get_controlli_by_piano(piano_id: str) -> Optional[pd.DataFrame]:
        """
        Recupera controlli eseguiti per un piano usando il campo descrizione_indicatore.

        Returns:
            DataFrame con controlli filtrati o None se non trovato
        """
        if controlli_df.empty or not piano_id:
            return None

        # Usa descrizione_indicatore con matching case-insensitive e startswith
        piano_upper = piano_id.upper()
        piano_filtrato = controlli_df[
            controlli_df['descrizione_indicatore'].str.upper().str.startswith(piano_upper, na=False)
        ]

        return piano_filtrato if not piano_filtrato.empty else None

    @staticmethod
    def get_osa_mai_controllati(asl: Optional[str] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Recupera stabilimenti mai controllati, opzionalmente filtrati per ASL.

        Returns:
            DataFrame filtrato (può essere vuoto)
        """
        if osa_mai_controllati_df.empty:
            return pd.DataFrame()

        df = osa_mai_controllati_df.copy()

        if asl:
            try:
                df = filter_by_asl(df, asl, 'asl')
            except ValueError:
                pass

        if limit and limit > 0:
            df = df.head(limit)

        return df

    @staticmethod
    def get_diff_programmati_eseguiti(uoc_name: str) -> pd.DataFrame:
        """
        Recupera differenze programmati vs eseguiti per struttura UOC.

        Returns:
            DataFrame filtrato per UOC
        """
        if diff_prog_eseg_df.empty or not uoc_name:
            return pd.DataFrame()

        return diff_prog_eseg_df[
            diff_prog_eseg_df['descrizione_uoc'].str.contains(uoc_name, case=False, na=False)
        ].copy()

    @classmethod
    def _initialize_qdrant(cls):
        """Lazy initialization di Qdrant + embedding model"""
        if cls._qdrant_client is not None:
            return

        try:
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer

            qdrant_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "qdrant_storage"
            )

            if not os.path.exists(qdrant_path):
                print(f"⚠️  Qdrant storage not found: {qdrant_path}")
                print("   Run: python3 tools/indexing/build_qdrant_index.py")
                cls._qdrant_available = False
                return

            cls._qdrant_client = QdrantClient(path=qdrant_path)

            cls._embedding_model = SentenceTransformer(
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            )

            try:
                cls._qdrant_client.get_collection("piani_monitoraggio")
                cls._qdrant_available = True
                print("✅ Qdrant semantic search disponibile")
            except:
                print("⚠️  Collection 'piani_monitoraggio' non trovata in Qdrant")
                cls._qdrant_available = False

        except ImportError as e:
            print(f"⚠️  Qdrant/SentenceTransformers non disponibile: {e}")
            print("   Falling back to keyword search")
            cls._qdrant_available = False
        except Exception as e:
            print(f"⚠️  Errore inizializzazione Qdrant: {e}")
            cls._qdrant_available = False

    # LRU Cache for embeddings and search results
    _embedding_cache = {}
    _search_results_cache = {}
    _cache_max_size = 100

    @classmethod
    def _get_cached_embedding(cls, query: str):
        """Get cached embedding or compute and cache it."""
        if query in cls._embedding_cache:
            return cls._embedding_cache[query]

        # Compute embedding
        embedding = cls._embedding_model.encode(query, show_progress_bar=False)

        # Cache with size limit
        if len(cls._embedding_cache) >= cls._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(cls._embedding_cache))
            del cls._embedding_cache[oldest_key]

        cls._embedding_cache[query] = embedding
        return embedding

    @classmethod
    def search_piani_semantic(cls, query: str, top_k: int = 10, score_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Semantic search usando Qdrant + sentence-transformers with embedding cache.

        Args:
            query: User query (es. "benessere animale negli allevamenti")
            top_k: Numero massimo risultati
            score_threshold: Soglia minima similarity (0-1)

        Returns:
            Lista di piani ordinati per similarity score
        """
        cls._initialize_qdrant()

        if not cls._qdrant_available:
            return []

        # Check cache for full search results
        cache_key = f"{query}_{top_k}_{score_threshold}"
        if cache_key in cls._search_results_cache:
            return cls._search_results_cache[cache_key]

        try:
            query_vector = cls._get_cached_embedding(query)

            search_results = cls._qdrant_client.query_points(
                collection_name="piani_monitoraggio",
                query=query_vector.tolist(),
                limit=top_k,
                score_threshold=score_threshold
            ).points

            matches = []
            for hit in search_results:
                matches.append({
                    'alias': hit.payload['alias'],
                    'alias_indicatore': hit.payload.get('alias_indicatore', ''),
                    'sezione': hit.payload.get('sezione', ''),
                    'descrizione': hit.payload.get('descrizione', ''),
                    'descrizione_2': hit.payload.get('descrizione_2', ''),
                    'similarity': hit.score,
                    'rank': len(matches) + 1
                })

            # Cache results
            if len(cls._search_results_cache) >= cls._cache_max_size:
                # Remove oldest entry
                oldest_key = next(iter(cls._search_results_cache))
                del cls._search_results_cache[oldest_key]

            cls._search_results_cache[cache_key] = matches
            return matches

        except Exception as e:
            print(f"❌ Errore semantic search: {e}")
            return []

    @classmethod
    def search_procedure_docs(cls, query: str, top_k: int = 10, score_threshold: float = 0.45) -> List[Dict[str, Any]]:
        """
        Ricerca semantica nella collection procedure_documents (RAG).
        Riusa _qdrant_client e _embedding_model gia' inizializzati.

        Args:
            query: Domanda dell'utente (es. "procedura ispezione semplice")
            top_k: Numero massimo chunk da restituire
            score_threshold: Soglia minima similarity (0-1)

        Returns:
            Lista di chunk ordinati per score, con content + metadata.
        """
        cls._initialize_qdrant()

        if not cls._qdrant_available:
            return []

        try:
            query_vector = cls._get_cached_embedding(query)

            search_results = cls._qdrant_client.query_points(
                collection_name="procedure_documents",
                query=query_vector.tolist(),
                limit=top_k,
                score_threshold=score_threshold
            ).points

            return [
                {
                    "content": hit.payload.get("content", ""),
                    "source_file": hit.payload.get("source_file", ""),
                    "section": hit.payload.get("section", ""),
                    "title": hit.payload.get("title", ""),
                    "score": hit.score
                }
                for hit in search_results
            ]

        except Exception as e:
            print(f"⚠️  Errore ricerca procedure_documents: {e}")
            return []

    # Class-level caches for performance
    _search_cache = {}
    _piani_cache = None

    @staticmethod
    def search_piani_by_keyword(keyword: str, similarity_threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Cerca piani per keyword usando similarità semantica con caching ottimizzato.

        Returns:
            Lista di dict con piano + score similarità
        """
        # Use cached piani data instead of reloading every time
        if DataRetriever._piani_cache is None:
            from data_sources.factory import get_data_source
            data_source = get_data_source()
            piani_raw = data_source.get_piani()
            # Precompute desc_full once and store in cache
            piani_raw['desc_full'] = (
                piani_raw['descrizione'].fillna('').astype(str) + " " +
                piani_raw.get('descrizione-2', pd.Series([''] * len(piani_raw))).fillna('').astype(str)
            ).str.strip()
            DataRetriever._piani_cache = piani_raw
            print(f"[DataRetriever] Cached piani data with precomputed desc_full: {len(DataRetriever._piani_cache)} rows")

        piani_df = DataRetriever._piani_cache

        if piani_df.empty or not keyword:
            return []

        # Cache check for search results
        cache_key = f"{keyword}_{similarity_threshold}"
        if cache_key in DataRetriever._search_cache:
            print(f"[DataRetriever] Using cached search result for: {keyword}")
            return DataRetriever._search_cache[cache_key]

        search_term_expanded = expand_terms(keyword)
        matches = []

        # desc_full is already precomputed in cache - no need to copy or recompute
        # Filter out empty descriptions directly
        valid_piani = piani_df[piani_df['desc_full'] != '']

        # Vectorized similarity calculation
        valid_descriptions = valid_piani['desc_full'].tolist()
        valid_indices = valid_piani.index.tolist()

        # Calculate similarities for all descriptions at once
        for i, desc_completa in enumerate(valid_descriptions):
            max_similarity = 0
            for term in search_term_expanded:
                sim = enhanced_similarity(term, desc_completa)
                max_similarity = max(max_similarity, sim)

            if max_similarity > similarity_threshold:
                row_idx = valid_indices[i]
                row_data = valid_piani.loc[row_idx]
                matches.append({
                    'sezione': row_data.get('sezione', ''),
                    'alias': row_data.get('alias', ''),
                    'alias_indicatore': row_data.get('alias_indicatore', ''),
                    'descrizione': row_data.get('descrizione', ''),
                    'descrizione-2': row_data.get('descrizione-2', ''),
                    'similarity': max_similarity
                })

        matches.sort(key=lambda x: x['similarity'], reverse=True)

        # Cache result with size limit
        if len(DataRetriever._search_cache) >= 50:
            # Remove oldest entries
            keys_to_remove = list(DataRetriever._search_cache.keys())[:10]
            for key in keys_to_remove:
                del DataRetriever._search_cache[key]

        DataRetriever._search_cache[cache_key] = matches
        print(f"[DataRetriever] Cached search result for: {keyword} ({len(matches)} matches)")

        return matches

    @staticmethod
    def clear_search_cache():
        """Clear search cache."""
        DataRetriever._search_cache.clear()
        DataRetriever._piani_cache = None
        print("[DataRetriever] Search cache cleared")

    @staticmethod
    def get_user_structure(user_asl: str, user_id: Optional[int] = None) -> Optional[Tuple[str, str]]:
        """
        Recupera struttura organizzativa utente da personale.csv.

        Returns:
            Tuple (user_structure, uoc_name) o None se non trovato
        """
        try:
            # Use data source instead of hardcoded path
            from data_sources.factory import get_data_source
            data_source = get_data_source()
            personale_df = data_source.get_personale()

            user_record = None
            if user_id:
                user_record = personale_df[personale_df['user_id'] == int(user_id)]

            if user_record is None or user_record.empty:
                user_record = personale_df[personale_df['asl'].str.upper() == user_asl.upper()]

            if user_record.empty:
                return None

            user_structure = user_record.iloc[0]['descrizione']
            user_uoc = user_record.iloc[0]['descrizione_area_struttura_complessa']

            structure_parts = user_structure.split('->')
            uoc_name = structure_parts[1].strip() if len(structure_parts) > 1 else user_uoc

            return (user_structure, uoc_name)

        except Exception as e:
            print(f"[DataRetriever.get_user_structure] Error: {e}")
            return None

    @staticmethod
    def get_establishment_history(
        num_registrazione: Optional[str] = None,
        partita_iva: Optional[str] = None,
        ragione_sociale: Optional[str] = None,
        limit: int = 50
    ) -> Optional[pd.DataFrame]:
        """
        Recupera storico controlli per stabilimento identificato da:
        - num_registrazione (es. "IT 123", "UE IT 2287 M")
        - partita_iva (solo numeri)
        - ragione_sociale (ricerca parziale case-insensitive)

        Includes non-conformità (NC) data joined from ocse_df.

        Returns:
            DataFrame con controlli ordinati per data (più recenti primi) o None
        """
        if controlli_df.empty:
            return None

        # Almeno un parametro deve essere specificato
        if not any([num_registrazione, partita_iva, ragione_sociale]):
            return None

        filters = []

        if num_registrazione:
            # Normalizza numero registrazione (rimuovi spazi, uppercase)
            num_norm = num_registrazione.upper().replace(" ", "")
            filters.append(
                controlli_df['num_registrazione'].fillna('').str.upper().str.replace(" ", "") == num_norm
            )

        if partita_iva:
            # Partita IVA: ricerca parziale per gestire zeri iniziali (02611810645 vs 2611810645)
            filters.append(
                controlli_df['partita_iva'].astype(str).str.contains(
                    str(partita_iva).strip(), na=False, regex=False
                )
            )

        if ragione_sociale:
            # Ricerca parziale case-insensitive (escape regex characters for safety)
            import re
            escaped_ragione_sociale = re.escape(ragione_sociale)
            filters.append(
                controlli_df['ragione_sociale'].fillna('').str.contains(
                    escaped_ragione_sociale, case=False, na=False, regex=True
                )
            )

        # Combina filtri con OR logic
        combined_filter = filters[0]
        for f in filters[1:]:
            combined_filter = combined_filter | f

        result_df = controlli_df[combined_filter].copy()

        if result_df.empty:
            return None

        # Join con NC (ocse_df) se disponibile
        if not ocse_df.empty and 'id_controllo' in result_df.columns:
            # Join left per mantenere tutti i controlli anche senza NC
            result_df = result_df.merge(
                ocse_df[['id_controllo_ufficiale', 'numero_nc_gravi', 'numero_nc_non_gravi',
                         'tipo_non_conformita', 'oggetto_non_conformita']],
                left_on='id_controllo',
                right_on='id_controllo_ufficiale',
                how='left'
            )

        # Ordina per data controllo (più recenti primi)
        if 'data_inizio_controllo' in result_df.columns:
            result_df['data_inizio_controllo'] = pd.to_datetime(
                result_df['data_inizio_controllo'], errors='coerce'
            )
            result_df = result_df.sort_values('data_inizio_controllo', ascending=False)

        return result_df.head(limit) if limit > 0 else result_df

    @staticmethod
    def get_osa_near_location(
        center_lat: float,
        center_lon: float,
        radius_km: float = 5.0,
        asl: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Recupera stabilimenti mai controllati vicino a una posizione geografica.

        Args:
            center_lat: Latitudine centro ricerca
            center_lon: Longitudine centro ricerca
            radius_km: Raggio di ricerca in km (default 5)
            asl: Filtra per ASL specifica (opzionale)
            limit: Numero massimo di risultati (opzionale)

        Returns:
            DataFrame con stabilimenti filtrati per prossimità, ordinati per distanza.
            Include colonna 'distanza_km'.
        """
        if osa_mai_controllati_df.empty:
            return pd.DataFrame()

        df = osa_mai_controllati_df.copy()

        # Filtra per ASL se specificata
        if asl:
            try:
                df = filter_by_asl(df, asl, 'asl')
            except ValueError:
                pass

        if df.empty:
            return pd.DataFrame()

        # Import lazy per evitare dipendenze circolari
        try:
            from tools.geo_utils import filter_by_proximity
        except ImportError:
            print("[DataRetriever.get_osa_near_location] geo_utils non disponibile")
            return pd.DataFrame()

        # Applica filtro prossimità
        # Note: la tabella osa_mai_controllati non ha coordinate,
        # filter_by_proximity tenterà geocodifica da indirizzo+comune
        filtered_df = filter_by_proximity(
            df=df,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            address_col='indirizzo',
            comune_col='comune'
        )

        # Limita risultati se richiesto
        if limit and limit > 0:
            filtered_df = filtered_df.head(limit)

        return filtered_df

    @staticmethod
    def get_nc_by_category(categoria: str, asl: Optional[str] = None) -> pd.DataFrame:
        """
        Filtra dataset OCSE per categoria NC specifica.

        Args:
            categoria: Nome categoria NC (es. 'HACCP', 'IGIENE DEGLI ALIMENTI')
            asl: Filtro opzionale per ASL specifica

        Returns:
            DataFrame filtrato per categoria NC
        """
        if ocse_df.empty:
            return pd.DataFrame()

        # Validazione categoria
        if categoria not in VALID_NC_CATEGORIES:
            return pd.DataFrame()

        ocse_copy = ocse_df.copy()

        # Filtra per categoria NC (partial match case-insensitive)
        ocse_copy = ocse_copy[ocse_copy['oggetto_non_conformita'].str.contains(categoria, case=False, na=False)]

        # Filtra per ASL se specificata
        if asl:
            try:
                ocse_copy = filter_by_asl(ocse_copy, asl, 'asl')
            except Exception:
                # Se il filtro ASL fallisce, continuiamo senza filtro ASL
                pass

        return ocse_copy

    @staticmethod
    def get_establishments_with_nc_category(categoria: str, limit: int = 20, asl: Optional[str] = None) -> pd.DataFrame:
        """
        Identifica stabilimenti con NC storiche per categoria specifica.

        Args:
            categoria: Nome categoria NC
            limit: Numero massimo di stabilimenti da restituire
            asl: Filtro opzionale per ASL specifica

        Returns:
            DataFrame con stabilimenti che hanno avuto NC nella categoria
        """
        if ocse_df.empty:
            return pd.DataFrame()

        # Validazione categoria
        if categoria not in VALID_NC_CATEGORIES:
            return pd.DataFrame()

        ocse_copy = ocse_df.copy()

        # Filtra per categoria NC (partial match case-insensitive)
        ocse_copy = ocse_copy[ocse_copy['oggetto_non_conformita'].str.contains(categoria, case=False, na=False)]

        # Filtra per ASL se specificata
        if asl:
            try:
                ocse_copy = filter_by_asl(ocse_copy, asl, 'asl')
            except Exception:
                # Se il filtro ASL fallisce, continuiamo senza filtro ASL
                pass

        if ocse_copy.empty:
            return pd.DataFrame()

        # Pulizia dati NC
        ocse_copy['numero_nc_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_gravi'], errors='coerce'
        ).fillna(0)
        ocse_copy['numero_nc_non_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_non_gravi'], errors='coerce'
        ).fillna(0)

        # Aggrega per stabilimento
        establishment_nc = ocse_copy.groupby([
            'numero_riconoscimento',
            'asl',
            'comune',
            'macroarea_sottoposta_a_controllo',
            'aggregazione_sottoposta_a_controllo'
        ]).agg({
            'numero_nc_gravi': 'sum',
            'numero_nc_non_gravi': 'sum',
            'id_controllo_ufficiale': 'count'
        }).reset_index()

        establishment_nc.columns = [
            'numero_riconoscimento', 'asl', 'comune', 'macroarea', 'aggregazione',
            'tot_nc_gravi', 'tot_nc_non_gravi', 'controlli_totali'
        ]

        # Calcola totale NC
        establishment_nc['tot_nc_categoria'] = (
            establishment_nc['tot_nc_gravi'] +
            establishment_nc['tot_nc_non_gravi']
        )

        # Calcola percentuale NC per la categoria
        establishment_nc['percentuale_nc_categoria'] = (
            establishment_nc['tot_nc_categoria'] /
            establishment_nc['controlli_totali'].replace(0, 1) * 100
        ).round(2)

        # Aggiungi informazione categoria
        establishment_nc['categoria_nc'] = categoria

        # Ordina per numero totale di NC nella categoria (decrescente)
        establishment_nc = establishment_nc.sort_values(
            'tot_nc_categoria', ascending=False
        )

        return establishment_nc.head(limit)


class BusinessLogic:
    """
    Logica di business: aggregazioni, correlazioni, ranking.
    NO testo di presentazione.
    """

    @staticmethod
    def aggregate_stabilimenti_by_piano(controlli_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """
        Aggrega controlli per tipologia stabilimento includendo non conformità.

        Approccio: join diretto su id_controllo per contare solo le NC
        dei controlli effettivamente presenti nel DataFrame.

        Returns:
            DataFrame con top_n tipologie ordinate per count, incluse NC
        """
        if controlli_df.empty:
            return pd.DataFrame()

        # Approccio semplice: join controlli con NC usando id_controllo
        if not ocse_df.empty and 'id_controllo' in controlli_df.columns:
            try:
                # Prepara dati NC con pulizia valori
                nc_data = ocse_df[['id_controllo_ufficiale', 'numero_nc_gravi', 'numero_nc_non_gravi']].copy()
                nc_data['numero_nc_gravi'] = pd.to_numeric(nc_data['numero_nc_gravi'], errors='coerce').fillna(0).astype('int64')
                nc_data['numero_nc_non_gravi'] = pd.to_numeric(nc_data['numero_nc_non_gravi'], errors='coerce').fillna(0).astype('int64')

                # Aggrega NC per id_controllo (un controllo può avere più righe NC)
                nc_per_controllo = nc_data.groupby('id_controllo_ufficiale').agg({
                    'numero_nc_gravi': 'sum',
                    'numero_nc_non_gravi': 'sum'
                }).reset_index()

                # Join controlli con NC
                controlli_con_nc = controlli_df.merge(
                    nc_per_controllo,
                    left_on='id_controllo',
                    right_on='id_controllo_ufficiale',
                    how='left'
                )

                # Riempi NaN con 0
                controlli_con_nc['numero_nc_gravi'] = controlli_con_nc['numero_nc_gravi'].fillna(0).astype('int64')
                controlli_con_nc['numero_nc_non_gravi'] = controlli_con_nc['numero_nc_non_gravi'].fillna(0).astype('int64')

                # Aggrega per tipologia stabilimento
                stabilimenti_count = controlli_con_nc.groupby(
                    ['macroarea_cu', 'aggregazione_cu', 'attivita_cu']
                ).agg({
                    'id_controllo': 'count',  # Numero controlli
                    'numero_nc_gravi': 'sum',
                    'numero_nc_non_gravi': 'sum'
                }).reset_index()

                stabilimenti_count = stabilimenti_count.rename(columns={'id_controllo': 'count'})

            except Exception as e:
                print(f"⚠️ Errore nel join NC: {e}, fallback a conteggio semplice")
                # Fallback: solo conteggio controlli senza NC
                stabilimenti_count = controlli_df.groupby(
                    ['macroarea_cu', 'aggregazione_cu', 'attivita_cu']
                ).size().reset_index(name='count')
                stabilimenti_count['numero_nc_gravi'] = 0
                stabilimenti_count['numero_nc_non_gravi'] = 0
        else:
            # Nessun dato NC disponibile
            stabilimenti_count = controlli_df.groupby(
                ['macroarea_cu', 'aggregazione_cu', 'attivita_cu']
            ).size().reset_index(name='count')
            stabilimenti_count['numero_nc_gravi'] = 0
            stabilimenti_count['numero_nc_non_gravi'] = 0

        # Calcola metriche di rischio
        if not stabilimenti_count.empty:
            try:
                # Calcola totale NC
                stabilimenti_count['tot_nc_totali'] = (
                    stabilimenti_count['numero_nc_gravi'] +
                    stabilimenti_count['numero_nc_non_gravi']
                )

                # Evita divisione per zero
                stabilimenti_count['count_safe'] = stabilimenti_count['count'].replace(0, 1)

                # Probabilità di NC = (NC totali) / (controlli totali)
                stabilimenti_count['prob_nc'] = (
                    stabilimenti_count['tot_nc_totali'] /
                    stabilimenti_count['count_safe']
                )

                # Impatto = (NC gravi) / (controlli totali)
                stabilimenti_count['impatto'] = (
                    stabilimenti_count['numero_nc_gravi'] /
                    stabilimenti_count['count_safe']
                )

                # Risk Score migliorato: P(NC) × Impatto × 100
                stabilimenti_count['punteggio_rischio'] = (
                    stabilimenti_count['prob_nc'] *
                    stabilimenti_count['impatto'] * 100
                ).round(3)

                # Rimuovi colonne helper
                stabilimenti_count = stabilimenti_count.drop(columns=['count_safe', 'tot_nc_totali'], errors='ignore')

            except Exception as e:
                print(f"⚠️ Errore nel calcolo metriche: {e}")
                stabilimenti_count['prob_nc'] = 0.0
                stabilimenti_count['impatto'] = 0.0
                stabilimenti_count['punteggio_rischio'] = 0.0

        return stabilimenti_count.sort_values('count', ascending=False).head(top_n)

    @staticmethod
    def calculate_delayed_plans(diff_df: pd.DataFrame, piano_id: Optional[str] = None, target_year: int = None) -> pd.DataFrame:
        """
        Calcola piani in ritardo (programmati > eseguiti) per l'anno specificato.
        Solo i ritardi dell'anno corrente sono operativamente rilevanti.

        Args:
            diff_df: DataFrame con dati programmati/eseguiti
            piano_id: Filtra per piano specifico (opzionale)
            target_year: Anno di riferimento (default: anno corrente 2025)

        Returns:
            DataFrame con piani in ritardo ordinati per gravità
        """
        if diff_df.empty:
            return pd.DataFrame()

        # Filtra per anno target (default da configurazione)
        if target_year is None:
            try:
                from configs.config_loader import get_config
                target_year = get_config().get_current_year()
            except ImportError:
                # Fallback se config_loader non disponibile
                target_year = 2025

        if 'anno' in diff_df.columns:
            diff_df = diff_df[diff_df['anno'] == target_year].copy()

        if diff_df.empty:
            return pd.DataFrame()

        # Ensure numeric coercion for programmati and eseguiti before subtraction
        diff_df['programmati'] = pd.to_numeric(diff_df['programmati'], errors='coerce').fillna(0)
        diff_df['eseguiti'] = pd.to_numeric(diff_df['eseguiti'], errors='coerce').fillna(0)
        diff_df['ritardo'] = diff_df['programmati'] - diff_df['eseguiti']
        delayed = diff_df[diff_df['ritardo'] > 0].copy()

        if piano_id:
            delayed = delayed[delayed['indicatore'].str.upper() == piano_id.upper()]

        return delayed.sort_values('ritardo', ascending=False)

    @staticmethod
    def correlate_piano_attivita(piano_id: str) -> pd.DataFrame:
        """
        Trova correlazione statistica piano → attività dai controlli 2025.

        Returns:
            DataFrame con attività correlate ordinate per frequency
        """
        if controlli_df.empty or not piano_id:
            return pd.DataFrame()

        piano_attivita = controlli_df.groupby(
            ['descrizione_piano', 'attivita_cu']
        ).size().reset_index(name='count')

        related = piano_attivita[
            piano_attivita['descrizione_piano'].str.contains(piano_id, case=False, na=False)
        ]

        return related.sort_values('count', ascending=False)

    @staticmethod
    def extract_unique_piano_descriptions(piano_rows: pd.DataFrame) -> Dict[str, Any]:
        """
        Estrae descrizioni uniche da righe piano.

        Returns:
            Dict con struttura {descrizione_main: {sezione, alias, descrizione-2: [...]}}
        """
        unique_descriptions = {}

        for row in piano_rows.itertuples(index=False):
            sezione = getattr(row, "sezione", "")
            alias = getattr(row, "alias", "")
            alias_ind = getattr(row, "alias_indicatore", "")
            desc1 = getattr(row, "descrizione", "")
            desc2 = getattr(row, "descrizione_2", "")

            if pd.notna(desc1) and desc1 not in unique_descriptions:
                unique_descriptions[desc1] = {
                    'sezione': sezione,
                    'alias': alias,
                    'descrizione-2': []
                }

            if pd.notna(desc2) and desc1 in unique_descriptions:
                if desc2 not in [d['text'] for d in unique_descriptions[desc1]['descrizione-2']]:
                    unique_descriptions[desc1]['descrizione-2'].append({
                        'text': desc2,
                        'alias_ind': alias_ind
                    })

        return unique_descriptions

    @staticmethod
    def compare_plans_metrics(piano1_id: str, piano2_id: str) -> Dict[str, Any]:
        """
        Confronta metriche di due piani.

        Returns:
            Dict con metriche comparative
        """
        p1_attivita = BusinessLogic._count_attivita(piano1_id)
        p1_stabilimenti = BusinessLogic._count_stabilimenti(piano1_id)

        p2_attivita = BusinessLogic._count_attivita(piano2_id)
        p2_stabilimenti = BusinessLogic._count_stabilimenti(piano2_id)

        return {
            'piano1': {
                'id': piano1_id,
                'attivita_count': p1_attivita,
                'stabilimenti_count': p1_stabilimenti
            },
            'piano2': {
                'id': piano2_id,
                'attivita_count': p2_attivita,
                'stabilimenti_count': p2_stabilimenti
            },
            'diff_attivita': p1_attivita - p2_attivita,
            'diff_stabilimenti': p1_stabilimenti - p2_stabilimenti
        }

    @staticmethod
    def _count_attivita(piano_id: str) -> int:
        """Helper: conta attività per piano."""
        piano_rows = DataRetriever.get_piano_by_id(piano_id)
        if piano_rows is None or piano_rows.empty:
            return 0

        count = 0
        for row in piano_rows.itertuples(index=False):
            if pd.notna(getattr(row, "descrizione", None)):
                count += 1
            if pd.notna(getattr(row, "descrizione_2", None)):
                count += 1
        return count

    @staticmethod
    def _count_stabilimenti(piano_id: str) -> int:
        """Helper: conta stabilimenti per piano."""
        controlli = DataRetriever.get_controlli_by_piano(piano_id)
        if controlli is None or controlli.empty:
            return 0

        stabilimenti_count = controlli.groupby(['macroarea_cu', 'aggregazione_cu']).size()
        return len(stabilimenti_count)

    @staticmethod
    def get_piano_statistics(asl: Optional[str] = None, top_n: int = 10) -> pd.DataFrame:
        """
        Calcola statistiche aggregate sui piani di controllo eseguiti.

        Args:
            asl: Filtra per ASL specifica (opzionale)
            top_n: Numero di piani da restituire (default: 10)

        Returns:
            DataFrame con statistiche piani ordinati per numero di controlli
            Colonne: piano_code, piano_description, num_controlli, num_stabilimenti, percentuale
        """
        if controlli_df.empty:
            return pd.DataFrame()

        # Filtra per ASL se specificata
        df = controlli_df.copy()
        if asl:
            # Normalizza ASL per matching flessibile
            asl_upper = asl.upper().strip()
            df = df[df['descrizione_asl'].fillna('').str.upper().str.contains(asl_upper, na=False, regex=False)]

        if df.empty:
            return pd.DataFrame()

        # Estrai codice piano dalla descrizione_piano (es. "A1 - Descrizione" -> "A1")
        df['piano_code'] = df['descrizione_piano'].astype(str).str.split().str[0].str.upper()

        # Aggrega per piano
        stats = df.groupby(['piano_code', 'descrizione_piano']).agg({
            'id_controllo': 'count',  # Numero controlli
            'macroarea_cu': lambda x: x.nunique(),  # Numero tipologie stabilimenti
        }).reset_index()

        stats = stats.rename(columns={
            'id_controllo': 'num_controlli',
            'macroarea_cu': 'num_stabilimenti'
        })

        # Calcola percentuale sul totale
        total_controls = stats['num_controlli'].sum()
        stats['percentuale'] = (stats['num_controlli'] / total_controls * 100).round(2)

        # Ordina per numero controlli e limita ai top N
        stats = stats.sort_values('num_controlli', ascending=False).head(top_n)

        return stats


class RiskAnalyzer:
    """
    Analisi rischio basata su non conformità storiche.
    """

    # Cache for risk scores
    _risk_scores_cache = None
    _categorized_risk_scores_cache = None

    @staticmethod
    def calculate_risk_scores() -> pd.DataFrame:
        """
        Calcola punteggio rischio per attività da dataset OCSE (NC storiche) con caching.

        Formula migliorata:
        risk_score = P(NC) × Impatto
        P(NC) = (numero totale di NC) / (numero di controlli)
        Impatto = (numero NC gravi) / (numero di controlli)

        Returns:
            DataFrame con punteggi rischio per attività
        """
        # Check cache first
        if RiskAnalyzer._risk_scores_cache is not None:
            print("[RiskAnalyzer] Using cached risk scores")
            return RiskAnalyzer._risk_scores_cache

        if ocse_df.empty:
            return pd.DataFrame()

        ocse_copy = ocse_df.copy()

        # Pulizia dati NC
        ocse_copy['numero_nc_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_gravi'], errors='coerce'
        ).fillna(0)
        ocse_copy['numero_nc_non_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_non_gravi'], errors='coerce'
        ).fillna(0)

        # Aggrega per attività
        rischio_per_attivita = ocse_copy.groupby([
            'macroarea_sottoposta_a_controllo',
            'aggregazione_sottoposta_a_controllo',
            'linea_attivita_sottoposta_a_controllo'
        ]).agg({
            'numero_nc_gravi': 'sum',
            'numero_nc_non_gravi': 'sum',
            'id_controllo_ufficiale': 'count'
        }).reset_index()

        rischio_per_attivita.columns = [
            'macroarea', 'aggregazione', 'linea_attivita',
            'tot_nc_gravi', 'tot_nc_non_gravi', 'numero_controlli_totali'
        ]

        # Calcola totale NC per attività
        rischio_per_attivita['tot_nc_totali'] = (
            rischio_per_attivita['tot_nc_gravi'] +
            rischio_per_attivita['tot_nc_non_gravi']
        )

        # Evita divisione per zero
        rischio_per_attivita['numero_controlli_safe'] = rischio_per_attivita['numero_controlli_totali'].replace(0, 1)

        # Formula migliorata: P(NC) × Impatto
        # P(NC) = (numero totale di NC) / (numero di controlli)
        rischio_per_attivita['prob_nc'] = (
            rischio_per_attivita['tot_nc_totali'] /
            rischio_per_attivita['numero_controlli_safe']
        )

        # Impatto = (numero NC gravi) / (numero di controlli)
        rischio_per_attivita['impatto'] = (
            rischio_per_attivita['tot_nc_gravi'] /
            rischio_per_attivita['numero_controlli_safe']
        )

        # Risk Score = P(NC) × Impatto × 100 (per valori leggibili)
        rischio_per_attivita['punteggio_rischio_totale'] = (
            rischio_per_attivita['prob_nc'] *
            rischio_per_attivita['impatto'] * 100
        ).round(3)

        # Pulizia: rimuovi colonne helper
        rischio_per_attivita = rischio_per_attivita.drop(columns=['numero_controlli_safe'])

        # Filtra solo attività con rischio > 0
        rischio_per_attivita = rischio_per_attivita[
            rischio_per_attivita['punteggio_rischio_totale'] > 0
        ]

        result = rischio_per_attivita.sort_values('punteggio_rischio_totale', ascending=False)

        # Cache the result
        RiskAnalyzer._risk_scores_cache = result
        print(f"[RiskAnalyzer] Cached risk scores: {len(result)} activities")

        return result

    @staticmethod
    def clear_risk_cache():
        """Clear all cached risk scores."""
        RiskAnalyzer._risk_scores_cache = None
        RiskAnalyzer._categorized_risk_scores_cache = None
        print("[RiskAnalyzer] All risk scores caches cleared")

    @staticmethod
    def calculate_categorized_risk_scores() -> pd.DataFrame:
        """
        Calcola punteggio rischio per attività con dettaglio per categoria NC.

        Estende il calcolo base aggiungendo:
        - Analisi per categoria di non conformità
        - Pesi specifici per categoria
        - Breakdown dettagliato delle NC per tipo

        Returns:
            DataFrame con punteggi rischio per attività e categoria NC
        """
        # Check cache first
        if RiskAnalyzer._categorized_risk_scores_cache is not None:
            print("[RiskAnalyzer] Using cached categorized risk scores")
            return RiskAnalyzer._categorized_risk_scores_cache

        ocse_df = DataRetriever.get_ocse()
        if ocse_df.empty:
            return pd.DataFrame()

        ocse_copy = ocse_df.copy()

        # Pulizia dati NC
        ocse_copy['numero_nc_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_gravi'], errors='coerce'
        ).fillna(0)
        ocse_copy['numero_nc_non_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_non_gravi'], errors='coerce'
        ).fillna(0)

        # Normalizza categorie NC: mappa varianti a categorie canoniche
        def normalize_nc_category(value):
            """Normalizza oggetto_non_conformita a categoria canonica."""
            if pd.isna(value):
                return None
            value_upper = str(value).upper()
            for categoria in VALID_NC_CATEGORIES:
                if categoria.upper() in value_upper:
                    return categoria
            return None

        ocse_copy['categoria_nc_normalized'] = ocse_copy['oggetto_non_conformita'].apply(normalize_nc_category)

        # Filtra solo record con categorie NC valide (dopo normalizzazione)
        ocse_copy = ocse_copy[ocse_copy['categoria_nc_normalized'].notna()]

        if ocse_copy.empty:
            return pd.DataFrame()

        # Aggrega per attività E categoria NC (usa categoria normalizzata)
        rischio_per_categoria = ocse_copy.groupby([
            'macroarea_sottoposta_a_controllo',
            'aggregazione_sottoposta_a_controllo',
            'linea_attivita_sottoposta_a_controllo',
            'categoria_nc_normalized'
        ]).agg({
            'numero_nc_gravi': 'sum',
            'numero_nc_non_gravi': 'sum',
            'id_controllo_ufficiale': 'count'
        }).reset_index()

        rischio_per_categoria.columns = [
            'macroarea', 'aggregazione', 'linea_attivita', 'categoria_nc',
            'tot_nc_gravi', 'tot_nc_non_gravi', 'numero_controlli_totali'
        ]

        # Calcola totale NC per categoria
        rischio_per_categoria['tot_nc_totali'] = (
            rischio_per_categoria['tot_nc_gravi'] +
            rischio_per_categoria['tot_nc_non_gravi']
        )

        # Evita divisione per zero
        rischio_per_categoria['numero_controlli_safe'] = rischio_per_categoria['numero_controlli_totali'].replace(0, 1)

        # Calcola probabilità NC e impatto per categoria
        rischio_per_categoria['prob_nc'] = (
            rischio_per_categoria['tot_nc_totali'] /
            rischio_per_categoria['numero_controlli_safe']
        )

        rischio_per_categoria['impatto'] = (
            rischio_per_categoria['tot_nc_gravi'] /
            rischio_per_categoria['numero_controlli_safe']
        )

        # Applica peso categoria
        rischio_per_categoria['peso_categoria'] = rischio_per_categoria['categoria_nc'].map(
            NC_CATEGORY_WEIGHTS
        ).fillna(0.5)  # Default weight per categorie non mappate

        # Risk Score = P(NC) × Impatto × Peso_Categoria × 100
        rischio_per_categoria['punteggio_rischio_categoria'] = (
            rischio_per_categoria['prob_nc'] *
            rischio_per_categoria['impatto'] *
            rischio_per_categoria['peso_categoria'] * 100
        ).round(3)

        # Pulizia: rimuovi colonne helper
        rischio_per_categoria = rischio_per_categoria.drop(columns=['numero_controlli_safe'])

        # Filtra solo record con rischio > 0
        rischio_per_categoria = rischio_per_categoria[
            rischio_per_categoria['punteggio_rischio_categoria'] > 0
        ]

        result = rischio_per_categoria.sort_values('punteggio_rischio_categoria', ascending=False)

        # Cache the result
        RiskAnalyzer._categorized_risk_scores_cache = result
        print(f"[RiskAnalyzer] Cached categorized risk scores: {len(result)} categories")

        return result

    @staticmethod
    def analyze_nc_category_trends(categoria: str, periodo_mesi: int = 12) -> pd.DataFrame:
        """
        Analizza trend temporali delle NC per categoria specifica.

        Args:
            categoria: Nome categoria NC (es. 'HACCP', 'IGIENE DEGLI ALIMENTI')
            periodo_mesi: Numero di mesi di analisi retrospettiva (default: 12)

        Returns:
            DataFrame con trend mensili delle NC per categoria e ASL
        """
        if ocse_df.empty:
            return pd.DataFrame()

        # Validazione categoria
        if categoria not in VALID_NC_CATEGORIES:
            return pd.DataFrame()

        ocse_copy = ocse_df.copy()

        # Filtra per categoria specifica (partial match case-insensitive)
        ocse_copy = ocse_copy[ocse_copy['oggetto_non_conformita'].str.contains(categoria, case=False, na=False)]

        if ocse_copy.empty:
            return pd.DataFrame()

        # Converti data_inizio_attivita a datetime se possibile
        # Usiamo anno_controllo come fallback per l'analisi temporale
        ocse_copy['anno_controllo'] = pd.to_numeric(
            ocse_copy['anno_controllo'], errors='coerce'
        )

        # Filtra per periodo (approssimazione con anno_controllo)
        # Se periodo_mesi <= 12, prendiamo solo l'anno corrente/recente
        anno_corrente = 2025  # Anno dei dati attuali
        if periodo_mesi <= 12:
            ocse_copy = ocse_copy[ocse_copy['anno_controllo'] >= anno_corrente]

        # Pulisci dati NC
        ocse_copy['numero_nc_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_gravi'], errors='coerce'
        ).fillna(0)
        ocse_copy['numero_nc_non_gravi'] = pd.to_numeric(
            ocse_copy['numero_nc_non_gravi'], errors='coerce'
        ).fillna(0)

        # Aggrega per ASL e anno
        trend_data = ocse_copy.groupby([
            'asl',
            'anno_controllo'
        ]).agg({
            'numero_nc_gravi': 'sum',
            'numero_nc_non_gravi': 'sum',
            'id_controllo_ufficiale': 'count'
        }).reset_index()

        trend_data.columns = [
            'asl', 'anno', 'nc_gravi', 'nc_non_gravi', 'controlli_totali'
        ]

        # Calcola totali e percentuali
        trend_data['nc_totali'] = trend_data['nc_gravi'] + trend_data['nc_non_gravi']
        trend_data['percentuale_nc'] = (
            trend_data['nc_totali'] / trend_data['controlli_totali'].replace(0, 1) * 100
        ).round(2)

        trend_data['categoria_nc'] = categoria

        # Ordina per ASL e anno
        trend_data = trend_data.sort_values(['asl', 'anno'])

        return trend_data

    @staticmethod
    def rank_osa_by_risk(
        osa_df: pd.DataFrame,
        risk_scores_df: pd.DataFrame,
        limit: int = 20
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Incrocia OSA mai controllati con punteggi rischio attività.

        Returns:
            Tuple (top OSA rischiosi display, tutti OSA rischiosi per export)
        """
        if osa_df.empty or risk_scores_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        osa_con_rischio = osa_df.merge(
            risk_scores_df,
            left_on=['macroarea', 'aggregazione', 'attivita'],
            right_on=['macroarea', 'aggregazione', 'linea_attivita'],
            how='left'
        )

        osa_con_rischio['punteggio_rischio_totale'] = osa_con_rischio['punteggio_rischio_totale'].fillna(0)
        osa_con_rischio['tot_nc_gravi'] = osa_con_rischio['tot_nc_gravi'].fillna(0)
        osa_con_rischio['tot_nc_non_gravi'] = osa_con_rischio['tot_nc_non_gravi'].fillna(0)
        osa_con_rischio['numero_controlli_totali'] = osa_con_rischio['numero_controlli_totali'].fillna(0)

        osa_con_rischio = osa_con_rischio.sort_values('punteggio_rischio_totale', ascending=False)

        osa_rischiosi_full = osa_con_rischio[osa_con_rischio['punteggio_rischio_totale'] > 0]
        osa_rischiosi_display = osa_rischiosi_full.head(limit)

        return osa_rischiosi_display, osa_rischiosi_full

    @staticmethod
    def find_priority_establishments_optimized(
        delayed_plans_df: pd.DataFrame,
        osa_df: pd.DataFrame,
        limit: int = 15
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Trova stabilimenti prioritari con algoritmo ottimizzato usando joins.
        1. Piani in ritardo
        2. Correlazione statistica piano → attività
        3. OSA mai controllati per quelle attività

        Returns:
            Tuple (DataFrame display, list full_data)
        """
        if delayed_plans_df.empty or osa_df.empty or controlli_df.empty:
            return pd.DataFrame(), []

        # Optimize: Pre-compute piano-attività correlations once
        piano_attivita_corr = controlli_df.groupby(
            ['descrizione_piano', 'attivita_cu']
        ).size().reset_index(name='count')

        # Normalize keys for better joins
        piano_attivita_corr['piano_norm'] = (
            piano_attivita_corr['descrizione_piano']
            .str.extract(r'([A-Z]+\d+)', expand=False)
            .str.upper()
        )
        osa_df_norm = osa_df.copy()
        osa_df_norm['attivita_norm'] = osa_df_norm['attivita'].str.upper().str.strip()

        # Vectorized approach: collect all activities for delayed plans
        top_delayed = delayed_plans_df.head(10).copy()
        all_related_activities = []

        # La colonna può essere 'piano' o 'indicatore' a seconda della sorgente dati
        piano_col = 'piano' if 'piano' in top_delayed.columns else 'indicatore'

        for piano_raw in top_delayed[piano_col].str.upper().unique():
            # Estrai codice base piano (es. "AO5_A" → "AO5", "att AO5_a" → "AO5")
            match = re.search(r'([A-Z]+\d+)', piano_raw)
            piano_id = match.group(1) if match else piano_raw

            activities = piano_attivita_corr[
                piano_attivita_corr['piano_norm'] == piano_id
            ]['attivita_cu'].head(5).tolist()
            all_related_activities.extend(activities)

        # Single vectorized filter for all activities
        all_activities_norm = [a.upper().strip() for a in all_related_activities]
        relevant_osa = osa_df_norm[
            osa_df_norm['attivita_norm'].isin(all_activities_norm)
        ]

        # Now create cross-join between delayed plans and relevant OSA
        priority_osa = []
        for delayed_tuple in top_delayed.itertuples(index=False):
            # Supporta sia 'piano' che 'indicatore' come nome colonna
            piano_raw = (getattr(delayed_tuple, 'piano', None) or
                        getattr(delayed_tuple, 'indicatore', '')).upper()

            # Estrai codice base piano (es. "AO5_A" → "AO5", "att AO5_a" → "AO5")
            match = re.search(r'([A-Z]+\d+)', piano_raw)
            piano_id = match.group(1) if match else piano_raw

            # Get activities for this specific piano
            plan_activities = piano_attivita_corr[
                piano_attivita_corr['piano_norm'] == piano_id
            ]['attivita_cu'].head(5).str.upper().str.strip().tolist()

            # Filter OSA for this piano's activities
            piano_osa = relevant_osa[relevant_osa['attivita_norm'].isin(plan_activities)].head(10)

            # Convert to required format
            for osa_tuple in piano_osa.itertuples(index=False):
                priority_osa.append({
                    'piano': getattr(delayed_tuple, 'piano', None) or getattr(delayed_tuple, 'indicatore', ''),
                    'descrizione_piano': getattr(delayed_tuple, 'descrizione_indicatore', 'N/D'),
                    'diff': getattr(delayed_tuple, 'ritardo', 0),
                    'attivita': getattr(osa_tuple, 'attivita', ''),
                    'comune': getattr(osa_tuple, 'comune', ''),
                    'indirizzo': getattr(osa_tuple, 'indirizzo', ''),
                    'num_riconoscimento': (getattr(osa_tuple, 'num_riconoscimento', None) or
                                         getattr(osa_tuple, 'n_reg', 'N/D')),
                    'macroarea': getattr(osa_tuple, 'macroarea', ''),
                    'aggregazione': getattr(osa_tuple, 'aggregazione', '')
                })

        if not priority_osa:
            return pd.DataFrame(), []

        priority_df = pd.DataFrame(priority_osa).drop_duplicates(subset=['num_riconoscimento'])

        all_data = []
        # Optimize: Use itertuples instead of iterrows
        for idx, row in enumerate(priority_df.itertuples(index=False)):
            num_id = getattr(row, 'num_riconoscimento', 'N/D')
            if pd.isna(num_id) or str(num_id) == 'nan':
                num_id = 'N/D'

            comune = getattr(row, 'comune', 'N/D')
            comune = str(comune).upper() if pd.notna(comune) else 'N/D'

            all_data.append({
                'macroarea': str(getattr(row, 'macroarea', '')),
                'comune': comune,
                'indirizzo': str(getattr(row, 'indirizzo', '')),
                'num_riconoscimento': str(num_id),
                'piano': str(getattr(row, 'piano', '')),
                'diff': int(getattr(row, 'diff', 0)),
                'attivita': str(getattr(row, 'attivita', '')),
                'aggregazione': str(getattr(row, 'aggregazione', 'N/D'))
            })

        priority_df_display = priority_df.head(limit)

        return priority_df_display, all_data

    # Compatibility alias for the old method name
    @staticmethod
    def find_priority_establishments(*args, **kwargs):
        """Compatibility alias - redirects to optimized version."""
        return RiskAnalyzer.find_priority_establishments_optimized(*args, **kwargs)
