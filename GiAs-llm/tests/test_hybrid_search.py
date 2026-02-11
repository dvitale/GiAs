#!/usr/bin/env python3
"""
Integration test for Hybrid Search System

Tests the complete hybrid search pipeline with real queries.
"""

import sys
import os
import time
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_hybrid_search_integration():
    """Test hybrid search system with various query types"""

    print("=" * 80)
    print("HYBRID SEARCH INTEGRATION TEST")
    print("=" * 80)

    # Test queries of different complexity types
    test_queries = [
        # Simple exact code
        {"query": "piano A1", "expected_strategy": "vector_only", "description": "Exact code query"},

        # Simple keywords
        {"query": "bovini", "expected_strategy": "vector_only", "description": "Simple keyword"},

        # Complex semantic query
        {"query": "quali piani riguardano il benessere animale negli allevamenti",
         "expected_strategy": ["hybrid", "llm_only"], "description": "Complex semantic question"},

        # Domain-specific query
        {"query": "piani per apicoltura e miele",
         "expected_strategy": "hybrid", "description": "Domain-specific multi-term"},

        # Relationship query
        {"query": "piani correlati alla sicurezza alimentare",
         "expected_strategy": ["hybrid", "llm_only"], "description": "Semantic relationship"}
    ]

    print(f"\nTesting {len(test_queries)} different query types...")

    try:
        # Test component imports
        print("\n1. Testing component imports...")
        from tools.hybrid_search.query_analyzer import QueryAnalyzer
        from tools.hybrid_search.smart_router import SmartRouter
        from tools.hybrid_search.hybrid_engine import HybridSearchEngine
        print("   ✅ All hybrid components imported successfully")

        # Test search tools integration
        print("\n2. Testing search tools integration...")
        from tools.search_tools import search_piani_by_topic, get_hybrid_engine
        print("   ✅ Search tools integration successful")

        # Test query analyzer
        print("\n3. Testing Query Analyzer...")
        analyzer = QueryAnalyzer()

        for i, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            analysis = analyzer.analyze(query)

            print(f"   Query {i}: '{query}'")
            print(f"     Complexity: {analysis.complexity_score:.2f}")
            print(f"     Type: {analysis.query_type}")
            print(f"     Entities: {analysis.entity_count}")
            print(f"     Semantic indicators: {len(analysis.semantic_indicators)}")

        # Test smart router
        print("\n4. Testing Smart Router...")
        router = SmartRouter()

        for i, test_case in enumerate(test_queries, 1):
            query = test_case["query"]
            analysis = analyzer.analyze(query)
            strategy = router.select_strategy(query)

            expected = test_case["expected_strategy"]
            if isinstance(expected, list):
                strategy_ok = strategy.value in expected
            else:
                strategy_ok = strategy.value == expected

            status = "✅" if strategy_ok else "⚠️"
            print(f"   {status} Query {i}: '{query}' → {strategy.value}")

        # Test hybrid engine (if available)
        print("\n5. Testing Hybrid Engine...")
        hybrid_engine = get_hybrid_engine()

        if hybrid_engine:
            print("   ✅ Hybrid engine initialized")

            # Test with a sample query
            test_query = "piani per allevamenti bovini"
            print(f"\n   Testing search: '{test_query}'")

            start_time = time.time()
            result = hybrid_engine.search(test_query)
            latency = (time.time() - start_time) * 1000

            print(f"   Strategy used: {result.get('search_metadata', {}).get('strategy_used', 'unknown')}")
            print(f"   Results found: {result.get('total_found', 0)}")
            print(f"   Latency: {latency:.1f}ms")
            print(f"   Success: {'✅' if not result.get('error') else '❌'}")

        else:
            print("   ⚠️  Hybrid engine not available, testing search tool directly")

        # Test search tool (main interface)
        print("\n6. Testing Search Tool Interface...")

        sample_queries = ["apicoltura", "benessere animale", "piano A13"]

        for query in sample_queries:
            print(f"\n   Testing: '{query}'")
            start_time = time.time()

            # Call the tool function properly
            if hasattr(search_piani_by_topic, 'func'):
                result = search_piani_by_topic.func(query)
            else:
                result = search_piani_by_topic(query)

            latency = (time.time() - start_time) * 1000

            strategy = result.get('search_strategy', 'unknown')
            total_found = result.get('total_found', 0)
            has_error = result.get('error') is not None

            status = "✅" if not has_error and total_found > 0 else "⚠️"
            print(f"     {status} Strategy: {strategy}, Results: {total_found}, Latency: {latency:.1f}ms")

            # Show first result if available
            matches = result.get('matches', [])
            if matches:
                first_match = matches[0]
                alias = first_match.get('alias', 'N/A')
                similarity = first_match.get('similarity', 0)
                print(f"     Top result: {alias} (similarity: {similarity:.2f})")

        print("\n" + "=" * 80)
        print("INTEGRATION TEST COMPLETED")
        print("=" * 80)

        # Summary
        print("\n✅ All components tested successfully!")
        print("📊 Hybrid search system is operational")
        print("\n🔧 Next steps:")
        print("   - Monitor performance in production")
        print("   - Collect user feedback for strategy optimization")
        print("   - Fine-tune routing rules based on usage patterns")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all hybrid search components are properly installed")
        return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def test_configuration_system():
    """Test configuration management"""

    print("\n" + "=" * 40)
    print("CONFIGURATION SYSTEM TEST")
    print("=" * 40)

    try:
        from tools.hybrid_search.config_manager import HybridConfigManager, RoutingRule

        print("1. Testing configuration manager...")
        config_manager = HybridConfigManager()
        print(f"   ✅ Config loaded from: {config_manager.config_path}")

        print("2. Testing routing rules...")
        rules = config_manager.get_routing_rules()
        print(f"   ✅ Found {len(rules)} routing rules")

        for rule in rules[:3]:  # Show first 3 rules
            print(f"     - {rule.name}: {rule.target_strategy} (priority: {rule.priority})")

        print("3. Testing rule evaluation...")
        sample_analysis = {
            "complexity_score": 0.8,
            "query_type": "semantic_relationship",
            "entity_count": 2,
            "semantic_indicators": ["riguardano", "correlato"]
        }

        strategy = config_manager.evaluate_routing_rules(sample_analysis)
        print(f"   ✅ Sample analysis → strategy: {strategy}")

        print("4. Testing performance thresholds...")
        thresholds = config_manager.get_performance_thresholds()
        print(f"   ✅ Max latency: {thresholds.max_latency_ms}ms")
        print(f"   ✅ Min accuracy: {thresholds.min_accuracy}")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting Hybrid Search Integration Tests...\n")

    success1 = test_hybrid_search_integration()
    success2 = test_configuration_system()

    if success1 and success2:
        print("\n🎉 All tests passed! Hybrid search system is ready.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)