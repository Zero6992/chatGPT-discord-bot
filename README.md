# chatGPT-discord-bot

> ### This is a project that provides you to build your own Discord bot using chatGPT
>
>  :star: A star would be highly appreciated


## Features

* `! [message]` The bot will respond to you via private message

* `!reset` The bot conversation history will be reset

# Setup

## Install

`pip install -r requirements.txt`

dependencies: Reverse Engineered ChatGPT by OpenAI [here](https://github.com/acheong08/ChatGPT) and discord.py

## Step 1: Create a Discord bot

1. Go to https://discord.com/developers/applications create an application
2. Build a Discord bot under the application
3. Get the token from bot setting

   ![1670143818339](https://user-images.githubusercontent.com/89479282/205949161-4b508c6d-19a7-49b6-b8ed-7525ddbef430.png)
4. Store the token to `config.json` under the `discord_bot_token`

   ![1670250610205](https://user-images.githubusercontent.com/89479282/205949488-f3f2903d-7fb8-4be3-a703-2174535b3cd7.png)
5. Turn MESSAGE CONTENT INTENT `ON`

   ![1670176647431](https://user-images.githubusercontent.com/89479282/205949323-4354bd7d-9bb9-4f4b-a87e-deb9933a89b5.png)
6. Invite your bot through OAuth2 URL Generator

   ![1670176722801](https://user-images.githubusercontent.com/89479282/205949600-0c7ddb40-7e82-47a0-b59a-b089f929d177.png)
## Step 2: Email and password authentication
Save both in `config.json`

   ![1670250583265](https://user-images.githubusercontent.com/89479282/205949713-8c0dbcca-9f63-4150-850d-bb21bac06158.png)

> **Warning**
> 
> If you are logging in with a Google or Microsoft account, please use the session token method below.

## Step 2: Session token authentication

Go to https://chat.openai.com/chat log in

1. Open console with `F12`
2. Open `Application` tab > Cookies

   ![image](https://user-images.githubusercontent.com/36258159/205494773-32ef651a-994d-435a-9f76-a26699935dac.png)
3. Copy the value for `__Secure-next-auth.session-token` and paste it into `config.json` under `session_token`. You do not need to fill out `email` and `password`

   ![1670250561033](https://user-images.githubusercontent.com/89479282/205950188-96ae9b35-539a-4246-857d-e97e9a0bf8fd.png)

## Step 3: Run the bot

1. Open a terminal or command prompt
2. Navigate to the directory where you installed the chatGPT Discord bot
3. Run `python main.py` to start the bot.

## Have A Good Chat !

   ![1670177247310](https://user-images.githubusercontent.com/89479282/205950120-71aa0a9d-0f5f-46a1-8bf8-d7ab655551f2.jpg)
