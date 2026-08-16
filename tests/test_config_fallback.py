# -*- coding: utf-8 -*-
"""
Tests für den config.py-Fallback.

config.py ist bewusst NICHT versioniert (sensible Zugangsdaten). Wenn sie im
Deployment fehlt, muss der Code auf config_example.py zurückfallen, ohne zu
crashen – z. B. beim Alexa-hosted Import aus dem Git-Repo.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

LAMBDA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda")


def _build_without_config():
    """Baut eine isolierte askplex-Kopie ohne config.py auf."""
    temp_dir = tempfile.mkdtemp(prefix="askplex-no-config-")
    askplex_dst = os.path.join(temp_dir, "askplex")
    shutil.copytree(os.path.join(LAMBDA_DIR, "askplex"), askplex_dst)
    os.remove(os.path.join(askplex_dst, "config.py"))
    return temp_dir


class TestConfigFallback:
    def test_import_without_config_falls_back_to_example(self):
        """Fehlt config.py, importiert askplex.controller die Vorlage config_example."""
        temp_dir = _build_without_config()
        try:
            script = (
                "import sys; sys.path.insert(0, {!r})\n"
                "import askplex.controller as c\n"
                "assert c.config.PMS_SERVER_TOKEN == ''\n"
                "assert c.config.PMS_DEFAULT_SECTION_NAME == ''\n"
                "assert c.config.PMS_SERVER_URL == 'https://'\n"
                "print('OK')\n"
            ).format(temp_dir)
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        assert result.returncode == 0, "STDERR: {}".format(result.stderr)
        assert "OK" in result.stdout

    def test_config_example_defines_all_expected_settings(self):
        """Die Vorlage stellt alle vom Code erwarteten Konstanten bereit."""
        import askplex.config_example as config_example

        for name in (
            "SKILL_LOG_LEVEL",
            "PMS_SERVER_URL",
            "PMS_SERVER_TOKEN",
            "PMS_DEFAULT_SECTION_NAME",
            "PMS_DEFAULT_MAX_RESULTS",
        ):
            assert hasattr(config_example, name), "{} fehlt in config_example".format(name)
