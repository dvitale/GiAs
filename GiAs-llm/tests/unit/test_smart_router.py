"""
Test per SmartRouter: verifica comportamento cpu_mode con backend LLM cloud/locale.
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.hybrid_search.smart_router import SmartRouter, SearchStrategy, RoutingConfig


class TestSmartRouterCpuMode:
    """Test cpu_mode + cloud/local LLM decoupling."""

    def _make_router(self, cpu_mode: bool, llm_cloud: bool) -> SmartRouter:
        """Crea router con cpu_mode e llm_cloud preimpostati."""
        router = SmartRouter()
        router._cpu_mode = cpu_mode
        router._llm_cloud = llm_cloud
        return router

    def test_cpu_mode_true_llm_cloud_does_not_force_vector_only(self):
        """cpu_mode=True + LLM cloud -> routing rules normali (NON forza vector_only)."""
        router = self._make_router(cpu_mode=True, llm_cloud=True)
        # Query complessa che normalmente va in hybrid
        strategy = router.select_strategy("quali piani riguardano il benessere animale e la sicurezza alimentare?")
        assert strategy != SearchStrategy.VECTOR_ONLY or strategy == SearchStrategy.VECTOR_ONLY
        # Il punto e' che NON viene forzato vector_only dal blocco cpu_mode
        # Verifichiamo che il codice passi alle routing rules
        # Una query complessa con termini di dominio dovrebbe andare in HYBRID
        assert strategy in (SearchStrategy.HYBRID, SearchStrategy.LLM_ONLY)

    def test_cpu_mode_true_llm_local_forces_vector_only(self):
        """cpu_mode=True + LLM locale -> forza vector_only."""
        router = self._make_router(cpu_mode=True, llm_cloud=False)
        strategy = router.select_strategy("quali piani riguardano il benessere animale?")
        assert strategy == SearchStrategy.VECTOR_ONLY

    def test_cpu_mode_false_routing_rules_normal(self):
        """cpu_mode=False -> routing rules normali in ogni caso."""
        for llm_cloud in (True, False):
            router = self._make_router(cpu_mode=False, llm_cloud=llm_cloud)
            strategy = router.select_strategy("quali piani riguardano il benessere animale e la sicurezza alimentare?")
            # Query complessa: non deve essere forzata a vector_only
            assert strategy in (SearchStrategy.HYBRID, SearchStrategy.LLM_ONLY)

    def test_empty_query_always_vector_only(self):
        """Query vuota -> vector_only indipendentemente da cpu_mode/cloud."""
        for cpu, cloud in [(True, True), (True, False), (False, False)]:
            router = self._make_router(cpu_mode=cpu, llm_cloud=cloud)
            assert router.select_strategy("") == SearchStrategy.VECTOR_ONLY
            assert router.select_strategy("   ") == SearchStrategy.VECTOR_ONLY


class TestIsLlmCloudBased:
    """Test per _is_llm_cloud_based()."""

    def test_cached_value_returned(self):
        """Dopo la prima chiamata, il valore e' cached."""
        router = SmartRouter()
        router._llm_cloud = True
        assert router._is_llm_cloud_based() is True

    def test_fallback_on_import_error(self):
        """Se LLMBackendConfig non importabile, ritorna False."""
        router = SmartRouter()
        router._llm_cloud = None
        with patch.dict("sys.modules", {"configs.config": None, "configs": None}):
            result = router._is_llm_cloud_based()
            assert result is False
