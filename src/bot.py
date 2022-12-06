import discord
import json
from src import responses

with open('config.json', 'r') as f:
    data = json.load(f)


# the common interface to send message
async def send_message(message, user_message, is_private=False, is_reply=True):
    try:
        if (is_reply):
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
        else:
            # directly send message
            await message.author.send(user_message)

    except Exception as e:
        await message.channel.send("**Error: I think there are something went wrong. Please try again later!**")
        print(e)

intents = discord.Intents.default()
intents.message_content = True


def run_discord_bot():
    TOKEN = data['discord_bot_token']
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'{client.user} is now running!')

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        username = str(message.author)
        user_message = str(message.content)
        channel = str(message.channel)

        print(f"{username} said: '{user_message}' ({channel})")
        # spilt user_message, using space
        user_message = user_message.split(' ', 1)

        if user_message[0] == '!chat_reset':
            responses.chatbot.reset_chat()
            print("The CHAT BOT has been successfully reset")
            await send_message(message, "**Info: I have forgotten everything.**", is_reply=False)
        # send DM to a user
        elif user_message[0] == '!chat_private':
            user_message = user_message[1]
            await send_message(message, user_message, is_private=True)
        # send messages to a chatroom
        elif user_message[0] == '!chat':
            user_message = user_message[1]
            await send_message(message, user_message, is_private=False)
        else:
            return

    client.run(TOKEN)
