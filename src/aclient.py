import os
import discord
import asyncio

from src import personas
from src.log import logger
from utils.message_utils import send_split_message

from dotenv import load_dotenv
from discord import app_commands
from asgiref.sync import sync_to_async

import g4f.debug
from g4f.client import Client
from g4f.stubs import ChatCompletion
from g4f.Provider import RetryProvider, OpenaiChat, Aichatos, Liaobots # gpt-4
from g4f.Provider import  DuckDuckGo, Ecosia  # gpt-3.5-turbo

from openai import AsyncOpenAI

g4f.debug.logging = True

load_dotenv()

class discordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.chatBot = Client(
            provider = RetryProvider([OpenaiChat, Aichatos, DuckDuckGo, Ecosia, Liaobots], shuffle=False),
        )
        self.chatModel = os.getenv("MODEL")
        self.conversation_history = []
        self.current_channel = None
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/chat | /help")
        self.isPrivate = False
        self.is_replying_all = os.getenv("REPLYING_ALL")
        self.replying_all_discord_channel_id = os.getenv("REPLYING_ALL_DISCORD_CHANNEL_ID")
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))

        config_dir = os.path.abspath(f"{__file__}/../../")
        prompt_name = 'system_prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.starting_prompt = f.read()

        self.message_queue = asyncio.Queue()

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
            response = await self.handle_response(user_message)
            response_content = f'> **{user_message}** - <@{str(author)}> \n\n{response}'
            await send_split_message(self, response_content, message)
        except Exception as e:
            logger.exception(f"Error while sending : {e}")
            # Error handling as before

    async def send_start_prompt(self):
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        try:
            if self.starting_prompt and discord_channel_id:
                channel = self.get_channel(int(discord_channel_id))
                logger.info(f"Send system prompt with size {len(self.starting_prompt)}")

                response = await self.handle_response(self.starting_prompt)
                await channel.send(f"{response}")

                logger.info(f"System prompt response: {response}")
            else:
                logger.info("No starting prompt given or no Discord channel selected. Skipping sending system prompt.")
        except Exception as e:
            logger.exception(f"Error while sending system prompt: {e}")

    async def handle_response(self, user_message) -> str:
        self.conversation_history.append({'role': 'user', 'content': user_message})
        if len(self.conversation_history) > 26:
             del self.conversation_history[4:6]
        if os.getenv("OPENAI_ENABLED") == "False":
            async_create = sync_to_async(self.chatBot.chat.completions.create, 
                                         thread_sensitive=True)
            response: ChatCompletion = await async_create(model=self.chatModel, 
                                                          messages=self.conversation_history)
        else:
            response = await self.openai_client.chat.completions.create(
                model=self.chatModel,
                messages=self.conversation_history
            )

        bot_response = response.choices[0].message.content
        self.conversation_history.append({'role': 'assistant', 'content': bot_response})

        return bot_response

    def reset_conversation_history(self):
        self.conversation_history = []
        personas.current_persona = "standard"

    # prompt engineering
    async def switch_persona(self, persona) -> None:
        self.reset_conversation_history()
        await self.handle_response(personas.PERSONAS.get(persona))
        await self.send_start_prompt()



discordClient = discordClient()
