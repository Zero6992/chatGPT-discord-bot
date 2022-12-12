import discord
from discord.ext import commands
from src import responses
from src import log

logger = log.setup_logger(__name__)

data = responses.get_config()

isPrivate = False


async def send_message(message, user_message):
    await message.response.defer(ephemeral=isPrivate)
    try:
        response = '> **' + user_message + '** - <@' + \
            str(message.user.id) + '>\n\n'
        response += await responses.handle_response(user_message)
        if len(response) > 1900:
            # Split the response into smaller chunks of no more than 1900 characters each(Discord limit is 2000 per chunk)
            if "```" in response:
                # Split the response if the code block exists
                parts = response.split("```")
                # Send the first message
                await message.followup.send(parts[0])
                # Send the code block in a seperate message
                code_block = parts[1].split("\n")
                formatted_code_block = ""
                for line in code_block:
                    while len(line) > 1900:
                    # Split the line at the 50th character
                        formatted_code_block += line[:1900] + "\n"
                        line = line[1900:]
                    formatted_code_block += line + "\n" # Add the line and seperate with new line

                # Send the code block in a separate message
                if (len(formatted_code_block) > 2000):
                    code_block_chunks = [formatted_code_block[i:i+1900] for i in range(0, len(formatted_code_block), 1900)]
                    for chunk in code_block_chunks:
                        await message.followup.send("```" + chunk + "```")
                else:
                    await message.followup.send("```" + formatted_code_block + "```") 

                # Send the remaining of the response in another message
                
                if len(parts) >= 3:
                    await message.followup.send(parts[2])
            else:
                response_chunks = [response[i:i+1900]
                               for i in range(0, len(response), 1900)]
                for chunk in response_chunks:
                    await message.followup.send(chunk)
        else:
            await message.followup.send(response)
    except Exception as e:
        await message.followup.send("> **Error: Something went wrong, please try again later!**")
        logger.exception(f"Error while sending message: {e}")

async def read_prompt(message) :
    import os
    import os.path

    await message.response.defer(ephemeral=isPrivate)

    try:
        config_dir = os.path.abspath(__file__ + "/../../")
        prompt_name = 'starting-prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        response = ""
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r") as f:
                for i, line in enumerate(f):
                    response += f'{i}: {line}'
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
        
        if response != "":
            await message.followup.send(response)
        else:
            await message.followup.send(f"입력된 설정이 없습니다")
        f.close()
    except Exception as e:
        await message.followup.send("> **Error: Something went wrong, please try again later!**")
        print(e)

async def write_prompt(message, user_message) :
    import os
    import os.path

    try:
        config_dir = os.path.abspath(__file__ + "/../../")
        prompt_name = 'starting-prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "a+") as f:
                f.write(user_message + "\n")
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
    except Exception as e:
        await message.response.defer(ephemeral=isPrivate)
        await message.followup.send("> **Error: Something went wrong, please try again later!**")
        print(e)
    await send_message(message, user_message)

async def insert_prompt(message, user_message, line_number) :
    import os
    import os.path

    try:
        await message.response.defer(ephemeral=isPrivate)
        config_dir = os.path.abspath(__file__ + "/../../")
        prompt_name = 'starting-prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r") as f:
                lines = f.readlines()

            if line_number < 1 or line_number > len(lines):
                logger.warning(f"Invalid line number {str(line_number)}")
                await message.followup.send(f"유효하지 않은 순서 값입니다")
            else:
                lines.insert(line_number, user_message + "\n")
                with open(prompt_path, "w") as f:
                    f.writelines(lines)
                    await message.followup.send(f"> 설정이 추가되었습니다: {user_message}")
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
    except Exception as e:
        await message.followup.send("> **Error: Something went wrong, please try again later!**")
        print(e)


async def delete_prompt(message, line_number) :
    import os
    import os.path
    
    await message.response.defer(ephemeral=isPrivate)
    try:
        config_dir = os.path.abspath(__file__ + "/../../")
        prompt_name = 'starting-prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r") as f:
                lines = f.readlines()

            if line_number < 1 or line_number > len(lines):
                logger.warning(f"Invalid line number {str(line_number)}")
                await message.followup.send(f"유효하지 않은 순서 값입니다")
            else:
                line = lines[line_number]
                del lines[line_number]
                await message.followup.send(f"> 설정이 삭제되었습니다: {line_number}: {line}")
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
    except Exception as e:
        await message.followup.send("> **Error: Something went wrong, please try again later!**")
        print(e)


async def send_start_prompt_line_by_line() :
    import os
    import os.path

    config_dir = os.path.abspath(__file__ + "/../../")
    prompt_name = 'starting-prompt.txt'
    prompt_path = os.path.join(config_dir, prompt_name)
    if os.path.isfile(prompt_path):
        with open(prompt_path, "r") as f:
            prompt = f.readline()
            while prompt:
                logger.info(f"Send starting prompt with size {len(prompt)}")
                response_message = await responses.handle_response(prompt)
                logger.info(f"Starting prompt response: {response_message}")
                prompt = f.readline()
    else:
        logger.info(f"No {prompt_name}. Skip sending starting prompt.")

async def send_start_prompt() :
    import os
    import os.path

    config_dir = os.path.abspath(__file__ + "/../../")
    prompt_name = 'starting-prompt.txt'
    prompt_path = os.path.join(config_dir, prompt_name)
    try:
        if os.path.isfile(prompt_path) and os.path.getsize(prompt_path) > 0:
            with open(prompt_path, "r") as f:
                prompt = f.read()
                logger.info(f"Send starting prompt with size {len(prompt)}")
                responseMessage = await responses.handle_response(prompt)
            logger.info(f"Starting prompt response: {responseMessage}")
        else:
            logger.info(f"No {prompt_name}. Skip sending starting prompt.")
    except Exception as e:
        logger.exception(f"Error while sending starting prompt: {e}")

def run_discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    activity = discord.Activity(type=discord.ActivityType.watching, name="/chat | /private | /public | /reset")
    client = commands.Bot(command_prefix='!', intents=intents, activity=activity)

    @client.event
    async def on_ready():
        await send_start_prompt_line_by_line()
        await client.tree.sync()
        logger.info(f'{client.user} is now running!')

    @client.tree.command(name="chat", description="Have a chat with ChatGPT")
    async def chat(interaction: discord.Interaction, *, message: str):
        if interaction.user == client.user:
            return
        username = str(interaction.user)
        user_message = message
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : '{user_message}' ({channel})")
        await send_message(interaction, user_message)

    @client.tree.command(name="private", description="Toggle private access")
    async def private(interaction: discord.Interaction):
        global isPrivate
        await interaction.response.defer(ephemeral=False)
        if not isPrivate:
            isPrivate = not isPrivate
            logger.warning("\x1b[31mSwitch to private mode\x1b[0m")
            await interaction.followup.send("> **Info: Next, the response will be sent via private message. If you want to switch back to public mode, use `/public`**")
        else:
            logger.info("You already on private mode!")
            await interaction.followup.send("> **Warn: You already on private mode. If you want to switch to public mode, use `/public`**")

    @client.tree.command(name="public", description="Toggle public access")
    async def public(interaction: discord.Interaction):
        global isPrivate
        await interaction.response.defer(ephemeral=False)
        if isPrivate:
            isPrivate = not isPrivate
            await interaction.followup.send("> **Info: Next, the response will be sent to the channel directly. If you want to switch back to private mode, use `/private`**")
            logger.warning("\x1b[31mSwitch to public mode\x1b[0m")
        else:
            await interaction.followup.send("> **Warn: You already on public mode. If you want to switch to private mode, use `/private`**")
            logger.info("You already on public mode!")

    @client.tree.command(name="reset", description="Complete reset ChatGPT conversation history")
    async def reset(interaction: discord.Interaction):
        responses.chatbot.reset_chat()
        await interaction.response.defer(ephemeral=False)
        await interaction.followup.send("> **Info: I have forgotten everything.**")
        logger.warning(
            "\x1b[31mChatGPT bot has been successfully reset\x1b[0m")
        await send_start_prompt_line_by_line()

    @client.tree.command(name="질문", description="스토리에 대하여 질문합니다(설정으로 기록하지 않습니다)")
    async def chat(interaction: discord.Interaction, *, message: str):
        if interaction.user == client.user:
            return
        username = str(interaction.user)
        user_message = message
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : '{user_message}' ({channel})")
        await send_message(interaction, user_message)

    @client.tree.command(name="설정입력", description="설정을 기록합니다")
    async def write_p(interaction: discord.Interaction, *, message: str):
        if interaction.user == client.user:
            return
        username = str(interaction.user)
        user_message = message
        channel = str(interaction.channel)
        logger.info(
            f"\x1b[31m{username}\x1b[0m : '{user_message}' ({channel})")
        await write_prompt(interaction, user_message)

    @client.tree.command(name="설정추가", description="설정을 지정한 순서에 추가합니다. (다음 실행에 적용됩니다)")
    async def write_p(interaction: discord.Interaction, *, message: str, linenumber: int):
        if interaction.user == client.user:
            return
        user_message = message
        await insert_prompt(interaction, user_message, linenumber)

    @client.tree.command(name="설정삭제", description="지정한 순서의 설정을 삭제합니다. (다음 실행에 적용됩니다)")
    async def delete_p(interaction: discord.Interaction, *, linenumber: int):
        if interaction.user == client.user:
            return
        await delete_prompt(interaction, linenumber)

    @client.tree.command(name="설정읽기", description="현재 설정을 읽습니다")
    async def read(interaction: discord.Interaction):
        if interaction.user == client.user:
            return
        await read_prompt(interaction)
    
    TOKEN = data['discord_bot_token']
    client.run(TOKEN)
