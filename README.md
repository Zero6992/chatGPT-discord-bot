# chatGPT-discord-bot

Reverse Engineered ChatGPT by OpenAI [here](https://github.com/acheong08/ChatGPT).

# Setup


## Install

`pip3 install revChatGPT`

## Create a discord bot

1. Go to https://discord.com/developers/applications create a bot
2. Get the token from Bot setting.
3. Store the token to bot.py TOKEN.
   ![1670143818339](image/README/1670143818339.png)
   ![1670143869537](image/README/1670143869537.png)

## Get your Bearer token

Go to https://chat.openai.com/chat and log in or sign up

1. Open console with `F12`
2. Go to Network tab in console
3. Find session request (Might need refresh)
4. Store the token to responses.py config.
   ![image](https://user-images.githubusercontent.com/36258159/205446680-b3f40499-9757-428b-9e2f-23e89ca99461.png)
   ![image](https://user-images.githubusercontent.com/36258159/205446730-793f8187-316c-4ae8-962c-0f4c1ee00bd1.png)

# Known issues

- Access token expires in one hour
