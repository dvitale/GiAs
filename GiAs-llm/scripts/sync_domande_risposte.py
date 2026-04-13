#!/usr/bin/env python3
"""
DEPRECATED: domande_risposte e' stata unificata in intent_examples.

La tabella intent_examples e' ora la single source of truth.
Per ricostruire l'indice Qdrant usare:

    python tools/indexing/build_intent_examples_index.py

Questo script esiste solo per backward-compatibility con chiamate esterne.
"""

import sys


def main():
    print("=" * 60)
    print("DEPRECATED: domande_risposte unificata in intent_examples")
    print("=" * 60)
    print()
    print("La tabella intent_examples e' ora la single source of truth.")
    print("Non serve piu' sincronizzare da domande_risposte.")
    print()
    print("Per ricostruire l'indice Qdrant:")
    print("  python tools/indexing/build_intent_examples_index.py")
    print()
    print("Per inserire nuovi esempi:")
    print("  INSERT INTO intent_examples (text, intent, example_type, source)")
    print("  VALUES ('domanda', 'intent', 'few_shot', 'fonte');")
    sys.exit(0)


if __name__ == "__main__":
    main()
