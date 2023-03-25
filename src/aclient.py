import discord
import os
from src import responses
from src import log
from discord import app_commands

logger = log.setup_logger(__name__)

class aclient(discord.Client):
    def __init__(self, isPrivate, isReplyingAll) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/chat | /help")
        self.isPrivate = isPrivate
        self.isReplyingAll = isReplyingAll

    async def send_message(self, message, user_message):
        if client.isReplyingAll == "False":
            author = message.user.id
            await message.response.defer(ephemeral=client.isPrivate)
        else:
            author = message.author.id
        try:
            response = (f'> **{user_message}** - <@{str(author)}' + '> \n\n')
            chat_model = os.getenv("CHAT_MODEL")
            if chat_model == "OFFICIAL":
                response = f"{response}{await responses.official_handle_response(user_message)}"
            elif chat_model == "UNOFFICIAL":
                response = f"{response}{await responses.unofficial_handle_response(user_message)}"
            char_limit = 1900
            if len(response) > char_limit:
                # Split the response into smaller chunks of no more than 1900 characters each(Discord limit is 2000 per chunk)
                if "```" in response:
                    # Split the response if the code block exists
                    parts = response.split("```")

                    for i in range(len(parts)):
                        if i%2 == 0: # indices that are even are not code blocks
                            if client.isReplyingAll == "True":
                                await message.channel.send(parts[i])
                            else:
                                await message.followup.send(parts[i])
                        else: # Odd-numbered parts are code blocks
                            code_block = parts[i].split("\n")
                            formatted_code_block = ""
                            for line in code_block:
                                while len(line) > char_limit:
                                    # Split the line at the 50th character
                                    formatted_code_block += line[:char_limit] + "\n"
                                    line = line[char_limit:]
                                formatted_code_block += line + "\n"  # Add the line and seperate with new line

                            # Send the code block in a separate message
                            if (len(formatted_code_block) > char_limit+100):
                                code_block_chunks = [formatted_code_block[i:i+char_limit]
                                                    for i in range(0, len(formatted_code_block), char_limit)]
                                for chunk in code_block_chunks:
                                    if client.isReplyingAll == "True":
                                        await message.channel.send(f"```{chunk}```")
                                    else:
                                        await message.followup.send(f"```{chunk}```")
                            elif client.isReplyingAll == "True":
                                await message.channel.send(f"```{formatted_code_block}```")
                            else:
                                await message.followup.send(f"```{formatted_code_block}```")
                else:
                    response_chunks = [response[i:i+char_limit]
                                    for i in range(0, len(response), char_limit)]
                    for chunk in response_chunks:
                        if client.isReplyingAll == "True":
                            await message.channel.send(chunk)
                        else:
                            await message.followup.send(chunk)
            elif client.isReplyingAll == "True":
                await message.channel.send(response)
            else:
                await message.followup.send(response)
        except Exception as e:
            if client.isReplyingAll == "True":
                await message.channel.send("> **Error: Something went wrong, please try again later!**")
            else:
                await message.followup.send("> **Error: Something went wrong, please try again later!**")
            logger.exception(f"Error while sending message: {e}")

    async def send_start_prompt(self):
        import os.path

        config_dir = os.path.abspath(f"{__file__}/../../")
        prompt_name = 'starting-prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        try:
            if os.path.isfile(prompt_path) and os.path.getsize(prompt_path) > 0:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt = f.read()
                    if (discord_channel_id):
                        logger.info(f"Send starting prompt with size {len(prompt)}")
                        chat_model = os.getenv("CHAT_MODEL")
                        response = ""
                        if chat_model == "OFFICIAL":
                            response = f"{response}{await responses.official_handle_response(prompt)}"
                        elif chat_model == "UNOFFICIAL":
                            response = f"{response}{await responses.unofficial_handle_response(prompt)}"
                        channel = self.get_channel(int(discord_channel_id))
                        await channel.send(response)
                        logger.info(f"Starting prompt response:{response}")
                    else:
                        logger.info("No Channel selected. Skip sending starting prompt.")
            else:
                logger.info(f"No {prompt_name}. Skip sending starting prompt.")
        except Exception as e:
            logger.exception(f"Error while sending starting prompt: {e}")


client = aclient(isPrivate=False, isReplyingAll=os.getenv("REPLYING_ALL"))