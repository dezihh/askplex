# -*- coding: utf-8 -*-
"""
Tests für die deterministische Künstlerauflösung und die nummerierte Auswahl.

Plex-Aufrufe werden gemockt; es wird kein echter Plex-Server benötigt.
"""

import json
import logging
import os
from unittest.mock import MagicMock

import pytest

try:
    from askplex.controller import Controller
    CONTROLLER_AVAILABLE = True
except ImportError:
    Controller = None
    CONTROLLER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not CONTROLLER_AVAILABLE,
    reason="ask-sdk-core/plexapi nicht installiert (Controller-Tests übersprungen)",
)


def _load_de_strings():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "lambda", "askplex", "language_strings.json")
    with open(path, encoding="utf-8") as language_file:
        return json.load(language_file)["de-DE"]


class FakeAttributesManager:
    """Bereitstellung von Request-, Session- und Persistent-Attributen."""

    def __init__(self, de_strings):
        self.request_attributes = {"_": de_strings}
        self.session_attributes = {}
        self.persistent_attributes = {
            "schema": 0,
            "playback_setting": {"loop": False, "shuffle": False},
            "playback_info": {
                "playlist": {},
                "play_order": [],
                "index": 0,
                "offset_in_ms": 0,
                "in_playback_session": False,
                "playback_index_changed": False,
                "next_stream_enqueued": False,
                "playlist_name": "",
            },
            "pms_settings": {"max_results": 100, "section_name": "Musik"},
        }


class FakeResponseBuilder:
    """Fluent ResponseBuilder-Mock (speak/ask/set_card/add_directive)."""

    def __init__(self):
        self.speech_text = None
        self.ask_texts = []
        self.card = None
        self.directives = []
        self.should_end_session = None
        self.response = object()

    def speak(self, text):
        self.speech_text = text
        return self

    def ask(self, text):
        self.ask_texts.append(text)
        return self

    def set_card(self, card):
        self.card = card
        return self

    def add_directive(self, directive):
        self.directives.append(directive)
        return self

    def set_should_end_session(self, value):
        self.should_end_session = value
        return self


class FakeHandlerInput:
    def __init__(self, de_strings):
        self.attributes_manager = FakeAttributesManager(de_strings)
        self.response_builder = FakeResponseBuilder()


def make_artist(rating_key, name):
    artist = MagicMock()
    artist.ratingKey = rating_key
    artist.title = name
    return artist


def make_track(rating_key, title, artist_name):
    track = MagicMock()
    track.ratingKey = rating_key
    track.title = title
    track.grandparentTitle = artist_name
    track.grandparentArt = "art/" + str(rating_key)
    track.parentTitle = "Album"
    track.parentThumb = "thumb/" + str(rating_key)
    track.getStreamURL.return_value = "http://plex.local/stream"
    return track


@pytest.fixture
def controller_with_handler():
    de_strings = _load_de_strings()
    handler = FakeHandlerInput(de_strings)
    ctrl = Controller(logging.getLogger("test-search"), handler)
    return ctrl, handler


@pytest.fixture
def patch_plex_server(monkeypatch):
    """Ersetzt PlexServer durch einen Mock, dessen section den Tests gehört."""
    def _patch(section, artists_by_rating_key=None):
        from askplex import controller as controller_module
        server = MagicMock()
        server.library.section.return_value = section
        artists_by_rating_key = artists_by_rating_key or {}
        server.fetchItem.side_effect = lambda rating_key: artists_by_rating_key.get(rating_key)
        monkeypatch.setattr(controller_module, "PlexServer", lambda *args, **kwargs: server)
        return server
    return _patch


def _set_section(ctrl, artists_by_title=None, all_artists=None):
    """Konfiguriert ctrl.section mit einer searchArtists-Mock-Funktion."""
    section = MagicMock()
    artists_by_title = artists_by_title or {}

    def fake_search_artists(title=None, maxresults=None):
        if title is None:
            return list(all_artists or [])
        return list(artists_by_title.get(title, []))

    section.searchArtists.side_effect = fake_search_artists
    ctrl.section = section
    return section


class TestResolveArtist:
    """resolve_artist: exakter Treffer, Alias, Vergleichsschlüssel, Mehrdeutigkeit."""

    def test_exact_match(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        _set_section(ctrl, {"AC/DC": [acdc]}, all_artists=[acdc])

        result = ctrl.resolve_artist("AC/DC")
        assert result["status"] == "match"
        assert result["match_source"] == "exact"
        assert result["candidates"] == [{"rating_key": "123", "name": "AC/DC"}]

    def test_alias_match(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        # Plex kennt "AC/DC", findet aber "ACDC" nicht exakt
        _set_section(ctrl, {"AC/DC": [acdc]}, all_artists=[acdc])

        result = ctrl.resolve_artist("ACDC")
        assert result["status"] == "match"
        assert result["match_source"] == "alias"
        assert result["candidates"][0]["name"] == "AC/DC"

    def test_alias_target_missing_in_plex(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        # Alias "acdc" -> "AC/DC", aber Plex kennt "AC/DC" nicht
        _set_section(ctrl, {}, all_artists=[])

        result = ctrl.resolve_artist("ACDC")
        assert result["status"] == "not_found"

    def test_normalized_single_match(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        # Keine exakte Suche und kein Alias: Vergleichsschlüssel greift
        _set_section(ctrl, {}, all_artists=[acdc])

        result = ctrl.resolve_artist("A.C.D.C.")
        assert result["status"] == "match"
        assert result["match_source"] == "normalized"
        assert result["candidates"][0]["name"] == "AC/DC"

    def test_not_found(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        _set_section(ctrl, {}, all_artists=[])

        result = ctrl.resolve_artist("ABCD")
        assert result["status"] == "not_found"
        assert result["candidates"] == []

    def test_multiple_candidates(self, controller_with_handler):
        ctrl, _ = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        acdc_spaced = make_artist(789, "AC DC")
        tribute = make_artist(456, "AC DC Tribute")
        _set_section(ctrl, {}, all_artists=[acdc, acdc_spaced, tribute])

        result = ctrl.resolve_artist("ACDC")
        assert result["status"] == "multiple"
        assert result["match_source"] == "normalized"
        names = [candidate["name"] for candidate in result["candidates"]]
        assert names == ["AC/DC", "AC DC"]


class TestPlayIntents:
    """play_music_by_artist / play_song_by_artist / play_album_by_artist."""

    def _make_slots(self, **kwargs):
        return {name: MagicMock(value=value) for name, value in kwargs.items()}

    def test_play_music_by_artist_multi_creates_selection(
            self, controller_with_handler, patch_plex_server, monkeypatch):
        ctrl, handler = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        acdc_spaced = make_artist(789, "AC DC")
        section = _set_section(ctrl, {}, all_artists=[acdc, acdc_spaced])
        patch_plex_server(section)

        from askplex import controller as controller_module
        monkeypatch.setattr(
            controller_module, "get_slot_value_v2",
            lambda handler_input, name: self._make_slots(artist="ACDC").get(name),
        )

        ctrl.play_music_by_artist()
        pending = handler.attributes_manager.session_attributes.get("pending_selection")
        assert pending is not None
        assert pending["continuation"]["action"] == "play_music_by_artist"
        assert len(pending["candidates"]) == 2
        # Sprachausgabe enthält die nummerierte Liste mit Zahlwörtern
        assert "Ich habe zwei passende Künstler gefunden" in handler.response_builder.speech_text
        assert "Nummer eins: AC/DC" in handler.response_builder.speech_text
        assert "Nummer zwei: AC DC" in handler.response_builder.speech_text
        # SimpleCard mit derselben Liste
        assert handler.response_builder.card is not None
        assert "1. AC/DC" in handler.response_builder.card.content

    def test_play_song_by_artist_keeps_song_in_continuation(
            self, controller_with_handler, patch_plex_server, monkeypatch):
        ctrl, handler = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        acdc_spaced = make_artist(789, "AC DC")
        section = _set_section(ctrl, {}, all_artists=[acdc, acdc_spaced])
        patch_plex_server(section)

        from askplex import controller as controller_module
        monkeypatch.setattr(
            controller_module, "get_slot_value_v2",
            lambda handler_input, name: self._make_slots(
                artist="ACDC", song="Thunderstruck").get(name),
        )

        ctrl.play_song_by_artist()
        pending = handler.attributes_manager.session_attributes.get("pending_selection")
        assert pending is not None
        assert pending["continuation"]["action"] == "play_song_by_artist"
        assert pending["continuation"]["song"] == "Thunderstruck"

    def test_play_album_by_artist_keeps_album_in_continuation(
            self, controller_with_handler, patch_plex_server, monkeypatch):
        ctrl, handler = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        acdc_spaced = make_artist(789, "AC DC")
        section = _set_section(ctrl, {}, all_artists=[acdc, acdc_spaced])
        patch_plex_server(section)

        from askplex import controller as controller_module
        monkeypatch.setattr(
            controller_module, "get_slot_value_v2",
            lambda handler_input, name: self._make_slots(
                artist="ACDC", album="Back in Black").get(name),
        )

        ctrl.play_album_by_artist()
        pending = handler.attributes_manager.session_attributes.get("pending_selection")
        assert pending is not None
        assert pending["continuation"]["action"] == "play_album_by_artist"
        assert pending["continuation"]["album"] == "Back in Black"

    def test_not_found_mentions_raw_value_and_card(
            self, controller_with_handler, patch_plex_server, monkeypatch):
        ctrl, handler = controller_with_handler
        section = _set_section(ctrl, {}, all_artists=[])
        patch_plex_server(section)

        from askplex import controller as controller_module
        monkeypatch.setattr(
            controller_module, "get_slot_value_v2",
            lambda handler_input, name: self._make_slots(artist="ABCD").get(name),
        )

        ctrl.play_music_by_artist()
        # Keine automatische Auswahl
        assert handler.attributes_manager.session_attributes.get("pending_selection") is None
        # Rohwert in Sprache und Karte
        assert "ABCD" in handler.response_builder.speech_text
        assert handler.response_builder.card is not None
        assert "Verstanden: ABCD" in handler.response_builder.card.content
        assert "Mein Plex" in handler.response_builder.card.title


class TestContinueAfterSelection:
    """continue_after_selection: Laden per ratingKey, Bereichsprüfung."""

    def _seed_pending(self, handler, candidates, continuation):
        handler.attributes_manager.session_attributes["pending_selection"] = {
            "entity_type": "artist",
            "query": "ACDC",
            "continuation": continuation,
            "candidates": candidates,
        }

    def test_valid_selection_loads_by_rating_key(
            self, controller_with_handler, patch_plex_server):
        ctrl, handler = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        acdc.tracks.return_value = [make_track(1, "Thunderstruck", "AC/DC")]
        acdc.popularTracks.return_value = []
        section = _set_section(ctrl, {}, all_artists=[acdc])
        server = patch_plex_server(section, artists_by_rating_key={123: acdc})

        self._seed_pending(handler, [
            {"rating_key": "123", "name": "AC/DC"},
            {"rating_key": "456", "name": "AC DC Tribute"},
        ], {"action": "play_music_by_artist"})

        ctrl.continue_after_selection(1)

        # Kandidat wird über die Plex-ID geladen, nicht per Namenssuche
        server.fetchItem.assert_called_once_with(123)
        # Pending-Zustand gelöscht
        assert handler.attributes_manager.session_attributes.get("pending_selection") is None
        # Erfolgsansage mit tatsächlichem Plex-Namen und "Mein Plex"
        assert "Ich spiele AC/DC in Mein Plex." in handler.response_builder.speech_text

    def test_out_of_range_keeps_pending(
            self, controller_with_handler, patch_plex_server):
        ctrl, handler = controller_with_handler
        section = _set_section(ctrl, {}, all_artists=[])
        patch_plex_server(section)

        self._seed_pending(handler, [
            {"rating_key": "123", "name": "AC/DC"},
            {"rating_key": "456", "name": "AC DC Tribute"},
        ], {"action": "play_music_by_artist"})

        ctrl.continue_after_selection(5)

        assert "Bitte sage eine Zahl zwischen eins und zwei." in handler.response_builder.speech_text
        # Pending-Auswahl bleibt erhalten
        assert handler.attributes_manager.session_attributes.get("pending_selection") is not None

    def test_no_pending_selection(self, controller_with_handler):
        ctrl, handler = controller_with_handler

        ctrl.continue_after_selection(1)

        assert "Es gibt momentan keine offene Auswahl in Mein Plex." in handler.response_builder.speech_text

    def test_song_continuation_searches_only_within_artist(
            self, controller_with_handler, patch_plex_server):
        ctrl, handler = controller_with_handler
        acdc = make_artist(123, "AC/DC")
        thunderstruck = make_track(1, "Thunderstruck", "AC/DC")
        acdc.track.return_value = thunderstruck
        section = _set_section(ctrl, {}, all_artists=[acdc])
        server = patch_plex_server(section, artists_by_rating_key={123: acdc})

        self._seed_pending(handler, [
            {"rating_key": "123", "name": "AC/DC"},
        ], {"action": "play_song_by_artist", "song": "Thunderstruck"})

        ctrl.continue_after_selection(1)

        server.fetchItem.assert_called_once_with(123)
        # Song wird ausschließlich innerhalb des Künstlers gesucht
        acdc.track.assert_called()
        assert "Thunderstruck" in handler.response_builder.speech_text