# -*- coding: utf-8 -*-
"""
Tests für den AMS-Controller (Alexa Music, Radio, and Podcast Skill API).

Plex-Aufrufe werden gemockt; die Queue wird in-memory gespeichert
(AMS_QUEUE_STORE=memory). Es wird kein echter Plex-Server benötigt.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["AMS_QUEUE_STORE"] = "memory"

from askplex.ams_controller import AMSController, CONTENT_ID_PREFIX


@pytest.fixture
def controller():
    logger = logging.getLogger("test_ams")
    return AMSController(logger)


def _fake_track(rating_key, title, artist="Artist", album="Album", duration=210000):
    track = MagicMock()
    track.ratingKey = rating_key
    track.title = title
    track.grandparentTitle = artist
    track.parentTitle = album
    track.parentThumb = "/library/metadata/{}/thumb".format(rating_key)
    track.grandparentArt = "/library/metadata/{}/art".format(rating_key)
    track.duration = duration
    track.getStreamURL.return_value = "http://plex.local/audio/{}/stream.m3u8?token=x".format(rating_key)
    return track


def _to_dict(controller, track):
    return controller._plex_track_to_dict(track)


def _initiate_event(content_id):
    return {
        "request": {
            "type": "Alexa.Media.Playback",
            "name": "Initiate",
            "payload": {"contentId": content_id},
        }
    }


class TestGetPlayableContent:
    def test_resolves_artist_by_text(self, controller):
        artist = MagicMock()
        artist.ratingKey = 42
        artist.title = "AC/DC"
        track = _to_dict(controller, _fake_track(1, "Highway to Hell"))

        with patch.object(controller, "_resolve_artist", return_value=artist) as resolve, \
                patch.object(controller, "_tracks_for_content", return_value=[track]):
            payload = {
                "selectionCriteria": {
                    "attributes": [
                        {"type": "ARTIST", "entityId": "unknown-id", "displayText": "AC/DC"}
                    ]
                }
            }
            response = controller.get_playable_content(payload)

        resolve.assert_called_once_with("AC/DC")
        assert response["header"]["name"] == "GetPlayableContent.Response"
        content = response["payload"]["content"]
        assert content["id"] == "plex:artist:42"
        assert content["metadata"]["type"] == "TRACK"

    def test_uses_catalog_entity_id_directly(self, controller):
        content_id = "{}:artist:42".format(CONTENT_ID_PREFIX)
        track = _to_dict(controller, _fake_track(1, "Highway to Hell"))
        with patch.object(controller, "_tracks_for_content", return_value=[track]):
            payload = {
                "selectionCriteria": {
                    "attributes": [
                        {"type": "ARTIST", "entityId": content_id}
                    ]
                }
            }
            response = controller.get_playable_content(payload)

        assert response["payload"]["content"]["id"] == content_id

    def test_returns_error_when_nothing_resolves(self, controller):
        with patch.object(controller, "_resolve_attribute", return_value=None):
            payload = {
                "selectionCriteria": {
                    "attributes": [{"type": "ARTIST", "entityId": "x"}]
                }
            }
            response = controller.get_playable_content(payload)

        assert response["header"]["name"] == "ErrorResponse"
        assert response["payload"]["type"] == "CRITERIA_NOT_FOUND"


class TestInitiate:
    def test_initiate_builds_queue_and_first_item(self, controller):
        tracks = [
            _to_dict(controller, _fake_track(1, "Song A")),
            _to_dict(controller, _fake_track(2, "Song B")),
        ]
        with patch.object(controller, "_tracks_for_content", return_value=tracks) as tracks_for:
            response = controller.initiate(_initiate_event("plex:artist:42")["request"]["payload"])

        tracks_for.assert_called_once_with("plex:artist:42")
        assert response["header"]["name"] == "Initiate.Response"
        playback_method = response["payload"]["playbackMethod"]
        assert playback_method["type"] == "ALEXA_AUDIO_PLAYER_QUEUE"
        assert playback_method["firstItem"]["metadata"]["name"]["display"] == "Song A"
        assert playback_method["firstItem"]["stream"]["uri"] == "http://plex.local/audio/1/stream.mp3?token=x"
        queue_id = playback_method["id"]
        assert controller.queue_store.load(queue_id)["contentId"] == "plex:artist:42"

    def test_initiate_respects_shuffle(self, controller):
        tracks = [
            _to_dict(controller, _fake_track(i, "Song {}".format(i)))
            for i in range(1, 11)
        ]
        with patch.object(controller, "_tracks_for_content", return_value=tracks):
            payload = _initiate_event("plex:artist:42")["request"]["payload"]
            payload["playbackModes"] = {"shuffle": True}
            response = controller.initiate(payload)

        playback_method = response["payload"]["playbackMethod"]
        assert playback_method["controls"][0]["name"] == "SHUFFLE"
        assert playback_method["controls"][0]["selected"] is True

    def test_initiate_missing_content_id(self, controller):
        response = controller.initiate({})
        assert response["header"]["name"] == "ErrorResponse"
        assert response["payload"]["type"] == "CRITERIA_NOT_FOUND"


class TestQueueNavigation:
    def _initiate_queue(self, controller):
        tracks = [
            _to_dict(controller, _fake_track(1, "Song A")),
            _to_dict(controller, _fake_track(2, "Song B")),
            _to_dict(controller, _fake_track(3, "Song C")),
        ]
        with patch.object(controller, "_tracks_for_content", return_value=tracks):
            response = controller.initiate(_initiate_event("plex:artist:42")["request"]["payload"])
        queue_id = response["payload"]["playbackMethod"]["id"]
        return queue_id

    def _item_reference(self, queue_id, item_id):
        return {
            "currentItemReference": {
                "namespace": "Alexa.Audio.PlayQueue",
                "name": "item",
                "value": {"id": item_id, "queueId": queue_id, "contentId": "plex:artist:42"},
            }
        }

    def test_get_next_item(self, controller):
        queue_id = self._initiate_queue(controller)
        payload = self._item_reference(queue_id, "1")
        response = controller.get_next_item(payload)

        assert response["header"]["name"] == "GetNextItem.Response"
        assert response["payload"]["isQueueFinished"] is False
        assert response["payload"]["item"]["metadata"]["name"]["display"] == "Song B"

    def test_get_next_item_queue_end(self, controller):
        queue_id = self._initiate_queue(controller)
        payload = self._item_reference(queue_id, "3")
        response = controller.get_next_item(payload)

        assert response["payload"]["isQueueFinished"] is True
        assert response["payload"]["item"] is None

    def test_get_previous_item(self, controller):
        queue_id = self._initiate_queue(controller)
        payload = self._item_reference(queue_id, "2")
        response = controller.get_previous_item(payload)

        assert response["payload"]["item"]["metadata"]["name"]["display"] == "Song A"

    def test_jump_to_item(self, controller):
        queue_id = self._initiate_queue(controller)
        payload = {
            "currentItemReference": {
                "namespace": "Alexa.Audio.PlayQueue",
                "name": "item",
                "value": {"id": "1", "queueId": queue_id, "contentId": "plex:artist:42"},
            },
            "targetItemReference": {
                "namespace": "Alexa.Audio.PlayQueue",
                "name": "item",
                "value": {"id": "3", "queueId": queue_id, "contentId": "plex:artist:42"},
            },
        }
        response = controller.jump_to_item(payload)
        assert response["payload"]["item"]["metadata"]["name"]["display"] == "Song C"

    def test_get_item(self, controller):
        queue_id = self._initiate_queue(controller)
        payload = {
            "targetItemReference": {
                "namespace": "Alexa.Media.PlayQueue",
                "name": "item",
                "value": {"id": "2", "queueId": queue_id, "contentId": "plex:artist:42"},
            }
        }
        response = controller.get_item(payload)
        assert response["header"]["name"] == "GetItem.Response"
        assert response["payload"]["item"]["metadata"]["name"]["display"] == "Song B"

    def test_get_next_item_unknown_queue(self, controller):
        payload = self._item_reference("unknown-queue", "1")
        response = controller.get_next_item(payload)
        assert response["header"]["name"] == "ErrorResponse"
        assert response["payload"]["type"] == "INVALID_ITEM"


class TestDispatch:
    def test_unknown_directive_returns_error(self, controller):
        event = {"request": {"type": "Alexa.XYZ", "name": "Nope", "payload": {}}}
        response = controller.handle(event)
        assert response["header"]["name"] == "ErrorResponse"
        assert response["payload"]["type"] == "INTERNAL_ERROR"

    def test_dispatch_routes_to_initiate(self, controller):
        tracks = [_to_dict(controller, _fake_track(1, "Song A"))]
        with patch.object(controller, "_tracks_for_content", return_value=tracks):
            response = controller.handle(_initiate_event("plex:artist:42"))
        assert response["header"]["name"] == "Initiate.Response"
