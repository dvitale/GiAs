"""
Test suite per le nuove funzionalità delle categorie NC.
M1.1 Step 1.1.4 - Test unitari per nuove funzioni
"""

import pytest
import pandas as pd
from agents.data_agent import (
    RiskAnalyzer,
    NC_CATEGORY_WEIGHTS,
    VALID_NC_CATEGORIES
)


class TestNCCategories:
    """Test per costanti e validazione categorie NC"""

    def test_nc_category_weights_exist(self):
        """Test che le costanti NC siano definite correttamente"""
        assert NC_CATEGORY_WEIGHTS is not None
        assert len(NC_CATEGORY_WEIGHTS) == 11
        assert 'HACCP' in NC_CATEGORY_WEIGHTS
        assert NC_CATEGORY_WEIGHTS['HACCP'] == 1.0

    def test_valid_nc_categories(self):
        """Test che VALID_NC_CATEGORIES sia consistente"""
        assert len(VALID_NC_CATEGORIES) == 11
        assert all(cat in NC_CATEGORY_WEIGHTS for cat in VALID_NC_CATEGORIES)

    def test_nc_weights_range(self):
        """Test che i pesi siano nel range corretto"""
        for weight in NC_CATEGORY_WEIGHTS.values():
            assert 0.0 <= weight <= 1.0


class TestCategorizedRiskScores:
    """Test per calculate_categorized_risk_scores()"""

    def test_categorized_risk_scores_structure(self):
        """Test struttura DataFrame restituito"""
        result = RiskAnalyzer.calculate_categorized_risk_scores()

        # Verifica che il metodo non sollevi eccezioni
        assert isinstance(result, pd.DataFrame)

        if not result.empty:
            # Verifica colonne attese
            expected_columns = [
                'macroarea', 'aggregazione', 'linea_attivita', 'categoria_nc',
                'tot_nc_gravi', 'tot_nc_non_gravi', 'numero_controlli_totali',
                'tot_nc_totali', 'prob_nc', 'impatto', 'peso_categoria',
                'punteggio_rischio_categoria'
            ]

            for col in expected_columns:
                assert col in result.columns, f"Colonna mancante: {col}"

    def test_categorized_risk_scores_categories_valid(self):
        """Test che tutte le categorie nel risultato siano valide"""
        result = RiskAnalyzer.calculate_categorized_risk_scores()

        if not result.empty:
            unique_categories = result['categoria_nc'].unique()
            for cat in unique_categories:
                assert cat in VALID_NC_CATEGORIES, f"Categoria non valida: {cat}"

    def test_categorized_risk_scores_weights_applied(self):
        """Test che i pesi categoria siano applicati correttamente"""
        result = RiskAnalyzer.calculate_categorized_risk_scores()

        if not result.empty:
            for _, row in result.head(3).iterrows():
                categoria = row['categoria_nc']
                peso_atteso = NC_CATEGORY_WEIGHTS[categoria]
                peso_effettivo = row['peso_categoria']
                assert peso_effettivo == peso_atteso, f"Peso errato per {categoria}"

    def test_categorized_risk_scores_sorting(self):
        """Test che i risultati siano ordinati per punteggio decrescente"""
        result = RiskAnalyzer.calculate_categorized_risk_scores()

        if len(result) > 1:
            scores = result['punteggio_rischio_categoria'].tolist()
            assert scores == sorted(scores, reverse=True), "Risultati non ordinati correttamente"


class TestNCCategoryTrends:
    """Test per analyze_nc_category_trends()"""

    def test_trends_with_valid_category(self):
        """Test analisi trend con categoria valida"""
        result = RiskAnalyzer.analyze_nc_category_trends('HACCP', 12)

        assert isinstance(result, pd.DataFrame)

        if not result.empty:
            expected_columns = [
                'asl', 'anno', 'nc_gravi', 'nc_non_gravi',
                'controlli_totali', 'nc_totali', 'percentuale_nc', 'categoria_nc'
            ]

            for col in expected_columns:
                assert col in result.columns, f"Colonna mancante: {col}"

            # Verifica che categoria_nc sia quella richiesta
            assert all(result['categoria_nc'] == 'HACCP')

    def test_trends_with_invalid_category(self):
        """Test analisi trend con categoria non valida"""
        result = RiskAnalyzer.analyze_nc_category_trends('CATEGORIA_INESISTENTE', 12)

        # Dovrebbe ritornare DataFrame vuoto per categoria non valida
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_trends_data_types(self):
        """Test che i tipi di dati siano corretti"""
        result = RiskAnalyzer.analyze_nc_category_trends('IGIENE DEGLI ALIMENTI', 12)

        if not result.empty:
            # Test tipi numerici
            assert pd.api.types.is_numeric_dtype(result['nc_gravi'])
            assert pd.api.types.is_numeric_dtype(result['nc_non_gravi'])
            assert pd.api.types.is_numeric_dtype(result['controlli_totali'])
            assert pd.api.types.is_numeric_dtype(result['percentuale_nc'])

    def test_trends_percentage_calculation(self):
        """Test che le percentuali siano calcolate correttamente"""
        result = RiskAnalyzer.analyze_nc_category_trends('HACCP', 12)

        if not result.empty:
            for _, row in result.head(3).iterrows():
                nc_totali = row['nc_totali']
                controlli = row['controlli_totali']
                percentuale_calcolata = (nc_totali / controlli * 100) if controlli > 0 else 0
                percentuale_effettiva = row['percentuale_nc']

                # Confronto con tolleranza per errori di arrotondamento
                assert abs(percentuale_calcolata - percentuale_effettiva) < 0.01


class TestIntegrationCategorizedAnalysis:
    """Test di integrazione per funzionalità categorie NC"""

    def test_end_to_end_analysis(self):
        """Test end-to-end: risk scores + trends per stessa categoria"""
        categoria = 'HACCP'

        # Test risk scores
        risk_result = RiskAnalyzer.calculate_categorized_risk_scores()
        categoria_risk = risk_result[risk_result['categoria_nc'] == categoria]

        # Test trends
        trend_result = RiskAnalyzer.analyze_nc_category_trends(categoria, 12)

        # Verifica coerenza: se ci sono risk scores, dovrebbero esserci anche trend
        if not categoria_risk.empty:
            assert not trend_result.empty, f"Inconsistenza: risk scores per {categoria} ma no trend data"

    def test_all_categories_processable(self):
        """Test che tutte le categorie possano essere elaborate"""
        errors = []

        for categoria in VALID_NC_CATEGORIES:
            try:
                # Test che ogni categoria possa essere processata senza errori
                trend_result = RiskAnalyzer.analyze_nc_category_trends(categoria, 12)
                assert isinstance(trend_result, pd.DataFrame)
            except Exception as e:
                errors.append(f"Errore con categoria {categoria}: {e}")

        assert len(errors) == 0, f"Errori trovati: {errors}"


if __name__ == "__main__":
    # Esecuzione test rapida per verifica locale
    print("🧪 Eseguendo test NC Categories...")

    # Test costanti
    test_constants = TestNCCategories()
    test_constants.test_nc_category_weights_exist()
    test_constants.test_valid_nc_categories()
    test_constants.test_nc_weights_range()
    print("✅ Test costanti NC passati")

    # Test risk scores
    test_risk = TestCategorizedRiskScores()
    test_risk.test_categorized_risk_scores_structure()
    test_risk.test_categorized_risk_scores_categories_valid()
    print("✅ Test risk scores categorizzati passati")

    # Test trends
    test_trends = TestNCCategoryTrends()
    test_trends.test_trends_with_valid_category()
    test_trends.test_trends_with_invalid_category()
    print("✅ Test analisi trend passati")

    # Test integrazione
    test_integration = TestIntegrationCategorizedAnalysis()
    test_integration.test_end_to_end_analysis()
    print("✅ Test integrazione passati")

    print("🎉 Tutti i test sono passati con successo!")