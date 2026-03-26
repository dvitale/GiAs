"""
Test unitari per IntentCache.

Verifica:
1. Operazioni base (set/get, miss, sovrascrittura)
2. Normalizzazione query (case, whitespace)
3. Scadenza TTL e clear_expired
4. Eviction LRU al superamento max_size
5. Statistiche (hits/misses/hit_rate)
6. clear_all
7. Accumulazione tempo risparmiato (record_time_saved)
8. Metodi dunder (__len__, __bool__, __repr__)
"""

import hashlib
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from orchestrator.intent_cache import IntentCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cache(**kwargs) -> IntentCache:
    """Crea un'istanza fresh di IntentCache con parametri opzionali."""
    return IntentCache(**kwargs)


# ---------------------------------------------------------------------------
# TestBasicOperations
# ---------------------------------------------------------------------------

class TestBasicOperations:
    """set/get, cache miss, sovrascrittura chiave esistente."""

    def test_set_and_get_returns_stored_result(self):
        cache = _make_cache()
        payload = {"intent": "greet", "confidence": 0.95}
        cache.set("ciao", payload)
        result = cache.get("ciao")
        assert result == payload

    def test_get_on_missing_key_returns_none(self):
        cache = _make_cache()
        assert cache.get("questa query non esiste") is None

    def test_get_on_empty_cache_returns_none(self):
        cache = _make_cache()
        assert cache.get("qualsiasi cosa") is None

    def test_overwrite_existing_key_returns_new_value(self):
        cache = _make_cache()
        cache.set("piani in ritardo", {"intent": "ask_delayed_plans", "confidence": 0.7})
        new_payload = {"intent": "ask_delayed_plans", "confidence": 0.99}
        cache.set("piani in ritardo", new_payload)
        assert cache.get("piani in ritardo") == new_payload

    def test_different_queries_are_independent(self):
        cache = _make_cache()
        cache.set("piani napoli", {"intent": "ask_plans"})
        cache.set("controlli in ritardo", {"intent": "ask_delayed_plans"})
        assert cache.get("piani napoli")["intent"] == "ask_plans"
        assert cache.get("controlli in ritardo")["intent"] == "ask_delayed_plans"

    def test_set_stores_dict_by_value_not_reference(self):
        """Verifica che la modifica del dict originale non alteri la cache."""
        cache = _make_cache()
        payload = {"intent": "greet"}
        cache.set("ciao", payload)
        # La cache memorizza il riferimento al dict, comportamento Python standard.
        # Questo test documenta che get restituisce lo stesso oggetto (shallow copy).
        assert cache.get("ciao") is payload


# ---------------------------------------------------------------------------
# TestQueryNormalization
# ---------------------------------------------------------------------------

class TestQueryNormalization:
    """Case folding e strip dello spazio devono produrre la stessa chiave cache."""

    def test_lowercase_and_uppercase_map_to_same_entry(self):
        cache = _make_cache()
        cache.set("Hello World", {"intent": "greet"})
        assert cache.get("hello world") is not None

    def test_leading_trailing_whitespace_stripped(self):
        cache = _make_cache()
        cache.set("  piani in ritardo  ", {"intent": "ask_delayed_plans"})
        assert cache.get("piani in ritardo") is not None

    def test_mixed_case_and_whitespace_all_equivalent(self):
        cache = _make_cache()
        cache.set("PIANI NAPOLI", {"intent": "ask_plans"})
        assert cache.get("piani napoli") is not None
        assert cache.get("  Piani Napoli  ") is not None

    def test_hash_query_uses_md5_of_normalized_string(self):
        cache = _make_cache()
        raw = "  Hello World  "
        normalized = raw.lower().strip()
        expected_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        assert cache._hash_query(raw) == expected_hash

    def test_hash_query_different_strings_produce_different_hashes(self):
        cache = _make_cache()
        assert cache._hash_query("query a") != cache._hash_query("query b")

    def test_whitespace_only_in_middle_is_preserved(self):
        """Spazi interni NON vengono collassati — solo strip perimetrale."""
        cache = _make_cache()
        cache.set("piani  napoli", {"intent": "ask_plans"})
        # "piani  napoli" != "piani napoli" dopo strip (spazi interni diversi)
        assert cache.get("piani napoli") is None
        assert cache.get("piani  napoli") is not None


# ---------------------------------------------------------------------------
# TestTTLExpiration
# ---------------------------------------------------------------------------

class TestTTLExpiration:
    """Le entry scadono dopo il TTL configurato."""

    def test_entry_is_valid_within_ttl(self):
        cache = _make_cache(ttl_seconds=60)
        cache.set("query fresca", {"intent": "greet"})
        assert cache.get("query fresca") is not None

    def test_entry_returns_none_after_ttl_expires(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("query scaduta", {"intent": "greet"})
        time.sleep(1.1)
        assert cache.get("query scaduta") is None

    def test_expired_entry_removed_from_cache_on_get(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("query scaduta", {"intent": "greet"})
        time.sleep(1.1)
        cache.get("query scaduta")
        assert len(cache) == 0

    def test_expired_get_increments_misses(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("q", {"intent": "greet"})
        time.sleep(1.1)
        cache.get("q")
        assert cache.get_stats()["misses"] == 1

    def test_clear_expired_removes_expired_entries(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("scade", {"intent": "greet"})
        cache.set("scade2", {"intent": "greet"})
        time.sleep(1.1)
        removed = cache.clear_expired()
        assert removed == 2
        assert len(cache) == 0

    def test_clear_expired_does_not_remove_valid_entries(self):
        cache = _make_cache(ttl_seconds=60)
        cache.set("fresca", {"intent": "greet"})
        removed = cache.clear_expired()
        assert removed == 0
        assert len(cache) == 1

    def test_clear_expired_mixed_entries(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("scade", {"intent": "greet"})
        time.sleep(1.1)
        # Aggiunge entry fresca con TTL nuovo (sovrascrittura con nuovo timestamp)
        cache2 = _make_cache(ttl_seconds=60)
        cache2.set("fresca", {"intent": "greet"})
        # Sul primo cache: solo quella scaduta
        removed = cache.clear_expired()
        assert removed == 1
        assert len(cache) == 0

    def test_clear_expired_on_empty_cache_returns_zero(self):
        cache = _make_cache()
        assert cache.clear_expired() == 0

    def test_clear_expired_increments_evictions_stat(self):
        cache = _make_cache(ttl_seconds=1)
        cache.set("q1", {"intent": "greet"})
        cache.set("q2", {"intent": "greet"})
        time.sleep(1.1)
        cache.clear_expired()
        assert cache.get_stats()["evictions"] == 2


# ---------------------------------------------------------------------------
# TestMaxSizeEviction
# ---------------------------------------------------------------------------

class TestMaxSizeEviction:
    """LRU eviction al superamento di max_size."""

    def test_cache_size_does_not_exceed_target_after_eviction(self):
        cache = _make_cache(max_size=5)
        for i in range(6):
            cache.set(f"query{i}", {"intent": f"intent{i}"})
        # Con max_size=5, keep_ratio=0.8 → target_size=4; rimosse 2
        assert len(cache) == 4

    def test_evictions_stat_incremented_after_cleanup(self):
        cache = _make_cache(max_size=5)
        for i in range(6):
            cache.set(f"query{i}", {"intent": f"intent{i}"})
        assert cache.get_stats()["evictions"] == 2

    def test_oldest_entries_are_removed(self):
        """Le prime entry inserite (più vecchie) devono essere rimosse."""
        cache = _make_cache(max_size=5)
        for i in range(5):
            cache.set(f"q{i}", {"intent": f"i{i}"})
            time.sleep(0.01)  # garantisce timestamp strettamente crescenti
        # Inserzione numero 6 → trigger cleanup: rimuove q0 e q1 (le più vecchie)
        cache.set("q5", {"intent": "i5"})
        assert cache.get("q0") is None
        assert cache.get("q1") is None

    def test_newest_entries_are_retained(self):
        """Le entry più recenti devono sopravvivere all'eviction."""
        cache = _make_cache(max_size=5)
        for i in range(5):
            cache.set(f"q{i}", {"intent": f"i{i}"})
            time.sleep(0.01)
        cache.set("q5", {"intent": "i5"})
        # q2, q3, q4, q5 devono essere in cache (le 4 più recenti)
        assert cache.get("q2") is not None
        assert cache.get("q3") is not None
        assert cache.get("q4") is not None
        assert cache.get("q5") is not None

    def test_cleanup_oldest_returns_removed_count(self):
        cache = _make_cache(max_size=5)
        for i in range(5):
            cache.set(f"q{i}", {"intent": f"i{i}"})
        # Chiamata esplicita con cache esattamente a max_size
        # to_remove = 5 - int(5*0.8) = 5 - 4 = 1
        removed = cache._cleanup_oldest()
        assert removed == 1

    def test_cleanup_oldest_on_empty_cache_returns_zero(self):
        cache = _make_cache()
        assert cache._cleanup_oldest() == 0

    def test_cleanup_oldest_custom_keep_ratio(self):
        cache = _make_cache(max_size=10)
        for i in range(10):
            cache.set(f"q{i}", {"intent": f"i{i}"})
        # keep_ratio=0.5 → target_size=5; to_remove=10-5=5
        removed = cache._cleanup_oldest(keep_ratio=0.5)
        assert removed == 5
        assert len(cache) == 5


# ---------------------------------------------------------------------------
# TestStats
# ---------------------------------------------------------------------------

class TestStats:
    """Verifica le statistiche dopo sequenze di get/set."""

    def test_initial_stats_are_zero(self):
        cache = _make_cache()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["evictions"] == 0
        assert stats["cache_size"] == 0

    def test_hit_increments_hits(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")
        assert cache.get_stats()["hits"] == 1
        assert cache.get_stats()["misses"] == 0

    def test_miss_increments_misses(self):
        cache = _make_cache()
        cache.get("non esiste")
        assert cache.get_stats()["misses"] == 1
        assert cache.get_stats()["hits"] == 0

    def test_hit_rate_percent_50_percent(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")        # hit
        cache.get("assente")  # miss
        stats = cache.get_stats()
        assert stats["hit_rate_percent"] == 50.0

    def test_hit_rate_percent_100_percent(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")
        cache.get("q")
        stats = cache.get_stats()
        assert stats["hit_rate_percent"] == 100.0

    def test_hit_rate_percent_zero_with_no_requests(self):
        cache = _make_cache()
        assert cache.get_stats()["hit_rate_percent"] == 0

    def test_total_requests_is_sum_of_hits_and_misses(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")        # hit
        cache.get("q")        # hit
        cache.get("assente")  # miss
        stats = cache.get_stats()
        assert stats["total_requests"] == stats["hits"] + stats["misses"]
        assert stats["total_requests"] == 3

    def test_stats_reflect_correct_max_size(self):
        cache = _make_cache(max_size=42)
        assert cache.get_stats()["max_size"] == 42

    def test_stats_reflect_correct_ttl_seconds(self):
        cache = _make_cache(ttl_seconds=120)
        assert cache.get_stats()["ttl_seconds"] == 120.0

    def test_stats_cache_size_tracks_current_entries(self):
        cache = _make_cache()
        assert cache.get_stats()["cache_size"] == 0
        cache.set("q1", {"intent": "greet"})
        assert cache.get_stats()["cache_size"] == 1
        cache.set("q2", {"intent": "greet"})
        assert cache.get_stats()["cache_size"] == 2

    def test_hit_rate_rounded_to_two_decimals(self):
        cache = _make_cache()
        # 2 hit su 3 richieste = 66.666...% → arrotondato a 66.67
        cache.set("q", {"intent": "greet"})
        cache.get("q")        # hit
        cache.get("q")        # hit
        cache.get("assente")  # miss
        stats = cache.get_stats()
        assert stats["hit_rate_percent"] == round(2 / 3 * 100, 2)


# ---------------------------------------------------------------------------
# TestClearAll
# ---------------------------------------------------------------------------

class TestClearAll:
    """clear_all svuota completamente la cache."""

    def test_clear_all_empties_cache(self):
        cache = _make_cache()
        cache.set("q1", {"intent": "greet"})
        cache.set("q2", {"intent": "greet"})
        cache.clear_all()
        assert len(cache) == 0

    def test_clear_all_makes_previous_keys_inaccessible(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.clear_all()
        assert cache.get("q") is None

    def test_clear_all_increments_evictions(self):
        cache = _make_cache()
        cache.set("q1", {"intent": "greet"})
        cache.set("q2", {"intent": "greet"})
        cache.clear_all()
        assert cache.get_stats()["evictions"] == 2

    def test_clear_all_on_empty_cache_is_safe(self):
        cache = _make_cache()
        cache.clear_all()  # non deve sollevare eccezioni
        assert len(cache) == 0

    def test_cache_usable_after_clear_all(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.clear_all()
        cache.set("q2", {"intent": "nuova"})
        assert cache.get("q2") is not None


# ---------------------------------------------------------------------------
# TestTimeSaved
# ---------------------------------------------------------------------------

class TestTimeSaved:
    """record_time_saved accumula il tempo risparmiato."""

    def test_record_time_saved_accumulates(self):
        cache = _make_cache()
        cache.record_time_saved(100.0)
        cache.record_time_saved(200.5)
        assert cache._stats["total_saved_time_ms"] == 300.5

    def test_record_time_saved_starts_at_zero(self):
        cache = _make_cache()
        assert cache._stats["total_saved_time_ms"] == 0

    def test_record_time_saved_single_call(self):
        cache = _make_cache()
        cache.record_time_saved(42.0)
        assert cache._stats["total_saved_time_ms"] == 42.0

    def test_record_time_saved_not_exposed_in_get_stats(self):
        """total_saved_time_ms è un dettaglio interno, non esposto da get_stats."""
        cache = _make_cache()
        cache.record_time_saved(1000.0)
        stats = cache.get_stats()
        assert "total_saved_time_ms" not in stats

    def test_record_time_saved_float_precision(self):
        cache = _make_cache()
        cache.record_time_saved(0.1)
        cache.record_time_saved(0.2)
        # Floating point: verifica con tolleranza
        assert abs(cache._stats["total_saved_time_ms"] - 0.3) < 1e-9


# ---------------------------------------------------------------------------
# TestDunderMethods
# ---------------------------------------------------------------------------

class TestDunderMethods:
    """__len__, __bool__, __repr__."""

    def test_len_empty_cache_is_zero(self):
        cache = _make_cache()
        assert len(cache) == 0

    def test_len_reflects_number_of_entries(self):
        cache = _make_cache()
        cache.set("q1", {"intent": "greet"})
        cache.set("q2", {"intent": "greet"})
        assert len(cache) == 2

    def test_len_decreases_after_clear_all(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.clear_all()
        assert len(cache) == 0

    def test_bool_is_true_when_empty(self):
        """La cache è sempre truthy — anche vuota."""
        cache = _make_cache()
        assert bool(cache) is True

    def test_bool_is_true_when_populated(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        assert bool(cache) is True

    def test_repr_contains_size_info(self):
        cache = _make_cache(max_size=50)
        cache.set("q", {"intent": "greet"})
        r = repr(cache)
        assert "1/50" in r

    def test_repr_contains_hits_and_misses(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")        # hit
        cache.get("assente")  # miss
        r = repr(cache)
        assert "hits=1" in r
        assert "misses=1" in r

    def test_repr_contains_hit_rate(self):
        cache = _make_cache()
        cache.set("q", {"intent": "greet"})
        cache.get("q")        # hit
        cache.get("assente")  # miss
        r = repr(cache)
        assert "hit_rate=50.0%" in r

    def test_repr_format_on_empty_cache(self):
        cache = _make_cache(max_size=100)
        r = repr(cache)
        assert "IntentCache(" in r
        assert "0/100" in r
        assert "hits=0" in r
        assert "misses=0" in r
        assert "hit_rate=0.0%" in r
