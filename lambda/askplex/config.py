# -*- coding: utf-8 -*-
"""
Konfigurationsvorlage für AskPlex.

Diese Datei ist die versionierte Vorlage (Default). Sie wird NIE direkt
bearbeitet. Stattdessen wird sie einmalig nach `config.py` kopiert und dort
die eigenen Werte eingetragen:

    cp lambda/askplex/config.example.py lambda/askplex/config.py

`config.py` ist in der .gitignore ausgenommen und wird daher bei
`git pull` / `git checkout` niemals überschrieben.
"""
import logging

# Loglevel des Skills (DEBUG, INFO, WARNING, ERROR)
SKILL_LOG_LEVEL = logging.INFO

# Plex Media Server config
# URL deines Plex-Servers, z. B. 'http://192.168.1.10:32400' oder 'https://plex.example.com'
PMS_SERVER_URL = 'https://'

# Plex API Token (Plex-Einstellungen -> Server -> Allgemein -> "Token")
PMS_SERVER_TOKEN = ''

# Name der Musik-Bibliothek (Section) auf deinem Plex-Server, z. B. 'Musik'
PMS_DEFAULT_SECTION_NAME = ''

# Maximale Anzahl an Tracks, die bei einer Suche geladen werden
PMS_DEFAULT_MAX_RESULTS = 100