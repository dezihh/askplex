import random

from typing import List, Dict
from logging import Logger

from ask_sdk_model import Response
from ask_sdk_model.interfaces.audioplayer import AudioItem, Stream, AudioItemMetadata, PlayDirective, PlayBehavior, StopDirective
from ask_sdk_model.interfaces import display
from ask_sdk_model.ui import SimpleCard

from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.utils import get_slot_value_v2

from plexapi.audio import Track
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound

from . import config
from . import prompts
from . import search_aliases
from .unicode_normalizer import get_normalizer

class Controller:
    """
    Controller class for managing playlist and playback operations.
    Attributes:
        logger (Logger): Logger instance for logging debug and info messages.
        handler_input (HandlerInput): HandlerInput instance for managing request and response attributes.
    Methods:
        add_track(track: Dict) -> None:
            Adds a track to the playlist.
        get_next_track(update_index: bool) -> Dict:
            Retrieves the next track in the playlist.
        get_prevous_track() -> Dict:
            Retrieves the previous track in the playlist.
        get_current_track() -> Dict:
            Retrieves the current track in the playlist.
        shuffle_play_order(shuffle: bool) -> None:
            Shuffles the playback order of the playlist based on the shuffle parameter.
        clear_playlist() -> None:
            Clears the current playlist and resets playback settings.
        track_to_audio_item(track: Dict, offset: int, previous_token: str) -> AudioItem:
            Converts a track (Dict) to an AudioItem object.
        resume_playback() -> Response:
            Handles the resume command.
        start_playback() -> Response:
            Handles the start over command.
        pause_playback() -> Response:
            Handles the pause command.
        previous_playback() -> Response:
            Handles the previous track command.
        next_playback() -> Response:
            Handles the next track command.
        loop_playback(enable: bool) -> Response:
            Enables or disables loop mode.
        shuffle_playback(enable: bool) -> Response:
            Enables or disables shuffle mode.
        retrieve_track_details() -> Response:
            Retrieves track details to the user.
        playback_started() -> Response:
            Handles the event when playback is started.
        playback_stopped() -> Response:
            Handles the event when playback is stopped.
        playback_nearly_finished() -> Response:
            Handles the event when playback is nearly finished.
        playback_finished() -> Response:
            Handles the event when playback is finished.
        playback_failed() -> Response:
            Handles the playback failure scenario.
        load_music_section() -> Response:
            Connects to a plex media server and loads the music section.
        set_playlist_name(name: str) -> None:
            Sets the playlist name used by alexa.
        add_plex_track(plex_track: Track) -> None:
            Adds a track (Track object) to the playlist.
        add_plex_tracks(plex_track_list: List[Track]) -> None:
            Adds a list of tracks (Track objects) to the playlist.
        play_random_music() -> Response:
            Plays random music.
        play_music_by_artist() -> Response:
            Plays music by a given artist.
        play_song_by_artist() -> Response:
            Plays a specific song by a given artist.
        play_album_by_artist() -> Response:
            Plays a specific album by a given artist.
        play_music_by_genre() -> Response:
            Plays music by a given genre.
        play_playlist() -> Response:
            Plays a Plex playlist.
    """
    def __init__(self, logger : Logger, handler_input : HandlerInput) -> None:
        """
        Initializes the controller with a logger and the handler input instance.
        Args:
            logger (Logger): The logger instance to be used for logging.
            handler_input (HandlerInput): The handler input instance.
        """

        self.logger = logger
        """Logger"""

        self.handler_input = handler_input
        """handler_input"""


#
# Playlist utils
#
    def add_track(self, track: Dict) -> None:
        """
        Adds a track to the playlist.
        Args:
            track (Dict): The track information
        Returns:
            None
        """

        self.logger.debug('In add_track()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        playlist_len = len(playback_info["playlist"])

        playback_info["playlist"][str(playlist_len)] = track
        playback_info["play_order"].append(playlist_len)


    def get_next_track(self, update_index: bool) -> Dict:
        """
        Retrieves the next track in the playlist.
        Returns:
            Dict: The next track information
        """

        self.logger.debug('In get_next_track()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_setting = persistence_attr.get("playback_setting")
        playback_info = persistence_attr.get("playback_info")

        index = int(playback_info["index"])
        playlist_len = len(playback_info["playlist"])

        if playlist_len == 0 or (index == (playlist_len - 1) and not playback_setting["loop"]):
            return None

        index = (index + 1) % playlist_len

        if update_index:
            playback_info["index"] = index
            playback_info["offset_in_ms"] = 0
            playback_info["playback_index_changed"] = True

        play_order = playback_info["play_order"]
        return playback_info["playlist"].get(str(play_order[index]))


    def get_prevous_track(self) -> Dict:
        """
        Retrieves the previous track in the playlist.
        Returns:
            Dict: The previous track information
        """

        self.logger.debug('In get_prevous_track()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_setting = persistence_attr.get("playback_setting")
        playback_info = persistence_attr.get("playback_info")

        index = int(playback_info["index"])
        playlist_len = len(playback_info["playlist"])

        if playlist_len == 0 or (index == 0 and not playback_setting["loop"]):
            return None

        index = (index - 1) if index > 0 else (playlist_len - 1)

        playback_info["index"] = index
        playback_info["offset_in_ms"] = 0
        playback_info["playback_index_changed"] = True

        play_order = playback_info["play_order"]
        return playback_info["playlist"].get(str(play_order[index]))


    def get_current_track(self) -> Dict:
        """
        Retrieves the current track information
        Returns:
            Dict: The current track information
        """

        self.logger.debug('In get_current_track()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        index = int(playback_info["index"])
        playlist_len = len(playback_info["playlist"])

        if index < playlist_len:
            play_order = playback_info["play_order"]
            return playback_info["playlist"].get(str(play_order[index]))


    def shuffle_play_order(self, shuffle: bool) -> None:
        """
        Adjusts the playback order of the playlist based on the shuffle parameter.
        If shuffle is True, the playback order is randomized, with the current index
        being moved to the start of the new order. If shuffle is False, the playback
        order is reset to the original order.
        Args:
            shuffle (bool): A flag indicating whether to shuffle the playback order.
        Returns:
            None
        """

        self.logger.debug('In shuffle_play_order()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        index = int(playback_info["index"])
        play_order = playback_info["play_order"]
        playlist_index = int(play_order[index])
        playlist_len = len(playback_info["playlist"])

        play_order = [l for l in range(0, playlist_len)]

        if shuffle:
            play_order.pop(index)
            random.shuffle(play_order)
            play_order.insert(0, index)
            index = 0
        else:
            index = playlist_index

        playback_info["play_order"] = play_order
        playback_info["index"] = index
        playback_info["playback_index_changed"] = True


    def clear_playlist(self) -> None:
        """
        Clears the current playlist and resets playback settings.
        This method performs the following actions:
        - Disables shuffle and loop settings.
        - Resets the playback index and offset.
        - Marks the playback index as changed.
        - Clears the playlist.
        Returns:
            None
        """

        self.logger.debug('In clear_playlist()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_setting = persistence_attr.get("playback_setting")
        playback_info = persistence_attr.get("playback_info")

        playback_setting["shuffle"] = False
        playback_setting["loop"] = False

        playback_info["index"] = 0
        playback_info["offset_in_ms"] = 0
        playback_info["playback_index_changed"] = True
        playback_info["playlist"] = {}
        playback_info["play_order"] = []


#
# Playback control
#
    def track_to_audio_item(self, track: Dict, offset: int, previous_token: str) -> AudioItem:
        """
        Converts a track (Dict) to an AudioItem object.
        Args:
            track (Dict): A dictionary containing track information with keys "title", "artist", "album", "album_art", "artist_art", "id", and "uri".
            offset (int): The offset in milliseconds for the audio stream.
            previous_token (str): The expected previous token for the audio stream.
        Returns:
            AudioItem: An object containing the audio stream and metadata for the track.
        """

        self.logger.debug('In track_to_audio_item()')

        metadata = AudioItemMetadata(
            title = track["title"],
            subtitle = track["artist"]
        )        
        if track["album_art"] is not None:
            metadata.art=display.Image(
                content_description = track["album"],
                sources=[
                    display.ImageInstance(
                        url=track["album_art"]
                    )
                ]
            )
        if track["artist_art"] is not None:
            metadata.background_image=display.Image(
                content_description = track["artist"],
                sources = [
                    display.ImageInstance(
                        url = track["artist_art"]
                    )
                ]
            )

        stream = Stream(token=track["id"], url=track["uri"], offset_in_milliseconds=offset, expected_previous_token=previous_token)
        return AudioItem(stream=stream, metadata=metadata)


    def resume_playback (self) -> Response:
        """
        Handles the resume command.
        This method resumes playback with the saved offset.
        Returns:
            Response: The response object with the play directive and the current track
            in audio item format. If there is no current track, the response object is empty.
        """

        self.logger.debug('In resume_playback()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        current_track = self.get_current_track()

        playback_info['next_stream_enqueued'] = False


        directive = PlayDirective(play_behavior=PlayBehavior.REPLACE_ALL, audio_item=self.track_to_audio_item(current_track, int(playback_info["offset_in_ms"]), None))
        self.handler_input.response_builder.add_directive(directive).set_should_end_session(True)

        return self.handler_input.response_builder.response


    def start_playback (self) -> Response:
        """
        Handles the start over command.
        This method resets the offset of the current track and then resumes playback.
        Returns:
            Response: The response object with the play directive and the current track
            in audio item format. If there is no current track, the response object is empty.
        """

        self.logger.debug('In start_playback()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        playback_info["offset_in_ms"] = 0

        return self.resume_playback()


    def pause_playback (self) -> Response:
        """
        Handles the pause command.
        Returns:
            Response: The response object with the stop directive.
        """
        self.logger.debug('In pause_playback()')

        self.handler_input.response_builder.add_directive(StopDirective()).set_should_end_session(True)
        return self.handler_input.response_builder.response


    def previous_playback (self) -> Response:
        """
        Handles the previous track command.
        Returns:
            Response: The response object with the play directive and the previous track
            in audio item format. If there are no more tracks, the response object is empty.
        """

        self.logger.debug('In previous_playback()')

        prevous_track = self.get_prevous_track()
        if prevous_track == None:
            return self.handler_input.response_builder.response

        directive = PlayDirective(play_behavior=PlayBehavior.REPLACE_ALL, audio_item=self.track_to_audio_item(prevous_track, 0, None))
        self.handler_input.response_builder.add_directive(directive).set_should_end_session(True)

        return self.handler_input.response_builder.response


    def next_playback (self) -> Response:
        """
        Handles the next track command.
        Returns:
            Response: The response object with the play directive and the next track
            in audio item format. If there are no more tracks, the response object is empty.
        """

        self.logger.debug('In next_playback()')

        next_track = self.get_next_track(True)
        if next_track == None:
            return self.handler_input.response_builder.response

        self.logger.debug(f'next_track: {next_track["title"]} by {next_track["artist"]}')

        directive = PlayDirective(play_behavior=PlayBehavior.REPLACE_ALL, audio_item=self.track_to_audio_item(next_track, 0, None))
        self.handler_input.response_builder.add_directive(directive).set_should_end_session(True)

        return self.handler_input.response_builder.response


    def loop_playback(self, enable: bool) -> Response:
        """
        Toggles playlist loop.
        Args:
            enable (bool): If True, enables the loop. If False, disables it.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In loop_playback()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_setting = persistence_attr.get("playback_setting")

        playback_setting["loop"] = enable

        return self.handler_input.response_builder.response


    def shuffle_playback(self, enable: bool) -> Response:
        """
        Toggles shuffle playback mode.
        Args:
            enable (bool): If True, shuffles the playlist. If False, re-sorts it.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In shuffle_playback()')

        self.shuffle_play_order(enable)

        return self.handler_input.response_builder.response


    def retrieve_track_details (self) -> Response:
        """
        Retrieves the details of the current track.
        Returns:
            Response: The response object containing the spoken output with the track details.
        """

        self.logger.debug('In retrieve_track_details()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get the current track
        current_track = self.get_current_track()

        # Ignore the request if there is no track
        if current_track == None:
            return self.handler_input.response_builder.response

        speak_output = data[prompts.SKILL_SONG_DETAILS].format(song=current_track["title"], artist=current_track["artist"])
        self.logger.info(speak_output)

        self.handler_input.response_builder.speak(speak_output).set_should_end_session(True)
        return self.handler_input.response_builder.response


#
# Playback events
#
    def playback_started (self) -> Response:
        """
        Handles the event when playback is started.
        This method only sets the playback session and returns the response.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In playback_started()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        playback_info["in_playback_session"] = True

        return self.handler_input.response_builder.response


    def playback_stopped (self) -> Response:
        """
        Handles the event when playback is stopped.
        This method only saves the playback offset and returns the response.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In playback_stopped()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        playback_info["offset_in_ms"] = self.handler_input.request_envelope.request.offset_in_milliseconds

        return self.handler_input.response_builder.response


    def playback_nearly_finished (self) -> Response:
        """
        Handles the event when playback is nearly finished.
        This method retrieves the next track and queues it for playback.
        Returns:
            Response: The response object with the enqueue directive and the next track
            in audio item format. If there are no more tracks, the response object is empty.
        """

        self.logger.debug('In playback_nearly_finished()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        if playback_info.get("next_stream_enqueued"):
            return self.handler_input.response_builder.response

        next_track = self.get_next_track(False)
        if next_track == None:
            return self.handler_input.response_builder.response

        current_track = self.get_current_track()
        playback_info["next_stream_enqueued"] = True
        self.logger.info(f'Queuing next track: {next_track["title"]} by {next_track["artist"]}')

        directive = PlayDirective(play_behavior=PlayBehavior.ENQUEUE, audio_item=self.track_to_audio_item(next_track, 0, current_track["id"]))
        self.handler_input.response_builder.add_directive(directive).set_should_end_session(True)

        return self.handler_input.response_builder.response


    def playback_finished (self) -> Response:
        """
        Handles the event when playback is finished.
        This method only updates the next playback index (the enqueue is already
        done in the PlaybackNearlyFinishedHandler), resets the playback_session and
        next_stream_enqueued flags and sets the track's offset to 0.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In playback_finished()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")

        # get next track just to update the index
        next_track = self.get_next_track(True)
        if next_track == None:
            return self.handler_input.response_builder.response

        playback_info["in_playback_session"] = False
        playback_info["next_stream_enqueued"] = False
        playback_info["offset_in_ms"] = 0

        self.logger.info(f'Next track: {next_track["title"]} by {next_track["artist"]} updated')
        return self.handler_input.response_builder.response


    def playback_failed (self) -> Response:
        """
        Handles the playback failure scenario
        This method is called when a playback failure occurs. It logs the event,
        and tries with the next track in the queue.
        Returns:
            Response: The response object with no output speech.
        """

        self.logger.debug('In playback_failed()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes

        return self.next_playback()

#
# Plex API utils
#
    def load_music_section (self) -> Response:
        """
        Loads the music section from the Plex server.
        This method attempts to connect to the Plex server using the provided
        configuration and retrieves the default music section. If the section
        is not found or there is a connection error, it handles the exceptions
        and returns an appropriate response.
        Returns:
            Response: The response object containing the speech output in case of error,
            otherwize returns None.
        """

        self.logger.debug('In load_music_section()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        try:
            self.plex_server = PlexServer(config.PMS_SERVER_URL, config.PMS_SERVER_TOKEN)
            self.section = self.plex_server.library.section(config.PMS_DEFAULT_SECTION_NAME)
        except NotFound  as exception:
            speak_output = data[prompts.PMS_SECTION_NOT_FOUND]
            self.logger.error(exception)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response
        except Exception as exception:
            speak_output = data[prompts.PMS_CONNECTION_ERROR]
            self.logger.error(exception)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response


    def set_playlist_name(self, name: str) -> None:
        """
        Sets the playlist name in the persistent attributes.

        Args:
            name (str): The name of the playlist to be set.

        Returns:
            None
        """

        self.logger.debug('In set_playlist_name()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")
        playback_info["playlist_name"] = name


    def add_plex_track(self, plex_track: Track) -> None:
        """
        Adds a Plex track to the playlist.
        Args:
            plex_track (Track): The Plex track to be added. It should be an instance of the Track class.
        Returns:
            None
        """

        self.logger.debug('In add_plex_track()')
        track = {
                "id": str(plex_track.ratingKey),
                "title": plex_track.title,
                "artist": plex_track.grandparentTitle,
                "artist_art": plex_track.url(plex_track.grandparentArt),
                "album": plex_track.parentTitle,
                "album_art": plex_track.url(plex_track.parentThumb),
                "uri": plex_track.getStreamURL().replace("m3u8", "mp3")
                }

        self.add_track(track)


    def add_plex_tracks(self, plex_track_list: List[Track]) -> None:
        """
        Adds a list of Plex tracks to the playlist.
        Args:
            plex_track_list (List[Track]): A list of Plex track objects to be added.
        Returns:
            None
        """

        self.logger.debug('In add_plex_tracks()')
        for plex_track in plex_track_list:
            self.add_plex_track(plex_track)

#
# Plex API control
#
    def play_random_music (self) -> Response:
        """
        Plays a random selection of music tracks.
        This method searches for random tracks. If no tracks are found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_random_music()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for random tracks
        try:
            plex_track_list = self.section.searchTracks(sort='random', maxresults=config.PMS_DEFAULT_MAX_RESULTS)
        except Exception as exception:
            speak_output = data[prompts.PMS_CONNECTION_ERROR]
            self.logger.error(exception)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        if len(plex_track_list) == 0:
            speak_output = data[prompts.PMS_TRACKS_SEARCH_EMPTY]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_tracks(plex_track_list)

        playlist_name = data[prompts.PMS_PLNAME_RANDOM_MUSIC]
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)

        return self.start_playback()


    def play_music_by_artist (self) -> Response:
        """
        Plays a music selection by a specified artist.
        This method searches for music by the specified artist, sorted by popularity
        if available in the plex media server. If no tracks are found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_music_by_artist()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get variable(s) from intent
        artist = get_slot_value_v2(self.handler_input, 'artist')
        if artist is None:
            speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for the artist (deterministic resolution)
        resolution = self.resolve_artist(artist.value)
        if resolution["status"] == "match":
            return self._play_music_by_resolved_artist(resolution["candidates"][0])
        if resolution["status"] == "multiple":
            return self._build_selection_response(
                entity_type="artist",
                query=artist.value,
                candidates=resolution["candidates"],
                continuation={"action": "play_music_by_artist"},
            )

        # not_found: diagnostische Fehlermeldung mit dem empfangenen Slotwert
        return self._build_not_found_response(query=artist.value, entity_label="Künstler")

    def play_song_by_artist (self) -> Response:
        """
        Play a specific song by a given artist.
        This method searches the specific song. If no track is found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_song_by_artist()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get variable(s) from intent
        artist = get_slot_value_v2(self.handler_input, 'artist')
        song = get_slot_value_v2(self.handler_input, 'song')
        if artist is None or song is None:
            speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for the artist (deterministic resolution)
        resolution = self.resolve_artist(artist.value)
        if resolution["status"] == "match":
            return self._play_song_by_resolved_artist(resolution["candidates"][0], song.value)
        if resolution["status"] == "multiple":
            return self._build_selection_response(
                entity_type="artist_for_song",
                query=artist.value,
                candidates=resolution["candidates"],
                continuation={"action": "play_song_by_artist", "song": song.value},
            )

        # not_found: diagnostische Fehlermeldung mit dem empfangenen Slotwert
        return self._build_not_found_response(query=artist.value, entity_label="Künstler")


    def play_album_by_artist (self) -> Response:
        """
        Play a specific album by a given artist.
        This method searches the specific album. If no tracks are found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_album_by_artist()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get variable(s) from intent
        artist = get_slot_value_v2(self.handler_input, 'artist')
        album = get_slot_value_v2(self.handler_input, 'album')
        if artist is None or album is None:
            speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for the artist (deterministic resolution)
        resolution = self.resolve_artist(artist.value)
        if resolution["status"] == "match":
            return self._play_album_by_resolved_artist(resolution["candidates"][0], album.value)
        if resolution["status"] == "multiple":
            return self._build_selection_response(
                entity_type="artist_for_album",
                query=artist.value,
                candidates=resolution["candidates"],
                continuation={"action": "play_album_by_artist", "album": album.value},
            )

        # not_found: diagnostische Fehlermeldung mit dem empfangenen Slotwert
        return self._build_not_found_response(query=artist.value, entity_label="Künstler")


    def play_music_by_genre (self) -> Response:
        """
        Play music by a given genre.
        This method searches music by genre. If no tracks are found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_music_by_genre()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get variable(s) from intent
        genre = get_slot_value_v2(self.handler_input, 'genre')
        if genre is None:
            speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for the style (Plex server is more specfic with style than genre tags)
        try:
            plex_track_list = self.section.searchTracks(sort='random', maxresults=config.PMS_DEFAULT_MAX_RESULTS, style=genre.value)
        except Exception as exception:
            speak_output = data[prompts.PMS_GENRE_SEARCH_ERROR].format(genre.value)
            self.logger.error(exception)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        if len(plex_track_list)==0:
            speak_output = data[prompts.PMS_GENRE_SEARCH_EMPTY].format(genre.value)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_tracks(plex_track_list)

        playlist_name = data[prompts.PMS_PLNAME_MUSIC_BY_GENRE].format(genre.value)
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)
        return self.start_playback()


    def play_playlist (self) -> Response:
        """
        Play a plex playlist.
        This method searches for a specific playlist. If no playlist is found or an error
        occurs during the search, an appropriate response is returned. Otherwise,
        it clears the current playlist, adds the found tracks to the playlist, sets
        the playlist name, and starts playback.
        Returns:
            Response: The response object containing the result of the playback action.
        """

        self.logger.debug('In play_playlist()')

        # get localization data
        data = self.handler_input.attributes_manager.request_attributes["_"]

        # Get variable(s) from intent
        playlist = get_slot_value_v2(self.handler_input, 'playlist')
        if playlist is None:
            speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Get the music section
        response = self.load_music_section()
        if response is not None:
            return response

        # Search for the playlist (Unicode-Varianten + Aliasbereich "playlists")
        plex_playlist = self._resolve_playlist(playlist.value)
        if plex_playlist is None:
            speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(playlist.value)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        # Defensive Prüfung: Playlist-Objekt oder Track-Liste
        if hasattr(plex_playlist, "items"):
            playlist_title = plex_playlist.title
            try:
                plex_track_list = plex_playlist.items()
            except Exception as exception:
                speak_output = data[prompts.PMS_PLAYLIST_SEARCH_ERROR].format(playlist.value)
                self.logger.error(exception)
                return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response
        else:
            playlist_title = playlist.value
            plex_track_list = plex_playlist

        if len(plex_track_list) == 0:
            speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(playlist.value)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_tracks(plex_track_list)

        playlist_name = data[prompts.PMS_PLNAME_PLAYLIST].format(playlist_title)
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)
        return self.start_playback()

#
# Deterministic search resolution
#
    def _artist_candidate(self, plex_artist) -> dict:
        """
        Erzeugt das Kandidatenformat für einen Plex-Künstler.

        Args:
            plex_artist: Plex-Künstlerobjekt.

        Returns:
            Dict mit "rating_key" (Plex-ID) und "name" (tatsächlicher Plex-Name).
        """
        return {
            "rating_key": str(plex_artist.ratingKey),
            "name": plex_artist.title,
        }

    def resolve_artist(self, query: str) -> dict:
        """
        Löst einen Künstlernamen deterministisch gegen Plex auf.

        Suchreihenfolge:
        1. Exakte Plex-Suche mit dem unveränderten Query (casefold-Vergleich).
        2. Alias aus search_aliases.json (Rohwert + normalisierte Leerzeichen),
           Aliasziel wird gegen tatsächlich vorhandene Plex-Künstler validiert.
        3. Vergleichsschlüssel über alle Plex-Künstler (get_comparison_key()).

        Es gibt keine Teilstring-Suche und kein Fuzzy Matching. Mehrere
        plausible Treffer werden als Kandidaten zurückgegeben.

        Returns:
            Dict mit "status" ("match" | "multiple" | "not_found"),
            "query", "match_source" ("exact" | "alias" | "normalized" | None)
            und "candidates" (Liste von Kandidaten-Dicts).
        """
        result = {
            "status": "not_found",
            "query": query,
            "match_source": None,
            "candidates": [],
        }

        if not query or not query.strip():
            return result

        # 1. Exakte Plex-Suche mit dem unveränderten Query
        try:
            exact_results = self.section.searchArtists(title=query)
        except Exception as exception:
            self.logger.error("Fehler bei der exakten Künstlersuche für '%s': %s", query, exception)
            exact_results = []

        exact_matches = [
            artist for artist in exact_results
            if str(artist.title).casefold() == query.casefold()
        ]
        if len(exact_matches) == 1:
            result["status"] = "match"
            result["match_source"] = "exact"
            result["candidates"] = [self._artist_candidate(exact_matches[0])]
            return result
        if len(exact_matches) > 1:
            result["status"] = "multiple"
            result["match_source"] = "exact"
            result["candidates"] = [self._artist_candidate(artist) for artist in exact_matches]
            return result

        # 2. Alias nachschlagen (zentrale Funktion, drei Schlüsselformen)
        aliases = search_aliases.get_aliases()
        artist_aliases = aliases.get("artists", {})
        alias_target = search_aliases.find_alias(query, artist_aliases)

        if alias_target:
            try:
                alias_results = self.section.searchArtists(title=alias_target)
            except Exception as exception:
                self.logger.error("Fehler bei der Alias-Künstlersuche für '%s': %s", alias_target, exception)
                alias_results = []

            alias_matches = [
                artist for artist in alias_results
                if str(artist.title).casefold() == alias_target.casefold()
            ]
            if len(alias_matches) == 1:
                result["status"] = "match"
                result["match_source"] = "alias"
                result["candidates"] = [self._artist_candidate(alias_matches[0])]
                return result
            if len(alias_matches) > 1:
                result["status"] = "multiple"
                result["match_source"] = "alias"
                result["candidates"] = [self._artist_candidate(artist) for artist in alias_matches]
                return result

        # 3. Suchvarianten gezielt gegen Plex suchen und den
        #    Vergleichsschlüssel prüfen. Anders als früher wird NICHT die
        #    gesamte Künstlerliste geladen (Timeout-Risiko bei großen
        #    Bibliotheken und Alexa-hosted Lambdas), sondern für jede
        #    Suchvariante eine schnelle serverseitige Substring-Suche
        #    ausgeführt. Die Exaktheit stellt der Vergleichsschlüssel sicher.
        normalizer = get_normalizer()
        matched_artists = []
        seen_rating_keys = set()

        search_variants = list(normalizer.get_search_variants(query))
        comparison_variant = normalizer.get_comparison_key(query)
        if comparison_variant and comparison_variant not in search_variants:
            search_variants.append(comparison_variant)

        for variant in search_variants:
            try:
                variant_results = self.section.searchArtists(title=variant)
            except Exception as exception:
                self.logger.error("Fehler bei der Variantensuche für '%s': %s", variant, exception)
                variant_results = []

            for artist in variant_results:
                if normalizer.get_comparison_key(str(artist.title)) == normalizer.get_comparison_key(query):
                    rating_key = str(artist.ratingKey)
                    if rating_key not in seen_rating_keys:
                        seen_rating_keys.add(rating_key)
                        matched_artists.append(artist)

        if len(matched_artists) == 1:
            result["status"] = "match"
            result["match_source"] = "normalized"
            result["candidates"] = [self._artist_candidate(matched_artists[0])]
            return result
        if len(matched_artists) > 1:
            result["status"] = "multiple"
            result["match_source"] = "normalized"
            result["candidates"] = [self._artist_candidate(artist) for artist in matched_artists]
            return result

        return result

    def _build_selection_response(self, entity_type: str, query: str, candidates: list, continuation: dict) -> Response:
        """
        Baut die nummerierte Auswahlantwort (Sprache + SimpleCard) und speichert
        den Auswahlzustand in den Session-Attributen.

        Args:
            entity_type: Art der Entität ("artist", "artist_for_song", ...).
            query: Vom Nutzer gesprochener Rohwert.
            candidates: Liste von Kandidaten-Dicts (höchstens drei werden genannt).
            continuation: Dict mit "action" und ggf. "song"/"album".
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]

        session_attr = self.handler_input.attributes_manager.session_attributes
        session_attr["pending_selection"] = {
            "entity_type": entity_type,
            "query": query,
            "continuation": continuation,
            "candidates": candidates,
        }

        # Höchstens drei Kandidaten vorlesen
        spoken_candidates = candidates[:3]
        count = len(spoken_candidates)

        if count == 1:
            prompt_text = data[prompts.SEARCH_SELECTION_PROMPT_ONE]
        elif count == 2:
            prompt_text = data[prompts.SEARCH_SELECTION_PROMPT_TWO]
        else:
            prompt_text = data[prompts.SEARCH_SELECTION_PROMPT_THREE]

        parts = [data[prompts.SEARCH_MULTIPLE_ARTISTS].format(count=self._number_word(count))]
        for index, candidate in enumerate(spoken_candidates, start=1):
            parts.append(data[prompts.SEARCH_SELECTION_ITEM].format(
                number=self._number_word(index), name=candidate["name"]))
        parts.append(prompt_text)
        speak_output = " ".join(parts)

        # SimpleCard mit derselben nummerierten Liste
        card_lines = [
            data.get(prompts.SEARCH_CARD_UNDERSTOOD, "Verstanden: {query}").format(query=query)
        ]
        for index, candidate in enumerate(spoken_candidates, start=1):
            card_lines.append("{}. {}".format(index, candidate["name"]))
        card_lines.append(prompt_text)
        card = SimpleCard(
            title=data.get(prompts.SEARCH_CARD_TITLE_SELECTION, "Mein Plex – Auswahl"),
            content="\n".join(card_lines),
        )

        self.handler_input.response_builder.speak(speak_output).ask(speak_output).set_card(card)
        self.logger.info(speak_output)
        return self.handler_input.response_builder.response

    def _build_not_found_response(self, query: str, entity_label: str) -> Response:
        """
        Baut die diagnostische Fehlermeldung (Sprache + SimpleCard) für einen
        nicht gefundenen Künstler. Der tatsächlich empfangene Slotwert wird
        genannt.
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        speak_output = data[prompts.SEARCH_ARTIST_NOT_FOUND_DIAGNOSTIC].format(query=query)

        card_lines = [
            data.get(prompts.SEARCH_CARD_UNDERSTOOD, "Verstanden: {query}").format(query=query),
            data.get(prompts.SEARCH_CARD_SEARCHED_AS, "Gesucht als: {entity}").format(entity=entity_label),
            data.get(prompts.SEARCH_CARD_RESULT, "Ergebnis: Kein Treffer"),
        ]
        card = SimpleCard(
            title=data.get(prompts.SEARCH_CARD_TITLE_NOT_FOUND, "Mein Plex – Suche"),
            content="\n".join(card_lines),
        )

        self.handler_input.response_builder.speak(speak_output).ask(speak_output).set_card(card)
        self.logger.info(speak_output)
        return self.handler_input.response_builder.response

    def _number_word(self, number: int) -> str:
        """
        Liefert das lokalisierte Zahlwort für 1-3 (für nummerierte Listen).
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        key = {
            1: prompts.SEARCH_NUMBER_ONE,
            2: prompts.SEARCH_NUMBER_TWO,
            3: prompts.SEARCH_NUMBER_THREE,
        }.get(number)
        if key:
            return data.get(key, str(number))
        return str(number)

    def _load_artist_by_rating_key(self, rating_key: str):
        """
        Lädt einen Plex-Künstler ausschließlich über seine Plex-ID (ratingKey).
        Es findet keine Namenssuche statt.
        """
        try:
            return self.plex_server.fetchItem(int(rating_key))
        except Exception as exception:
            self.logger.error("Fehler beim Laden des Künstlers mit ratingKey %s: %s", rating_key, exception)
            return None

    def _play_music_by_resolved_artist(self, candidate: dict) -> Response:
        """
        Spielt die Musik eines bereits aufgelösten Künstlers.

        Der Künstler wird über seine Plex-ID geladen. Für Playlistname und
        Erfolgsansage wird der tatsächliche Plex-Name verwendet.
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        plex_artist = self._load_artist_by_rating_key(candidate["rating_key"])
        if plex_artist is None:
            speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(candidate["name"])
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        try:
            plex_track_list = plex_artist.popularTracks()
        except Exception as exception:
            self.logger.error("Fehler beim Laden der beliebten Tracks von %s: %s", plex_artist.title, exception)
            plex_track_list = []

        if len(plex_track_list) == 0:
            # No popular tracks, so look for any tracks
            try:
                plex_track_list = plex_artist.tracks()
            except Exception as exception:
                self.logger.error("Fehler beim Laden der Tracks von %s: %s", plex_artist.title, exception)
                plex_track_list = []

        if len(plex_track_list) == 0:
            speak_output = data[prompts.PMS_TRACKS_SEARCH_EMPTY]
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_tracks(plex_track_list)

        playlist_name = data[prompts.PMS_PLNAME_MUSIC_BY_ARTIST].format(plex_artist.title)
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.SEARCH_PLAYING_ARTIST].format(artist=plex_artist.title)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)
        return self.start_playback()

    def _find_track_in_artist(self, plex_artist, song: str):
        """
        Sucht einen Song ausschließlich innerhalb eines Künstlers.

        Zuerst wird der Aliasbereich "songs" geprüft, danach die bestehenden
        Unicode-/Umlaut-Varianten. Es gibt keine globale Songsuche.
        """
        aliases = search_aliases.get_aliases()
        song_aliases = aliases.get("songs", {})
        alias_target = search_aliases.find_alias(song, song_aliases)

        if alias_target:
            try:
                return plex_artist.track(alias_target)
            except NotFound:
                pass
            except Exception as exception:
                self.logger.error("Fehler bei der Song-Aliassuche für '%s': %s", alias_target, exception)
                return None

        normalizer = get_normalizer()
        for variant in normalizer.get_search_variants(song):
            try:
                return plex_artist.track(variant)
            except NotFound:
                continue
            except Exception as exception:
                self.logger.error("Fehler bei der Songsuche für '%s': %s", variant, exception)
                return None
        return None

    def _play_song_by_resolved_artist(self, candidate: dict, song: str) -> Response:
        """
        Spielt einen Song innerhalb eines bereits aufgelösten Künstlers.
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        plex_artist = self._load_artist_by_rating_key(candidate["rating_key"])
        if plex_artist is None:
            speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(candidate["name"])
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        plex_track = self._find_track_in_artist(plex_artist, song)
        if plex_track is None:
            speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song=song, artist=plex_artist.title)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_track(plex_track)

        playlist_name = data[prompts.PMS_PLNAME_SONG].format(song=plex_track.title, artist=plex_artist.title)
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)
        return self.start_playback()

    def _find_album_in_artist(self, plex_artist, album: str):
        """
        Sucht ein Album ausschließlich innerhalb eines Künstlers.

        Zuerst wird der Aliasbereich "albums" geprüft, danach die bestehenden
        Unicode-/Umlaut-Varianten.
        """
        aliases = search_aliases.get_aliases()
        album_aliases = aliases.get("albums", {})
        alias_target = search_aliases.find_alias(album, album_aliases)

        if alias_target:
            try:
                return plex_artist.album(alias_target)
            except NotFound:
                pass
            except Exception as exception:
                self.logger.error("Fehler bei der Album-Aliassuche für '%s': %s", alias_target, exception)
                return None

        normalizer = get_normalizer()
        for variant in normalizer.get_search_variants(album):
            try:
                return plex_artist.album(variant)
            except NotFound:
                continue
            except Exception as exception:
                self.logger.error("Fehler bei der Albumsuche für '%s': %s", variant, exception)
                return None
        return None

    def _play_album_by_resolved_artist(self, candidate: dict, album: str) -> Response:
        """
        Spielt ein Album innerhalb eines bereits aufgelösten Künstlers.
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        plex_artist = self._load_artist_by_rating_key(candidate["rating_key"])
        if plex_artist is None:
            speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(candidate["name"])
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        plex_album = self._find_album_in_artist(plex_artist, album)
        if plex_album is None:
            speak_output = data[prompts.PMS_ALBUM_SEARCH_EMPTY].format(album=album, artist=plex_artist.title)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        try:
            plex_track_list = plex_album.tracks()
        except Exception as exception:
            speak_output = data[prompts.PMS_ALBUM_SEARCH_ERROR].format(album, plex_artist.title)
            self.logger.error(exception)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        if len(plex_track_list) == 0:
            speak_output = data[prompts.PMS_ALBUM_SEARCH_EMPTY].format(album=album, artist=plex_artist.title)
            self.logger.error(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        self.clear_playlist()
        self.add_plex_tracks(plex_track_list)

        playlist_name = data[prompts.PMS_PLNAME_ALBUM].format(album=plex_album.title, artist=plex_artist.title)
        self.set_playlist_name(playlist_name)
        speak_output = data[prompts.PMS_PLAYING].format(playlist_name)

        self.handler_input.response_builder.speak(speak_output)
        self.logger.info(speak_output)
        return self.start_playback()

    def _resolve_playlist(self, query: str):
        """
        Löst eine Playlist deterministisch auf (Unicode-Varianten + Alias).

        Playlists werden nur mit Playlists verglichen.
        """
        aliases = search_aliases.get_aliases()
        playlist_aliases = aliases.get("playlists", {})
        alias_target = search_aliases.find_alias(query, playlist_aliases)

        normalizer = get_normalizer()
        variants = normalizer.get_search_variants(query)
        if alias_target:
            variants = [alias_target] + variants

        for variant in variants:
            try:
                result = self.section.playlist(title=variant)
                if result is None:
                    continue
                # Defensive Prüfung: PlexAPI liefert je nach Version ein
                # Playlist-Objekt oder direkt eine Track-Liste.
                if hasattr(result, "items"):
                    return result
                if isinstance(result, list):
                    return result
                self.logger.error("Unerwarteter Rückgabetyp der Playlistsuche für '%s': %s",
                                  variant, type(result))
                return None
            except NotFound:
                continue
            except Exception as exception:
                self.logger.error("Fehler bei der Playlistsuche für '%s': %s", variant, exception)
                return None
        return None

    def continue_after_selection(self, selection_index: int) -> Response:
        """
        Setzt eine Aktion nach nummerierter Auswahl fort.

        Der gewählte Kandidat wird ausschließlich über seine Plex-ID
        (ratingKey) geladen – es findet keine erneute Namenssuche statt.
        """
        data = self.handler_input.attributes_manager.request_attributes["_"]
        session_attr = self.handler_input.attributes_manager.session_attributes
        pending = session_attr.get("pending_selection")

        if not pending:
            speak_output = data[prompts.SEARCH_SELECTION_MISSING]
            self.logger.info(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        candidates = pending.get("candidates", [])
        if selection_index < 1 or selection_index > len(candidates):
            speak_output = data[prompts.SEARCH_SELECTION_INVALID].format(
                first=self._number_word(1), last=self._number_word(len(candidates)))
            self.logger.info(speak_output)
            return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

        candidate = candidates[selection_index - 1]
        continuation = pending.get("continuation", {})
        action = continuation.get("action")

        # Auswahlzustand löschen, bevor die Aktion fortgesetzt wird
        session_attr.pop("pending_selection", None)

        if action == "play_music_by_artist":
            return self._play_music_by_resolved_artist(candidate)
        if action == "play_song_by_artist":
            return self._play_song_by_resolved_artist(candidate, continuation.get("song"))
        if action == "play_album_by_artist":
            return self._play_album_by_resolved_artist(candidate, continuation.get("album"))

        speak_output = data[prompts.SKILL_EXCEPTION]
        self.logger.error("Unbekannte continuation action: %s", action)
        return self.handler_input.response_builder.speak(speak_output).ask(speak_output).response

    def set_playlist_name(self, name: str) -> None:
        """
        Sets the playlist name in the persistent attributes.

        Args:
            name (str): The name of the playlist to be set.

        Returns:
            None
        """

        self.logger.debug('In set_playlist_name()')
        persistence_attr = self.handler_input.attributes_manager.persistent_attributes
        playback_info = persistence_attr.get("playback_info")
        playback_info["playlist_name"] = name