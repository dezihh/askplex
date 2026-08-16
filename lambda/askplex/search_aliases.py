# -*- coding: utf-8 -*-
"""
Zentraler Alias-Loader für die deterministische Suche.

Lädt die Aliasdatei `search_aliases.json` genau einmal (Modulinstanz) und
stellt die Aliasbereiche nach Entitätstyp getrennt bereit. Eine fehlende oder
ungültige Aliasdatei darf die Lambda-Funktion niemals zum Absturz bringen –
in diesem Fall werden leere Aliasbereiche verwendet.
"""

import json
import os
import logging

from .unicode_normalizer import get_normalizer

logger = logging.getLogger(__name__)

ALIAS_PATH = os.path.join(os.path.dirname(__file__), "search_aliases.json")

_EMPTY_ALIASES = {
    "artists": {},
    "songs": {},
    "albums": {},
    "playlists": {},
}

_aliases = None


def load_aliases(alias_path: str = ALIAS_PATH) -> dict:
    """
    Lädt die Aliasdatei und normalisiert die Schlüssel (casefold).

    Args:
        alias_path: Pfad zur Aliasdatei (Standard: neben diesem Modul).

    Returns:
        Dict mit den Bereichen "artists", "songs", "albums", "playlists".
        Bei einem Ladefehler werden leere Aliasbereiche zurückgegeben.
    """
    try:
        with open(alias_path, encoding="utf-8") as alias_file:
            data = json.load(alias_file)

        if not isinstance(data, dict):
            raise ValueError("Aliasdatei ist kein JSON-Objekt")

        result = {key: {} for key in _EMPTY_ALIASES}
        for key in result:
            section = data.get(key, {})
            if isinstance(section, dict):
                result[key] = {
                    str(alias_key).casefold(): str(alias_value)
                    for alias_key, alias_value in section.items()
                }
        return result
    except Exception as exception:
        logger.error("Fehler beim Laden der Aliasdatei %s: %s", alias_path, exception)
        return {key: {} for key in _EMPTY_ALIASES}


def get_aliases() -> dict:
    """
    Gibt die einmalig geladene Aliasinstanz zurück (Modul-Singleton).

    Returns:
        Dict mit den Aliasbereichen nach Entitätstyp.
    """
    global _aliases
    if _aliases is None:
        _aliases = load_aliases()
    return _aliases


def reset_aliases() -> None:
    """
    Setzt die gecachte Aliasinstanz zurück (für Tests).
    """
    global _aliases
    _aliases = None


def find_alias(query: str, aliases: dict):
    """
    Löst eine Anfrage gegen einen Aliasbereich deterministisch auf.

    Es werden nacheinander drei Schlüsselformen geprüft, damit eine einzige
    Aliasschreibweise möglichst viele Sprechvarianten abdeckt:

    1. Der rohe Anfragewert (casefold), z. B. ``a. b. c. d.``
    2. Leerzeichen-normalisiert, z. B. ``a. c. d. c.``
    3. Vergleichsschlüssel (Satzzeichen/Leerzeichen/Großschreibung
       ignoriert), z. B. ``abcd``

    Ein Eintrag ``"abcd": "AB/CD"`` fängt damit automatisch ``AB/CD``,
    ``ABCD``, ``A B C D``, ``A.B.C.D.`` und ``a. b. c. d.`` ab.

    Args:
        query: Vom Nutzer gesprochener Rohwert.
        aliases: Aliasbereich als Dict (Schlüssel casefold-normalisiert).

    Returns:
        Aliasziel (kanonischer Plex-Name) oder None.
    """
    if not query or not aliases:
        return None

    candidates = [
        query.casefold(),
        " ".join(query.split()).casefold(),
        get_normalizer().get_comparison_key(query),
    ]
    for candidate in candidates:
        if candidate in aliases:
            return aliases[candidate]
    return None