import discord
import json
from discord.ext import commands
from src import responses


with open('config.json', 'r') as f:
    data = json.load(f)

async def send_message(message, user_message, is_private):
    try:
        response = responses.handle_response(user_message)
        if len(response) > 2000:
            # Split the response into smaller chunks of no more than 2000 characters each
            response_chunks = [response[i:i+2000]
                               for i in range(0, len(response), 2000)]
            for chunk in response_chunks:
                # Send each chunk separately
                await message.author.send(chunk) if is_private else await message.channel.send(chunk)
        else:
            await message.author.send(response) if is_private else await message.channel.send(response)

    except Exception as e:
        await message.channel.send("**Error: I think there are something went wrong. Please try again later!**")
        print(e)

intents = discord.Intents.default()
intents.message_content = True
is_private = False

def run_discord_bot():
    TOKEN = data['discord_bot_token']
    client = commands.Bot(command_prefix='/', intents=intents)
    
    @client.event
    async def on_ready():
        print(f'{client.user} is now running!')

    @client.command()
    async def chat(ctx, *, message: str):
        if ctx.author == client.user:
            return
        username = str(ctx.author)
        user_message = message
        channel = str(ctx.channel)
        print(f"{username} said: '{user_message}' ({channel})")
        await send_message(ctx, user_message, is_private)
        
    @client.command()
    async def private(ctx):
            global is_private
            if not is_private:
                is_private = not is_private
                print("Switch to private mode")
                await ctx.channel.send("**Info: Next, the response will be sent via private message. If you want to switch back to public mode, use `/public`**")
            else:
                print("You already on private mode!")
                await ctx.channel.send("**Warn: You already on private mode. If you want to switch to public mode, use `/public`**")


    @client.command()
    async def public(ctx):
            global is_private
            if is_private:
                is_private =  not is_private
                print("Switch to public mode")
                await ctx.channel.send("**Info: Next, the response will be sent to the channel directly. If you want to switch back to private mode, use `/private`**")
            else:
                print("You already on public mode!")
                await ctx.channel.send("**Warn: You already on public mode. If you want to switch to private mode, use `/private`**")            

    @client.command()
    async def reset(ctx):
        responses.chatbot.reset_chat()
        await ctx.channel.send("**Info: I have forgotten everything.**")
        print("The CHAT BOT has been successfully reset")


    client.run(TOKEN)
