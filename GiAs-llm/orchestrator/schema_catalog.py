"""
SchemaCatalog - Genera catalogo schema compatto per il prompt LLM.

Singleton con lazy loading da DB. Pattern analogo a IntentMetadataService.
Rende l'LLM consapevole della struttura dati (tabelle, colonne, valori validi)
per migliorare classificazione intent e estrazione slot.
"""

import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SchemaCatalog:
    """Genera catalogo schema compatto per il prompt LLM, caricato da DB."""

    _instance: Optional['SchemaCatalog'] = None
    _initialized: bool = False

    def __new__(cls) -> 'SchemaCatalog':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SchemaCatalog._initialized:
            return
        self._catalog_text: Optional[str] = None
        self._schema_data: Dict[str, Dict[str, Any]] = {}
        self._loaded: bool = False
        SchemaCatalog._initialized = True

    def get_compact_catalog(self) -> str:
        """Ritorna catalogo compatto (~300 token) per prompt classificazione."""
        self._ensure_loaded()
        if self._catalog_text:
            return self._catalog_text
        return self._static_fallback()

    def get_full_schema(self, table_key: str = None) -> dict:
        """Schema completo per query_data_tool (Fase 2)."""
        self._ensure_loaded()
        if table_key:
            return self._schema_data.get(table_key, {})
        return self._schema_data

    def get_pii_columns(self, table_key: str) -> list:
        """Colonne PII da blacklistare."""
        self._ensure_loaded()
        entry = self._schema_data.get(table_key, {})
        return entry.get("pii_columns", [])

    def get_all_pii_columns(self) -> Dict[str, list]:
        """Ritorna mappa table_key -> lista colonne PII."""
        self._ensure_loaded()
        return {
            k: v.get("pii_columns", [])
            for k, v in self._schema_data.items()
            if v.get("pii_columns")
        }

    def _ensure_loaded(self):
        """Lazy loading: carica alla prima chiamata."""
        if self._loaded:
            return
        self._catalog_text = self._load_from_db()
        self._loaded = True

    def _load_from_db(self) -> Optional[str]:
        """Carica da schema_metadata e compatta per prompt."""
        try:
            from data_sources.postgresql_source import PostgreSQLDataSource
            engine = PostgreSQLDataSource._engine
            if engine is None:
                logger.info("[SchemaCatalog] DB engine non disponibile, uso fallback statico")
                return None

            from sqlalchemy import text

            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT table_key, table_name, df_variable, description_it,
                           columns, relationships, valid_values, pii_columns,
                           row_count_approx
                    FROM schema_metadata
                    WHERE is_active = TRUE
                    ORDER BY table_key
                """)).fetchall()

                if not rows:
                    logger.warning("[SchemaCatalog] Tabella schema_metadata vuota")
                    return None

                lines = []
                rel_lines = []
                for row in rows:
                    table_key = row[0]
                    table_name = row[1]
                    df_variable = row[2]
                    description = row[3]
                    columns_json = row[4] or []
                    relationships_json = row[5] or []
                    valid_values_json = row[6] or {}
                    pii_columns = list(row[7]) if row[7] else []
                    row_count = row[8]

                    # Salva schema completo per Fase 2
                    self._schema_data[table_key] = {
                        "table_name": table_name,
                        "df_variable": df_variable,
                        "description_it": description,
                        "columns": columns_json,
                        "relationships": relationships_json,
                        "valid_values": valid_values_json,
                        "pii_columns": pii_columns,
                        "row_count_approx": row_count,
                    }

                    # Genera riga compatta per prompt
                    col_parts = []
                    for col in columns_json:
                        name = col.get("name", "")
                        if not col.get("filterable", False):
                            continue
                        samples = col.get("sample_values", [])
                        if samples:
                            col_parts.append(f"{name}({','.join(str(s) for s in samples[:3])})")
                        else:
                            col_parts.append(name)

                    # Aggiungi valori validi per colonne enumerabili
                    valid_parts = []
                    for col_name, values in valid_values_json.items():
                        if isinstance(values, list) and values:
                            valid_parts.append(f"{col_name}: {', '.join(str(v) for v in values)}")

                    row_info = f" ~{row_count:,} righe" if row_count else ""
                    line = f"- {table_name}{row_info}: {description}"
                    if col_parts:
                        line += f"\n  Filtri: {', '.join(col_parts)}"
                    if valid_parts:
                        line += f"\n  Valori: {'; '.join(valid_parts)}"

                    lines.append(line)

                    # Relazioni (stesso loop, evita seconda iterazione)
                    for rel in relationships_json:
                        target = rel.get("target_table", "")
                        desc = rel.get("description", "")
                        if target and desc:
                            rel_lines.append(f"  {table_name}.{rel.get('source_col','')} → {target}.{rel.get('target_col','')}: {desc}")

                catalog = "\n".join(lines)
                if rel_lines:
                    catalog += "\n\nRELAZIONI:\n" + "\n".join(rel_lines)

                table_count = len(rows)
                logger.info(f"[SchemaCatalog] Catalogo caricato da DB ({table_count} tabelle)")
                return catalog

        except Exception as e:
            logger.warning(f"[SchemaCatalog] Errore caricamento DB: {e}")
            return None

    def _static_fallback(self) -> str:
        """Fallback hardcoded se DB non disponibile."""
        return (
            "- piani_monitoraggio ~730 righe: Piani di controllo veterinario per sezione PRISCAV\n"
            "  Filtri: sezione(SEZIONE A,SEZIONE B,SEZIONE C), alias(A1,A22,B2), alias_indicatore, anno, tipo_attivita\n"
            "  Valori: sezione: SEZIONE A=Sicurezza Alimentare, SEZIONE B=Sanità Animale, SEZIONE C=Igiene Allevamenti, "
            "SEZIONE D=Alimentazione Animale, SEZIONE E=Farmacosorveglianza, SEZIONE F=Benessere Animale, SEZIONE G=Sottoprodotti\n"
            "- masterlist ~105,000 righe: Tassonomia attività (NORMA, MACROAREA, AGGREGAZIONE, LINEA DI ATTIVITA)\n"
            "- cu_eseguiti_x ~3,200,000 righe: Controlli eseguiti 2025 (descrizione_asl, descrizione_uoc, descrizione_piano, macroarea_cu, sezione, data_inizio_controllo, num_riconoscimento, alias_piano_attivita, alias_indicatore)\n"
            "- osa_mai_controllati ~643,000 righe: Stabilimenti mai controllati (asl, comune, macroarea, aggregazione, attivita)\n"
            "- ocse_isp_semp: NC storiche 2016-2025 (macroarea_sottoposta_a_controllo, aggregazione_sottoposta_a_controllo, anno_controllo, asl, comune)\n"
            "- cu_diff_programmati_eseguiti: Programmati vs eseguiti per indicatore, descrizione_asl, descrizione_uoc, anno\n"
            "- personale ~100,000 righe: Struttura organizzativa (user_id, asl, descrizione_area_struttura_complessa)"
        )

    def reload(self):
        """Hot-reload: resetta stato e ricarica da DB."""
        self._loaded = False
        self._catalog_text = None
        self._schema_data.clear()
        self._ensure_loaded()
        logger.info(f"[SchemaCatalog] Reload completato ({len(self._schema_data)} tabelle)")


# --- Factory function ---

_catalog_instance: Optional[SchemaCatalog] = None


def get_schema_catalog() -> SchemaCatalog:
    """Restituisce singleton SchemaCatalog."""
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = SchemaCatalog()
    return _catalog_instance
