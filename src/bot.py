import discord
import os
import openai
from random import randrange
from discord import app_commands
from src import responses
from src import log
from src import art
from src import personas


logger = log.setup_logger(__name__)

isPrivate = False
isReplyAll = False


class aclient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.activity = discord.Activity(type=discord.ActivityType.custom, name="Being evil. 😈")


async def send_message(message, user_message):
    global isReplyAll
    if not isReplyAll:
        author = message.user.id
        await message.response.defer(ephemeral=isPrivate)
    else:
        author = message.author.id
    try:
        response = '> **' + user_message + '** - <@' + \
            str(author) + '> \n\n'
        response = f"{response}{await responses.handle_response(user_message)}"
        char_limit = 1900
        if len(response) > char_limit:
            # Split the response into smaller chunks of no more than 1900 characters each(Discord limit is 2000 per chunk)
            if "```" in response:
                # Split the response if the code block exists
                
                parts = response.split("```")

                for i in range(0, len(parts)):
                    if i%2 == 0: # indices that are even are not code blocks
                        if isReplyAll:
                            await message.channel.send(parts[i])
                        else:
                            await message.followup.send(parts[i])

                    # Send the code block in a seperate message
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
                                if isReplyAll:
                                    await message.channel.send("```" + chunk + "```")
                                else:
                                    await message.followup.send("```" + chunk + "```")
                        else:
                            if isReplyAll:
                                await message.channel.send("```" + formatted_code_block + "```")
                            else:
                                await message.followup.send("```" + formatted_code_block + "```")

            else:
                response_chunks = [response[i:i+char_limit]
                                   for i in range(0, len(response), char_limit)]
                for chunk in response_chunks:
                    if isReplyAll:
                        await message.channel.send(chunk)
                    else:
                        await message.followup.send(chunk)
                        
        else:
            if isReplyAll:
                await message.channel.send(response)
            else:
                await message.followup.send(response)
    except Exception as e:
        if isReplyAll:
            await message.channel.send("> **Error: Something went wrong, please try again later!**")
        else:
            await message.followup.send("> **Error: Something went wrong, please try again later!**")
        logger.exception(f"Error while sending message: {e}")


async def send_start_prompt(client):
    import os.path

    config_dir = os.path.abspath(__file__ + "/../../")
    prompt_name = 'starting-prompt.txt'
    prompt_path = os.path.join(config_dir, prompt_name)
    discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
    try:
        if os.path.isfile(prompt_path) and os.path.getsize(prompt_path) > 0:
            with open(prompt_path, "r") as f:
                prompt = f.read()
                if (discord_channel_id):
                    logger.info(f"Send starting prompt with size {len(prompt)}")
                    responseMessage = await responses.handle_response(prompt)
                    channel = client.get_channel(int(discord_channel_id))
                    await channel.send(responseMessage)
                    logger.info(f"Starting prompt response:{responseMessage}")
                else:
                    logger.info("No Channel selected. Skip sending starting prompt.")
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
    except Exception as e:
        logger.exception(f"Error while sending starting prompt: {e}")


def run_discord_bot():
    client = aclient()


    @client.event
    async def on_ready():
        await send_start_prompt(client)
        await client.tree.sync()
        logger.info(f'{client.user} is now running!')


    @client.tree.command(name="chat", description="Have a chat with ChatGPT")
    async def chat(interaction: discord.Interaction, *, message: str):
        global isReplyAll
        if isReplyAll:
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                "> **Warn: You already on replyAll mode. If you want to use slash command, switch to normal mode, use `/replyall` again**")
            logger.warning("\x1b[31mYou already on replyAll mode, can't use slash command!\x1b[0m")
            return
        if interaction.user == client.user:
            return
        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : /chat [{message}] in ({channel})")
        await send_message(interaction, message)


    @client.tree.command(name="private", description="Toggle private access")
    async def private(interaction: discord.Interaction):
        global isPrivate
        await interaction.response.defer(ephemeral=False)
        if not isPrivate:
            isPrivate = not isPrivate
            logger.warning("\x1b[31mSwitch to private mode\x1b[0m")
            await interaction.followup.send(
                "> **Info: Next, the response will be sent via private message. If you want to switch back to public mode, use `/public`**")
        else:
            logger.info("You already on private mode!")
            await interaction.followup.send(
                "> **Warn: You already on private mode. If you want to switch to public mode, use `/public`**")


    @client.tree.command(name="public", description="Toggle public access")
    async def public(interaction: discord.Interaction):
        global isPrivate
        await interaction.response.defer(ephemeral=False)
        if isPrivate:
            isPrivate = not isPrivate
            await interaction.followup.send(
                "> **Info: Next, the response will be sent to the channel directly. If you want to switch back to private mode, use `/private`**")
            logger.warning("\x1b[31mSwitch to public mode\x1b[0m")
        else:
            await interaction.followup.send(
                "> **Warn: You already on public mode. If you want to switch to private mode, use `/private`**")
            logger.info("You already on public mode!")


    @client.tree.command(name="replyall", description="Toggle replyAll access")
    async def replyall(interaction: discord.Interaction):
        global isReplyAll
        await interaction.response.defer(ephemeral=False)
        if isReplyAll:
            await interaction.followup.send(
                "> **Info: The bot will only response to the slash command `/chat` next. If you want to switch back to replyAll mode, use `/replyAll` again.**")
            logger.warning("\x1b[31mSwitch to normal mode\x1b[0m")
        else:
            await interaction.followup.send(
                "> **Info: Next, the bot will response to all message in the server. If you want to switch back to normal mode, use `/replyAll` again.**")
            logger.warning("\x1b[31mSwitch to replyAll mode\x1b[0m")
        isReplyAll = not isReplyAll
    

    @client.tree.command(name="reset", description="Complete reset ChatGPT conversation history")
    async def reset(interaction: discord.Interaction):
        responses.chatbot.reset_chat()
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("> **Info: I have forgotten everything.**")
        logger.warning(
            "\x1b[31mChatGPT bot has been successfully reset\x1b[0m")
        await send_start_prompt(client)


    @client.tree.command(name="help", description="Show help for the bot")
    async def help(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send(""":star:**BASIC COMMANDS** \n
        - `/chat [message]` Chat with ChatGPT!
        - `/draw [prompt]` Generate an image with the Dalle2 model
        - `/switchpersona [persona]` Switch between optional chatGPT jailbreaks
                `random`: Picks a random persona
                `chatGPT`: Standard chatGPT mode
                `dan`: Dan Mode 11.0, infamous Do Anything Now Mode
                `sda`: Superior DAN has even more freedom in DAN Mode
                `evil`: Evil Confidant, evil trusted confidant
                `based`: BasedGPT v2, sexy gpt
                `oppo`: OPPO says exact opposite of what chatGPT would say
                `dev`: Developer Mode, v2 Developer mode enabled
                `meanie`: Meanie, says mean things

        - `/public` ChatGtGPT switch between replyall mode and default mode
        - `/reset` Clear ChatGPT conversation history\n
        For complete documentation, please visit https://github.com/Zero6992/chatGPT-discord-bot
        chatGPT Jailbreaks are from https://www.jailbreakchat.com/""")
        logger.info(
            "\x1b[31mSomeone needs help!\x1b[0m")

    
    @client.tree.command(name="draw", description="Generate an image with the Dalle2 model")
    async def draw(interaction: discord.Interaction, *, prompt: str):
        global isReplyAll
        if isReplyAll:
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                "> **Warn: You are already on replyAll mode. If you want to use slash command, switch to normal mode, use `/replyall` again**")
            logger.warning("\x1b[31mYou are already on replyAll mode, can't use slash command!\x1b[0m")
            return
        if interaction.user == client.user:
            return
        

        #await interaction.response.defer(ephemeral=False)
        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : /draw [{prompt}] in ({channel})")


        await interaction.response.defer(thinking=True)
        try:
            path = await art.draw(prompt)

            file = discord.File(path, filename="image.png")
            title = '> **' + prompt + '**\n'
            embed = discord.Embed(title=title)
            embed.set_image(url="attachment://image.png")

            # send image in an embed
            await interaction.followup.send(file=file, embed=embed)
            logger.info(
            f"\x1b[0m {art.count_remaining_images()} images remaining")

        except openai.InvalidRequestError:
            await interaction.followup.send(
                "> **Warn: Inappropriate request 😿**")
            logger.info(
            f"\x1b[31m{username}\x1b[0m made an inappropriate request.!")

        except Exception as e:
            await interaction.followup.send(
                "> **Warn: Something went wrong 😿**")
            logger.exception(f"Error while generating image: {e}")


    @client.tree.command(name="switchpersona", description="Switch between optional chatGPT jailbreaks")
    async def chat(interaction: discord.Interaction, *, persona: str):
        global isReplyAll
        if isReplyAll:
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                "> **Warn: You already on replyAll mode. If you want to use slash command, switch to normal mode, use `/replyall` again**")
            logger.warning("\x1b[31mYou already on replyAll mode, can't use slash command!\x1b[0m")
            return
        if interaction.user == client.user:
            return

        await interaction.response.defer(thinking=True)
        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : '/switchpersona {persona}' ({channel})")
        
        persona = persona.lower()

        if persona == personas.current_persona:
            await interaction.followup.send(f"> **Warn: Already set to `{persona}` persona**")

        elif persona == "standard":
            responses.chatbot.reset_chat()
            personas.current_persona = "standard"
            await interaction.followup.send(
                f"> **Info: Switched to `{persona}` persona**")

        elif persona == "random":
            choices = list(personas.PERSONAS.keys())
            choice = randrange(0, len(choices))
            chosen_persona = personas.PERSONAS.get(choices[choice])
            personas.current_persona = chosen_persona
            await responses.switch_persona(chosen_persona)
            await interaction.followup.send(
                f"> **Info: Switched to `{persona}` persona**")


        elif persona in personas.PERSONAS:
            try:
                await responses.switch_persona(persona)
                personas.current_persona = persona
                await interaction.followup.send(
                f"> **Info: Switched to `{persona}` persona**")
            except Exception as e:
                await interaction.followup.send(
                    "> **Error: Something went wrong, please try again later! 😿**")
                logger.exception(f"Error while switching persona: {e}")
                
        else:
            await interaction.followup.send(
                f"> **Error: No available persona: `{persona}` 😿**")
            logger.info(
                f'{username} requested an unavailable persona: `{persona}`')

        
    @client.event
    async def on_message(message):
        if isReplyAll:
            if message.author == client.user:
                return
            username = str(message.author)
            message = str(message.content)
            channel = str(message.channel)
            logger.info(f"\x1b[31m{username}\x1b[0m : '{message}' ({channel})")
            await send_message(message, message)
    
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    client.run(TOKEN)
