#!/usr/bin/env python3
"""
Test rapido per workflow conversazionali multi-turno.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.graph import ConversationGraph

def test_delayed_plans():
    """Test intent ask_delayed_plans con metadata completi."""
    print("=" * 80)
    print("TEST: Piani in ritardo")
    print("=" * 80)

    graph = ConversationGraph()

    # Metadata completi con ASL e UOC
    metadata = {
        "asl": "NA1",
        "uoc": "SIAV NA1 NORD",  # Esempio UOC - sostituisci con UOC reale dal tuo DB
        "user_id": "test_user_123"
    }

    result = graph.run(
        message="quali sono i miei piani in ritardo",
        metadata=metadata
    )

    print(f"\n📊 Intent rilevato: {result.get('intent')}")
    print(f"🔧 Slots estratti: {result.get('slots')}")
    print(f"❓ Needs clarification: {result.get('needs_clarification')}")

    if result.get('error'):
        print(f"\n❌ Errore: {result.get('error')}")
    else:
        print(f"\n✅ Risposta:\n{result.get('response')}")

    return result

def test_workflow_suggest_controls():
    """Test workflow conversazionale con strategie multiple."""
    print("\n" + "=" * 80)
    print("TEST: Workflow 'suggerisci controlli' (multi-turno)")
    print("=" * 80)

    graph = ConversationGraph()

    metadata = {
        "asl": "NA1",
        "uoc": "SIAV NA1 NORD",
        "user_id": "test_user_123"
    }

    # Turno 1: Richiesta ambigua → dovrebbe presentare strategie
    print("\n🔵 TURNO 1: Richiesta ambigua")
    result1 = graph.run(
        message="vorrei avere indicazioni su quali controlli eseguire",
        metadata=metadata
    )

    print(f"Intent: {result1.get('intent')}")
    print(f"Workflow attivo: {result1.get('workflow_id')}")
    print(f"Pending question: {result1.get('pending_question', {}).get('type')}")
    print(f"\nRisposta:\n{result1.get('response')[:500]}...")  # Prime 500 char

    if result1.get('workflow_id'):
        # Turno 2: Scelta strategia
        print("\n🔵 TURNO 2: Scelta strategia")

        # Simula passaggio workflow_context
        workflow_context = {
            "workflow_id": result1.get("workflow_id"),
            "workflow_nonce": result1.get("workflow_nonce"),
            "workflow_type": result1.get("workflow_type"),
            "workflow_stage": result1.get("workflow_stage"),
            "pending_question": result1.get("pending_question"),
            "available_options": result1.get("available_options"),
            "workflow_history": result1.get("workflow_history", []),
            "accumulated_filters": result1.get("accumulated_filters", {}),
        }

        result2 = graph.run(
            message="1",  # Scelta prima opzione
            metadata=metadata,
            workflow_context=workflow_context
        )

        print(f"Intent: {result2.get('intent')}")
        print(f"Workflow stage: {result2.get('workflow_stage')}")
        print(f"\nRisposta:\n{result2.get('response')[:500]}...")

    return result1

def test_workflow_oppure():
    """Test richiesta 'oppure?' per alternative."""
    print("\n" + "=" * 80)
    print("TEST: Richiesta 'oppure?' per alternative")
    print("=" * 80)

    graph = ConversationGraph()

    metadata = {
        "asl": "NA1",
        "user_id": "test_user_123"
    }

    # Setup workflow context simulato (dopo presentazione strategie)
    from orchestrator.workflow_strategies import WORKFLOW_STRATEGIES
    from orchestrator.workflow_validator import WorkflowValidator
    import time

    strategies = WORKFLOW_STRATEGIES["ask_suggest_controls"]["strategies"]

    workflow_context = {
        "workflow_id": f"ask_suggest_controls_{int(time.time())}",
        "workflow_nonce": WorkflowValidator.create_workflow_nonce(),
        "workflow_type": "ask_suggest_controls",
        "workflow_stage": "choosing",
        "pending_question": {
            "type": "strategy_choice",
            "question": "test",
            "workflow_nonce": "test_nonce"
        },
        "available_options": [{"id": s["id"], "label": s["label"]} for s in strategies],
        "workflow_history": [],
        "accumulated_filters": {},
        "current_strategy_index": 0,
        "available_strategies": strategies
    }

    # Fix nonce in pending_question
    workflow_context["pending_question"]["workflow_nonce"] = workflow_context["workflow_nonce"]

    result = graph.run(
        message="oppure?",
        metadata=metadata,
        workflow_context=workflow_context
    )

    print(f"Intent rilevato: {result.get('intent')}")
    print(f"Prossima strategia mostrata: {result.get('workflow_context', {}).get('current_strategy_index')}")
    print(f"\nRisposta:\n{result.get('response')}")

    return result

if __name__ == "__main__":
    print("\n🧪 Test Suite Workflow Conversazionali Multi-Turno\n")

    # Test 1: Intent semplice con metadata
    test_delayed_plans()

    # Test 2: Workflow multi-turno
    # test_workflow_suggest_controls()

    # Test 3: Richiesta "oppure?"
    # test_workflow_oppure()

    print("\n" + "=" * 80)
    print("✅ Test completati!")
    print("=" * 80)
