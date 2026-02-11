#!/usr/bin/env python3
"""
Debug endpoint per diagnosticare problemi GChat
Porta 5006 per non interferire con il server principale
"""

from flask import Flask, request, jsonify
import traceback
import logging
import sys
import os

# Configura logging dettagliato
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_gchat.log')
    ]
)

app = Flask(__name__)

@app.route('/debug_query', methods=['POST'])
def debug_query():
    """Endpoint di debug per simulare la query GChat"""
    try:
        data = request.json
        message = data.get('text', '')

        print(f"\n🔍 DEBUG START: '{message}'")
        print("=" * 60)

        # 1. Test classificazione intent
        print("1. CLASSIFICAZIONE INTENT...")
        from orchestrator.router import Router
        from llm.client import LLMClient

        llm = LLMClient()
        router = Router(llm)
        classification = router.classify(message)

        intent = classification.get('intent')
        slots = classification.get('slots', {})

        print(f"   Intent: {intent}")
        print(f"   Slots: {slots}")
        print(f"   Expected: ask_risk_based_priority")

        if intent != 'ask_risk_based_priority':
            print(f"   ⚠️ INTENT MISMATCH! Got {intent}")

        # 2. Test workflow completo
        print("\n2. WORKFLOW COMPLETO...")
        from orchestrator.graph import ConversationGraph

        graph = ConversationGraph(llm)

        state = {
            'message': message,
            'metadata': {'asl': 'NA1', 'uoc': 'SEPE', 'user_id': 'debug'},
            'intent': intent,
            'slots': slots,
            'tool_output': None,
            'final_response': '',
            'needs_clarification': False,
            'error': ''
        }

        print(f"   Initial state: {state}")

        # Esegui workflow
        result = graph.graph.invoke(state)

        # 3. Analizza risultati
        print("\n3. RISULTATI...")
        tool_output = result.get('tool_output', {})
        tool_type = tool_output.get('type', 'unknown')
        tool_data = tool_output.get('data', {})

        print(f"   Tool type: {tool_type}")
        print(f"   Tool data keys: {list(tool_data.keys())}")

        if 'error' in tool_data:
            error_msg = tool_data['error']
            print(f"   ❌ TOOL ERROR: {error_msg}")

            # Analizza il tipo di errore
            if 'piano' in error_msg.lower():
                print("   🚨 PIANO COLUMN ERROR DETECTED!")
            elif 'asl' in error_msg.lower():
                print("   ℹ️ ASL parameter error (expected)")
            elif 'uoc' in error_msg.lower():
                print("   ℹ️ UOC parameter error (expected)")
            else:
                print(f"   🤔 Other error type: {error_msg}")
        else:
            print("   ✅ Tool executed successfully")

        final_response = result.get('final_response', '')
        print(f"   Final response length: {len(final_response)}")

        # 4. Test specifici per tool
        print("\n4. TEST TOOL SPECIFICI...")

        # Test risk tool diretto
        print("   Testing risk_tool directly...")
        try:
            from tools.risk_tools import risk_tool
            risk_result = risk_tool(asl='NA1')
            if 'error' in risk_result and 'piano' in risk_result['error'].lower():
                print("   ❌ risk_tool has piano error")
            else:
                print("   ✅ risk_tool works")
        except Exception as e:
            print(f"   ❌ risk_tool exception: {e}")

        # Test priority tool diretto
        print("   Testing priority_tool directly...")
        try:
            from tools.priority_tools import priority_tool
            priority_result = priority_tool(asl='NA1', uoc='SEPE', action='priority')
            if 'error' in priority_result and 'piano' in priority_result['error'].lower():
                print("   ❌ priority_tool has piano error")
            else:
                print("   ✅ priority_tool works")
        except Exception as e:
            print(f"   ❌ priority_tool exception: {e}")

        print("\n" + "=" * 60)
        print("🔍 DEBUG END")

        return jsonify({
            'debug': True,
            'message_received': message,
            'intent_classified': intent,
            'intent_expected': 'ask_risk_based_priority',
            'intent_correct': intent == 'ask_risk_based_priority',
            'slots': slots,
            'tool_type': tool_type,
            'tool_data': tool_data,
            'has_error': 'error' in tool_data,
            'error_message': tool_data.get('error', None),
            'final_response': final_response,
            'workflow_result': result
        })

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()

        print(f"\n❌ DEBUG ENDPOINT ERROR: {error_msg}")
        print(f"Traceback:\n{tb}")

        return jsonify({
            'debug_error': True,
            'error': error_msg,
            'traceback': tb
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'debug_endpoint'})

@app.route('/test_tools', methods=['GET'])
def test_tools():
    """Test tutti i tool per verificare fix"""
    results = {}

    try:
        # Test risk_tool
        from tools.risk_tools import risk_tool
        risk_result = risk_tool(asl='NA1')
        results['risk_tool'] = {
            'success': 'piano' not in str(risk_result.get('error', '')).lower(),
            'result': risk_result
        }
    except Exception as e:
        results['risk_tool'] = {'success': False, 'error': str(e)}

    try:
        # Test priority_tool
        from tools.priority_tools import priority_tool
        priority_result = priority_tool(asl='NA1', uoc='SEPE', action='priority')
        results['priority_tool'] = {
            'success': 'piano' not in str(priority_result.get('error', '')).lower(),
            'result': priority_result
        }
    except Exception as e:
        results['priority_tool'] = {'success': False, 'error': str(e)}

    return jsonify(results)

if __name__ == '__main__':
    print("🚀 Starting GChat Debug Server on port 5006")
    print("Available endpoints:")
    print("  POST /debug_query - Debug specific query")
    print("  GET  /health      - Health check")
    print("  GET  /test_tools  - Test all tools")
    print("\nExample usage:")
    print("curl -X POST http://localhost:5006/debug_query -H 'Content-Type: application/json' -d '{\"text\": \"query here\"}'")

    app.run(host='0.0.0.0', port=5006, debug=True)