# -*- coding: utf-8 -*-
"""
Unicode Normalizer for AskPlex
Provides robust search fallback strategies for German Umlaute and Unicode handling.

Features:
- Case normalization (preserves original search, falls back to .title() and .lower())
- Umlaut variant fallback (ä↔a, ö↔o, ü↔u, ß↔ss)
- Whitespace normalization
- Diacritic removal as last resort

Usage:
    from unicode_normalizer import UnicodeNormalizer

    normalizer = UnicodeNormalizer()
    search_variants = normalizer.get_search_variants("die ärzte")
    # Returns: ["die ärzte", "Die Ärzte", "DIE ÄRZTE", "die aerzte", ...]
"""

import unicodedata
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class UnicodeNormalizer:
    """Handles Unicode and Umlaut normalization with fallback strategies."""

    # Umlaut and special character mappings
    UMLAUT_VARIANTS = {
        'ä': 'a',
        'ö': 'o',
        'ü': 'u',
        'ß': 'ss',
        'Ä': 'A',
        'Ö': 'O',
        'Ü': 'U',
    }

    # Reverse mapping for fallback
    UMLAUT_REVERSE = {
        'a': 'ä',
        'o': 'ö',
        'u': 'ü',
        'ss': 'ß',
        'A': 'Ä',
        'O': 'Ö',
        'U': 'Ü',
    }

    # Common Plex naming patterns
    PRIORITY_CASES = [
        lambda x: x,  # Original (no change)
        lambda x: x.title(),  # Title Case: "die ärzte" → "Die Ärzte"
        lambda x: x.lower(),  # Lowercase: "DIE ÄRZTE" → "die ärzte"
        lambda x: x.upper(),  # UPPERCASE: "die ärzte" → "DIE ÄRZTE"
    ]

    def __init__(self, enable_diacritic_removal: bool = True):
        """
        Initialize normalizer.

        Args:
            enable_diacritic_removal: If True, last resort fallback removes all diacritics
        """
        self.enable_diacritic_removal = enable_diacritic_removal

    def get_search_variants(self, query: str) -> List[str]:
        """
        Generate multiple search variants for robust fallback.

        Returns list ordered by priority:
        1. Original query
        2. Case variations (title, lower, upper)
        3. Umlaut variants (ä→a, ö→o, etc.)
        4. Diacritic removal (if enabled)

        Args:
            query: Original search query

        Returns:
            List of search variants ordered by confidence
        """
        if not query or not isinstance(query, str):
            return [query] if query else [""]

        variants = []
        seen = set()  # Prevent duplicates

        # Step 1: Case variations (highest priority)
        for case_func in self.PRIORITY_CASES:
            variant = case_func(query)
            if variant not in seen:
                variants.append(variant)
                seen.add(variant)

        # Step 2: Umlaut variants (medium priority)
        for case_func in self.PRIORITY_CASES:
            umlaut_variant = self._remove_umlauts(case_func(query))
            if umlaut_variant not in seen and umlaut_variant != case_func(query):
                variants.append(umlaut_variant)
                seen.add(umlaut_variant)

        # Step 3: Diacritic removal (last resort)
        if self.enable_diacritic_removal:
            diacritic_variant = self._remove_diacritics(query)
            if diacritic_variant not in seen and diacritic_variant != query:
                variants.append(diacritic_variant)
                seen.add(diacritic_variant)

        logger.debug(f"Search variants for '{query}': {variants}")
        return variants

    def _remove_umlauts(self, text: str) -> str:
        """
        Replace German Umlaute with base characters.

        Examples:
            "Die Ärzte" → "Die Aerzte"
            "Björk" → "Bjork"
            "Schöne Musik" → "Schone Musik"
        """
        result = text
        for umlaut, replacement in self.UMLAUT_VARIANTS.items():
            result = result.replace(umlaut, replacement)
        return result

    def _remove_diacritics(self, text: str) -> str:
        """
        Remove all diacritics/accents using Unicode normalization.

        Examples:
            "Björk" → "Bjork"
            "Crème Brûlée" → "Creme Brulee"
            "José" → "Jose"
        """
        # Normalize to NFD (decomposed form)
        nfd = unicodedata.normalize('NFD', text)
        # Filter out combining characters (diacritics)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    def normalize_for_storage(self, text: str) -> str:
        """
        Normalize text for consistent storage/comparison.

        Used when building internal playlist names or identifiers.
        Returns lowercase, whitespace-normalized version.
        """
        if not text:
            return text

        # Normalize whitespace
        normalized = ' '.join(text.split())
        # Convert to lowercase for comparison
        return normalized.lower()

    def get_best_match(self, query: str, candidates: List[str]) -> tuple:
        """
        Find best matching candidate from list.

        Uses priority: exact match > case match > partial match > variant match

        Args:
            query: Search query
            candidates: List of candidate strings to match against

        Returns:
            Tuple of (matched_string, match_score)
            match_score: 0=exact, 1=case-insensitive, 2=umlaut-variant, 3=partial
        """
        if not candidates:
            return None, -1

        candidates_lower = {c: c.lower() for c in candidates}
        query_lower = query.lower()

        # Priority 0: Exact match
        for candidate in candidates:
            if candidate == query:
                return candidate, 0

        # Priority 1: Case-insensitive match
        for candidate, lower in candidates_lower.items():
            if lower == query_lower:
                return candidate, 1

        # Priority 2: Umlaut-variant match
        query_no_umlaut = self._remove_umlauts(query_lower)
        for candidate, lower in candidates_lower.items():
            if self._remove_umlauts(lower) == query_no_umlaut:
                return candidate, 2

        # Priority 3: Diacritic match
        query_no_diacritics = self._remove_diacritics(query_lower)
        for candidate, lower in candidates_lower.items():
            if self._remove_diacritics(lower) == query_no_diacritics:
                return candidate, 3

        # No match found
        return None, -1


class SearchStrategy:
    """Encapsulates search fallback logic for integration into controller."""

    def __init__(self):
        self.normalizer = UnicodeNormalizer()

    def search_with_fallback(self, search_func, query: str, max_results: int = 100):
        """
        Execute search with intelligent fallback.

        Tries multiple variants of the query until results are found.

        Args:
            search_func: Callable that performs the actual search
                        Should accept (title=query_variant) and return results
            query: Original search query
            max_results: Max results to return

        Returns:
            Search results or empty list if no matches found

        Example:
            strategy = SearchStrategy()
            results = strategy.search_with_fallback(
                search_func=section.searchArtists,
                query="die ärzte"
            )
        """
        variants = self.normalizer.get_search_variants(query)

        for variant in variants:
            try:
                results = search_func(title=variant, maxresults=max_results)
                if results and len(results) > 0:
                    logger.info(f"Search succeeded with variant: '{variant}'")
                    return results
                logger.debug(f"No results for variant: '{variant}'")
            except Exception as e:
                logger.warning(f"Search error with variant '{variant}': {e}")
                continue

        logger.warning(f"No results found for query '{query}' after trying {len(variants)} variants")
        return []


# Singleton instance for convenience
_normalizer_instance = None

def get_normalizer() -> UnicodeNormalizer:
    """Get or create singleton normalizer instance."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = UnicodeNormalizer()
    return _normalizer_instance


def get_search_strategy() -> SearchStrategy:
    """Get new search strategy instance."""
    return SearchStrategy()
