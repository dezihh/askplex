# -*- coding: utf-8 -*-
"""
Smoke-Tests für den AMS-Lambda-Handler (lambda_function.lambda_handler).

Die Queue wird in-memory gespeichert; Plex-Aufrufe werden gemockt.
"""

import logging
import os
from unittest.mock import patch

import pytest

os.environ["AMS_QUEUE_STORE"] = "memory"

import sys

LAMBDA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

from lambda_function import lambda_handler


@pytest.fixture
def mock_tracks():
    from unittest.mock import MagicMock

    track = MagicMock()
    track.ratingKey = 1
    track.title = "Highway to Hell"
    track.grandparentTitle = "AC/DC"
    track.parentTitle = "Highway to Hell"
    track.parentThumb = "/library/metadata/1/thumb"
    track.grandparentArt = "/library/metadata/1/art"
    track.duration = 208000
    track.getStreamURL.return_value = "http://plex.local/audio/1/stream.m3u8?token=x"
    return track


class TestLambdaHandler:
    def test_ignores_skill_events(self):
        event = {"request": {"type": "SKILL_ENABLED", "requestId": "x"}}
        assert lambda_handler(event, None) == {}

    def test_unknown_directive(self):
        event = {"request": {"type": "Alexa.XYZ", "name": "Nope", "payload": {}}}
        response = lambda_handler(event, None)
        assert response["header"]["name"] == "ErrorResponse"

    def test_full_initiate_flow(self, mock_tracks):
        from askplex.ams_controller import AMSController

        controller = AMSController(logging.getLogger("smoke"))
        with patch.object(controller, "_tracks_for_content", return_value=[controller._plex_track_to_dict(mock_tracks)]), \
                patch("lambda_function.controller", controller):
            event = {
                "request": {
                    "type": "Alexa.Media.Playback",
                    "name": "Initiate",
                    "payload": {"contentId": "plex:artist:42"},
                }
            }
            response = lambda_handler(event, None)

        assert response["header"]["name"] == "Initiate.Response"
        playback_method = response["payload"]["playbackMethod"]
        assert playback_method["firstItem"]["metadata"]["name"]["display"] == "Highway to Hell"
        assert playback_method["firstItem"]["stream"]["uri"] == "http://plex.local/audio/1/stream.mp3?token=x"
