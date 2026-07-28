# -*- coding: utf-8 -*-
"""
Example: Modified controller.py snippet showing Unicode patch integration

This file demonstrates the key changes needed in controller.py to support
robust Unicode and Umlaut handling with automatic fallback.

Full integration instructions are in PATCH_INSTRUCTIONS.md
"""

# ============================================================================
# CHANGE #1: Add import at top of controller.py
# ============================================================================

import logging
from ask_sdk_core.utils import get_slot_value_v2
from ask_sdk_model import Response
# ... other imports ...

# NEW IMPORT FOR UNICODE SUPPORT
from askplex.unicode_normalizer import SearchStrategy, get_normalizer


# ============================================================================
# CHANGE #2: Modify Controller.__init__ to add search_strategy
# ============================================================================

class Controller:
    """
    Handles all playback control and Plex API interactions.
    """

    def __init__(self, logger, handler_input):
        """Initialize controller with Unicode support."""
        self.logger = logger
        self.handler_input = handler_input
        self.attributes_manager = handler_input.attributes_manager

        # Get device info
        device_id = handler_input.request_envelope.context.system.device.device_id

        # Initialize Alexa SDK
        self.speech_synthesizer = SpeechSynthesizer()

        # Try to initialize Plex connection
        try:
            # ... existing Plex connection code ...
            self.plex_server = PlexServer(config.PMS_SERVER_URL, config.PMS_SERVER_TOKEN)
            self.section = self.plex_server.library.section(config.PMS_DEFAULT_SECTION_NAME)
        except Exception as e:
            self.logger.error(f"Plex connection error: {e}")
            raise

        # NEW: Initialize search strategy for Unicode-aware searches
        self.search_strategy = SearchStrategy()
        self.normalizer = get_normalizer()

        # Load existing playlist from session
        self.playback_info = self.attributes_manager.persistent_attributes.get(
            "playback_info", {}
        )


# ============================================================================
# CHANGE #3: Update play_music_by_artist() with Unicode fallback
# ============================================================================

def play_music_by_artist(self) -> Response:
    """
    Play popular tracks by a specific artist.

    NOW WITH UNICODE FALLBACK:
    - Handles case variations ("die ärzte", "Die Ärzte", "DIE ÄRZTE")
    - Handles Umlaut variants ("Aerzte" vs "Ärzte")
    - Graceful degradation through multiple search attempts
    """
    data = self.handler_input.attributes_manager.request_attributes["_"]

    # Get artist name from voice input
    artist = get_slot_value_v2(self.handler_input, 'artist')

    if artist is None:
        speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
        return self.handler_input.response_builder.speak(speak_output).response

    try:
        # MODIFIED: Use search_strategy with fallback instead of direct search
        artist_results = self.search_strategy.search_with_fallback(
            search_func=self.section.searchArtists,
            query=artist.value
        )

        self.logger.info(f"Artist search for '{artist.value}': {len(artist_results)} results")

    except Exception as exception:
        self.logger.error(f"Artist search error: {exception}")
        speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(artist.value)
        return self.handler_input.response_builder.speak(speak_output).response

    if len(artist_results) == 0:
        self.logger.warning(f"No artist found for: {artist.value}")
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return self.handler_input.response_builder.speak(speak_output).response

    # Get popular tracks from artist
    try:
        # Most Plex servers provide popularTracks()
        plex_track_list = artist_results[0].popularTracks()

        if not plex_track_list:
            # Fallback: get all tracks if no popular tracks
            plex_track_list = artist_results[0].tracks()

    except Exception as e:
        self.logger.error(f"Error getting tracks: {e}")
        plex_track_list = artist_results[0].tracks()

    # Load into playlist
    self.clear_playlist()
    self.add_plex_tracks(plex_track_list)

    # Build response with proper playlist name
    playlist_name = data[prompts.PMS_PLNAME_MUSIC_BY_ARTIST].format(artist.value)
    speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

    return self.start_playback(speak_output)


# ============================================================================
# CHANGE #4: Add new helper methods for Unicode-aware searches
# ============================================================================

def _search_track_with_fallback(self, artist, song_name: str):
    """
    Search for a specific track within an artist's library.

    Tries multiple variants of the song name:
    1. Original ("Die Geschichte")
    2. Title Case ("Die Geschichte")
    3. Lower case ("die geschichte")
    4. Upper case ("DIE GESCHICHTE")
    5. Umlaut variants ("Die Gesichte")

    Args:
        artist: PlexAPI Artist object
        song_name: Song title from voice input

    Returns:
        PlexAPI Track object or None
    """
    variants = self.normalizer.get_search_variants(song_name)

    for variant in variants:
        try:
            self.logger.debug(f"Searching track with variant: '{variant}'")
            track = artist.track(variant)

            if track:
                self.logger.info(f"Track found with variant: '{variant}'")
                return track

        except Exception as e:
            self.logger.debug(f"Track search failed for '{variant}': {e}")
            continue

    self.logger.warning(f"No track found for: {song_name}")
    return None


def _search_album_with_fallback(self, artist, album_name: str):
    """
    Search for an album within an artist's library.

    Tries multiple variants of the album name with Unicode fallbacks.

    Args:
        artist: PlexAPI Artist object
        album_name: Album title from voice input

    Returns:
        PlexAPI Album object or None
    """
    variants = self.normalizer.get_search_variants(album_name)

    for variant in variants:
        try:
            self.logger.debug(f"Searching album with variant: '{variant}'")
            album = artist.album(variant)

            if album:
                self.logger.info(f"Album found with variant: '{variant}'")
                return album

        except Exception as e:
            self.logger.debug(f"Album search failed for '{variant}': {e}")
            continue

    self.logger.warning(f"No album found for: {album_name}")
    return None


def _search_playlist_with_fallback(self, playlist_name: str):
    """
    Search for a playlist by name with Unicode fallback.

    Tries multiple variants of the playlist name.

    Args:
        playlist_name: Playlist name from voice input

    Returns:
        PlexAPI Playlist object or None
    """
    variants = self.normalizer.get_search_variants(playlist_name)

    for variant in variants:
        try:
            self.logger.debug(f"Searching playlist with variant: '{variant}'")
            playlist = self.section.playlist(title=variant)

            if playlist:
                self.logger.info(f"Playlist found with variant: '{variant}'")
                return playlist

        except Exception as e:
            self.logger.debug(f"Playlist search failed for '{variant}': {e}")
            continue

    self.logger.warning(f"No playlist found for: {playlist_name}")
    return None


# ============================================================================
# CHANGE #5: Update play_song_by_artist() to use fallback
# ============================================================================

def play_song_by_artist(self) -> Response:
    """
    Play a specific song by a specific artist.

    Uses fallback search for both artist and song names.
    """
    data = self.handler_input.attributes_manager.request_attributes["_"]

    artist = get_slot_value_v2(self.handler_input, 'artist')
    song = get_slot_value_v2(self.handler_input, 'song')

    if artist is None or song is None:
        speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
        return self.handler_input.response_builder.speak(speak_output).response

    try:
        # MODIFIED: Artist search with fallback
        artist_results = self.search_strategy.search_with_fallback(
            search_func=self.section.searchArtists,
            query=artist.value
        )

    except Exception as exception:
        self.logger.error(f"Artist search error: {exception}")
        speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(artist.value)
        return self.handler_input.response_builder.speak(speak_output).response

    if len(artist_results) == 0:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return self.handler_input.response_builder.speak(speak_output).response

    try:
        # MODIFIED: Track search with fallback
        plex_track = self._search_track_with_fallback(
            artist_results[0],
            song.value
        )

        if plex_track is None:
            speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song.value)
            return self.handler_input.response_builder.speak(speak_output).response

    except Exception as e:
        self.logger.error(f"Track search error: {e}")
        speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song.value)
        return self.handler_input.response_builder.speak(speak_output).response

    self.clear_playlist()
    self.add_plex_tracks([plex_track])

    playlist_name = data[prompts.PMS_PLNAME_SONG_BY_ARTIST].format(
        song.value, artist.value
    )
    speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

    return self.start_playback(speak_output)


# ============================================================================
# CHANGE #6: Update play_playlist() to use fallback
# ============================================================================

def play_playlist(self) -> Response:
    """
    Play a playlist by name.

    Uses fallback search for playlist name.
    """
    data = self.handler_input.attributes_manager.request_attributes["_"]

    playlist = get_slot_value_v2(self.handler_input, 'playlist')

    if playlist is None:
        speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
        return self.handler_input.response_builder.speak(speak_output).response

    try:
        # MODIFIED: Playlist search with fallback
        plex_playlist = self._search_playlist_with_fallback(playlist.value)

        if plex_playlist is None:
            speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(
                playlist.value
            )
            return self.handler_input.response_builder.speak(speak_output).response

        plex_track_list = plex_playlist.tracks()

    except Exception as exception:
        self.logger.error(f"Playlist search error: {exception}")
        speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(
            playlist.value
        )
        return self.handler_input.response_builder.speak(speak_output).response

    if len(plex_track_list) == 0:
        speak_output = data[prompts.PMS_PLAYLIST_EMPTY].format(playlist.value)
        return self.handler_input.response_builder.speak(speak_output).response

    self.clear_playlist()
    self.add_plex_tracks(plex_track_list)

    speak_output = data[prompts.PMS_PLAYING].format(plex_playlist.title)

    return self.start_playback(speak_output)
