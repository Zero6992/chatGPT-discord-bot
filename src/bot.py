import discord
import json
from discord import app_commands
from discord.ext import commands
from src import responses


with open('config.json', 'r') as f:
    data = json.load(f)

async def send_message(message, user_message, is_private):
    try:
        response = '> **' + user_message + '** - <@' + str(message.user.id)  + '>\n\n' + responses.handle_response(user_message)
        if len(response) > 2000:
            # Split the response into smaller chunks of no more than 2000 characters each
            response_chunks = [response[i:i+2000]
                               for i in range(0, len(response), 2000)]
            for chunk in response_chunks:
                if is_private:
                    await message.followup.send(chunk)
                else:
                    await message.channel.send(chunk)
                    await message.followup.send(' :tada: :tada: The reply to this message has been sent')
        else:
            if is_private:
                await message.followup.send(response)
            else:
                await message.channel.send(response)
                await message.followup.send(' :tada: :tada: The reply to this message has been sent')

    except Exception as e:
        await message.followup.send('I made a mistake, please ask me again later')
        await message.channel.send("> **Error: There are something went wrong. Please try again later!**")
        print(e)

intents = discord.Intents.default()
intents.message_content = True
is_private = False

def run_discord_bot():
    TOKEN = data['discord_bot_token']
    client = commands.Bot(command_prefix='!', intents=intents)
            
    @client.event
    async def on_ready():
        await client.tree.sync()
        print(f'{client.user} is now running!')

    @client.tree.command(name="chat", description="Have a chat with chatGPT")
    async def chat(interaction: discord.Interaction, *, message: str):
        if interaction.user == client.user:
            return
        username = str(interaction.user)
        user_message = message
        channel = str(interaction.channel)
        print(f"{username} said: '{user_message}' ({channel})")
        await interaction.response.defer(ephemeral = True)
        await send_message(interaction, user_message, is_private)
        
    @client.tree.command(name="private", description="Toggle private access")
    async def private(interaction: discord.Interaction):
            global is_private
            await interaction.response.defer(ephemeral = True)
            if not is_private:
                is_private = not is_private
                print("Switch to private mode")
                await interaction.followup.send("**Info: Next, the response will be sent via private message. If you want to switch back to public mode, use `/public`**")
                await interaction.channel.send("> **Info: Next, the response will be sent via private message. If you want to switch back to public mode, use `/public`**")
            else:
                print("You already on private mode!")
                await interaction.followup.send("**Warn: You already on private mode. If you want to switch to public mode, use `/public`**")


    @client.tree.command(name="public", description="Toggle public access")
    async def public(interaction: discord.Interaction):
            global is_private
            await interaction.response.defer(ephemeral = True)
            if is_private:
                is_private =  not is_private
                print("Switch to public mode")
                await interaction.followup.send("**Info: Next, the response will be sent to the channel directly. If you want to switch back to private mode, use `/private`**")
                await interaction.channel.send("> **Info: Next, the response will be sent to the channel directly. If you want to switch back to private mode, use `/private`**")
            else:
                print("You already on public mode!")
                await interaction.followup.send("**Warn: You already on public mode. If you want to switch to private mode, use `/private`**")            

    @client.tree.command(name="reset", description="Complete reset gptChat conversation history")
    async def reset(interaction: discord.Interaction):
        responses.chatbot.reset_chat()
        await interaction.response.defer(ephemeral = True)
        await interaction.followup.send("**Info: I have forgotten everything.**")
        await interaction.channel.send("> **Info: I have forgotten everything.**")
        print("The CHAT BOT has been successfully reset")


    client.run(TOKEN)
