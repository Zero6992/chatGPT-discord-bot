"""Operational logs omit prompts, credentials and raw provider diagnostics."""

import logging

logger = logging.getLogger("discord_ai_bot")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
# HTTP URLs can contain signed artifact credentials. Never log provider transports.
for name in ("httpx", "httpcore"):
    logging.getLogger(name).disabled = True
