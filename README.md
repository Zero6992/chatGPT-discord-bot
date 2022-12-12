# chatGPT-discord-bot

> ### This is a project that provides you to build your own Discord bot using ChatGPT
>
> ⭐️ A star would be highly appreciated

## Features

* `/chat [message]` Chat with ChatGPT!
* `/private` ChatGPT switch to private mode
* `/public`  ChatGPT switch to public  mode
* `/reset`   ChatGPT conversation history will be erased

### Chat

![image](https://user-images.githubusercontent.com/89479282/206497774-47d960cd-1aeb-4fba-9af5-1f9d6ff41f00.gif)

### Mode

* `public mode (default)`  the bot directly reply on the channel

  ![image](https://user-images.githubusercontent.com/89479282/206565977-d7c5d405-fdb4-4202-bbdd-715b7c8e8415.gif)
* `private mode` the bot's reply can only be seen by who use the command

  ![image](https://user-images.githubusercontent.com/89479282/206565873-b181e600-e793-4a94-a978-47f806b986da.gif)

# Setup

## Install

`pip install -r requirements.txt`

dependencies: Reverse Engineered ChatGPT by OpenAI [here](https://github.com/acheong08/ChatGPT) and discord.py

## Step 1: Create a Discord bot

1. Go to https://discord.com/developers/applications create an application
2. Build a Discord bot under the application
3. Get the token from bot setting

   ![image](https://user-images.githubusercontent.com/89479282/205949161-4b508c6d-19a7-49b6-b8ed-7525ddbef430.png)
4. Store the token to `config.json` under the `discord_bot_token`

   ![image](https://user-images.githubusercontent.com/89479282/205949488-f3f2903d-7fb8-4be3-a703-2174535b3cd7.png)
5. Turn MESSAGE CONTENT INTENT `ON`

   ![image](https://user-images.githubusercontent.com/89479282/205949323-4354bd7d-9bb9-4f4b-a87e-deb9933a89b5.png)
6. Invite your bot through OAuth2 URL Generator

   ![image](https://user-images.githubusercontent.com/89479282/205949600-0c7ddb40-7e82-47a0-b59a-b089f929d177.png)

## Step 2: Token authentication

Go to https://chat.openai.com/chat log in

1. Open console with `F12`

2. Open `Application` tab > Cookies

    ![image](https://user-images.githubusercontent.com/36258159/206955081-8a8e1ff9-d12c-456c-9a67-5c1a7438f76c.png)

3. Copy the value for `__Secure-next-auth.session-token` from cookies and paste it into `config.json` under `session_token`

4. Find your `cf_clearance` from cookies and paste it into `config.json` under `cf_clearance`

5. Get your `user-agent` from network and paste it into `config.json` under `user-agent`

    Network > Headers > Request Headers > `User-Agent`
  
    ![image](https://user-images.githubusercontent.com/89479282/207018691-da7de05e-89c1-4111-a2d6-c220fa35754b.png
)


6. It should be look like this

  ![image](https://user-images.githubusercontent.com/89479282/206976671-31c989d1-c1af-494f-876a-3dc632ffc4da.PNG)

## Step 3: Run the bot

1. Open a terminal or command prompt
2. Navigate to the directory where you installed the ChatGPT Discord bot
3. Run `python3 main.py` to start the bot

## Step 3: Run the bot with docker

1. Build the Docker image `docker build -t chatgpt-discord-bot --platform linux/amd64 .`
2. Run the Docker container  `docker run --platform linux/amd64 -d chatgpt-discord-bot`

   ### Stop the bot:

   * `docker ps` to see the list of running services
   * `docker stop <BOT CONTAINER ID>` to stop the running bot
## Optional: Setup starting prompt

* A starting prompt would be invoked when the bot is first started or reset
* You can set it up by modifying the content in `starting-prompt.txt`
* All the text in the file will be fired as a prompt to the bot  

### Have A Good Chat !

