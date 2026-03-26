#!/usr/bin/env python3
"""
Test per verificare la nuova formula di risk score
"""

import sys
import os
import pandas as pd

# Aggiungi path per imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agents.data_agent import RiskAnalyzer
    from agents.data import controlli_df
except ImportError:
    print("❌ Errore import moduli")
    sys.exit(1)

def print_comparison():
    """Confronta vecchia vs nuova formula di risk score"""

    print("🔬 TEST NUOVA FORMULA RISK SCORE")
    print("=" * 60)

    # Formula vecchia
    def old_formula(nc_gravi, nc_non_gravi):
        return nc_gravi * 3 + nc_non_gravi * 1

    # Formula nuova
    def new_formula(nc_gravi, nc_non_gravi, controlli):
        if controlli == 0:
            return 0
        tot_nc = nc_gravi + nc_non_gravi
        prob_nc = tot_nc / controlli
        impatto = nc_gravi / controlli
        return prob_nc * impatto * 100

    # Esempi di test
    test_cases = [
        {"attivita": "Allevamento bovini", "nc_gravi": 10, "nc_non_gravi": 5, "controlli": 20},
        {"attivita": "Macellazione ungulati", "nc_gravi": 3, "nc_non_gravi": 12, "controlli": 50},
        {"attivita": "Trasformazione latte", "nc_gravi": 8, "nc_non_gravi": 2, "controlli": 15},
        {"attivita": "Allevamento suini", "nc_gravi": 1, "nc_non_gravi": 20, "controlli": 100},
        {"attivita": "Acquacoltura", "nc_gravi": 5, "nc_non_gravi": 1, "controlli": 8}
    ]

    print(f"{'Attività':<20} {'NC_G':<4} {'NC_NG':<5} {'Ctrl':<5} {'Vecchia':<8} {'Nuova':<8} {'Interpretazione'}")
    print("-" * 85)

    for case in test_cases:
        old_score = old_formula(case['nc_gravi'], case['nc_non_gravi'])
        new_score = new_formula(case['nc_gravi'], case['nc_non_gravi'], case['controlli'])

        # Interpretazione
        if new_score > 20:
            interpretation = "ALTO RISCHIO"
        elif new_score > 5:
            interpretation = "MEDIO RISCHIO"
        elif new_score > 1:
            interpretation = "BASSO RISCHIO"
        else:
            interpretation = "RISCHIO MINIMO"

        print(f"{case['attivita']:<20} {case['nc_gravi']:<4} {case['nc_non_gravi']:<5} {case['controlli']:<5} "
              f"{old_score:<8.0f} {new_score:<8.1f} {interpretation}")

    print("\n📊 VANTAGGI NUOVA FORMULA:")
    print("✅ Considera il numero di controlli (normalizza)")
    print("✅ Distingue probabilità da impatto")
    print("✅ Un'attività con poche NC su molti controlli = minor rischio")
    print("✅ Un'attività con molte NC gravi su pochi controlli = maggior rischio")

    print("\n🎯 INTERPRETAZIONE RISK SCORE:")
    print("• > 20: ALTO RISCHIO (priorità massima)")
    print("• 5-20: MEDIO RISCHIO (priorità normale)")
    print("• 1-5: BASSO RISCHIO (controllo programmato)")
    print("• < 1: RISCHIO MINIMO (controllo routine)")

def test_real_data():
    """Test con dati reali da controlli_df (cu_eseguiti_nc)"""
    print(f"\n TEST CON DATI REALI")
    print("=" * 60)

    if controlli_df.empty:
        print("Dataset controlli vuoto")
        return

    try:
        risk_scores = RiskAnalyzer.calculate_risk_scores()

        if risk_scores.empty:
            print("❌ Nessun risk score calcolato")
            return

        print(f"📋 Calcolati risk scores per {len(risk_scores)} attività")
        print(f"\n🔝 TOP 5 ATTIVITÀ A MAGGIOR RISCHIO:")
        print("-" * 80)

        top_5 = risk_scores.head()
        for idx, row in top_5.iterrows():
            print(f"{idx+1}. {row['macroarea'][:30]:<30}")
            print(f"   📊 Risk Score: {row['punteggio_rischio_totale']:.3f}")
            print(f"   🔍 NC Gravi: {row['tot_nc_gravi']}, NC Non Gravi: {row['tot_nc_non_gravi']}")
            print(f"   📈 Controlli totali: {row['numero_controlli_totali']}")
            if row['numero_controlli_totali'] > 0:
                prob = (row['tot_nc_gravi'] + row['tot_nc_non_gravi']) / row['numero_controlli_totali']
                impact = row['tot_nc_gravi'] / row['numero_controlli_totali']
                print(f"   📊 P(NC): {prob:.3f}, Impatto: {impact:.3f}")
            print()

        # Statistiche
        print(f"📊 STATISTICHE:")
        print(f"   Risk Score medio: {risk_scores['punteggio_rischio_totale'].mean():.3f}")
        print(f"   Risk Score massimo: {risk_scores['punteggio_rischio_totale'].max():.3f}")
        print(f"   Risk Score minimo: {risk_scores['punteggio_rischio_totale'].min():.3f}")

        # Distribuzione
        high_risk = len(risk_scores[risk_scores['punteggio_rischio_totale'] > 20])
        medium_risk = len(risk_scores[(risk_scores['punteggio_rischio_totale'] > 5) & (risk_scores['punteggio_rischio_totale'] <= 20)])
        low_risk = len(risk_scores[risk_scores['punteggio_rischio_totale'] <= 5])

        print(f"   🔴 Alto rischio (>20): {high_risk} attività")
        print(f"   🟡 Medio rischio (5-20): {medium_risk} attività")
        print(f"   🟢 Basso rischio (≤5): {low_risk} attività")

    except Exception as e:
        print(f"❌ Errore nel test: {e}")

if __name__ == "__main__":
    print_comparison()
    test_real_data()
    print(f"\n✅ Test completato!")