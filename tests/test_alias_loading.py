# -*- coding: utf-8 -*-
"""
Tests für den zentralen Alias-Loader (search_aliases.py).
"""

import json

import pytest

from askplex import search_aliases


@pytest.fixture(autouse=True)
def reset_alias_cache():
    """Stellt sicher, dass jeder Test mit frischem Alias-Zustand startet."""
    search_aliases.reset_aliases()
    yield
    search_aliases.reset_aliases()


def _write_aliases(tmp_path, data):
    alias_file = tmp_path / "search_aliases.json"
    alias_file.write_text(json.dumps(data), encoding="utf-8")
    return str(alias_file)


class TestAliasLoading:
    def test_loads_initial_aliases(self):
        """Die versionierte Aliasdatei ist gültig und enthält die erwarteten Aliase."""
        aliases = search_aliases.load_aliases()
        assert aliases["artists"]["acdc"] == "AC/DC"
        assert aliases["artists"]["ac dc"] == "AC/DC"
        assert aliases["artists"]["a c d c"] == "AC/DC"
        assert aliases["artists"]["pink"] == "P!nk"
        assert aliases["artists"]["guns and roses"] == "Guns N' Roses"
        assert aliases["songs"] == {}
        assert aliases["albums"] == {}
        assert aliases["playlists"] == {}

    def test_missing_file_yields_empty_aliases(self, tmp_path):
        """Fehlende Datei -> leere Aliasbereiche, kein Absturz."""
        aliases = search_aliases.load_aliases(str(tmp_path / "nope.json"))
        assert aliases == {"artists": {}, "songs": {}, "albums": {}, "playlists": {}}

    def test_invalid_json_yields_empty_aliases(self, tmp_path):
        """Ungültiges JSON -> leere Aliasbereiche, kein Absturz."""
        alias_file = tmp_path / "search_aliases.json"
        alias_file.write_text("{ kaputt", encoding="utf-8")
        aliases = search_aliases.load_aliases(str(alias_file))
        assert aliases == {"artists": {}, "songs": {}, "albums": {}, "playlists": {}}

    def test_non_dict_root_yields_empty_aliases(self, tmp_path):
        """JSON ohne Objekt-Root -> leere Aliasbereiche."""
        alias_file = tmp_path / "search_aliases.json"
        alias_file.write_text('[1, 2, 3]', encoding="utf-8")
        aliases = search_aliases.load_aliases(str(alias_file))
        assert aliases == {"artists": {}, "songs": {}, "albums": {}, "playlists": {}}

    def test_keys_are_casefolded(self, tmp_path):
        """Alias-Schlüssel werden casefold-normalisiert abgelegt."""
        alias_file = tmp_path / "search_aliases.json"
        alias_file.write_text(
            json.dumps({"artists": {"ACDC": "AC/DC"}}), encoding="utf-8"
        )
        aliases = search_aliases.load_aliases(str(alias_file))
        assert aliases["artists"]["acdc"] == "AC/DC"

    def test_non_dict_section_is_ignored(self, tmp_path):
        """Kein Dict als Aliasbereich -> leerer Bereich."""
        alias_file = tmp_path / "search_aliases.json"
        alias_file.write_text(
            json.dumps({"artists": "AC/DC"}), encoding="utf-8"
        )
        aliases = search_aliases.load_aliases(str(alias_file))
        assert aliases["artists"] == {}

    def test_get_aliases_singleton(self):
        """get_aliases() liefert eine stabile, einmalig geladene Instanz."""
        first = search_aliases.get_aliases()
        second = search_aliases.get_aliases()
        assert first is second
        assert first["artists"]["acdc"] == "AC/DC"