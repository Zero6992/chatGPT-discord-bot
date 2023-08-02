import os
import json
import discord
import asyncio
from typing import Union

from src import responses
from src.log import logger
from auto_login.AutoLogin import GoogleBardAutoLogin, MicrosoftBingAutoLogin
from utils.message_utils import send_split_message, send_response_with_images

from dotenv import load_dotenv
from discord import app_commands

from revChatGPT.V3 import Chatbot
from revChatGPT.V1 import AsyncChatbot
from Bard import Chatbot as BardChatbot
from EdgeGPT.EdgeGPT import Chatbot as EdgeChatbot

load_dotenv()

class aclient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.current_channel = None
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/chat | /help")
        self.isPrivate = False
        self.is_replying_all = os.getenv("REPLYING_ALL")
        self.replying_all_discord_channel_id = os.getenv("REPLYING_ALL_DISCORD_CHANNEL_ID")
        self.openAI_email = os.getenv("OPENAI_EMAIL")
        self.openAI_password = os.getenv("OPENAI_PASSWORD")
        self.openAI_API_key = os.getenv("OPENAI_API_KEY")
        self.openAI_gpt_engine = os.getenv("GPT_ENGINE")
        self.chatgpt_session_token = os.getenv("SESSION_TOKEN")
        self.chatgpt_access_token = os.getenv("ACCESS_TOKEN")
        self.chatgpt_paid = os.getenv("PUID")

        bing_enable_auto_login = os.getenv("bing_enable_auto_login")
        bard_enable_auto_login = os.getenv("bard_enable_auto_login")
        chrome_version = int(os.getenv("chrome_version")) if bard_enable_auto_login == 'True' or bing_enable_auto_login == 'True' else None

        if bard_enable_auto_login == 'True':
            google_account = os.getenv("google_account")
            google_password = os.getenv("google_password")
            self.bard_session_id = GoogleBardAutoLogin(google_account, google_password, chrome_version).get_cookie()
        else:
            self.bard_secure_1psid = os.getenv("BARD_SECURE_1PSID")
            self.bard_secure_1psidts = os.getenv("BARD_SECURE_1PSIDTS")

        if bing_enable_auto_login == 'True':
            bing_account = os.getenv("bing_account")
            bing_password = os.getenv("bing_password")
            MicrosoftBingAutoLogin(bing_account, bing_password, chrome_version).dump_cookies()

        config_dir = os.path.abspath(f"{__file__}/../../")
        prompt_name = 'system_prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.starting_prompt = f.read()

        self.chat_model = os.getenv("CHAT_MODEL")
        self.chatbot = self.get_chatbot_model()
        self.message_queue = asyncio.Queue()

    def get_chatbot_model(self, prompt = None) -> Union[AsyncChatbot, Chatbot]:
        if not prompt:
            prompt = self.starting_prompt
        if self.chat_model == "UNOFFICIAL":
            return AsyncChatbot(config = {
                "access_token": self.chatgpt_access_token,
                "model": "text-davinci-002-render-sha" if self.openAI_gpt_engine == "gpt-3.5-turbo" else self.openAI_gpt_engine,
                "PUID": self.chatgpt_paid
            })
        elif self.chat_model == "OFFICIAL":
                return Chatbot(api_key=self.openAI_API_key, engine=self.openAI_gpt_engine, system_prompt=prompt)
        elif self.chat_model == "Bard":
            return BardChatbot(secure_1psid=self.bard_secure_1psid, secure_1psidts=self.bard_secure_1psidts)
        elif self.chat_model == "Bing":
            cookies = json.loads(open("./cookies.json", encoding="utf-8").read())
            return EdgeChatbot(cookies=cookies)

    async def process_messages(self):
        while True:
            if self.current_channel is not None:
                while not self.message_queue.empty():
                    async with self.current_channel.typing():
                        message, user_message = await self.message_queue.get()
                        try:
                            await self.send_message(message, user_message)
                        except Exception as e:
                            logger.exception(f"Error while processing message: {e}")
                        finally:
                            self.message_queue.task_done()
            await asyncio.sleep(1)


    async def enqueue_message(self, message, user_message):
        await message.response.defer(ephemeral=self.isPrivate) if self.is_replying_all == "False" else None
        await self.message_queue.put((message, user_message))

    async def send_message(self, message, user_message):
        if self.is_replying_all == "False":
            author = message.user.id
        else:
            author = message.author.id
        try:
            response = (f'> **{user_message}** - <@{str(author)}> \n\n')
            if self.chat_model == "OFFICIAL":
                response = f"{response}{await responses.official_handle_response(user_message, self)}"
                await send_split_message(self, response, message)
            elif self.chat_model == "UNOFFICIAL":
                response = f"{response}{await responses.unofficial_handle_response(user_message, self)}"
                await send_split_message(self, response, message)
            elif self.chat_model == "Bard":
                if self.is_replying_all == "True":
                    await message.channel.send(response)
                else:
                    await message.followup.send(response)
                response = await responses.bard_handle_response(user_message, self)
                await send_response_with_images(self, response, message)
            elif self.chat_model == "Bing":
                response = f"{response}{await responses.bing_handle_response(user_message, self)}"
                await send_split_message(self, response, message)
        except Exception as e:
            logger.exception(f"Error while sending : {e}")
            if self.is_replying_all == "True":
                await message.channel.send(f"> **ERROR: Something went wrong, please try again later!** \n ```ERROR MESSAGE: {e}```")
            else:
                await message.followup.send(f"> **ERROR: Something went wrong, please try again later!** \n ```ERROR MESSAGE: {e}```")

    async def send_start_prompt(self):
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        try:
            if self.starting_prompt:
                if (discord_channel_id):
                    channel = self.get_channel(int(discord_channel_id))
                    logger.info(f"Send system prompt with size {len(self.starting_prompt)}")
                    response = ""
                    if self.chat_model == "OFFICIAL":
                        response = f"{response}{await responses.official_handle_response(self.starting_prompt, self)}"
                        await channel.send(response)
                    elif self.chat_model == "UNOFFICIAL":
                        response = f"{response}{await responses.unofficial_handle_response(self.starting_prompt, self)}"
                        await channel.send(response)
                    elif self.chat_model == "Bard":
                        response = await responses.bard_handle_response(self.starting_prompt, self)
                        await channel.send(response.get("content"))
                    elif self.chat_model == "Bing":
                        response = f"{response}{await responses.bing_handle_response(self.starting_prompt, self)}"
                        await channel.send(response)
                    logger.info(f"System prompt response:{response}")
                else:
                    logger.info("No Channel selected. Skip sending system prompt.")
            else:
                logger.info(f"Not given starting prompt. Skiping...")
        except Exception as e:
            logger.exception(f"Error while sending system prompt: {e}")


client = aclient()
