#!/usr/bin/env python3
"""Application entry point; configuration is loaded before client construction."""

import os
from pathlib import Path

from dotenv import load_dotenv

from src.bot import run_discord_bot
from src.config import load_settings
from src.domain import BotError
from src.log import logger


def main() -> None:
    load_dotenv()
    os.umask(0o077)
    try:
        settings = load_settings(Path(os.environ.get("BOT_CONFIG", "config.toml")))
        token = os.environ.get("DISCORD_BOT_TOKEN", "")
        if not token:
            raise BotError("DISCORD_BOT_TOKEN is required.")
        run_discord_bot(settings, token)
    except BotError as error:
        logger.error("%s", error)
        raise SystemExit(1) from None
    except Exception:
        logger.error("Bot stopped unexpectedly. Check runtime configuration and permissions.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
