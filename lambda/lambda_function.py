import json
import logging
import os
import sys

from askplex import config
from askplex.ams_controller import AMSController

logger = logging.getLogger(__name__)
logger.setLevel(config.SKILL_LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

controller = AMSController(logger)


def lambda_handler(event, context):
    logger.debug("Alexa Request: %s", json.dumps(event))

    request = event.get("request", {})
    request_type = request.get("type")

    # Reine Events (Skill aktiviert/deaktiviert, Playback-Telemetrie) brauchen keine Antwort
    if request_type and not request_type.startswith("Alexa."):
        logger.info("Event empfangen: %s", request_type)
        return {}

    return controller.handle(event)
