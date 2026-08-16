# -*- coding: utf-8 -*-
"""
Tests für die Alexa-Interaction-Models: Sample Utterances dürfen nur
Unicode-Buchstaben, Leerzeichen, Punkte, Unterstriche, Apostrophe,
Bindestriche und Slot-Platzhalter ({...}) enthalten.
"""

import json
import glob
import os
import unicodedata

import pytest

INTERACTION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skill-package", "interactionModels", "custom",
)

ALLOWED_EXTRA = set("._'-{}")
COMBINING_CATEGORIES = {"Mn", "Mc", "Me"}


def _find_interaction_files():
    return sorted(glob.glob(os.path.join(INTERACTION_DIR, "*.json")))


def _samples_from_file(path):
    with open(path, encoding="utf-8") as model_file:
        data = json.load(model_file)
    language_model = data["interactionModel"]["languageModel"]
    for intent in language_model.get("intents", []):
        for sample in intent.get("samples", []):
            yield intent.get("name"), sample


def _invalid_characters(sample):
    return [
        char for char in sample
        if not (char.isalnum() or char.isspace() or char in ALLOWED_EXTRA)
        and unicodedata.category(char) not in COMBINING_CATEGORIES
    ]


@pytest.mark.parametrize(
    "model_file",
    _find_interaction_files(),
    ids=lambda path: os.path.basename(path),
)
class TestSampleUtterances:
    def test_all_samples_contain_only_allowed_characters(self, model_file):
        problems = []
        for intent_name, sample in _samples_from_file(model_file):
            invalid = _invalid_characters(sample)
            if invalid:
                problems.append("{}: {!r} -> {}".format(intent_name, sample, sorted(set(invalid))))
        assert not problems, "Ungültige Zeichen in Sample Utterances:\n{}".format("\n".join(problems))
