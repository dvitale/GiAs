#!/usr/bin/env python3
"""
Script di diagnostica per il server cloud.
Identifica problemi di compatibilità dati e configurazione.
"""

import traceback
import os

def main():
    print("🌐 DIAGNOSTICA SERVER CLOUD")
    print("=" * 50)

    try:
        # 1. Informazioni ambiente
        print("1. AMBIENTE:")
        print(f"   - Working directory: {os.getcwd()}")
        print(f"   - Files presenti: {len(os.listdir('.'))}")

        # Controlla dataset
        dataset_dirs = [d for d in os.listdir('.') if d.startswith('dataset')]
        print(f"   - Dataset directories: {dataset_dirs}")

        if os.path.exists('config.json'):
            print("   ✅ config.json presente")
        else:
            print("   ❌ config.json mancante")

        # 2. Test configurazione
        print("\n2. CONFIGURAZIONE:")
        try:
            from configs.config import AppConfig
            AppConfig.print_model_config()
            print("   ✅ Config loaded successfully")
        except Exception as e:
            print(f"   ❌ Config error: {e}")

        # 3. Test caricamento dati
        print("\n3. CARICAMENTO DATI:")
        try:
            from agents.data import piani_df, controlli_df, osa_mai_controllati_df, diff_prog_eseg_df

            print(f"   - piani_df: {len(piani_df)} rows")
            print(f"   - controlli_df: {len(controlli_df)} rows")
            print(f"   - osa_mai_controllati_df: {len(osa_mai_controllati_df)} rows")
            print(f"   - diff_prog_eseg_df: {len(diff_prog_eseg_df)} rows")

            # Verifica colonne critiche
            print(f"   - controlli_df columns: {list(controlli_df.columns)}")
            print(f"   - diff_prog_eseg_df columns: {list(diff_prog_eseg_df.columns)}")

            # Cerca colonna 'piano' che causa l'errore
            for df_name, df in [('controlli_df', controlli_df), ('diff_prog_eseg_df', diff_prog_eseg_df)]:
                if 'piano' in df.columns:
                    print(f"   ✅ Column 'piano' found in {df_name}")
                    print(f"      Sample values: {df['piano'].head().tolist()}")
                else:
                    print(f"   ❌ Column 'piano' MISSING in {df_name}")
                    # Cerca colonne simili
                    piano_like = [col for col in df.columns if 'piano' in col.lower()]
                    if piano_like:
                        print(f"      Similar columns: {piano_like}")

            print("   ✅ Data loading successful")

        except Exception as e:
            print(f"   ❌ Data loading error: {e}")
            traceback.print_exc()

        # 4. Test tools
        print("\n4. TEST TOOLS:")
        try:
            from tools.risk_tools import get_risk_based_priority
            from tools.priority_tools import get_priority_establishments

            # Test priorità (quello che dovrebbe funzionare)
            priority_func = get_priority_establishments.func if hasattr(get_priority_establishments, 'func') else get_priority_establishments
            priority_result = priority_func(asl="NA1")

            print(f"   - Priority tool result keys: {list(priority_result.keys())}")
            if "error" in priority_result:
                print(f"   ❌ Priority error: {priority_result['error']}")
            else:
                print("   ✅ Priority tool works")

            # Test risk (quello che fallisce)
            risk_func = get_risk_based_priority.func if hasattr(get_risk_based_priority, 'func') else get_risk_based_priority
            risk_result = risk_func()  # Test caso base

            print(f"   - Risk tool result keys: {list(risk_result.keys())}")
            if "error" in risk_result:
                print(f"   ✅ Risk tool expected error: {risk_result['error']}")

        except Exception as e:
            print(f"   ❌ Tools error: {e}")
            traceback.print_exc()

        # 5. Test LLM (solo connessione)
        print("\n5. TEST LLM:")
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                print(f"   ✅ Ollama online: {len(models)} models")
                for model in models:
                    print(f"      - {model.get('name', 'unknown')}")
            else:
                print(f"   ❌ Ollama error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Ollama connection error: {e}")

        print("\n" + "=" * 50)
        print("🎯 DIAGNOSTICA COMPLETATA")

    except Exception as e:
        print(f"\n❌ ERRORE CRITICO: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()