# AskPlex Unicode Patch - Integration Guide

## 📋 Übersicht

Dieser Patch behebt die Umlaut-Probleme in askplex durch robuste Search-Fallbacks:

✅ **Vorher:**
```
User: "Alexa, spiele die ärzte"
Plex DB: "Die Ärzte"
Result: ❌ NICHT GEFUNDEN (case mismatch)
```

✅ **Nachher:**
```
User: "Alexa, spiele die ärzte"
Plex DB: "Die Ärzte"
Result: ✅ GEFUNDEN (automatisches fallback zu "Die Ärzte")
```

---

## 🚀 Installation

### Option 1: Schnell (für Dein Fork)

1. Kopiere `unicode_normalizer.py` in dein askplex Fork:
   ```
   lambda/askplex/unicode_normalizer.py
   ```

2. Kopiere `test_unicode_normalizer.py` für Tests:
   ```
   lambda/tests/test_unicode_normalizer.py
   ```

3. Wende die Controller-Änderungen an (siehe nächster Abschnitt)

### Option 2: Production-Deploy (AWS Lambda)

1. ZIP mit allen Dateien:
   ```
   lambda/
   ├── askplex/
   │   ├── __init__.py
   │   ├── controller.py        ← MODIFIZIERT
   │   ├── unicode_normalizer.py ← NEU
   │   └── ...
   ├── lambda_function.py       ← MODIFIZIERT (encoding fix)
   └── requirements.txt
   ```

2. Hochladen wie gewöhnlich zu AWS Lambda

---

## 🔧 Integrations-Änderungen

### In `lambda_function.py` (JSON Encoding Fix)

**ÄNDERUNG #1: LocalizationInterceptor**

Suche nach:
```python
with open("askplex/language_strings.json") as language_prompts:
    language_data = json.load(language_prompts)
```

Ersetze durch:
```python
with open("askplex/language_strings.json", encoding='utf-8') as language_prompts:
    language_data = json.load(language_prompts)
```

**Warum:** Garantiert UTF-8 Handling auch auf non-UTF-8 Systemen.

---

### In `controller.py` (Unicode-Aware Searches)

**ÄNDERUNG #1: Import hinzufügen**

Am Anfang der Datei (nach anderen Imports):
```python
from askplex.unicode_normalizer import SearchStrategy, get_normalizer
```

**ÄNDERUNG #2: In `__init__`-Methode der Controller-Klasse**

```python
def __init__(self, logger, handler_input):
    self.logger = logger
    self.handler_input = handler_input
    # ... andere Init-Code ...

    # NEU: Search Strategy für robuste Suche
    self.search_strategy = SearchStrategy()
    self.normalizer = get_normalizer()
```

**ÄNDERUNG #3: Play by Artist (searchArtists)**

**VORHER:**
```python
def play_music_by_artist(self) -> Response:
    data = self.handler_input.attributes_manager.request_attributes["_"]
    artist = get_slot_value_v2(self.handler_input, 'artist')

    if artist is None:
        speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
        return response

    try:
        artist_results = self.section.searchArtists(title=artist.value)
    except Exception as exception:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(artist.value)
        return response

    if len(artist_results) == 0:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return response
```

**NACHHER:**
```python
def play_music_by_artist(self) -> Response:
    data = self.handler_input.attributes_manager.request_attributes["_"]
    artist = get_slot_value_v2(self.handler_input, 'artist')

    if artist is None:
        speak_output = data[prompts.SKILL_INTENT_SLOTS_MISSING]
        return response

    try:
        # NEUE METHODE: Mit Unicode-Fallback
        artist_results = self.search_strategy.search_with_fallback(
            search_func=self.section.searchArtists,
            query=artist.value
        )
    except Exception as exception:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_ERROR].format(artist.value)
        return response

    if len(artist_results) == 0:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return response
```

**ÄNDERUNG #4: Play Song by Artist (searchTracks)**

**VORHER:**
```python
def play_song_by_artist(self) -> Response:
    # ... Setup ...

    artist_results = self.section.searchArtists(title=artist.value)
    if len(artist_results) == 0:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return response

    try:
        plex_track = artist_results[0].track(song.value)
    except:
        speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song.value)
```

**NACHHER:**
```python
def play_song_by_artist(self) -> Response:
    # ... Setup ...

    # Kunstler mit Fallback
    artist_results = self.search_strategy.search_with_fallback(
        search_func=self.section.searchArtists,
        query=artist.value
    )
    if len(artist_results) == 0:
        speak_output = data[prompts.PMS_ARTIST_SEARCH_EMPTY].format(artist.value)
        return response

    try:
        # Song mit Fallback
        plex_track = self._search_track_with_fallback(
            artist_results[0],
            song.value
        )
        if plex_track is None:
            speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song.value)
            return response
    except Exception as e:
        speak_output = data[prompts.PMS_SONG_SEARCH_EMPTY].format(song.value)
```

**ÄNDERUNG #5: Play Album by Artist**

**VORHER:**
```python
def play_album_by_artist(self) -> Response:
    # ...
    artist_results = self.section.searchArtists(title=artist.value)
    # ...
    plex_track_list = artist_results[0].album(album.value).tracks()
```

**NACHHER:**
```python
def play_album_by_artist(self) -> Response:
    # ...
    artist_results = self.search_strategy.search_with_fallback(
        search_func=self.section.searchArtists,
        query=artist.value
    )
    # ...
    # Album mit Fallback
    plex_album = self._search_album_with_fallback(
        artist_results[0],
        album.value
    )
    if plex_album is None:
        speak_output = data[prompts.PMS_ALBUM_SEARCH_EMPTY].format(album.value)
        return response

    plex_track_list = plex_album.tracks()
```

**ÄNDERUNG #6: Play by Genre**

**VORHER:**
```python
def play_music_by_genre(self) -> Response:
    # ...
    plex_track_list = self.section.searchTracks(
        sort='random',
        style=genre.value,
        maxresults=config.PMS_DEFAULT_MAX_RESULTS
    )
```

**NACHHER:**
```python
def play_music_by_genre(self) -> Response:
    # ...
    plex_track_list = self.search_strategy.search_with_fallback(
        search_func=lambda title='', **kwargs: self.section.searchTracks(
            sort='random',
            style=genre.value,
            maxresults=config.PMS_DEFAULT_MAX_RESULTS
        ),
        query=genre.value
    )
```

**ÄNDERUNG #7: Play Playlist**

**VORHER:**
```python
def play_playlist(self) -> Response:
    # ...
    try:
        plex_track_list = self.section.playlist(title=playlist.value).tracks()
    except:
        speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(playlist.value)
```

**NACHHER:**
```python
def play_playlist(self) -> Response:
    # ...
    try:
        plex_playlist = self._search_playlist_with_fallback(playlist.value)
        if plex_playlist is None:
            speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(playlist.value)
            return response
        plex_track_list = plex_playlist.tracks()
    except Exception as e:
        speak_output = data[prompts.PMS_PLAYLIST_SEARCH_EMPTY].format(playlist.value)
```

---

## 🆕 Neue Helper-Methoden (in Controller-Klasse hinzufügen)

```python
def _search_track_with_fallback(self, artist, song_name: str):
    """Search for track with Umlaut fallback."""
    variants = self.normalizer.get_search_variants(song_name)

    for variant in variants:
        try:
            track = artist.track(variant)
            if track:
                self.logger.info(f"Track found with variant: '{variant}'")
                return track
        except Exception as e:
            self.logger.debug(f"Track search error with '{variant}': {e}")
            continue

    return None


def _search_album_with_fallback(self, artist, album_name: str):
    """Search for album with Umlaut fallback."""
    variants = self.normalizer.get_search_variants(album_name)

    for variant in variants:
        try:
            album = artist.album(variant)
            if album:
                self.logger.info(f"Album found with variant: '{variant}'")
                return album
        except Exception as e:
            self.logger.debug(f"Album search error with '{variant}': {e}")
            continue

    return None


def _search_playlist_with_fallback(self, playlist_name: str):
    """Search for playlist with Umlaut fallback."""
    variants = self.normalizer.get_search_variants(playlist_name)

    for variant in variants:
        try:
            playlist = self.section.playlist(title=variant)
            if playlist:
                self.logger.info(f"Playlist found with variant: '{variant}'")
                return playlist
        except Exception as e:
            self.logger.debug(f"Playlist search error with '{variant}': {e}")
            continue

    return None
```

---

## 🧪 Testen

### 1. Lokale Unit Tests

```bash
cd lambda
python -m pytest tests/test_unicode_normalizer.py -v
```

Erwartet Output:
```
test_die_aerzte_scenario PASSED
test_bjork_scenario PASSED
test_case_variations PASSED
test_umlaut_removal PASSED
```

### 2. Integration Test (manuell)

```python
from askplex.unicode_normalizer import UnicodeNormalizer

normalizer = UnicodeNormalizer()

# Test 1: Die Ärzte
variants = normalizer.get_search_variants("die ärzte")
print("Variants for 'die ärzte':")
for i, v in enumerate(variants, 1):
    print(f"  {i}. {v}")

# Test 2: Björk
match, score = normalizer.get_best_match(
    "bjork",
    ["Björk", "Rammstein"]
)
print(f"\nBest match for 'bjork': {match} (score: {score})")

# Test 3: Umlaut removal
no_umlaut = normalizer._remove_umlauts("Schöne Musik")
print(f"\nUmlaut removal: 'Schöne Musik' → '{no_umlaut}'")
```

Erwartet:
```
Variants for 'die ärzte':
  1. die ärzte
  2. Die Ärzte
  3. DIE ÄRZTE
  4. die aerzte
  ...

Best match for 'bjork': Björk (score: 2)

Umlaut removal: 'Schöne Musik' → 'Schone Musik'
```

### 3. AWS Lambda Test

Nach Deploy:
```
Test Event:
{
  "request": {
    "intent": {
      "name": "PlayMusicByArtist",
      "slots": {
        "artist": {
          "value": "die ärzte"
        }
      }
    }
  }
}
```

Erwartet: Findet "Die Ärzte" auch wenn in Plex als "Die Ärzte" gespeichert

---

## 📊 Fallback-Priorität

Die `unicode_normalizer` versucht Suchen in dieser Reihenfolge:

1. **Original Query** - "die ärzte" (wenn es zufällig passt)
2. **Title Case** - "Die Ärzte" ← **Meistens erfolgreich!**
3. **Lower Case** - "die ärzte"
4. **Upper Case** - "DIE ÄRZTE"
5. **Umlaut Variant** - "die aerzte" ← **Fallback für alte DBs**
6. **Diacritics Removed** - "die aerzte" ← **Last Resort**

Stoppt sobald Ergebnisse gefunden werden → sehr schnell!

---

## ⚠️ Wichtige Hinweise

### Performance
- ✅ **Schnell:** Stoppt nach erstem Match
- ✅ **Effizient:** Meisten Suchen nur 1-2 Versuche
- ⚠️ **Logging:** Bei vielen Varianten Logging enablen nur im DEBUG-Modus

### Sicherheit
- ✅ Keine Breaking Changes
- ✅ Backward-kompatibel
- ✅ UTF-8 safe

### Datenschutz
- ✅ Keine Daten an externe Services
- ✅ Lokale Normalisierung nur
- ✅ Keine neuen API-Calls

---

## 📝 Changelog

### Version 1.0
- ✅ Unicode Normalizer hinzugefügt
- ✅ Case-Fallback implementiert
- ✅ Umlaut-Varianten hinzugefügt
- ✅ UTF-8 Encoding Fix für JSON
- ✅ Umfassende Tests

### Tested mit
- ✅ Python 3.8+
- ✅ AWS Lambda (Python 3.11)
- ✅ German, English, Spanish locales

---

## 🤝 Support

### Probleme?

1. **Suche funktioniert nicht:**
   - Prüfe Plex Datenbank auf exakte Schreibweise
   - Aktiviere DEBUG-Logging: `SKILL_LOG_LEVEL = logging.DEBUG`
   - Check CloudWatch logs für Varianten-Versuche

2. **Performance-Probleme:**
   - Reduziere MAX_RESULTS in config.py
   - Normalisiere Plex-Datenbank auf konsistente Namensgebung

3. **Encoding-Fehler:**
   - Stelle sicher encoding='utf-8' in lambda_function.py
   - Test lokal mit `test_unicode_normalizer.py`

---

## 📚 Weitere Ressourcen

- [Unicode HOWTO in Python](https://docs.python.org/3/howto/unicode.html)
- [PlexAPI Documentation](https://python-plexapi.readthedocs.io/)
- [Alexa Skills SDK](https://github.com/alexa/alexa-skills-kit-sdk-for-python)
