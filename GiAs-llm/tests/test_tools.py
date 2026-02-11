"""
Test per i tools (piano, priority, risk, search)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.piano_tools import piano_tool, get_piano_description, get_piano_attivita
from tools.search_tools import search_tool, search_piani_by_topic
from tools.priority_tools import priority_tool, get_priority_establishment, suggest_controls
from tools.risk_tools import risk_tool, get_risk_based_priority


class TestPianoTools:
    """Test per piano_tools.py"""

    @patch('tools.piano_tools.DataRetriever')
    def test_get_piano_description_success(self, mock_retriever):
        """Test recupero descrizione piano con successo"""
        mock_df = pd.DataFrame({
            'sezione': ['A'],
            'alias': ['A1'],
            'descrizione': ['Test description']
        })
        mock_retriever.get_piano_by_id.return_value = mock_df

        with patch('tools.piano_tools.BusinessLogic') as mock_logic, \
             patch('tools.piano_tools.ResponseFormatter') as mock_formatter:
            mock_logic.extract_unique_piano_descriptions.return_value = {'desc': {}}
            mock_formatter.format_piano_description.return_value = "Formatted response"

            result = get_piano_description("A1")

            assert "error" not in result
            assert result["piano_code"] == "A1"
            assert "description" in result

    @patch('tools.piano_tools.DataRetriever')
    def test_get_piano_description_not_found(self, mock_retriever):
        """Test piano non trovato"""
        mock_retriever.get_piano_by_id.return_value = pd.DataFrame()

        result = get_piano_description("XXX")

        assert "error" in result
        assert "non trovato" in result["error"].lower()

    def test_get_piano_description_empty_code(self):
        """Test con codice piano vuoto"""
        result = get_piano_description("")

        assert "error" in result
        assert "non specificato" in result["error"].lower()

    @patch('tools.piano_tools.DataRetriever')
    def test_get_piano_attivita_success(self, mock_retriever):
        """Test recupero attività piano"""
        mock_controlli = pd.DataFrame({
            'descrizione_piano': ['Piano A1'],
            'macroarea_cu': ['Area1'],
            'aggregazione_cu': ['Agg1'],
            'attivita_cu': ['Att1']
        })
        mock_retriever.get_controlli_by_piano.return_value = mock_controlli

        with patch('tools.piano_tools.BusinessLogic') as mock_logic, \
             patch('tools.piano_tools.ResponseFormatter') as mock_formatter:
            mock_stabilimenti = pd.DataFrame({'count': [10]})
            mock_logic.aggregate_stabilimenti_by_piano.return_value = mock_stabilimenti
            mock_formatter.format_stabilimenti_analysis.return_value = "Analysis"

            result = get_piano_attivita("A1")

            assert "error" not in result
            assert result["piano_code"] == "A1"
            assert "top_stabilimenti" in result

    def test_piano_tool_router(self):
        """Test router piano_tool"""
        with patch('tools.piano_tools.get_piano_description') as mock_desc:
            mock_desc.return_value = {"piano_code": "A1"}
            result = piano_tool(action="description", piano_code="A1")
            assert result["piano_code"] == "A1"

        with patch('tools.piano_tools.get_piano_attivita') as mock_att:
            mock_att.return_value = {"piano_code": "A1"}
            result = piano_tool(action="stabilimenti", piano_code="A1")
            assert result["piano_code"] == "A1"

        result = piano_tool(action="invalid", piano_code="A1")
        assert "error" in result


class TestSearchTools:
    """Test per search_tools.py"""

    @patch('tools.search_tools.DataRetriever')
    def test_search_piani_by_topic_success(self, mock_retriever):
        """Test ricerca piani con risultati"""
        mock_retriever.search_piani_by_keyword.return_value = [
            {'alias': 'A1', 'similarity': 0.9, 'descrizione': 'Test'},
            {'alias': 'A2', 'similarity': 0.8, 'descrizione': 'Test2'}
        ]

        with patch('tools.search_tools.ResponseFormatter') as mock_formatter:
            mock_formatter.format_search_results.return_value = "Results"

            result = search_piani_by_topic("bovini")

            assert "error" not in result
            assert result["total_found"] == 2
            assert len(result["matches"]) == 2

    @patch('tools.search_tools.DataRetriever')
    def test_search_piani_no_results(self, mock_retriever):
        """Test ricerca senza risultati"""
        mock_retriever.search_piani_by_keyword.return_value = []

        result = search_piani_by_topic("xyz")

        assert "error" in result
        assert result["total_found"] == 0

    def test_search_piani_empty_query(self):
        """Test con query vuota"""
        result = search_piani_by_topic("")

        assert "error" in result


class TestPriorityTools:
    """Test per priority_tools.py"""

    @patch('tools.priority_tools.DataRetriever')
    def test_get_priority_establishment_missing_params(self, mock_retriever):
        """Test parametri mancanti"""
        result = get_priority_establishment(None, "UOC1")
        assert "error" in result

        result = get_priority_establishment("NA1", None)
        assert "error" in result

    @patch('tools.priority_tools.DataRetriever')
    @patch('tools.priority_tools.BusinessLogic')
    @patch('tools.priority_tools.RiskAnalyzer')
    def test_get_priority_establishment_success(self, mock_risk, mock_logic, mock_retriever):
        """Test recupero stabilimenti prioritari"""
        mock_diff = pd.DataFrame({
            'piano': ['A1'],
            'programmati': [10],
            'eseguiti': [5]
        })
        mock_retriever.get_diff_programmati_eseguiti.return_value = mock_diff

        mock_delayed = pd.DataFrame({
            'piano': ['A1'],
            'ritardo': [5],
            'programmati': [10],
            'eseguiti': [5],
            'descrizione_indicatore': ['Test']
        })
        mock_logic.calculate_delayed_plans.return_value = mock_delayed

        mock_osa = pd.DataFrame({'comune': ['Napoli']})
        mock_retriever.get_osa_mai_controllati.return_value = mock_osa

        mock_priority_display = pd.DataFrame({'macroarea': ['Test']})
        mock_priority_data = [{'macroarea': 'Test'}]
        mock_risk.find_priority_establishments.return_value = (mock_priority_display, mock_priority_data)

        with patch('tools.priority_tools.ResponseFormatter') as mock_formatter:
            mock_formatter.format_priority_establishments.return_value = "Priority response"

            result = get_priority_establishment("NA1", "UOC Test", "A1")

            assert "error" not in result
            assert result["asl"] == "NA1"
            assert "priority_establishments" in result

    @patch('tools.priority_tools.DataRetriever')
    def test_suggest_controls_success(self, mock_retriever):
        """Test suggerimenti controlli"""
        mock_osa = pd.DataFrame({
            'comune': ['Napoli', 'Salerno'],
            'indirizzo': ['Via 1', 'Via 2']
        })
        mock_retriever.get_osa_mai_controllati.return_value = mock_osa

        with patch('tools.priority_tools.ResponseFormatter') as mock_formatter:
            mock_formatter.format_suggest_controls.return_value = "Suggestions"

            result = suggest_controls("NA1", limit=2)

            assert "error" not in result
            assert result["total_never_controlled"] == 2


class TestRiskTools:
    """Test per risk_tools.py"""

    def test_get_risk_based_priority_missing_asl(self):
        """Test ASL mancante"""
        result = get_risk_based_priority(None)

        assert "error" in result
        assert "non specificata" in result["error"].lower()

    @patch('tools.risk_tools.RiskAnalyzer')
    @patch('tools.risk_tools.DataRetriever')
    def test_get_risk_based_priority_success(self, mock_retriever, mock_analyzer):
        """Test analisi rischio con successo"""
        mock_risk_scores = pd.DataFrame({
            'macroarea': ['Area1'],
            'aggregazione': ['Agg1'],
            'linea_attivita': ['Att1'],
            'punteggio_rischio_totale': [100],
            'tot_nc_gravi': [5],
            'tot_nc_non_gravi': [10],
            'numero_controlli_totali': [20]
        })
        mock_analyzer.calculate_risk_scores.return_value = mock_risk_scores

        mock_osa = pd.DataFrame({
            'macroarea': ['Area1'],
            'aggregazione': ['Agg1'],
            'attivita': ['Att1'],
            'comune': ['Napoli'],
            'indirizzo': ['Via 1'],
            'num_riconoscimento': ['123'],
            'n_reg': ['REG1'],
            'codice_fiscale': ['CF123']
        })
        mock_retriever.get_osa_mai_controllati.return_value = mock_osa

        mock_risky_display = pd.DataFrame({
            'punteggio_rischio_totale': [100],
            'tot_nc_gravi': [5],
            'tot_nc_non_gravi': [10],
            'numero_controlli_totali': [20],
            'macroarea': ['Area1'],
            'aggregazione': ['Agg1'],
            'comune': ['Napoli'],
            'indirizzo': ['Via 1'],
            'num_riconoscimento': ['123'],
            'n_reg': ['REG1'],
            'codice_fiscale': ['CF123'],
            'data_inizio_attivita': ['2020-01-01']
        })
        mock_risky_full = mock_risky_display.copy()
        mock_analyzer.rank_osa_by_risk.return_value = (mock_risky_display, mock_risky_full)

        with patch('tools.risk_tools.ResponseFormatter') as mock_formatter:
            mock_formatter.format_risk_based_priority.return_value = "Risk analysis"

            result = get_risk_based_priority("NA1")

            assert "error" not in result
            assert result["asl"] == "NA1"
            assert "risky_establishments" in result
            assert result["total_risky"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
