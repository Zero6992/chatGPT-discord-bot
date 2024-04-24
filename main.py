import os

from src import bot
from dotenv import load_dotenv
from g4f.cookies import set_cookies


if __name__ == '__main__':
    set_cookies(".bing.com", {
    "_U": str(os.getenv("BING_COOKIE"))
    })
    set_cookies(".google.com", {
    "__Secure-1PSID": str(os.getenv("GOOGLE_PSID"))
    })
    bot.run_discord_bot()
