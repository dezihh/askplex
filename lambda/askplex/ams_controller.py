# -*- coding: utf-8 -*-
"""
AMS-Controller für den AskPlex Music Skill.

Implementiert die Directives der Alexa Music, Radio, and Podcast Skill API
(V3): GetPlayableContent, Initiate, Reinitiate, GetNextItem, GetPreviousItem,
JumpToItem und GetItem. Die Namensauflösung nutzt die deterministische
Suchlogik aus unicode_normalizer.py und search_aliases.py, die Plex-Anbindung
erfolgt über plexapi.
"""

import json
import os
import time
import uuid

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer

from . import config
from . import search_aliases
from .unicode_normalizer import get_normalizer

CONTENT_ID_PREFIX = "plex"

QUEUE_TTL_SECONDS = 6 * 60 * 60
STREAM_VALID_SECONDS = 6 * 60 * 60


class QueueStore:
    """
    Persistiert AMS-Queues (contentId -> Track-Liste) für die
    GetNextItem/GetPreviousItem/JumpToItem-Calls.

    Standardmäßig wird DynamoDB genutzt (Tabelle per Env-Variable
    AMS_QUEUES_TABLE_NAME, Default "askplex-ams-queues", Hash-Key "queueId",
    TTL-Feld "expiresAt"). Für Tests kann über AMS_QUEUE_STORE=memory auf eine
    In-Memory-Implementierung umgeschaltet werden.
    """

    def __init__(self, logger):
        self.logger = logger
        self._memory: Dict[str, Dict] = {}

    def save(self, queue_id: str, queue_data: Dict) -> None:
        store = os.environ.get("AMS_QUEUE_STORE", "dynamodb")
        if store == "memory":
            self._memory[queue_id] = queue_data
            return

        table = self._table()
        try:
            item = dict(queue_data)
            item["queueId"] = queue_id
            item["expiresAt"] = int(time.time()) + QUEUE_TTL_SECONDS
            table.put_item(Item=item)
        except Exception as exception:
            self.logger.error("Fehler beim Speichern der Queue %s: %s", queue_id, exception)

    def load(self, queue_id: Optional[str]) -> Optional[Dict]:
        if queue_id is None:
            return None
        store = os.environ.get("AMS_QUEUE_STORE", "dynamodb")
        if store == "memory":
            return self._memory.get(queue_id)

        table = self._table()
        try:
            response = table.get_item(Key={"queueId": queue_id})
            return response.get("Item")
        except Exception as exception:
            self.logger.error("Fehler beim Laden der Queue %s: %s", queue_id, exception)
            return None

    def _table(self):
        table_name = os.environ.get("AMS_QUEUES_TABLE_NAME", "askplex-ams-queues")
        import boto3
        return boto3.resource("dynamodb").Table(table_name)


class AMSController:
    """
    Behandelt die Directives der Alexa Music, Radio, and Podcast Skill API.
    Jede Methode erhält das Request-Payload und liefert das Response-Dict,
    das die Lambda direkt als JSON zurückgibt.
    """

    def __init__(self, logger):
        self.logger = logger
        self.plex_server = None
        self.section = None
        self.queue_store = QueueStore(logger)

    def handle(self, event: Dict) -> Dict:
        request = event.get("request", {})
        namespace = request.get("type")
        name = request.get("name")
        payload = request.get("payload", {}) or {}

        handler = {
            ("Alexa.Media.Search", "GetPlayableContent"): self.get_playable_content,
            ("Alexa.Media.Playback", "Initiate"): self.initiate,
            ("Alexa.Media.Playback", "Reinitiate"): self.reinitiate,
            ("Alexa.Audio.PlayQueue", "GetNextItem"): self.get_next_item,
            ("Alexa.Audio.PlayQueue", "GetPreviousItem"): self.get_previous_item,
            ("Alexa.Audio.PlayQueue", "JumpToItem"): self.jump_to_item,
            ("Alexa.Media.PlayQueue", "GetItem"): self.get_item,
        }.get((namespace, name))

        if handler is None:
            self.logger.warning("Unbekannte Directive: %s / %s", namespace, name)
            return self.error_response("Alexa", "INTERNAL_ERROR", "Unsupported directive: {} {}".format(namespace, name))

        try:
            return handler(payload)
        except Exception as exception:
            self.logger.error("Fehler in %s: %s", name, exception, exc_info=True)
            return self.error_response("Alexa", "INTERNAL_ERROR", str(exception))

    #
    # Alexa.Media.Search
    #
    def get_playable_content(self, payload: Dict) -> Dict:
        selection_criteria = payload.get("selectionCriteria", {})
        attributes = selection_criteria.get("attributes", [])

        for attribute in attributes:
            entity_type = attribute.get("type")
            entity_id = attribute.get("entityId")
            display_text = attribute.get("displayText") or attribute.get("text") or attribute.get("value")

            content_id = self._resolve_attribute(entity_type, entity_id, display_text)
            if content_id is None:
                continue

            metadata = self._content_metadata(content_id)
            if metadata is None:
                continue

            return self._response(
                "Alexa.Media.Search", "GetPlayableContent.Response",
                {"content": {"id": content_id, "metadata": metadata}},
            )

        return self.error_response("Alexa.Media", "CRITERIA_NOT_FOUND", "No playable content found.")

    def _resolve_attribute(self, entity_type: str, entity_id: Optional[str], display_text: Optional[str]) -> Optional[str]:
        if entity_id and entity_id.startswith(CONTENT_ID_PREFIX + ":"):
            return entity_id

        if not display_text:
            return None

        query = str(display_text)

        if entity_type == "ARTIST":
            artist = self._resolve_artist(query)
            if artist is not None:
                return "{}:artist:{}".format(CONTENT_ID_PREFIX, artist.ratingKey)
            return None

        if entity_type == "ALBUM":
            album = self._resolve_album(query)
            if album is not None:
                return "{}:album:{}".format(CONTENT_ID_PREFIX, album.ratingKey)
            return None

        if entity_type == "PLAYLIST":
            playlist = self._resolve_playlist(query)
            if playlist is not None:
                return "{}:playlist:{}".format(CONTENT_ID_PREFIX, playlist.ratingKey)
            return None

        if entity_type == "TRACK":
            track = self._resolve_track(query)
            if track is not None:
                return "{}:track:{}".format(CONTENT_ID_PREFIX, track.ratingKey)
            return None

        if entity_type == "GENRE":
            return "{}:genre:{}".format(CONTENT_ID_PREFIX, query)
        if entity_type == "STATION":
            return "{}:station:{}".format(CONTENT_ID_PREFIX, query)

        return None

    def _content_metadata(self, content_id: str) -> Optional[Dict]:
        track_list = self._tracks_for_content(content_id)
        if not track_list:
            return None
        return {
            "type": "TRACK",
            "name": {"speech": {"type": "PLAIN_TEXT", "text": track_list[0]["title"]}, "display": track_list[0]["title"]},
        }

    #
    # Alexa.Media.Playback
    #
    def initiate(self, payload: Dict) -> Dict:
        return self._initiate(payload)

    def reinitiate(self, payload: Dict) -> Dict:
        return self._initiate(payload)

    def _initiate(self, payload: Dict) -> Dict:
        content_id = payload.get("contentId")
        if not content_id:
            return self.error_response("Alexa.Media", "CRITERIA_NOT_FOUND", "Missing contentId.")

        track_list = self._tracks_for_content(content_id)
        if not track_list:
            return self.error_response("Alexa.Media", "CONTENT_NOT_FOUND", "No tracks for contentId {}.".format(content_id))

        playback_modes = payload.get("playbackModes", {}) or {}
        shuffle = bool(playback_modes.get("shuffle"))
        loop = bool(playback_modes.get("loop"))

        queue_id = str(uuid.uuid4())
        order = list(range(len(track_list)))
        if shuffle:
            import random
            random.shuffle(order)

        queue_data = {
            "contentId": content_id,
            "tracks": track_list,
            "order": order,
            "loop": loop,
            "playlist_name": self._playlist_name(content_id),
        }
        self.queue_store.save(queue_id, queue_data)

        first_item = self._build_item(track_list[order[0]])
        playback_method = {
            "type": "ALEXA_AUDIO_PLAYER_QUEUE",
            "id": queue_id,
            "controls": [
                {"type": "TOGGLE", "name": "SHUFFLE", "enabled": True, "selected": shuffle},
                {"type": "TOGGLE", "name": "LOOP", "enabled": True, "selected": loop},
            ],
            "firstItem": first_item,
        }

        return self._response(
            "Alexa.Media.Playback", "Initiate.Response",
            {"playbackMethod": playback_method},
        )

    #
    # Alexa.Audio.PlayQueue
    #
    def get_next_item(self, payload: Dict) -> Dict:
        queue_id = self._queue_id_from(payload)
        queue_data = self.queue_store.load(queue_id)
        if queue_data is None:
            return self.error_response("Alexa.Media", "INVALID_ITEM", "Unknown queue {}.".format(queue_id))

        current = self._current_position(payload, queue_data)
        next_position = self._advance(queue_data, current, direction=1)
        if next_position is None:
            return self._response(
                "Alexa.Audio.PlayQueue", "GetNextItem.Response",
                {"isQueueFinished": True, "item": None},
            )

        return self._response(
            "Alexa.Audio.PlayQueue", "GetNextItem.Response",
            {"isQueueFinished": False, "item": self._build_item(self._track_at(queue_data, next_position))},
        )

    def get_previous_item(self, payload: Dict) -> Dict:
        queue_id = self._queue_id_from(payload)
        queue_data = self.queue_store.load(queue_id)
        if queue_data is None:
            return self.error_response("Alexa.Media", "INVALID_ITEM", "Unknown queue {}.".format(queue_id))

        current = self._current_position(payload, queue_data)
        previous_position = self._advance(queue_data, current, direction=-1)
        if previous_position is None:
            return self._response(
                "Alexa.Audio.PlayQueue", "GetPreviousItem.Response",
                {"isQueueFinished": True, "item": None},
            )

        return self._response(
            "Alexa.Audio.PlayQueue", "GetPreviousItem.Response",
            {"isQueueFinished": False, "item": self._build_item(self._track_at(queue_data, previous_position))},
        )

    def jump_to_item(self, payload: Dict) -> Dict:
        queue_id = self._queue_id_from(payload)
        queue_data = self.queue_store.load(queue_id)
        if queue_data is None:
            return self.error_response("Alexa.Media", "INVALID_ITEM", "Unknown queue {}.".format(queue_id))

        target_item_id = self._target_item_id(payload)
        if target_item_id is None:
            return self.error_response("Alexa.Media", "INVALID_ITEM", "No target item.")

        track = self._find_track_by_id(queue_data, target_item_id)
        if track is None:
            return self.error_response("Alexa.Media", "INVALID_ITEM", "Item {} not in queue.".format(target_item_id))

        return self._response(
            "Alexa.Audio.PlayQueue", "JumpToItem.Response",
            {"item": self._build_item(track)},
        )

    #
    # Alexa.Media.PlayQueue
    #
    def get_item(self, payload: Dict) -> Dict:
        target_reference = payload.get("targetItemReference", {})
        value = target_reference.get("value", {})
        item_id = value.get("id")
        queue_id = value.get("queueId")

        queue_data = self.queue_store.load(queue_id) if queue_id else None
        track = self._find_track_by_id(queue_data or {}, item_id) if queue_id else None
        if track is None:
            return self.error_response("Alexa.Media", "ITEM_NOT_FOUND", "Item {} not found.".format(item_id))

        return self._response(
            "Alexa.Media.PlayQueue", "GetItem.Response",
            {"item": self._build_item(track)},
        )

    #
    # Queue-Helfer
    #
    def _queue_id_from(self, payload: Dict) -> Optional[str]:
        reference = payload.get("currentItemReference", {})
        value = reference.get("value", {})
        return value.get("queueId")

    def _current_position(self, payload: Dict, queue_data: Dict) -> int:
        reference = payload.get("currentItemReference", {})
        value = reference.get("value", {})
        current_id = value.get("id")
        order = queue_data.get("order", [])
        tracks = queue_data.get("tracks", [])
        for index, track_index in enumerate(order):
            if str(tracks[track_index]["id"]) == str(current_id):
                return index
        return -1

    def _target_item_id(self, payload: Dict) -> Optional[str]:
        reference = payload.get("targetItemReference") or payload.get("currentItemReference", {})
        value = reference.get("value", {})
        return value.get("id")

    def _advance(self, queue_data: Dict, current: int, direction: int) -> Optional[int]:
        order = queue_data.get("order", [])
        loop = queue_data.get("loop", False)

        if current < 0:
            return 0 if order else None

        next_index = current + direction
        if 0 <= next_index < len(order):
            return next_index
        if loop:
            return (next_index % len(order)) if order else None
        return None

    def _track_at(self, queue_data: Dict, position: int) -> Dict:
        order = queue_data.get("order", [])
        tracks = queue_data.get("tracks", [])
        return tracks[order[position]]

    def _find_track_by_id(self, queue_data: Dict, item_id: str) -> Optional[Dict]:
        tracks = queue_data.get("tracks", [])
        for track in tracks:
            if str(track["id"]) == str(item_id):
                return track
        return None

    #
    # Plex-Zugriff
    #
    def _connect(self):
        if self.plex_server is None:
            self.plex_server = PlexServer(config.PMS_SERVER_URL, config.PMS_SERVER_TOKEN)
        if self.section is None:
            self.section = self.plex_server.library.section(config.PMS_DEFAULT_SECTION_NAME)

    def _tracks_for_content(self, content_id: str) -> List[Dict]:
        if not content_id or not content_id.startswith(CONTENT_ID_PREFIX + ":"):
            return []
        parts = content_id.split(":")
        if len(parts) < 3:
            return []

        entity_type = parts[1]
        key = ":".join(parts[2:])

        try:
            self._connect()
        except Exception as exception:
            self.logger.error("Plex-Verbindung fehlgeschlagen: %s", exception)
            return []

        try:
            if entity_type == "artist":
                plex_artist = self.plex_server.fetchItem(int(key))
                tracks = self._artist_tracks(plex_artist)
            elif entity_type == "album":
                plex_album = self.plex_server.fetchItem(int(key))
                tracks = plex_album.tracks()
            elif entity_type == "playlist":
                plex_playlist = self.plex_server.fetchItem(int(key))
                tracks = plex_playlist.items()
            elif entity_type == "track":
                plex_track = self.plex_server.fetchItem(int(key))
                tracks = [plex_track]
            elif entity_type == "genre":
                tracks = self.section.searchTracks(style=key, maxresults=config.PMS_DEFAULT_MAX_RESULTS)
            elif entity_type == "station":
                tracks = self.section.searchTracks(maxresults=config.PMS_DEFAULT_MAX_RESULTS)
            else:
                return []
        except Exception as exception:
            self.logger.error("Fehler beim Laden von %s: %s", content_id, exception)
            return []

        return [self._plex_track_to_dict(track) for track in tracks if track is not None]

    def _artist_tracks(self, plex_artist):
        try:
            tracks = plex_artist.popularTracks()
        except Exception:
            tracks = []
        if len(tracks) == 0:
            try:
                tracks = plex_artist.tracks()
            except Exception:
                tracks = []
        return tracks

    def _plex_track_to_dict(self, plex_track) -> Dict:
        return {
            "id": str(plex_track.ratingKey),
            "title": plex_track.title,
            "artist": plex_track.grandparentTitle,
            "artist_art": plex_track.url(plex_track.grandparentArt),
            "album": plex_track.parentTitle,
            "album_art": plex_track.url(plex_track.parentThumb),
            "uri": plex_track.getStreamURL().replace("m3u8", "mp3"),
            "duration": getattr(plex_track, "duration", None),
        }

    def _build_item(self, track: Dict) -> Dict:
        art = None
        if track.get("album_art"):
            art = {
                "sources": [
                    {"url": track["album_art"], "size": "X_LARGE", "widthPixels": 600, "heightPixels": 600}
                ]
            }

        metadata = {
            "type": "TRACK",
            "name": {
                "speech": {"type": "PLAIN_TEXT", "text": track["title"]},
                "display": track["title"],
            },
        }
        if track.get("artist"):
            metadata["authors"] = [
                {"name": {"speech": {"type": "PLAIN_TEXT", "text": track["artist"]}, "display": track["artist"]}}
            ]
        if art:
            metadata["art"] = art

        item = {
            "id": str(track["id"]),
            "playbackInfo": {"type": "DEFAULT"},
            "metadata": metadata,
            "controls": [
                {"type": "COMMAND", "name": "NEXT", "enabled": True},
                {"type": "COMMAND", "name": "PREVIOUS", "enabled": True},
            ],
            "rules": {"feedbackEnabled": True},
            "stream": {
                "id": str(track["id"]),
                "uri": track["uri"],
                "offsetInMilliseconds": 0,
                "validUntil": (datetime.now(timezone.utc) + timedelta(seconds=STREAM_VALID_SECONDS)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            },
        }
        if track.get("duration"):
            item["durationInMilliseconds"] = int(track["duration"])

        return item

    def _playlist_name(self, content_id: str) -> str:
        parts = content_id.split(":")
        if len(parts) < 3:
            return content_id
        return " ".join(parts[1:])

    #
    # Deterministische Namensauflösung (wie im bisherigen Controller)
    #
    def _resolve_artist(self, query: str):
        exact = self._search_artist_exact(query)
        if exact is not None:
            return exact

        aliases = search_aliases.get_aliases()
        artist_aliases = aliases.get("artists", {})
        for alias_key in (query.casefold(), " ".join(query.split()).casefold()):
            if alias_key in artist_aliases:
                alias_target = artist_aliases[alias_key]
                exact = self._search_artist_exact(alias_target)
                if exact is not None:
                    return exact

        normalizer = get_normalizer()
        try:
            self._connect()
            all_artists = self.section.searchArtists()
        except Exception:
            return None

        names = [str(artist.title) for artist in all_artists]
        normalized = normalizer.get_exact_normalized_matches(query, names)
        if len(normalized) == 1:
            for artist in all_artists:
                if str(artist.title) in normalized:
                    return artist
        return None

    def _search_artist_exact(self, query: str):
        try:
            self._connect()
            results = self.section.searchArtists(title=query)
        except Exception:
            return None
        matches = [artist for artist in results if str(artist.title).casefold() == query.casefold()]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_album(self, query: str):
        try:
            self._connect()
            results = self.section.searchAlbums(title=query)
        except Exception:
            return None
        matches = [album for album in results if str(album.title).casefold() == query.casefold()]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_track(self, query: str):
        try:
            self._connect()
            results = self.section.searchTracks(title=query, maxresults=config.PMS_DEFAULT_MAX_RESULTS)
        except Exception:
            return None
        matches = [track for track in results if str(track.title).casefold() == query.casefold()]
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_playlist(self, query: str):
        try:
            self._connect()
            results = self.section.playlists()
        except Exception:
            return None
        matches = [playlist for playlist in results if str(playlist.title).casefold() == query.casefold()]
        if len(matches) == 1:
            return matches[0]
        return None

    #
    # Antwort-Helfer
    #
    def _response(self, namespace: str, name: str, payload: Dict) -> Dict:
        return {
            "header": {
                "namespace": namespace,
                "name": name,
                "messageId": str(uuid.uuid4()),
                "payloadVersion": "1.0",
            },
            "payload": payload,
        }

    def error_response(self, namespace: str, error_type: str, message: str) -> Dict:
        return {
            "header": {
                "messageId": str(uuid.uuid4()),
                "namespace": namespace,
                "name": "ErrorResponse",
                "payloadVersion": "1.0",
            },
            "payload": {"type": error_type, "message": message},
        }
