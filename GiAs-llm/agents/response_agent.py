# pyright: reportArgumentType=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportOperatorIssue=false
"""
Response/Generation Agent - Layer 3

Responsabilità:
- Trasforma risultati strutturati in risposta naturale
- Stile, formattazione, bullet point, warning
- Generazione suggestions dinamiche
- NO logica di dominio "hard"
"""

import pandas as pd
from typing import Dict, List, Any, Optional


class ResponseFormatter:
    """
    Formattazione risposte da dati strutturati a testo naturale.
    Template-based, nessuna logica di dominio.
    """

    # Mappa sezioni a descrizioni (basata su nomenclatura PRISCAV)
    SEZIONE_DESCRIZIONI = {
        'A': 'Sicurezza Alimentare',
        'B': 'Sanità Animale',
        'C': 'Igiene Allevamenti e Produzioni Zootecniche',
        'D': 'Alimentazione Animale',
        'E': 'Farmacosorveglianza',
        'F': 'Benessere Animale',
        'G': 'Sottoprodotti di Origine Animale',
    }

    @staticmethod
    def _is_attivita(indicator: str) -> bool:
        """Controlla se l'indicatore ha prefisso ATT (case-insensitive)."""
        if not indicator:
            return False
        return str(indicator).strip().upper().startswith('ATT')

    @staticmethod
    def _label_for_piano(indicators) -> str:
        """Restituisce 'Piano/Attività' se almeno un indicatore ha prefisso ATT, altrimenti 'Piano'.

        Args:
            indicators: singolo str o lista di str/dict con alias_indicatore
        """
        if isinstance(indicators, str):
            return "Piano/Attività" if ResponseFormatter._is_attivita(indicators) else "Piano"
        # Lista di indicatori (str o dict)
        for ind in (indicators or []):
            alias = ind.get('alias_indicatore', ind.get('alias_ind', '')) if isinstance(ind, dict) else ind
            if ResponseFormatter._is_attivita(alias):
                return "Piano/Attività"
        return "Piano"

    @staticmethod
    def _safe_int(value) -> int:
        """Converte valore NC a intero, gestendo NaN/vuoti/None."""
        try:
            if pd.notna(value) and value != '':
                return int(value)
        except Exception:
            pass
        return 0

    @staticmethod
    def format_piano_description(
        piano_id: str,
        unique_descriptions: Dict[str, Any],
        total_variants: int
    ) -> str:
        """
        Formatta descrizione piano da dati strutturati.

        Interpretazione campi:
        - alias: nome del piano
        - alias_indicatore: nome del sottopiano
        - descrizione: descrizione del piano
        - descrizione sottopiano: descrizione del sotto-piano
        - campionamento: True = prelievo campioni, False = attività di controllo
        - sezione: sezione del piano (importante per classificazione)
        """
        # Se piano_id ha prefisso ATT, è una query attività (non piano)
        is_attivita_query = piano_id.upper().startswith("ATT ")
        display_id = piano_id.upper().replace("ATT ", "") if is_attivita_query else piano_id.upper()
        entity_label = "Attività" if is_attivita_query else "Piano"
        response = f"**📋 Descrizione {entity_label} {display_id}**\n\n"

        for desc_main, info in unique_descriptions.items():
            sezione = info.get('sezione', '')
            alias = info.get('alias_piano_attivita', piano_id)
            campionamento = info.get('campionamento')

            # Descrizione sezione - estrae lettera da "SEZIONE A" o usa direttamente "A"
            sezione_letter = sezione.replace('SEZIONE', '').strip().upper() if sezione else ''
            sezione_desc = ResponseFormatter.SEZIONE_DESCRIZIONI.get(sezione_letter, '') if sezione_letter else ''
            if sezione and sezione_desc:
                response += f"**Sezione {sezione_letter}** - {sezione_desc}\n"
            elif sezione:
                response += f"**Sezione {sezione}**\n"

            # Indicatori (terzo livello) - carica prima per determinare etichetta piano
            sottopiani = info.get('sottopiani') or info.get('descrizione_indicatore', [])
            if is_attivita_query:
                response += f"**Attività:** {display_id}\n"
                response += f"**Piano di riferimento:** {alias}\n"
            else:
                piano_label = ResponseFormatter._label_for_piano(sottopiani)
                response += f"**{piano_label}:** {alias}\n"

            # Tipo attività (campionamento)
            if campionamento is True:
                response += f"**Tipo attività:** 🧪 Prelievo campioni\n"
            elif campionamento is False:
                response += f"**Tipo attività:** 🔍 Controllo ufficiale\n"
            # Se None, non mostriamo il campo

            response += f"\n**Descrizione del piano:**\n{desc_main}\n\n"

            if sottopiani:
                response += f"**Indicatori ({len(sottopiani)}):**\n\n"
                for idx, sottopiano in enumerate(sottopiani, 1):
                    # Supporta sia nuova struttura che vecchia per retrocompatibilità
                    alias_ind = sottopiano.get('alias_indicatore') or sottopiano.get('alias_ind', '')
                    desc_sotto = sottopiano.get('descrizione_sottopiano') or sottopiano.get('text', '')
                    camp_sotto = sottopiano.get('campionamento')

                    response += f"{idx}. **Indicatore {alias_ind}**\n"
                    response += f"   {desc_sotto}\n"

                    # Mostra tipo attività indicatore se diverso o specificato
                    if camp_sotto is True:
                        response += f"   _Tipo: Prelievo campioni_\n"
                    elif camp_sotto is False:
                        response += f"   _Tipo: Controllo ufficiale_\n"

                    response += "\n"

        response += f"**Totale varianti:** {total_variants}\n"

        return response

    @staticmethod
    def format_stabilimenti_analysis(
        piano_id: str,
        piano_desc: str,
        top_stabilimenti: pd.DataFrame,
        total_controls: int,
        unique_establishments: int
    ) -> str:
        """
        Formatta analisi stabilimenti controllati con dati di non conformità.
        """
        response = f"**Stabilimenti per il piano {piano_id.upper()}:**\n\n"
        response += f"**Piano:** {piano_desc}\n\n"
        response += "**Top 10 tipologie di stabilimenti controllati:**\n\n"

        for i, row in enumerate(top_stabilimenti.itertuples(index=False)):
            response += f"{i+1}. **{getattr(row, 'macroarea_cu', 'N/A')}**\n"
            response += f"   - **Aggregazione:** {getattr(row, 'aggregazione_cu', 'N/A')}\n"
            response += f"   - **Attività:** {getattr(row, 'attivita_cu', 'N/A')}\n"
            response += f"   - **Controlli eseguiti:** {getattr(row, 'count', 0)}\n"

            # Aggiungi non conformità se disponibili
            if hasattr(row, 'numero_nc_gravi') and hasattr(row, 'numero_nc_non_gravi'):
                nc_gravi = int(getattr(row, 'numero_nc_gravi', 0))
                nc_non_gravi = int(getattr(row, 'numero_nc_non_gravi', 0))
                punteggio = int(getattr(row, 'punteggio_rischio', 0))

                response += f"   - **Non conformità:** {nc_gravi} gravi, {nc_non_gravi} non gravi\n"
                if punteggio > 0:
                    response += f"   - **Punteggio rischio:** {punteggio}/100\n"

            response += "\n"

        response += f"**Totale controlli eseguiti:** {total_controls}\n"
        response += f"**Tipologie di stabilimenti coinvolte:** {unique_establishments}\n"

        # Aggiungi legenda se ci sono non conformità
        if not top_stabilimenti.empty and 'numero_nc_gravi' in top_stabilimenti.columns:
            response += "\n**Legenda Punteggio Rischio:**\n"
            response += "• Formula: P(NC) × Impatto × 100\n"
            response += "• P(NC) = (NC totali) / (controlli totali)\n"
            response += "• Impatto = (NC gravi) / (controlli totali)\n"
            response += "• Dati aggregati per linea di attività (livello regionale)\n"

        return response

    @staticmethod
    def format_stabilimenti_analysis_summary(
        piano_id: str,
        piano_desc: str,
        top_stabilimenti: pd.DataFrame,
        total_controls: int,
        unique_establishments: int,
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi stabilimenti controllati (fase 1 del sistema 2-fasi).
        Mostra solo le prime N tipologie con nome e conteggio controlli.
        """
        response = f"**📊 Sintesi Stabilimenti Piano {piano_id.upper()}**\n\n"
        response += f"**Piano:** {piano_desc}\n"
        response += f"**Totale controlli:** {total_controls:,}\n"
        response += f"**Tipologie coinvolte:** {unique_establishments}\n\n"

        response += f"**Top {min(limit, len(top_stabilimenti))} tipologie:**\n\n"

        for i, row in enumerate(top_stabilimenti.head(limit).itertuples(index=False)):
            macroarea = getattr(row, 'macroarea_cu', 'N/A')
            count = getattr(row, 'count', 0)
            response += f"{i+1}. **{macroarea}** — {count} controlli\n"

        if unique_establishments > limit:
            response += f"\n... e altre {unique_establishments - limit} tipologie.\n"

        return response

    @staticmethod
    def format_search_results(
        search_term: str,
        matches: List[Dict[str, Any]],
        max_display: Optional[int] = 10
    ) -> str:
        """
        Formatta risultati ricerca piani con tutti i dettagli:
        Sezione, alias_piano_attivita, descrizione_piano, alias_indicatore, descrizione_indicatore, campionamento.
        """
        response = f"**Piani trovati per: '{search_term}'**\n\n"
        response += f"**Trovati {len(matches)} risultati rilevanti:**\n\n"

        display_matches = matches[:max_display] if max_display else matches
        for idx, piano_info in enumerate(display_matches, 1):
            sezione = piano_info.get('sezione', '')
            alias = piano_info.get('alias_piano_attivita', '')
            alias_ind = piano_info.get('alias_indicatore', '')
            desc = piano_info.get('descrizione_piano', '') or ''
            desc2 = piano_info.get('descrizione_indicatore', '') or ''
            campionamento = piano_info.get('campionamento')

            # Campionamento: Si/No/N.D.
            if campionamento is True:
                camp_label = "Si"
            elif campionamento is False:
                camp_label = "No"
            else:
                camp_label = "N.D."

            # Sezione con descrizione PRISCAV
            sezione_letter = sezione.replace('SEZIONE', '').strip().upper() if sezione else ''
            sezione_desc = ResponseFormatter.SEZIONE_DESCRIZIONI.get(sezione_letter, '')
            if sezione_desc:
                sezione_display = f"{sezione} ({sezione_desc})"
            else:
                sezione_display = sezione

            piano_label = ResponseFormatter._label_for_piano(alias_ind)
            response += f"{idx}. **Sezione:** {sezione_display}\n"
            response += f"   **{piano_label}:** {alias} — {desc}\n"
            if alias_ind:
                response += f"   **Indicatore:** {alias_ind}"
                if desc2:
                    response += f" — {desc2}"
                response += "\n"
            response += f"   **Campionamento:** {camp_label}"
            if 'similarity' in piano_info and piano_info['similarity'] is not None:
                response += f" - Rilevanza: {piano_info['similarity']:.0%}"
            response += "\n\n"

        if max_display and len(matches) > max_display:
            response += f"... e altri {len(matches) - max_display} risultati.\n\n"

        return response

    @staticmethod
    def format_search_results_summary(
        search_term: str,
        matches: List[Dict[str, Any]],
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi risultati ricerca piani (fase 1 del sistema 2-fasi).
        Mostra i primi N risultati con sezione, piano, alias_indicatore e campionamento.
        """
        response = f"**Risultati per: '{search_term}'**\n\n"
        response += f"**Trovati {len(matches)} risultati rilevanti.**\n\n"

        response += f"**Top {min(limit, len(matches))} risultati:**\n\n"

        for idx, piano_info in enumerate(matches[:limit], 1):
            alias_ind = piano_info.get('alias_indicatore', '')
            campionamento = piano_info.get('campionamento')
            camp_label = "Si" if campionamento is True else ("No" if campionamento is False else "N.D.")

            piano_label = ResponseFormatter._label_for_piano(alias_ind)
            response += f"{idx}. **{piano_info['sezione']}** - {piano_label} **{piano_info.get('alias_piano_attivita', '')}**"
            if alias_ind:
                response += f" - Indicatore {alias_ind}"
            response += f" - Camp.: {camp_label}"
            if 'similarity' in piano_info and piano_info['similarity'] is not None:
                response += f" - Ril.: {piano_info['similarity']:.0%}"
            response += "\n"

        if len(matches) > limit:
            response += f"\n... e altri {len(matches) - limit} risultati.\n"

        return response

    @staticmethod
    def format_risk_based_priority_summary(
        result: Dict[str, Any],
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi priorità basata su rischio (fase 1 del sistema 2-fasi).
        Mostra solo i primi N stabilimenti con riepilogo.
        """
        user_asl = result.get('user_asl', 'N/D')
        piano_id = result.get('piano_code')
        osa_total_count = result.get('osa_total_count', 0)
        osa_risky_count = result.get('osa_risky_count', 0)
        activities_count = result.get('activities_count', 0)
        osa_rischiosi_data = result.get('osa_rischiosi', [])

        response = f"**🎯 Sintesi Priorità Controlli Basate sul Rischio**\n"
        response += f"**ASL:** {user_asl}\n"

        if piano_id:
            response += f"**Piano:** {piano_id}\n"

        response += f"\n**📊 Riepilogo:**\n"
        response += f"• OSA mai controllati: {osa_total_count}\n"
        response += f"• OSA in attività ad alto rischio: **{osa_risky_count}**\n"
        response += f"• Attività critiche identificate: {activities_count}\n\n"

        if not osa_rischiosi_data:
            response += "✅ Nessuna criticità significativa identificata.\n"
            return response

        # Converti in DataFrame se è una lista
        if isinstance(osa_rischiosi_data, list):
            osa_df = pd.DataFrame(osa_rischiosi_data)
        else:
            osa_df = osa_rischiosi_data

        response += f"**🚨 Top {limit} Stabilimenti a Maggior Rischio:**\n\n"

        for idx, row in enumerate(osa_df.head(limit).itertuples(index=False), 1):
            macroarea = getattr(row, 'macroarea', 'N/D')
            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'
            # Supporta entrambi i nomi campo per backwards compatibility
            punteggio = getattr(row, 'punteggio_rischio', None) or getattr(row, 'punteggio_rischio_totale', 0)
            try:
                punteggio = int(punteggio) if punteggio else 0
            except (ValueError, TypeError):
                punteggio = 0

            response += f"{idx}. **{macroarea}** - {comune}\n"
            response += f"   ⚠️ Risk Score: **{punteggio}/100**\n\n"

        response += "**Raccomandazione:** Dare priorità assoluta ai primi 5 stabilimenti.\n"

        return response

    @staticmethod
    def format_risk_based_priority(
        user_asl: str,
        piano_id: Optional[str],
        osa_total_count: int,
        osa_risky_count: int,
        activities_count: int,
        osa_rischiosi: pd.DataFrame,
        has_results: bool = True,
        max_display: Optional[int] = 20
    ) -> str:
        """
        Formatta analisi priorità basata su rischio.
        """
        response = f"**Priorità Controlli Basate sul Rischio Storico delle Linee di Attività**\n"
        response += f"**ASL:** {user_asl}\n"

        if piano_id:
            response += f"**Piano:** {piano_id}\n"

        if not has_results:
            response += f"**OSA mai controllati totali:** {osa_total_count}\n"
            response += "Buone notizie! Gli stabilimenti mai controllati nella tua ASL "
            if piano_id:
                response += f"per il piano {piano_id} "
            response += "appartengono a linee di attività che storicamente non hanno mostrato criticità "
            response += "significative (nessuna non conformità rilevata in passato per quelle linee di attività).\n"
            response += "Puoi procedere con controlli standard seguendo altre priorità operative."
            return response

        response += f"**OSA mai controllati analizzati:** {osa_total_count}\n"
        response += f"**OSA in linee di attività ad alto rischio:** {osa_risky_count}\n"
        response += f"**Linee di attività critiche identificate (regionale):** {activities_count}\n"

        title_suffix = f" per Piano {piano_id}" if piano_id else ""
        display_count = max_display if max_display else len(osa_rischiosi)
        response += f"**Top {display_count} OSA Mai Controllati in Linee di Attività ad Alto Rischio{title_suffix}:**\n"
        response += "*(Ordinati per rischiosità storica della linea di attività a livello regionale)*\n"

        display_df = osa_rischiosi.head(max_display) if max_display else osa_rischiosi
        for idx, row in enumerate(display_df.itertuples(index=False), 1):
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            numero_id = getattr(row, 'num_riconoscimento', '') if pd.notna(getattr(row, 'num_riconoscimento', '')) else getattr(row, 'n_reg', '')
            if not numero_id or str(numero_id) == 'nan':
                numero_id = getattr(row, 'codice_fiscale', '')

            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'
            indirizzo = getattr(row, 'indirizzo', '')
            punteggio = int(getattr(row, 'punteggio_rischio_totale', 0))
            nc_gravi = int(getattr(row, 'tot_nc_gravi', 0))
            nc_non_gravi = int(getattr(row, 'tot_nc_non_gravi', 0))
            controlli = int(getattr(row, 'numero_controlli_totali', 0))
            aggregazione = getattr(row, 'aggregazione', '')

            if ragione:
                response += f"{idx}. **{ragione}**\n"
                response += f"   {getattr(row, 'macroarea', '')} - {aggregazione} | {comune}\n"
            else:
                response += f"{idx}. **{getattr(row, 'macroarea', '')}** - {aggregazione} | {comune}\n"
            response += f"   {indirizzo} | ID: {numero_id}\n"
            response += f"   Rischio: **{punteggio}/100** | NC: {nc_gravi} gravi, {nc_non_gravi} non gravi | Controlli: {controlli}\n"

        response += "**Legenda Punteggio Rischio:**\n"
        response += "• Il punteggio è calcolato sulla linea di attività, non sul singolo stabilimento\n"
        response += "• Formula: P(NC) × Impatto × 100\n"
        response += "• P(NC) = (NC totali) / (controlli totali)\n"
        response += "• Impatto = (NC gravi) / (controlli totali)\n"
        response += "• Dati aggregati da controlli regionali 2016-2025 (Regione Campania)\n\n"

        response += "**Raccomandazione:**\n"
        response += "Questi stabilimenti NON sono mai stati controllati ma appartengono "
        response += "a linee di attività che hanno mostrato criticità significative nei controlli "
        response += "effettuati a livello regionale (Regione Campania). Dare priorità assoluta ai primi 5 della lista."

        if max_display and osa_risky_count > max_display:
            response += f"\n\n**Nota:** Visualizzati {max_display} su {osa_risky_count} risultati. Usa il pulsante 'Scarica' per ottenere l'elenco completo."

        return response

    @staticmethod
    def format_priority_establishments_summary(
        result: Dict[str, Any],
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi stabilimenti prioritari (fase 1 del sistema 2-fasi).
        """
        user_asl = result.get('user_asl', 'N/D')
        uoc_name = result.get('uoc_name', 'N/D')
        piano_id = result.get('piano_code')
        delayed_count = result.get('delayed_plans_count', 0)
        total_found = result.get('total_found', 0)
        priority_data = result.get('priority_establishments', [])

        response = f"**🎯 Sintesi Stabilimenti Prioritari**\n"
        response += f"**ASL:** {user_asl} | **Struttura:** {uoc_name}\n"

        if piano_id:
            response += f"**Piano:** {piano_id}\n"

        response += f"\n**📊 Riepilogo:**\n"
        response += f"• Piani in ritardo: {delayed_count}\n"
        response += f"• Stabilimenti prioritari trovati: **{total_found}**\n\n"

        if not priority_data:
            response += "✅ Nessuno stabilimento prioritario identificato.\n"
            return response

        # Converti in DataFrame se è una lista
        if isinstance(priority_data, list):
            priority_df = pd.DataFrame(priority_data)
        else:
            priority_df = priority_data

        response += f"**🚨 Top {limit} Stabilimenti da Controllare:**\n\n"

        for idx, row in enumerate(priority_df.head(limit).itertuples(index=False), 1):
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            macroarea = getattr(row, 'macroarea', 'N/D')
            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'
            piano = getattr(row, 'piano', 'N/D')
            diff = int(getattr(row, 'diff', 0))

            if ragione:
                response += f"{idx}. **{ragione}** - {comune}\n"
            else:
                response += f"{idx}. **{macroarea}** - {comune}\n"
            response += f"   Piano: {piano} (ritardo: {diff})\n\n"

        response += "**Raccomandazione:** Dare priorità ai primi 5 stabilimenti.\n"

        return response

    @staticmethod
    def format_priority_establishments(
        user_asl: str,
        uoc_name: str,
        piano_id: Optional[str],
        delayed_count: int,
        total_found: int,
        priority_df_display: pd.DataFrame,
        max_display: Optional[int] = 15
    ) -> str:
        """
        Formatta stabilimenti prioritari da programmazione.
        """
        response = f"**Stabilimenti Prioritari da Controllare**\n"
        response += f"**ASL:** {user_asl}\n"
        response += f"**Struttura:** {uoc_name}\n"

        if piano_id:
            response += f"**Piano:** {piano_id}\n"
            response += f"**Ritardo piano:** {delayed_count} record\n"
        else:
            response += f"**Piani in ritardo:** {delayed_count}\n"

        response += f"**Totale stabilimenti trovati:** {total_found}\n"

        title_suffix = f" per Piano {piano_id}" if piano_id else ""
        display_count = max_display if max_display else len(priority_df_display)
        response += f"**Top {display_count} Stabilimenti Prioritari{title_suffix} (mai controllati):**\n"
        response += "*(Ordinati per urgenza programmazione e correlazione statistica)*\n"

        display_df = priority_df_display.head(max_display) if max_display else priority_df_display
        for idx, row in enumerate(display_df.itertuples(index=False)):
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            num_id = getattr(row, 'num_riconoscimento', '')
            if pd.isna(num_id) or str(num_id) == 'nan':
                num_id = 'N/D'

            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'
            indirizzo = getattr(row, 'indirizzo', '')
            piano = getattr(row, 'piano', '')
            diff = int(getattr(row, 'diff', 0))
            attivita = getattr(row, 'attivita', '')[:80]

            if ragione:
                response += f"{idx + 1}. **{ragione}**\n"
                response += f"   {getattr(row, 'macroarea', '')} | {comune} | {indirizzo}\n"
            else:
                response += f"{idx + 1}. **{getattr(row, 'macroarea', '')}** | {comune} | {indirizzo}\n"
            response += f"   ID: {num_id} | Piano in ritardo: {piano} ({diff} controlli)\n"
            response += f"   Attività: {attivita}...\n"

        response += "\n**Metodologia:**\n"
        response += "1. Identificati piani in ritardo per la tua struttura\n"
        response += "2. Correlazione statistica piano → attività (da controlli 2025)\n"
        response += "3. Individuati stabilimenti mai controllati per quelle attività\n"
        response += "**Raccomandazione:** Dare priorità ai primi 5 stabilimenti della lista."

        if max_display and total_found > max_display:
            response += f"\n**Nota:** Visualizzati {max_display} su {total_found} risultati. Usa il pulsante 'Scarica' per ottenere l'elenco completo."

        return response

    @staticmethod
    def format_delayed_plans_summary(
        delayed_plans: List[Dict[str, Any]],
        uoc_details: List[Dict[str, Any]],  # noqa: kept for API compat
        total_delayed: int,
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi piani in ritardo (fase 1 del sistema 2-fasi).
        """
        response = f"**📊 Sintesi Piani in Ritardo**\n\n"
        response += f"**Totale piani in ritardo:** {total_delayed}\n\n"

        if not delayed_plans:
            response += "✅ Nessun piano in ritardo.\n"
            return response

        # Converti in DataFrame se è una lista
        if isinstance(delayed_plans, list):
            delayed_df = pd.DataFrame(delayed_plans)
        else:
            delayed_df = delayed_plans

        # Calcola totale controlli mancanti
        total_mancanti = delayed_df['ritardo'].sum() if 'ritardo' in delayed_df.columns else 0
        response += f"**Controlli mancanti totali:** {int(total_mancanti)}\n\n"

        response += f"**🚨 Top {limit} Piani Più Critici:**\n\n"

        for idx, row in enumerate(delayed_df.head(limit).itertuples(index=False), 1):
            piano_id = getattr(row, 'alias_indicatore', 'N/D')
            ritardo = int(getattr(row, 'ritardo', 0))
            programmati = int(getattr(row, 'programmati', 0))
            eseguiti = int(getattr(row, 'eseguiti', 0))

            percentuale = (eseguiti / programmati * 100) if programmati > 0 else 0

            label = "Attività" if ResponseFormatter._is_attivita(piano_id) else "Piano"
            response += f"{idx}. **{label} {piano_id}** - Ritardo: {ritardo}\n"
            response += f"   Completamento: {percentuale:.0f}% ({eseguiti}/{programmati})\n\n"

        response += "**Raccomandazione:** Prioritizzare i piani con maggior ritardo.\n"

        return response

    @staticmethod
    def format_delayed_plans(
        user_asl: str,
        uoc_name: str,
        total_plans_delayed: int,
        total_delay: int,
        top_delayed: pd.DataFrame,
        worst_plan_details: Optional[pd.DataFrame] = None,
        worst_plan_id: Optional[str] = None,
        uos_name: Optional[str] = None,
        tipo: Optional[str] = None
    ) -> tuple:
        """
        Formatta analisi piani/attività in ritardo.

        Returns:
            Tuple (main_response, detail_response)
        """
        # Titolo dinamico in base al tipo richiesto
        if tipo == "attivita":
            title_label = "Attività"
        elif tipo == "tutti":
            title_label = "Piani e Attività"
        else:
            title_label = "Piani"
        response = f"**Analisi {title_label} in Ritardo**\n"
        response += f"**ASL:** {user_asl}\n"
        response += f"**Struttura:** {uoc_name}\n"
        if uos_name:
            response += f"**UOS:** {uos_name}\n"
        response += f"**{title_label} in ritardo:** {total_plans_delayed}\n"
        response += f"**Controlli mancanti totali:** {total_delay}\n"
        response += "\n─────────────────────────────────────\n"

        for idx, row in enumerate(top_delayed.itertuples(index=False)):
            piano_id = getattr(row, 'alias_indicatore', '')
            ritardo = int(getattr(row, 'ritardo', ''))
            programmati = int(getattr(row, 'programmati', ''))
            eseguiti = int(getattr(row, 'eseguiti', ''))
            descrizione = getattr(row, 'descrizione_indicatore', '')[:80] + "..." if len(getattr(row, 'descrizione_indicatore', '')) > 80 else getattr(row, 'descrizione_indicatore', '')

            percentuale_eseguita = (eseguiti / programmati * 100) if programmati > 0 else 0

            label = "Attività" if ResponseFormatter._is_attivita(piano_id) else "Piano"
            response += f"**{idx + 1}. {label} {piano_id}**\n"
            response += f"   {descrizione}\n"
            response += f"   Programmati: {programmati} | Eseguiti: {eseguiti} | Ritardo: {ritardo}\n"
            response += f"   Completamento: {percentuale_eseguita:.1f}%\n\n"

        if total_plans_delayed > 10:
            response += f"\n**Nota:** Altri {total_plans_delayed - 10} {title_label.lower()} in ritardo disponibili.\n"

        response += "\n─────────────────────────────────────\n"
        response += "**Raccomandazioni:**\n"
        response += f"• Prioritizza {'le attività' if tipo == 'attivita' else 'i piani'} con maggior ritardo\n"
        response += "• Verifica risorse disponibili per recupero\n"
        response += "• Pianifica interventi straordinari se necessario\n"

        detail_response = None
        if worst_plan_details is not None and worst_plan_id and not worst_plan_details.empty:
            detail_label = "Attività" if ResponseFormatter._is_attivita(worst_plan_id) else "Piano"
            detail_response = f"\n**Dettaglio strutture per {detail_label} {worst_plan_id}:**\n"

            for detail in worst_plan_details.itertuples(index=False):
                uoc = getattr(detail, 'descrizione_uoc', '')
                uos = getattr(detail, 'descrizione_uos', '')

                uoc = uoc[:50] + "..." if pd.notna(uoc) and len(str(uoc)) > 50 else uoc
                uos = uos[:50] + "..." if pd.notna(uos) and len(str(uos)) > 50 else uos

                detail_response += f"• **UOC:** {uoc}\n"
                if pd.notna(uos) and str(uos).strip():
                    detail_response += f"  **UOS:** {uos}\n"
                detail_response += f"  Programmati: {int(getattr(detail, 'programmati', 0))} | Eseguiti: {int(getattr(detail, 'eseguiti', 0))} | Ritardo: {int(getattr(detail, 'ritardo', 0))}\n\n"

        return response, detail_response

    @staticmethod
    def format_check_plan_delayed(
        piano_code: str,
        is_delayed: bool,
        asl: str,  # noqa: kept for API compat
        uoc: str,
        ritardo: int = 0,
        programmati: int = 0,
        eseguiti: int = 0,
        sottopiani: list = None
    ) -> str:
        """
        Formatta risposta per verifica se un piano specifico è in ritardo.
        Mostra sempre i dettagli numerici per motivare la risposta.
        """
        percentuale_eseguita = (eseguiti / programmati * 100) if programmati > 0 else 100

        if not is_delayed:
            response = f"**No**, il piano {piano_code} non è in ritardo per la struttura {uoc}.\n\n"
            if programmati > 0:
                response += f"**Dettagli:**\n"
                response += f"• Controlli programmati: {programmati}\n"
                response += f"• Controlli eseguiti: {eseguiti}\n"
                response += f"• Completamento: {percentuale_eseguita:.1f}%\n"
            else:
                response += f"Non ci sono controlli programmati per questo piano nella tua struttura."
            return response

        response = f"**Sì**, il piano {piano_code} è in ritardo per la struttura {uoc}.\n\n"

        if sottopiani:
            if len(sottopiani) > 1:
                response += f"**Indicatori in ritardo:** {', '.join(sottopiani)}\n\n"
                response += f"**Dettagli aggregati:**\n"
            else:
                response += f"**Indicatore specifico:** {sottopiani[0]}\n\n"
                response += f"**Dettagli:**\n"
        else:
            response += f"**Dettagli:**\n"
        response += f"• Controlli programmati: {programmati}\n"
        response += f"• Controlli eseguiti: {eseguiti}\n"
        response += f"• Ritardo: {ritardo} controlli\n"
        response += f"• Completamento: {percentuale_eseguita:.1f}%\n"

        return response

    @staticmethod
    def format_comparison(
        piano1_id: str,
        piano2_id: str,
        metrics: Dict[str, Any]
    ) -> str:
        """
        Formatta confronto tra due piani.
        """
        response = f"**Confronto tra Piano {piano1_id.upper()} e Piano {piano2_id.upper()}:**\n\n"

        p1 = metrics['piano1']
        p2 = metrics['piano2']

        response += f"**{piano1_id.upper()}:**\n"
        response += f"  • Attività correlate: {p1['attivita_count']}\n"
        response += f"  • Stabilimenti controllati: {p1['stabilimenti_count']}\n\n"

        response += f"**{piano2_id.upper()}:**\n"
        response += f"  • Attività correlate: {p2['attivita_count']}\n"
        response += f"  • Stabilimenti controllati: {p2['stabilimenti_count']}\n\n"

        response += "**Analisi Comparativa:**\n"

        diff_att = metrics['diff_attivita']
        diff_stab = metrics['diff_stabilimenti']

        if diff_att > 0:
            response += f"Il piano {piano1_id.upper()} copre {diff_att} attività in più\n"
        elif diff_att < 0:
            response += f"Il piano {piano2_id.upper()} copre {abs(diff_att)} attività in più\n"
        else:
            response += f"≈ I piani hanno un numero simile di attività\n"

        if diff_stab > 0:
            response += f"Il piano {piano1_id.upper()} controlla {diff_stab} stabilimenti in più\n"
        elif diff_stab < 0:
            response += f"Il piano {piano2_id.upper()} controlla {abs(diff_stab)} stabilimenti in più\n"
        else:
            response += f"≈ I piani controllano un numero simile di stabilimenti\n"

        return response

    @staticmethod
    def format_suggest_controls(
        asl: Optional[str],
        filtered_count: int,
        sample_df: pd.DataFrame,
        limit: int
    ) -> str:
        """
        Formatta suggerimenti controlli base.
        """
        response = f"**Suggerimenti Controlli Prioritari**\n"

        if asl:
            response += f"**ASL:** {asl}\n"

        response += f"**Stabilimenti mai controllati:** {filtered_count:,}\n"
        response += f"**Mostrando i primi {limit}:**\n"

        for num, row in enumerate(sample_df.itertuples(index=False), 1):
            def _val(attr):
                v = str(getattr(row, attr, ''))
                return '' if v in ('N.D.', 'N/D', 'nan', 'None', '') else v

            ragione = _val('ragione_sociale')
            comune = _val('comune').upper()
            indirizzo = _val('indirizzo')
            attivita = _val('attivita')
            num_ric = _val('num_riconoscimento') or _val('n_reg')

            # Intestazione: ragione_sociale o comune
            header = ragione or comune or 'Stabilimento'
            # Dettagli sotto l'intestazione (solo campi valorizzati)
            details = []
            if comune and comune != header.upper():
                details.append(comune)
            if indirizzo:
                details.append(indirizzo)
            if num_ric:
                details.append(f"ID: {num_ric}")

            response += f"**{num}. {header}**"
            if details:
                response += f" | {' | '.join(details)}"
            response += "\n"
            if attivita:
                response += f"   Attività: {attivita[:100]}{'...' if len(attivita) > 100 else ''}\n"

        if filtered_count > limit:
            response += f"\n**Nota:** Altri {filtered_count - limit:,} stabilimenti disponibili"
            if asl:
                response += f" nella tua ASL"
            response += ".\n"

        response += "\n**Prossimi passi:**\n"
        response += "• Pianifica ispezioni presso questi stabilimenti\n"
        response += "• Verifica conformità normativa\n"
        response += "• Aggiorna registro controlli\n"

        return response

    @staticmethod
    def format_establishment_history_summary(
        result: Dict[str, Any],
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi storico stabilimento (fase 1 del sistema 2-fasi).
        Mostra info stabilimento + riepilogo + ultimi N controlli.
        """
        history_data = result.get('history', [])
        total_controls = result.get('total_controls', 0)

        if not history_data:
            return "❌ Nessun controllo trovato per lo stabilimento specificato."

        # Converti in DataFrame se è una lista
        if isinstance(history_data, list):
            history_df = pd.DataFrame(history_data)
        else:
            history_df = history_data

        # Estrai info stabilimento dal primo record
        first_row = history_df.iloc[0]
        stab_ragione = first_row.get('ragione_sociale', 'N.D.')
        stab_reg = first_row.get('num_registrazione', 'N.D.')
        stab_asl = first_row.get('descrizione_asl', 'N.D.')

        response = f"**📋 Storico Controlli Stabilimento**\n\n"
        response += f"**Ragione Sociale:** {stab_ragione}\n"
        response += f"**N. Registrazione:** {stab_reg}\n"
        response += f"**ASL:** {stab_asl}\n\n"

        response += f"**📊 Totale controlli:** {total_controls}\n\n"

        # Riepilogo sintetico NC
        if 'numero_nc_gravi' in history_df.columns:
            total_nc_gravi = 0
            total_nc_non_gravi = 0
            controlli_con_nc = 0

            for row in history_df.itertuples(index=False):
                nc_g = getattr(row, 'numero_nc_gravi', 0)
                nc_ng = getattr(row, 'numero_nc_non_gravi', 0)

                nc_g_val = ResponseFormatter._safe_int(nc_g)
                nc_ng_val = ResponseFormatter._safe_int(nc_ng)

                total_nc_gravi += nc_g_val
                total_nc_non_gravi += nc_ng_val

                if nc_g_val > 0 or nc_ng_val > 0:
                    controlli_con_nc += 1

            if total_controls > 0:
                tasso_conformita = ((total_controls - controlli_con_nc) / total_controls) * 100
            else:
                tasso_conformita = 100

            response += f"**⚠️ Non Conformità:**\n"
            response += f"• NC Gravi: {total_nc_gravi} | NC Non Gravi: {total_nc_non_gravi}\n"
            response += f"• Tasso conformità: **{tasso_conformita:.1f}%**\n\n"

        # Piani più frequenti
        piani_freq = history_df['descrizione_piano'].value_counts().head(3)
        response += "**📋 Piani più controllati:**\n"
        for piano, count in piani_freq.items():
            response += f"• {piano}: {count}\n"

        response += f"\n**🕐 Ultimi {limit} controlli:**\n\n"

        for idx, row in enumerate(history_df.head(limit).itertuples(index=False), 1):
            data_controllo = getattr(row, 'data_inizio_controllo', 'N.D.')
            if pd.notna(data_controllo):
                try:
                    data_controllo = pd.to_datetime(data_controllo).strftime('%d/%m/%Y')
                except Exception:
                    pass

            piano = getattr(row, 'descrizione_piano', 'N.D.')
            nc_gravi = getattr(row, 'numero_nc_gravi', 0)
            nc_non_gravi = getattr(row, 'numero_nc_non_gravi', 0)

            nc_gravi = ResponseFormatter._safe_int(nc_gravi)
            nc_non_gravi = ResponseFormatter._safe_int(nc_non_gravi)

            esito = "⚠️ NC" if (nc_gravi > 0 or nc_non_gravi > 0) else "✅ OK"
            response += f"{idx}. {data_controllo} - {piano[:40]}... {esito}\n"

        return response

    @staticmethod
    def format_establishment_history(
        history_df: pd.DataFrame,
        num_registrazione: Optional[str] = None,
        numero_riconoscimento: Optional[str] = None,
        partita_iva: Optional[str] = None,
        ragione_sociale: Optional[str] = None,
        max_display: Optional[int] = 20
    ) -> str:
        """
        Formatta storico controlli stabilimento.
        Supporta controlli_df (cu_eseguiti_nc) con NC inline.
        """
        if history_df.empty:
            search_criteria = []
            if num_registrazione:
                search_criteria.append(f"Numero registrazione: {num_registrazione}")
            if numero_riconoscimento:
                search_criteria.append(f"Numero riconoscimento: {numero_riconoscimento}")
            if partita_iva:
                search_criteria.append(f"P.IVA: {partita_iva}")
            if ragione_sociale:
                search_criteria.append(f"Ragione sociale: {ragione_sociale}")

            criteria_str = " / ".join(search_criteria) if search_criteria else "parametri specificati"
            return f"❌ **Nessun controllo trovato** per {criteria_str}.\n\n" \
                   f"Verifica che i dati siano corretti e che lo stabilimento sia presente nel database."

        # Estrai info stabilimento dal primo record
        first_row = history_df.iloc[0]
        stab_ragione = first_row.get('ragione_sociale', 'N.D.')
        stab_reg = first_row.get('num_registrazione', 'N.D.')
        stab_ric = first_row.get('numero_riconoscimento', numero_riconoscimento or 'N.D.')
        stab_piva = first_row.get('partita_iva', 'N.D.')
        stab_asl = first_row.get('descrizione_asl', 'N.D.')
        response = f"**📋 Storico Controlli Stabilimento**\n\n"
        response += f"**Ragione Sociale:** {stab_ragione}\n"
        if stab_reg and stab_reg != 'N.D.':
            response += f"**Numero Registrazione:** {stab_reg}\n"
        if stab_ric and stab_ric != 'N.D.':
            response += f"**Numero Riconoscimento:** {stab_ric}\n"
        if stab_piva and stab_piva != 'N.D.':
            response += f"**Partita IVA:** {stab_piva}\n"
        response += f"**ASL:** {stab_asl}\n\n"

        response += f"**📊 Totale controlli trovati:** {len(history_df)}\n\n"
        response += "────────────────────────────────────\n\n"

        # Limita visualizzazione
        display_limit = min(max_display, len(history_df)) if max_display else len(history_df)

        for idx, row in enumerate(history_df.head(display_limit).itertuples(index=False), 1):
            data_controllo = getattr(row, 'data_inizio_controllo', 'N.D.')
            if pd.notna(data_controllo):
                try:
                    data_controllo = pd.to_datetime(data_controllo).strftime('%d/%m/%Y')
                except Exception:
                    pass

            piano = getattr(row, 'descrizione_piano', 'N.D.')
            tecnica = getattr(row, 'tecnica_controllo', 'N.D.')
            macroarea = getattr(row, 'macroarea_cu', 'N.D.')
            aggregazione = getattr(row, 'aggregazione_cu', 'N.D.')
            attivita = getattr(row, 'attivita_cu', 'N.D.')
            uoc = getattr(row, 'descrizione_uoc', 'N.D.')

            # NC data
            nc_gravi = getattr(row, 'numero_nc_gravi', 0)
            nc_non_gravi = getattr(row, 'numero_nc_non_gravi', 0)
            tipo_nc = getattr(row, 'tipo_non_conformita', '')

            # Converti NC a numeri gestendo NaN
            nc_gravi = ResponseFormatter._safe_int(nc_gravi)
            nc_non_gravi = ResponseFormatter._safe_int(nc_non_gravi)

            response += f"{idx}. **{data_controllo}** | Piano: {piano} | Tecnica: {tecnica}\n"
            response += f"   {macroarea} > {aggregazione} > {attivita}\n"
            response += f"   UOC: {uoc}"

            # Mostra NC se presenti
            if nc_gravi > 0 or nc_non_gravi > 0:
                response += f" | ⚠️ NC: {nc_gravi} gravi, {nc_non_gravi} non gravi"
                if tipo_nc and pd.notna(tipo_nc) and str(tipo_nc).strip():
                    response += f" ({tipo_nc})"
            else:
                response += f" | ✅ Conforme"

            response += "\n"

        if len(history_df) > display_limit:
            response += f"... e altri {len(history_df) - display_limit} controlli.\n\n"

        # Analisi sintetica
        response += "────────────────────────────────────\n\n"
        response += "**📈 Riepilogo:**\n"

        # Piani più frequenti
        piani_freq = history_df['descrizione_piano'].value_counts().head(3)
        response += "**Piani più controllati:**\n"
        for piano, count in piani_freq.items():
            response += f"- {piano}: {count} controlli\n"

        # Tecnica controllo
        tecnica_freq = history_df['tecnica_controllo'].value_counts().head(3)
        response += "**Tecniche di controllo:**\n"
        for tecnica, count in tecnica_freq.items():
            response += f"- {tecnica}: {count} controlli\n"

        # Riepilogo NC se disponibili
        if 'numero_nc_gravi' in history_df.columns and 'numero_nc_non_gravi' in history_df.columns:
            # Calcola totali gestendo NaN
            total_nc_gravi = 0
            total_nc_non_gravi = 0
            controlli_con_nc = 0

            for row in history_df.itertuples(index=False):
                nc_g = getattr(row, 'numero_nc_gravi', 0)
                nc_ng = getattr(row, 'numero_nc_non_gravi', 0)

                nc_g_val = ResponseFormatter._safe_int(nc_g)
                nc_ng_val = ResponseFormatter._safe_int(nc_ng)

                total_nc_gravi += nc_g_val
                total_nc_non_gravi += nc_ng_val

                if nc_g_val > 0 or nc_ng_val > 0:
                    controlli_con_nc += 1

            response += "**⚠️ Non Conformità (NC):**\n"
            response += f"- Totale NC Gravi: {total_nc_gravi}\n"
            response += f"- Totale NC Non Gravi: {total_nc_non_gravi}\n"
            response += f"- Controlli con NC: {controlli_con_nc}/{len(history_df)}\n"

            # Tasso di conformità
            if len(history_df) > 0:
                tasso_conformita = ((len(history_df) - controlli_con_nc) / len(history_df)) * 100
                response += f"- Tasso di conformità: {tasso_conformita:.1f}%\n"

        return response

    @staticmethod
    def format_top_risk_activities(
        activities_data: List[Dict[str, Any]],
        total_activities: int,
        high_risk_count: int,
        medium_risk_count: int,
        avg_risk_score: float,
        limit: int
    ) -> str:
        """
        Formatta la lista delle top linee di attività più rischiose.
        """
        if not activities_data:
            return "Nessuna linea di attività con dati di rischio disponibili al momento."

        response = f"🔍 **TOP {limit} LINEE DI ATTIVITÀ A MAGGIOR RISCHIO**\n\n"
        response += f"📊 **Panoramica generale:**\n"
        response += f"- Linee di attività analizzate: {total_activities:,}\n"
        response += f"- Alto rischio (>7): {high_risk_count} linee di attività\n"
        response += f"- Medio rischio (3-7): {medium_risk_count} linee di attività\n"
        response += f"- Risk score medio: {avg_risk_score:.1f}\n\n"

        response += f"🎯 **Classifica per Risk Score:**\n\n"

        for activity in activities_data:
            rank = activity['rank']
            risk_score = activity['risk_score']
            macroarea = activity['macroarea']
            aggregazione = activity['aggregazione']
            nc_gravi = activity['nc_gravi']
            nc_non_gravi = activity['nc_non_gravi']
            controlli = activity['controlli_totali']

            # Determina livello di rischio (soglie calibrate: P90=6.6, P75=3.0)
            if risk_score > 7:
                risk_level = "🔴 ALTO RISCHIO"
            elif risk_score > 3:
                risk_level = "🟡 MEDIO RISCHIO"
            elif risk_score > 1:
                risk_level = "🟢 BASSO RISCHIO"
            else:
                risk_level = "⚪ RISCHIO MINIMO"

            response += f"**{rank}. {macroarea}**\n"
            if aggregazione and aggregazione != 'nan':
                response += f"   📍 Aggregazione: {aggregazione}\n"
            response += f"   📊 Risk Score: **{risk_score:.3f}** ({risk_level})\n"
            response += f"   🔍 NC Gravi: {nc_gravi}, NC Non Gravi: {nc_non_gravi}\n"
            response += f"   📈 Controlli totali: {controlli}"

            # Calcola e mostra metriche interpretabili
            if controlli > 0:
                prob_nc = (nc_gravi + nc_non_gravi) / controlli
                impatto = nc_gravi / controlli
                response += f"\n   📊 NC per controllo: {prob_nc:.1f}, NC gravi per controllo: {impatto:.1f}"

            response += "\n\n"

        # Suggerimenti operativi
        response += f"⚡ **Raccomandazioni:**\n"
        response += f"- Prioritizzare controlli per linee di attività con risk score > 7 (alto rischio)\n"
        response += f"- Pianificare ispezioni mirate per le prime {min(5, len(activities_data))} linee di attività\n"
        response += f"- Monitorare evoluzione risk score dopo i controlli"

        if total_activities > limit:
            response += f"\n\n📋 **Nota:** Altre {total_activities - limit} linee di attività disponibili con risk score inferiore"

        return response

    @staticmethod
    def format_piano_statistics(stats: pd.DataFrame, asl: Optional[str] = None) -> str:
        """
        Formatta statistiche aggregate sui piani di controllo.

        Args:
            stats: DataFrame con statistiche piani
            asl: ASL per cui sono state calcolate le statistiche (opzionale)

        Returns:
            Stringa formattata in markdown
        """
        if stats.empty:
            if asl:
                return f"Non sono disponibili statistiche sui controlli eseguiti per l'ASL **{asl}**."
            else:
                return "Non sono disponibili statistiche sui controlli eseguiti."

        # Header
        if asl:
            response = f"**Statistiche Piani di Controllo - ASL {asl.upper()}**\n\n"
        else:
            response = "**Statistiche Piani di Controllo - Tutti i Controlli**\n\n"

        # Totale controlli
        total_controls = stats['num_controlli'].sum()
        total_plans = len(stats)
        response += f"**Totale controlli:** {total_controls:,}\n"
        response += f"**Piani attivi:** {total_plans}\n\n"

        # Top piani
        response += "**📊 Top Piani per Numero di Controlli:**\n\n"

        for idx, row in enumerate(stats.itertuples(index=False), 1):
            piano_code = getattr(row, 'piano_code', 'N/A')
            piano_desc = getattr(row, 'descrizione_piano', 'N/A')
            num_controlli = getattr(row, 'num_controlli', 0)
            num_stabilimenti = getattr(row, 'num_stabilimenti', 0)
            percentuale = getattr(row, 'percentuale', 0.0)

            # Emoji per ranking
            if idx == 1:
                emoji = "🥇"
            elif idx == 2:
                emoji = "🥈"
            elif idx == 3:
                emoji = "🥉"
            else:
                emoji = f"{idx}."

            response += f"{emoji} **Piano {piano_code}**\n"
            response += f"   • **Descrizione:** {piano_desc}\n"
            response += f"   • **Controlli eseguiti:** {num_controlli:,} ({percentuale:.1f}% del totale)\n"
            response += f"   • **Tipologie stabilimenti:** {num_stabilimenti}\n\n"

        # Aggiungi suggerimenti
        if len(stats) > 0:
            top_piano = stats.iloc[0]
            response += "**💡 Informazioni Utili:**\n"
            response += f"• Il piano più frequente è **{top_piano['piano_code']}** con {top_piano['num_controlli']:,} controlli\n"

            if len(stats) >= 3:
                top_3_perc = stats.head(3)['percentuale'].sum()
                response += f"• I top 3 piani rappresentano il **{top_3_perc:.1f}%** di tutti i controlli\n"

        return response


    @staticmethod
    def format_nearby_priority(
        location: str,
        center_coords: tuple,
        radius_km: float,
        nearby_df: pd.DataFrame,
        total_found: int
    ) -> str:
        """
        Formatta elenco stabilimenti prioritari vicino a una posizione.

        Args:
            location: Indirizzo cercato
            center_coords: Coordinate (lat, lon) del centro ricerca
            radius_km: Raggio utilizzato
            nearby_df: DataFrame con stabilimenti filtrati (include distanza_km)
            total_found: Totale stabilimenti trovati

        Returns:
            Stringa formattata markdown
        """
        if nearby_df.empty:
            return (
                f"Nessun stabilimento mai controllato trovato entro {radius_km} km "
                f"da **{location}**. Prova ad aumentare il raggio."
            )

        lat, lon = center_coords
        response = f"**Stabilimenti Prioritari vicino a {location}**\n\n"
        response += f"**Centro ricerca:** {location} ({lat:.4f}, {lon:.4f})\n"
        response += f"**Raggio:** {radius_km} km\n"
        response += f"**Stabilimenti trovati:** {total_found}\n\n"

        response += "**Stabilimenti da controllare (ordinati per vicinanza e rischio):**\n\n"

        for idx, row in enumerate(nearby_df.itertuples(index=False), 1):
            distanza = getattr(row, 'distanza_km', 0)
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            macroarea = getattr(row, 'macroarea', 'N/D')
            aggregazione = getattr(row, 'aggregazione', 'N/D')
            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'
            indirizzo = getattr(row, 'indirizzo', 'N/D')
            num_ric = getattr(row, 'num_riconoscimento', '') or getattr(row, 'n_reg', '')
            if not num_ric or str(num_ric) == 'nan':
                num_ric = 'N/D'

            risk_score = getattr(row, 'punteggio_rischio_totale', 0)
            try:
                risk_score = int(risk_score) if pd.notna(risk_score) else 0
            except (ValueError, TypeError):
                risk_score = 0

            if ragione:
                response += f"{idx}. **{ragione}** — {aggregazione}\n"
            else:
                response += f"{idx}. **{macroarea}** — {aggregazione}\n"
            response += f"   {indirizzo}, {comune} ({distanza:.1f} km)\n"
            response += f"   N. Registrazione: {num_ric}"

            if risk_score > 0:
                response += f" | Risk Score: {risk_score}/100"

            response += "\n   Mai controllato\n\n"

        if total_found > len(nearby_df):
            response += f"... e altri {total_found - len(nearby_df)} stabilimenti.\n\n"

        response += "**Raccomandazione:** Dai priorità agli stabilimenti più vicini con risk score elevato.\n"

        return response

    @staticmethod
    def format_nearby_priority_summary(
        result: Dict[str, Any],
        limit: int = 5
    ) -> str:
        """
        Formatta sintesi stabilimenti vicini (fase 1 del sistema 2-fasi).

        Args:
            result: Dizionario con dati ricerca
            limit: Numero max stabilimenti da mostrare

        Returns:
            Stringa formattata markdown
        """
        import re

        location = result.get('location', 'N/D')
        resolved_address = result.get('resolved_address', '')
        center_coords = result.get('center_coords', (0, 0))
        radius_km = result.get('radius_km', 5.0)
        total_found = result.get('total_found', 0)
        nearby_data = result.get('nearby_establishments', [])

        if not nearby_data:
            return (
                f"Nessun stabilimento mai controllato trovato entro {radius_km} km "
                f"da **{location}**.\nProva ad aumentare il raggio o verificare l'indirizzo."
            )

        # Converti in DataFrame se necessario
        if isinstance(nearby_data, list):
            nearby_df = pd.DataFrame(nearby_data)
        else:
            nearby_df = nearby_data

        lat, lon = center_coords

        # Prepara warning se l'indirizzo risolto è in un comune diverso
        warning_prefix = ""
        if resolved_address and "⚠️ ATTENZIONE:" in resolved_address:
            # Estrai info dal warning
            city_match = re.search(r'NON è nel comune di (\w+) città, ma a ([^)]+)', resolved_address)
            if city_match:
                city_name = city_match.group(1)
                actual_comune = city_match.group(2)

                # Pulisci l'indirizzo dal warning
                clean_resolved = resolved_address
                clean_resolved = re.sub(r'⚠️ ATTENZIONE:\s*', '', clean_resolved)
                clean_resolved = re.sub(r'\s*\(NON è nel comune di[^)]+\)', '', clean_resolved)
                clean_resolved = clean_resolved.strip()

                warning_prefix = (
                    f"**⚠️ ATTENZIONE - Posizione SBAGLIATA!**\n\n"
                    f"Ho cercato \"{location}\" ma ho trovato un indirizzo a **{actual_comune}**, "
                    f"NON nel comune di **{city_name}** città.\n\n"
                    f"📍 *{clean_resolved}*\n\n"
                    f"**Per cercare nel capoluogo {city_name}, prova:**\n"
                    f"- \"centro {city_name}\" o \"{city_name} centro storico\"\n"
                    f"- Un indirizzo con CAP (es. \"Via Roma, 82100 {city_name}\")\n\n"
                    f"---\n\n"
                    f"**Risultati per la posizione trovata ({actual_comune}):**\n\n"
                )

        response = warning_prefix + f"**Sintesi Stabilimenti vicino a {location}**\n\n"
        response += f"**Centro:** ({lat:.4f}, {lon:.4f})\n"
        response += f"**Raggio:** {radius_km} km\n"
        response += f"**Trovati:** {total_found} stabilimenti\n\n"

        response += f"**Top {min(limit, len(nearby_df))} Stabilimenti:**\n\n"

        for idx, row in enumerate(nearby_df.head(limit).itertuples(index=False), 1):
            distanza = getattr(row, 'distanza_km', 0)
            ragione = getattr(row, 'ragione_sociale', None)
            ragione = str(ragione).strip() if pd.notna(ragione) and str(ragione).strip() else None
            macroarea = getattr(row, 'macroarea', 'N/D')
            comune = str(getattr(row, 'comune', '')).upper() if pd.notna(getattr(row, 'comune', '')) else 'N/D'

            risk_score = getattr(row, 'punteggio_rischio_totale', 0)
            try:
                risk_score = int(risk_score) if pd.notna(risk_score) else 0
            except (ValueError, TypeError):
                risk_score = 0

            risk_indicator = f" | Risk: {risk_score}/100" if risk_score > 0 else ""
            label = ragione if ragione else macroarea

            response += f"{idx}. **{label}** — {comune} ({distanza:.1f} km){risk_indicator}\n"

        if total_found > limit:
            response += f"\n... e altri {total_found - limit} stabilimenti.\n"

        response += "\n**Raccomandazione:** Dai priorità agli stabilimenti più vicini.\n"

        return response


class SuggestionGenerator:
    """
    Generazione suggestions dinamiche per follow-up conversazione.
    """

    @staticmethod
    def generate_piano_suggestions(piano_id: str) -> List[Dict[str, str]]:
        """
        Genera suggestions per un piano specifico.
        """
        return [
            {
                "text": f"Descrizione del **piano {piano_id}**",
                "query": f"di cosa tratta il piano {piano_id}"
            },
            {
                "text": f"Confronta con un **altro piano**",
                "query": f"confronta piano {piano_id} con A1"
            },
            {
                "text": f"**Esporta** i dati",
                "query": f"esporta dati piano {piano_id}"
            }
        ]

    @staticmethod
    def generate_priority_suggestions() -> List[Dict[str, str]]:
        """
        Genera suggestions per priorità controlli.
        """
        return [
            {
                "text": "Suggerimenti basati sulla programmazione ritardata",
                "query": "quale stabilimento dovrei controllare per primo secondo la programmazione"
            },
            {
                "text": "Esporta dati per pianificare i controlli",
                "query": "esporta dati priorità controlli"
            }
        ]

    @staticmethod
    def generate_search_suggestions(matches: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Genera suggestions da risultati ricerca.
        """
        suggestions = []
        for piano_info in matches[:3]:
            alias = piano_info.get('alias_piano_attivita', piano_info.get('alias', ''))
            suggestions.append({
                "text": f"Descrivi il piano {alias}",
                "query": f"di cosa tratta il piano {alias}"
            })
        return suggestions

    @staticmethod
    def generate_description_suggestions(piano_id: str) -> List[Dict[str, str]]:
        """
        Genera suggestions per descrizione piano.
        """
        return [
            {
                "text": f"Vedere gli **stabilimenti** controllati per questo piano",
                "query": f"stabilimenti del piano {piano_id.upper()}"
            },
            {
                "text": "Confronta con un **altro piano**",
                "query": f"confronta piano {piano_id.upper()} con A1"
            },
            {
                "text": "Cerca **piani simili**",
                "query": f"quali piani riguardano {piano_id.upper()}"
            }
        ]

    @staticmethod
    def generate_comparison_suggestions(piano1_id: str, piano2_id: str) -> List[Dict[str, str]]:
        """
        Genera suggestions per confronto piani.
        """
        return [
            {
                "text": f"Dettagli piano {piano1_id}",
                "query": f"dettagli piano {piano1_id}"
            },
            {
                "text": f"Dettagli piano {piano2_id}",
                "query": f"dettagli piano {piano2_id}"
            },
            {
                "text": f"Confronta con altri piani simili",
                "query": f"quali piani sono simili a {piano1_id}"
            }
        ]

    @staticmethod
    def generate_help_suggestions() -> List[Dict[str, str]]:
        """
        Genera suggestions per help system.
        """
        return [
            {
                "text": "Analizza gli **stabilimenti** di un piano",
                "query": "stabilimenti del piano A1"
            },
            {
                "text": "Scopri **chi controllare**",
                "query": "chi dovrei controllare per primo?"
            },
            {
                "text": "Descrizione di un **piano specifico**",
                "query": "di cosa tratta il piano A32?"
            },
            {
                "text": "Cerca **piani per argomento**",
                "query": "quali piani riguardano allevamenti?"
            }
        ]

    @staticmethod
    def format_nc_category_analysis(stats: Dict[str, Any], stabilimenti_nc: pd.DataFrame) -> str:
        """
        Formatta analisi non conformità per categoria specifica.

        Args:
            stats: Statistiche aggregate per la categoria
            stabilimenti_nc: DataFrame stabilimenti con più NC nella categoria

        Returns:
            Stringa formattata in italiano
        """
        categoria = stats['categoria']
        asl_filtro = stats.get('asl_filtro')

        response = f"**📊 Analisi Non Conformità - {categoria}**\n\n"

        if asl_filtro:
            response += f"🏥 **Filtro ASL:** {asl_filtro}\n\n"

        # Statistiche generali
        response += f"**📈 Statistiche Generali:**\n"
        response += f"• **Controlli totali:** {stats['totale_controlli']:,}\n"
        response += f"• **NC gravi:** {stats['nc_gravi']:,}\n"
        response += f"• **NC non gravi:** {stats['nc_non_gravi']:,}\n"
        response += f"• **Stabilimenti coinvolti:** {stats['stabilimenti_coinvolti']:,}\n"

        if not asl_filtro and len(stats['asl_coinvolte']) > 1:
            response += f"• **ASL coinvolte:** {len(stats['asl_coinvolte'])} ({', '.join(stats['asl_coinvolte'][:3])}{'...' if len(stats['asl_coinvolte']) > 3 else ''})\n"

        response += "\n"

        # Stabilimenti critici
        if not stabilimenti_nc.empty:
            response += f"**🚨 Stabilimenti Critici ({categoria}):**\n\n"

            for idx, row in enumerate(stabilimenti_nc.head(5).itertuples(), 1):
                response += f"{idx}. **{row.numero_riconoscimento}** ({row.asl})\n"
                response += f"   📍 {row.comune} - {row.macroarea}\n"
                response += f"   🔴 **{int(row.tot_nc_categoria)} NC** in {int(row.controlli_totali)} controlli ({row.percentuale_nc_categoria:.1f}%)\n\n"

        else:
            response += "ℹ️ Nessun stabilimento con NC significative in questa categoria.\n\n"

        # Raccomandazioni
        response += "**💡 Raccomandazioni:**\n"
        if stats['nc_gravi'] > 0:
            response += f"• Priorità agli stabilimenti con NC gravi ({stats['nc_gravi']} casi)\n"

        response += f"• Monitoraggio specifico per categoria **{categoria}**\n"
        response += "• Controlli mirati sui stabilimenti elencati sopra\n"

        return response

    @staticmethod
    def format_risk_prediction(prediction_data: Dict[str, Any], top_categories: pd.DataFrame) -> str:
        """
        Formatta predizione categorie di rischio per attività.

        Args:
            prediction_data: Dati predizione con macroarea/aggregazione
            top_categories: DataFrame con top categorie di rischio

        Returns:
            Stringa formattata in italiano
        """
        macroarea = prediction_data['macroarea']
        aggregazione = prediction_data['aggregazione']

        response = f"**🔮 Predizione Rischio - {macroarea}**\n\n"
        response += f"**🎯 Attività:** {aggregazione}\n\n"

        response += "**📊 Categorie NC ad Alto Rischio (Top 5):**\n\n"

        for idx, row in enumerate(top_categories.head(5).itertuples(index=False)):
            categoria = getattr(row, 'categoria_nc', '')
            risk_score = getattr(row, 'punteggio_rischio_categoria', '')
            prob_nc = getattr(row, 'prob_nc', 0)
            impatto = getattr(row, 'impatto', 0)

            # Determina livello rischio per emoji
            if risk_score >= 50:
                risk_emoji = "🔴"
                risk_level = "ALTO"
            elif risk_score >= 20:
                risk_emoji = "🟡"
                risk_level = "MEDIO"
            else:
                risk_emoji = "🟢"
                risk_level = "BASSO"

            response += f"{idx + 1}. {risk_emoji} **{categoria}**\n"
            response += f"   • **Rischio:** {risk_level} (Score: {risk_score:.1f})\n"
            response += f"   • **NC per controllo:** {prob_nc:.1f}\n"
            response += f"   • **NC gravi per controllo:** {impatto:.1f}\n\n"

        # Raccomandazioni specifiche
        response += "**💡 Raccomandazioni per i Controlli:**\n"

        if len(top_categories) > 0:
            top_category = top_categories.iloc[0]
            response += f"• **Priorità assoluta:** {top_category['categoria_nc']}\n"

            if top_category['punteggio_rischio_categoria'] >= 50:
                response += "• 🔴 **Controlli urgenti** raccomandati per questa categoria\n"
            elif top_category['punteggio_rischio_categoria'] >= 20:
                response += "• 🟡 **Controlli programmati** entro breve periodo\n"

        response += f"• Focalizzare ispezioni su: {', '.join(top_categories['categoria_nc'].head(3).tolist())}\n"
        response += "• Preparare checklist specifiche per le categorie ad alto rischio\n"

        return response
