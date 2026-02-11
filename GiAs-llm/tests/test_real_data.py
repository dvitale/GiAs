#!/usr/bin/env python3
"""
Test del sistema con dati reali caricati da ./dataset
"""

import sys
sys.path.insert(0, '/opt/lang-env/GiAs-llm')

from agents.data_agent import DataRetriever, BusinessLogic, RiskAnalyzer
from agents.response_agent import ResponseFormatter

def test_piano_description():
    print("=" * 60)
    print("TEST 1: Descrizione Piano A1")
    print("=" * 60)

    piano_rows = DataRetriever.get_piano_by_id('A1')
    if piano_rows is None or piano_rows.empty:
        print("❌ Piano A1 non trovato")
        return False

    unique_descriptions = BusinessLogic.extract_unique_piano_descriptions(piano_rows)
    response = ResponseFormatter.format_piano_description('A1', unique_descriptions, len(piano_rows))

    print(f"✅ Piano A1 trovato")
    print(f"   - Varianti: {len(piano_rows)}")
    print(f"   - Descrizioni uniche: {len(unique_descriptions)}")
    print(f"\nRisposta formattata:\n{response[:300]}...\n")
    return True


def test_controlli_statistics():
    print("=" * 60)
    print("TEST 2: Statistiche Controlli Piano A32")
    print("=" * 60)

    controlli_df = DataRetriever.get_controlli_by_piano('A32')
    if controlli_df is None or controlli_df.empty:
        print("❌ Nessun controllo trovato per piano A32")
        return False

    top_stabilimenti = BusinessLogic.aggregate_stabilimenti_by_piano(controlli_df, top_n=10)

    print(f"✅ Controlli eseguiti: {len(controlli_df)}")
    print(f"   - Stabilimenti aggregati: {len(top_stabilimenti)}")
    print(f"\nTop 5 stabilimenti più controllati:")
    for i, row in enumerate(top_stabilimenti.head(5).itertuples(), 1):
        print(f"   {i}. {row.macroarea_cu} - {row.aggregazione_cu}: {row.count} controlli")
    print()
    return True


def test_risk_analysis():
    print("=" * 60)
    print("TEST 3: Analisi Rischio")
    print("=" * 60)

    rischio_per_attivita = RiskAnalyzer.calculate_risk_scores()
    if rischio_per_attivita.empty:
        print("❌ Nessun score di rischio calcolato")
        return False

    print(f"✅ Attività con score di rischio: {len(rischio_per_attivita)}")
    print(f"\nTop 5 attività a maggior rischio:")
    for i, row in enumerate(rischio_per_attivita.head(5).itertuples(), 1):
        print(f"   {i}. {row.macroarea[:50]}: {row.punteggio_rischio_totale:.1f} punti (NC gravi: {row.tot_nc_gravi})")
    print()
    return True


def test_osa_mai_controllati():
    print("=" * 60)
    print("TEST 4: OSA Mai Controllati (ASL NA1)")
    print("=" * 60)

    osa_df = DataRetriever.get_osa_mai_controllati(asl='NA1')
    if osa_df is None or osa_df.empty:
        print("⚠️  Nessun OSA mai controllato per ASL NA1")
        return True

    print(f"✅ OSA mai controllati in ASL NA1: {len(osa_df)}")
    print(f"\nPrimi 5 stabilimenti:")
    for i, row in enumerate(osa_df.head(5).itertuples(), 1):
        comune = getattr(row, 'comune', 'N/A')
        macroarea = getattr(row, 'macroarea', 'N/A')
        print(f"   {i}. {comune[:30]} - {macroarea[:40]}")
    print()
    return True


def test_search_piani():
    print("=" * 60)
    print("TEST 5: Ricerca Semantica Piani (keyword: 'bovini')")
    print("=" * 60)

    matches = DataRetriever.search_piani_by_keyword('bovini', similarity_threshold=0.3)
    if not matches:
        print("❌ Nessun piano trovato per keyword 'bovini'")
        return False

    print(f"✅ Piani trovati: {len(matches)}")
    print(f"\nTop 3 match:")
    for i, match in enumerate(matches[:3], 1):
        piano_id = match.get('alias', match.get('piano_id', 'N/A'))
        print(f"   {i}. Piano {piano_id} (similarità: {match['similarity']:.2f})")
        print(f"      {match['descrizione'][:80]}...")
    print()
    return True


def test_delayed_plans():
    print("=" * 60)
    print("TEST 6: Piani in Ritardo")
    print("=" * 60)

    from agents.data import diff_prog_eseg_df

    if diff_prog_eseg_df.empty:
        print("⚠️  Nessun dato programmazione disponibile")
        return True

    delayed = BusinessLogic.calculate_delayed_plans(diff_prog_eseg_df)

    print(f"✅ Record programmazione analizzati: {len(diff_prog_eseg_df)}")
    print(f"   - Piani in ritardo: {len(delayed)}")
    if not delayed.empty:
        print(f"\nTop 3 piani in ritardo:")
        for i, row in enumerate(delayed.head(3).itertuples(), 1):
            gap = getattr(row, 'gap', 0)
            piano = getattr(row, 'piano', 'N/A')
            print(f"   {i}. Piano {piano}: gap di {gap} controlli")
    print()
    return True


def main():
    print("\n" + "=" * 60)
    print("TEST SISTEMA CON DATI REALI")
    print("=" * 60 + "\n")

    from agents.data import piani_df, controlli_df, osa_mai_controllati_df, ocse_df, diff_prog_eseg_df, attivita_df

    print(f"📊 Dataset caricati:")
    print(f"   - Piani: {len(piani_df)}")
    print(f"   - Attività: {len(attivita_df)}")
    print(f"   - Controlli: {len(controlli_df)}")
    print(f"   - OSA mai controllati: {len(osa_mai_controllati_df)}")
    print(f"   - OCSE (NC): {len(ocse_df)}")
    print(f"   - Programmati vs Eseguiti: {len(diff_prog_eseg_df)}")
    print()

    results = []
    results.append(("Descrizione Piano", test_piano_description()))
    results.append(("Statistiche Controlli", test_controlli_statistics()))
    results.append(("Analisi Rischio", test_risk_analysis()))
    results.append(("OSA Mai Controllati", test_osa_mai_controllati()))
    results.append(("Ricerca Semantica", test_search_piani()))
    results.append(("Piani in Ritardo", test_delayed_plans()))

    print("=" * 60)
    print("RIEPILOGO TEST")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotale: {passed}/{total} test passati ({passed*100//total}%)")
    print("=" * 60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
