# -*- coding: utf-8 -*-
"""
pytest-Konfiguration: stellt sicher, dass das `askplex`-Paket aus dem
`lambda`-Verzeichnis importierbar ist. Es wird keine Kopie des
Produktionsmoduls in den Testordner gelegt.
"""

import os
import sys

LAMBDA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda")
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)