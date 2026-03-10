"""
Query Builder Tools - Intent query_data con Query Builder vincolato.

Permette interrogazioni su dati tabulari non coperte dai 20 intent specifici.
L'LLM produce un Operation Descriptor JSON che viene validato e eseguito
su DataFrame in memoria (no SQL diretto).

Sicurezza:
- Whitelist tabelle (le 7 note)
- Whitelist colonne (validate contro DataFrame.columns a runtime)
- Whitelist operazioni (count, sum, mean, filter, group_count, top_n, distinct)
- Blacklist PII da schema_metadata.pii_columns
- Limite righe: max 100 risultati
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Pydantic Model per validazione Operation Descriptor
# ═══════════════════════════════════════════════════════════════════

VALID_OPERATIONS = {"count", "sum", "mean", "filter", "group_count", "top_n", "distinct"}
VALID_FILTER_OPS = {"eq", "neq", "contains", "gte", "lte", "in", "not_in"}
MAX_RESULT_ROWS = 100


class FilterDescriptor(BaseModel):
    column: str
    op: str
    value: Any

    @field_validator("op")
    @classmethod
    def validate_op(cls, v):
        if v not in VALID_FILTER_OPS:
            raise ValueError(f"Operatore filtro '{v}' non valido. Validi: {VALID_FILTER_OPS}")
        return v


class OrderByDescriptor(BaseModel):
    column: str
    direction: str = "desc"

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v):
        if v not in ("asc", "desc"):
            raise ValueError(f"Direzione '{v}' non valida. Validi: asc, desc")
        return v


class QueryDescriptor(BaseModel):
    table: str
    operation: str
    filters: List[FilterDescriptor] = []
    group_by: List[str] = []
    order_by: Optional[OrderByDescriptor] = None
    limit: int = 20

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v):
        if v not in VALID_OPERATIONS:
            raise ValueError(f"Operazione '{v}' non valida. Valide: {VALID_OPERATIONS}")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        return min(max(1, v), MAX_RESULT_ROWS)


# ═══════════════════════════════════════════════════════════════════
# Safe Query Executor
# ═══════════════════════════════════════════════════════════════════

# Mappa table_key → variabile DataFrame nel modulo agents.data
TABLE_KEY_TO_DF = {
    "piani": "piani_df",
    "masterlist": "attivita_df",
    "controlli": "controlli_df",
    "mai_controllati": "osa_mai_controllati_df",
    "nc_storiche": "ocse_df",
    "programmazione": "diff_prog_eseg_df",
}

# Alias comuni che l'LLM potrebbe usare
TABLE_ALIASES = {
    "piani_monitoraggio": "piani",
    "cu_eseguiti": "controlli",
    "osa_mai_controllati": "mai_controllati",
    "ocse_isp_semp": "nc_storiche",
    "cu_diff_programmati_eseguiti": "programmazione",
}


class SafeQueryExecutor:
    """Esegue operazioni pandas su DataFrame in memoria con validazione stretta."""

    def __init__(self):
        self._pii_columns: Dict[str, List[str]] = {}
        self._load_pii_columns()

    def _load_pii_columns(self):
        """Carica colonne PII da SchemaCatalog."""
        try:
            from orchestrator.schema_catalog import get_schema_catalog
            self._pii_columns = get_schema_catalog().get_all_pii_columns()
        except Exception:
            # Fallback hardcoded
            self._pii_columns = {
                "controlli": ["partita_iva", "ragione_sociale", "num_registrazione",
                              "codice_fiscale", "nominativo_rappresentante"],
                "mai_controllati": ["partita_iva", "ragione_sociale", "num_riconoscimento"],
                "personale": ["codice_fiscale", "namefirst", "namelast"],
            }

    def execute(self, descriptor: QueryDescriptor) -> Dict[str, Any]:
        """Esegue query validata su DataFrame in memoria."""
        import pandas as pd

        # 1. Risolvi table_key
        table_key = self._resolve_table_key(descriptor.table)
        if not table_key:
            return {"error": f"Tabella '{descriptor.table}' non trovata. Tabelle valide: {list(TABLE_KEY_TO_DF.keys())}"}

        # 2. Carica DataFrame
        df = self._get_dataframe(table_key)
        if df is None or df.empty:
            return {"error": f"Dati non disponibili per tabella '{table_key}'"}

        # 3. Valida colonne contro DataFrame reale
        pii_cols = set(self._pii_columns.get(table_key, []))
        all_cols = set(df.columns)

        # 3b. Valida colonne group_by
        for col in descriptor.group_by:
            if col not in all_cols:
                return {"error": f"Colonna '{col}' non esiste per group_by. Colonne: {sorted(all_cols - pii_cols)[:20]}"}
            if col in pii_cols:
                return {"error": f"Colonna '{col}' contiene dati personali e non è usabile per group_by"}

        # 4. Pre-processa filtri: traduci colonne concettuali a colonne reali
        processed_filters = self._preprocess_filters(descriptor.filters, table_key, all_cols)

        # 4b. Valida filtri processati (PII check)
        for f in processed_filters:
            if f.column in pii_cols:
                return {"error": f"Colonna '{f.column}' contiene dati personali e non è interrogabile"}

        logger.info(f"[QueryBuilder] Esecuzione: table={table_key}, op={descriptor.operation}, "
                     f"filters={[(f.column, f.op, f.value) for f in processed_filters]}, df_rows={len(df)}")
        filtered_df = self._apply_filters(df, processed_filters)
        if filtered_df.empty:
            # Diagnostica: mostra valori unici della colonna filtrata
            diag = ""
            if descriptor.filters:
                first_filter = descriptor.filters[0]
                if first_filter.column in all_cols:
                    sample_vals = df[first_filter.column].dropna().unique()[:5]
                    diag = f" Valori esempio in '{first_filter.column}': {list(sample_vals)}"
            logger.warning(f"[QueryBuilder] Nessun risultato dopo filtri.{diag}")
            return {"data": [], "total": 0, "message": f"Nessun risultato per i filtri specificati.{diag}"}

        # 5. Esegui operazione
        try:
            result = self._execute_operation(filtered_df, descriptor, pii_cols)
            return result
        except Exception as e:
            logger.error(f"[QueryBuilder] Errore esecuzione: {e}")
            return {"error": f"Errore esecuzione query: {str(e)}"}

    def _resolve_table_key(self, table: str) -> Optional[str]:
        """Risolve il nome tabella al table_key canonico."""
        table_lower = table.lower().strip()
        if table_lower in TABLE_KEY_TO_DF:
            return table_lower
        if table_lower in TABLE_ALIASES:
            return TABLE_ALIASES[table_lower]
        # Fuzzy: cerca per nome parziale
        for key in TABLE_KEY_TO_DF:
            if key in table_lower or table_lower in key:
                return key
        return None

    def _get_dataframe(self, table_key: str):
        """Carica DataFrame dal modulo agents.data."""
        try:
            # Import diretto (funziona nel contesto del server dove agents.data è già caricato)
            from agents.data import (
                piani_df, attivita_df, controlli_df,
                osa_mai_controllati_df, ocse_df, diff_prog_eseg_df
            )
            df_map = {
                "piani": piani_df,
                "masterlist": attivita_df,
                "controlli": controlli_df,
                "mai_controllati": osa_mai_controllati_df,
                "nc_storiche": ocse_df,
                "programmazione": diff_prog_eseg_df,
            }
            df = df_map.get(table_key)
            if df is not None:
                logger.info(f"[QueryBuilder] DataFrame '{table_key}' caricato: {len(df)} righe, colonne: {list(df.columns)[:10]}")
            else:
                logger.warning(f"[QueryBuilder] DataFrame '{table_key}' non trovato nella mappa")
            return df
        except Exception as e:
            logger.warning(f"[QueryBuilder] Errore caricamento DataFrame {table_key}: {e}")
        return None

    def _preprocess_filters(self, filters: List[FilterDescriptor], table_key: str, all_cols: set) -> List[FilterDescriptor]:
        """Traduce colonne concettuali a colonne reali nel DataFrame.

        Es: 'anno' → filtro su 'data_inizio_controllo' con range date
            'asl' → 'descrizione_asl'
        """
        # Mappa alias colonna → colonna reale per tabella
        COLUMN_ALIASES = {
            "controlli": {
                "anno": "data_inizio_controllo",
                "year": "data_inizio_controllo",
                "asl": "descrizione_asl",
                "uoc": "descrizione_uoc",
                "uos": "descrizione_uos",
                "piano": "descrizione_piano",
                "indicatore": "descrizione_indicatore",
                "macroarea": "macroarea_cu",
                "aggregazione": "aggregazione_cu",
                "attivita": "attivita_cu",
                "latitudine": "latitudine_stab",
                "longitudine": "longitudine_stab",
            },
            "mai_controllati": {
                "attivita": "attivita",
            },
            "nc_storiche": {
                "macroarea": "macroarea_sottoposta_a_controllo",
            },
            "programmazione": {
                "asl": "descrizione_asl",
                "uoc": "descrizione_uoc",
                "uos": "descrizione_uos",
            },
        }

        aliases = COLUMN_ALIASES.get(table_key, {})
        processed = []

        for f in filters:
            col = f.column
            op = f.op
            val = f.value

            # Risolvi alias
            if col in aliases:
                real_col = aliases[col]
                logger.info(f"[QueryBuilder] Alias colonna: {col} → {real_col}")
                col = real_col

            # Se la colonna ancora non esiste, prova fuzzy match
            if col not in all_cols:
                # Cerca match parziale
                matches = [c for c in all_cols if col.lower() in c.lower() or c.lower() in col.lower()]
                if matches:
                    col = matches[0]
                    logger.info(f"[QueryBuilder] Fuzzy match colonna: {f.column} → {col}")
                else:
                    logger.warning(f"[QueryBuilder] Colonna '{f.column}' non trovata, skip filtro")
                    continue

            # Gestione speciale: filtro anno su colonna datetime
            if col == "data_inizio_controllo" and f.column in ("anno", "year"):
                try:
                    year = int(val)
                    # Converti filtro anno in range date
                    processed.append(FilterDescriptor(column=col, op="gte", value=f"{year}-01-01"))
                    processed.append(FilterDescriptor(column=col, op="lte", value=f"{year}-12-31"))
                    logger.info(f"[QueryBuilder] Filtro anno {year} → range date {year}-01-01 / {year}-12-31")
                    continue
                except (ValueError, TypeError):
                    pass

            # Normalizza valore ASL: "ASL BENEVENTO" / "ASL di Benevento" → "BENEVENTO"
            # I valori reali in DB sono "DIPARTIMENTO DI PREVENZIONE BENEVENTO"
            if isinstance(val, str) and col in ("descrizione_asl",):
                import re
                asl_match = re.match(r'^(?:ASL|Asl|asl)\s+(?:di\s+)?(.+)$', val.strip(), re.IGNORECASE)
                if asl_match:
                    val = asl_match.group(1).strip()
                    logger.info(f"[QueryBuilder] Normalizzazione ASL: '{f.value}' → '{val}'")

            # Forza contains per filtri su testo che usano eq (più robusto)
            if op == "eq" and isinstance(val, str):
                op = "contains"
                logger.info(f"[QueryBuilder] Upgrade eq→contains per colonna testo '{col}'")

            processed.append(FilterDescriptor(column=col, op=op, value=val))

        return processed

    def _apply_filters(self, df, filters: List[FilterDescriptor]):
        """Applica filtri al DataFrame. Non copia per performance su grandi tabelle."""
        result = df
        for f in filters:
            col = f.column
            val = f.value
            try:
                if f.op == "eq":
                    # eq usa contains per robustezza (es. "BENEVENTO" match "ASL DI BENEVENTO")
                    mask = result[col].fillna("").astype(str).str.upper().str.contains(str(val).upper(), na=False, regex=False)
                    result = result[mask]
                elif f.op == "neq":
                    result = result[result[col].astype(str).str.upper() != str(val).upper()]
                elif f.op == "contains":
                    result = result[result[col].fillna("").astype(str).str.upper().str.contains(str(val).upper(), na=False, regex=False)]
                elif f.op == "gte":
                    import pandas as pd
                    if pd.api.types.is_datetime64_any_dtype(result[col]):
                        result = result[result[col] >= pd.Timestamp(val)]
                    else:
                        result = result[result[col] >= val]
                elif f.op == "lte":
                    import pandas as pd
                    if pd.api.types.is_datetime64_any_dtype(result[col]):
                        result = result[result[col] <= pd.Timestamp(val)]
                    else:
                        result = result[result[col] <= val]
                elif f.op == "in":
                    if isinstance(val, list):
                        upper_vals = [str(v).upper() for v in val]
                        result = result[result[col].astype(str).str.upper().isin(upper_vals)]
                elif f.op == "not_in":
                    if isinstance(val, list):
                        upper_vals = [str(v).upper() for v in val]
                        result = result[~result[col].astype(str).str.upper().isin(upper_vals)]
                logger.info(f"[QueryBuilder] Filtro {col} {f.op} '{val}': {len(result)} righe rimanenti")
            except Exception as e:
                logger.warning(f"[QueryBuilder] Filtro {col} {f.op} '{val}' fallito: {e}")
                continue  # Skip filtri non applicabili
        return result

    def _execute_operation(self, df, descriptor: QueryDescriptor, pii_cols: set) -> Dict[str, Any]:
        """Esegue l'operazione sul DataFrame filtrato."""
        import pandas as pd

        op = descriptor.operation
        limit = descriptor.limit

        if op == "count":
            return {"data": [{"count": len(df)}], "total": 1}

        elif op == "distinct":
            if descriptor.group_by:
                col = descriptor.group_by[0]
                values = df[col].dropna().unique().tolist()[:limit]
                return {"data": [{"column": col, "values": values, "total_distinct": len(df[col].dropna().unique())}], "total": 1}
            return {"data": [{"count": len(df)}], "total": 1}

        elif op == "group_count":
            if not descriptor.group_by:
                return {"error": "group_count richiede almeno un campo group_by"}
            grouped = df.groupby(descriptor.group_by).size().reset_index(name="count")
            grouped = grouped.sort_values("count", ascending=False).head(limit)
            # Rimuovi colonne PII
            safe_cols = [c for c in grouped.columns if c not in pii_cols]
            records = grouped[safe_cols].to_dict(orient="records")
            return {"data": records, "total": len(records)}

        elif op == "sum":
            if descriptor.group_by:
                # Trova colonne numeriche non PII
                num_cols = [c for c in df.select_dtypes(include=["number"]).columns
                           if c not in pii_cols and c not in descriptor.group_by]
                if not num_cols:
                    return {"error": "Nessuna colonna numerica disponibile per sum"}
                grouped = df.groupby(descriptor.group_by)[num_cols].sum().reset_index().head(limit)
                records = grouped.to_dict(orient="records")
                return {"data": records, "total": len(records)}
            else:
                num_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in pii_cols]
                sums = {col: float(df[col].sum()) for col in num_cols[:10]}
                return {"data": [sums], "total": 1}

        elif op == "mean":
            if descriptor.group_by:
                num_cols = [c for c in df.select_dtypes(include=["number"]).columns
                           if c not in pii_cols and c not in descriptor.group_by]
                if not num_cols:
                    return {"error": "Nessuna colonna numerica disponibile per mean"}
                grouped = df.groupby(descriptor.group_by)[num_cols].mean().round(2).reset_index().head(limit)
                records = grouped.to_dict(orient="records")
                return {"data": records, "total": len(records)}
            else:
                num_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in pii_cols]
                means = {col: round(float(df[col].mean()), 2) for col in num_cols[:10]}
                return {"data": [means], "total": 1}

        elif op == "filter":
            # Restituisce righe filtrate (rimuovi PII)
            safe_cols = [c for c in df.columns if c not in pii_cols]
            result_df = df[safe_cols].head(limit)
            records = result_df.to_dict(orient="records")
            return {"data": records, "total": len(df), "showing": len(records)}

        elif op == "top_n":
            if descriptor.order_by:
                col = descriptor.order_by.column
                asc = descriptor.order_by.direction == "asc"
                df_sorted = df.sort_values(col, ascending=asc).head(limit)
            else:
                df_sorted = df.head(limit)
            safe_cols = [c for c in df_sorted.columns if c not in pii_cols]
            records = df_sorted[safe_cols].to_dict(orient="records")
            return {"data": records, "total": len(df), "showing": len(records)}

        return {"error": f"Operazione '{op}' non supportata"}


# ═══════════════════════════════════════════════════════════════════
# Query Builder Prompt (per la seconda chiamata LLM)
# ═══════════════════════════════════════════════════════════════════

QUERY_BUILDER_SYSTEM_PROMPT = """Sei un query builder per dati veterinari GIAS. Genera un Operation Descriptor JSON per interrogare DataFrame in memoria.

FORMATO OUTPUT (JSON esatto):
{{
  "table": "nome_tabella",
  "operation": "group_count|count|sum|mean|filter|top_n|distinct",
  "filters": [{{"column": "col", "op": "eq|neq|contains|gte|lte|in", "value": "val"}}],
  "group_by": ["col1"],
  "order_by": {{"column": "count", "direction": "desc"}},
  "limit": 20
}}

SCHEMA DATI:
{schema}

OPERAZIONI DISPONIBILI:
- count: conta righe totali (dopo filtri)
- group_count: conta per gruppo (richiede group_by)
- sum: somma colonne numeriche (opzionale group_by)
- mean: media colonne numeriche (opzionale group_by)
- filter: restituisce righe filtrate (max 100)
- top_n: ordina e prendi le prime N (richiede order_by)
- distinct: valori unici di una colonna (usa group_by per specificare la colonna)

OPERATORI FILTRO:
- eq: uguale (case-insensitive)
- neq: diverso
- contains: contiene testo (case-insensitive)
- gte: maggiore o uguale
- lte: minore o uguale
- in: in lista di valori

COLONNE PII (NON usare mai):
{pii_columns}

REGOLE:
- Usa SOLO colonne che esistono nello schema
- MAI accedere a colonne PII (codice_fiscale, partita_iva, ragione_sociale, etc.)
- Limite massimo: 100 righe
- Preferisci aggregazioni (group_count, sum) a filter su tabelle grandi (>100K righe)

ALIAS COLONNE (il sistema traduce automaticamente):
- "anno" / "year" → filtro range su data_inizio_controllo (tabella controlli)
- "asl" → descrizione_asl
- Per ASL usa SOLO il nome città: "BENEVENTO" (NON "ASL Benevento", NON "Dipartimento...")

ESEMPI:
"quanti controlli per macroarea" → {{"table":"controlli","operation":"group_count","filters":[],"group_by":["macroarea_cu"],"limit":20}}
"distribuzione NC per anno" → {{"table":"nc_storiche","operation":"group_count","filters":[],"group_by":["anno"],"order_by":{{"column":"anno","direction":"asc"}},"limit":20}}
"controlli a Napoli nel 2025" → {{"table":"controlli","operation":"count","filters":[{{"column":"descrizione_asl","op":"contains","value":"NAPOLI"}},{{"column":"anno","op":"eq","value":"2025"}}],"limit":1}}
"quanti controlli ASL Benevento 2025" → {{"table":"controlli","operation":"count","filters":[{{"column":"descrizione_asl","op":"contains","value":"BENEVENTO"}},{{"column":"anno","op":"eq","value":"2025"}}],"limit":1}}
"top 10 macroaree con più NC gravi" → {{"table":"nc_storiche","operation":"top_n","filters":[],"group_by":["macroarea_sottoposta_a_controllo"],"order_by":{{"column":"numero_nc_gravi","direction":"desc"}},"limit":10}}

Output: SOLO JSON valido, niente altro."""


def build_query_with_llm(message: str, llm_client) -> Optional[QueryDescriptor]:
    """Chiama LLM per generare Operation Descriptor dalla domanda utente."""
    try:
        from orchestrator.schema_catalog import get_schema_catalog
        catalog = get_schema_catalog()
        schema = catalog.get_compact_catalog()
        pii = catalog.get_all_pii_columns()
        pii_str = "\n".join(f"- {k}: {', '.join(v)}" for k, v in pii.items() if v)

        prompt = QUERY_BUILDER_SYSTEM_PROMPT.format(
            schema=schema,
            pii_columns=pii_str or "(nessuna)"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ]

        response = llm_client.query(
            messages=messages,
            temperature=0.0,
            max_tokens=500,
            json_mode=True,
        )

        if not response:
            return None

        # Parse JSON dalla risposta
        import json
        import re

        # Estrai JSON dalla risposta (potrebbe avere testo prima/dopo)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if not json_match:
            logger.warning(f"[QueryBuilder] Nessun JSON trovato nella risposta LLM: {response[:200]}")
            return None

        data = json.loads(json_match.group())
        logger.info(f"[QueryBuilder] LLM descriptor JSON: {json.dumps(data, ensure_ascii=False)}")
        descriptor = QueryDescriptor(**data)
        return descriptor

    except Exception as e:
        logger.warning(f"[QueryBuilder] Errore build query: {e}")
        return None
