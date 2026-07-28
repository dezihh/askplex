# -*- coding: utf-8 -*-
"""
Unit tests for Unicode Normalizer
Run with: python -m pytest test_unicode_normalizer.py -v
"""

import pytest
from unicode_normalizer import UnicodeNormalizer, SearchStrategy, get_normalizer


class TestUnicodeNormalizer:
    """Test Unicode normalization functionality."""

    @pytest.fixture
    def normalizer(self):
        return UnicodeNormalizer()

    def test_get_search_variants_basic(self, normalizer):
        """Test basic search variant generation."""
        variants = normalizer.get_search_variants("test")
        assert "test" in variants
        assert len(variants) > 0

    def test_german_umlaute_original(self, normalizer):
        """Test that original query with Umlaute is first variant."""
        variants = normalizer.get_search_variants("Die Ärzte")
        assert variants[0] == "Die Ärzte"

    def test_case_variations(self, normalizer):
        """Test case normalization produces multiple variants."""
        variants = normalizer.get_search_variants("die ärzte")
        # Should have case variations
        assert "die ärzte" in variants  # original
        assert "Die Ärzte" in variants  # title case
        assert "DIE ÄRZTE" in variants  # uppercase

    def test_umlaut_removal(self, normalizer):
        """Test Umlaut to ASCII conversion."""
        result = normalizer._remove_umlauts("Die Ärzte")
        assert result == "Die Aerzte"

        result = normalizer._remove_umlauts("Björk")
        assert result == "Bjork"

        result = normalizer._remove_umlauts("Schöne Musik")
        assert result == "Schone Musik"

    def test_umlaut_variants_in_search(self, normalizer):
        """Test that Umlaut variants are in search variants."""
        variants = normalizer.get_search_variants("Die Ärzte")
        # Should include non-umlaut version
        assert any("Aerzte" in v for v in variants)

    def test_diacritic_removal(self, normalizer):
        """Test diacritic removal using Unicode normalization."""
        result = normalizer._remove_diacritics("Björk")
        assert result == "Bjork"

        result = normalizer._remove_diacritics("Crème Brûlée")
        assert result == "Creme Brulee"

        result = normalizer._remove_diacritics("José")
        assert result == "Jose"

    def test_normalize_for_storage(self, normalizer):
        """Test storage normalization."""
        result = normalizer.normalize_for_storage("Die  Ärzte")  # Double space
        assert result == "die ärzte"  # lowercase, normalized whitespace

        result = normalizer.normalize_for_storage("BJÖRK")
        assert result == "björk"

    def test_get_best_match_exact(self, normalizer):
        """Test best match with exact hit."""
        candidates = ["Die Ärzte", "Rammstein", "Björk"]
        match, score = normalizer.get_best_match("Die Ärzte", candidates)

        assert match == "Die Ärzte"
        assert score == 0  # Exact match

    def test_get_best_match_case_insensitive(self, normalizer):
        """Test best match with case-insensitive hit."""
        candidates = ["Die Ärzte", "Rammstein"]
        match, score = normalizer.get_best_match("die ärzte", candidates)

        assert match == "Die Ärzte"
        assert score == 1  # Case-insensitive match

    def test_get_best_match_umlaut_variant(self, normalizer):
        """Test best match with Umlaut variant."""
        candidates = ["Die Ärzte", "Rammstein"]
        match, score = normalizer.get_best_match("Die Aerzte", candidates)

        assert match == "Die Ärzte"
        assert score == 2  # Umlaut variant match

    def test_get_best_match_no_match(self, normalizer):
        """Test best match with no candidates found."""
        candidates = ["Metallica", "Guns N Roses"]
        match, score = normalizer.get_best_match("Die Ärzte", candidates)

        assert match is None
        assert score == -1

    def test_empty_query(self, normalizer):
        """Test handling of empty queries."""
        variants = normalizer.get_search_variants("")
        assert "" in variants

        variants = normalizer.get_search_variants(None)
        assert None in variants

    def test_singleton_normalizer(self):
        """Test that get_normalizer returns same instance."""
        norm1 = get_normalizer()
        norm2 = get_normalizer()
        assert norm1 is norm2


class TestSearchStrategy:
    """Test search strategy with fallback logic."""

    @pytest.fixture
    def strategy(self):
        return SearchStrategy()

    def test_search_with_fallback_success_on_first(self, strategy):
        """Test successful search on first variant."""
        call_count = 0
        results = ["Result1", "Result2"]

        def mock_search(title, maxresults=100):
            nonlocal call_count
            call_count += 1
            return results if title == "Test" else []

        result = strategy.search_with_fallback(mock_search, "Test")
        assert result == results
        assert call_count == 1  # Should succeed on first try

    def test_search_with_fallback_success_on_second(self, strategy):
        """Test successful search on second variant (case fallback)."""
        call_attempts = []
        results = ["Result1"]

        def mock_search(title, maxresults=100):
            call_attempts.append(title)
            # Succeed on title-case variant
            return results if title == "Die Ärzte" else []

        result = strategy.search_with_fallback(mock_search, "die ärzte")
        assert result == results
        assert len(call_attempts) > 1  # Should try multiple variants
        assert "Die Ärzte" in call_attempts

    def test_search_with_fallback_exception_handling(self, strategy):
        """Test that search exceptions don't crash, continue fallback."""
        call_attempts = []
        results = ["Result1"]

        def mock_search(title, maxresults=100):
            call_attempts.append(title)
            if "test" in title.lower():
                return results
            raise Exception("Search failed")

        result = strategy.search_with_fallback(mock_search, "test")
        assert result == results  # Should eventually succeed

    def test_search_with_fallback_no_results(self, strategy):
        """Test search with no matching results."""
        def mock_search(title, maxresults=100):
            return []

        result = strategy.search_with_fallback(mock_search, "NonExistentArtist")
        assert result == []


class TestGermanUmlauteIntegration:
    """Integration tests with real German music scenarios."""

    @pytest.fixture
    def normalizer(self):
        return UnicodeNormalizer()

    def test_die_aerzte_scenario(self, normalizer):
        """Test the classic "Die Ärzte" scenario."""
        # Simulate Plex database with "Die Ärzte"
        plex_database = ["Die Ärzte", "Rammstein", "Björk"]

        # User says "die ärzte" (lowercase)
        user_query = "die ärzte"
        variants = normalizer.get_search_variants(user_query)

        # Try each variant against database
        for variant in variants:
            match, score = normalizer.get_best_match(variant, plex_database)
            if match:
                assert match == "Die Ärzte"
                break
        else:
            pytest.fail("No match found for Die Ärzte")

    def test_bjork_scenario(self, normalizer):
        """Test Björk with various spellings."""
        plex_database = ["Björk", "Deftones", "Thom Yorke"]

        # Try different ways user might say it
        user_queries = ["björk", "Björk", "BJÖRK", "Bjork"]

        for user_query in user_queries:
            variants = normalizer.get_search_variants(user_query)
            found = False

            for variant in variants:
                match, score = normalizer.get_best_match(variant, plex_database)
                if match == "Björk":
                    found = True
                    break

            assert found, f"Failed to find Björk for query: {user_query}"

    def test_umlaute_in_response(self, normalizer):
        """Test that Umlaute are preserved in responses."""
        artist_name = "Die Ärzte"
        response = f"Wiedergabe von Musik von {artist_name} in AskPlex."

        assert "Ärzte" in response
        assert response == "Wiedergabe von Musik von Die Ärzte in AskPlex."


if __name__ == "__main__":
    # Run with: python test_unicode_normalizer.py
    pytest.main([__file__, "-v"])
