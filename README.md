# chatGPT-discord-bot

Reverse Engineered ChatGPT by OpenAI [here](https://github.com/acheong08/ChatGPT).

# Setup


## Install
`pip install -U discord.py`
`pip3 install revChatGPT`

## Create a discord bot

1. Go to https://discord.com/developers/applications create an application.
2. And build a bot under the application.
3. Get the token from Bot setting.


   ![1670143818339](image/README/1670143818339.png)
4. Store the token to `config.json` under the `discord_bot_token`

   ![1670176461891](image/README/1670176461891.png)
5. Turn MESSAGE CONTENT INTENT `ON`

   ![1670176647431](image/README/1670176647431.png)
6. Invite your bot through OAuth2 URL Generator

   ![1670176722801](image/README/1670176722801.png)

## Get your session token
Go to https://chat.openai.com/chat sign up and log in
1. Open console with `F12`
2. Open `Application` tab > Cookies

   ![image](https://user-images.githubusercontent.com/36258159/205494773-32ef651a-994d-435a-9f76-a26699935dac.png)
3. Copy the value for `__Secure-next-auth.session-token` and paste it into `config.json` under `session_token`. You do not need to fill out `Authorization`

   ![1670176444011](image/README/1670176444011.png)


## Have A Good Chat !

   ![1670177247310](image/README/1670177247310.jpg)
