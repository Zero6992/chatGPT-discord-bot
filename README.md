# ChatGPT Discord Bot

> ### Build your own Discord bot using ChatGPT

---
> [!IMPORTANT]
>
> **Major Update (2024/03):**
> - GPT-4 now supported for free
> - Utilize OpenAI API can ensure smoother experiences, refer [Optional: Configuring OpenAI API](#optional-configuring-openai-api)

### Chat

![image](https://user-images.githubusercontent.com/89479282/206497774-47d960cd-1aeb-4fba-9af5-1f9d6ff41f00.gif)

# Setup
## Prerequisites
* **Python 3.9 or later**
* **Rename the file `.env.example` to `.env`**
* Running `pip3 install -r requirements.txt` to install the required dependencies
* Google Chrome for [Image Generation](https://github.com/Zero6992/chatGPT-discord-bot?tab=readme-ov-file#image-generation)
---
## Step 1: Create a Discord bot

1. Go to https://discord.com/developers/applications create an application
2. Build a Discord bot under the application
3. Get the token from bot setting

   ![image](https://user-images.githubusercontent.com/89479282/205949161-4b508c6d-19a7-49b6-b8ed-7525ddbef430.png)
4. Store the token to `.env` under the `DISCORD_BOT_TOKEN`

   <img height="190" width="390" alt="image" src="https://user-images.githubusercontent.com/89479282/222661803-a7537ca7-88ae-4e66-9bec-384f3e83e6bd.png">

5. Turn MESSAGE CONTENT INTENT `ON`

   ![image](https://user-images.githubusercontent.com/89479282/205949323-4354bd7d-9bb9-4f4b-a87e-deb9933a89b5.png)

6. Invite your bot to your server via OAuth2 URL Generator

   ![image](https://user-images.githubusercontent.com/89479282/205949600-0c7ddb40-7e82-47a0-b59a-b089f929d177.png)



## Step 2: Run the bot on the desktop

1. Open a terminal or command prompt

2. Navigate to the directory where you installed the ChatGPT Discord bot

3. Run `python3 main.py` or `python main.py` to run the bot
---
## Step 2: Run the bot with Docker

1. Build the Docker image & run the Docker container with `docker compose up -d`

2. Inspect whether the bot works well `docker logs -t chatgpt-discord-bot`

   ### Stop the bot:

   * `docker ps` to see the list of running services
   * `docker stop <BOT CONTAINER ID>` to stop the running bot

### Have a good chat!
---

## Optional: Configuring OpenAI API


1. Obtain your API key by visiting https://platform.openai.com/api-keys
2. Paste the API key under `OPENAI_KEY` in `.env`
3. Set `OPENAI_ENABLED` to `True` in `.env`

> [!NOTE]
> GPT-4 API is subject to certain restrictions.
>
> Details https://help.openai.com/en/articles/7102672-how-can-i-access-gpt-4

## Image Generation

<img src="https://i.imgur.com/Eo1ZzKk.png" width="300" alt="image">

### Microsoft Bing Image Generation
1. Go to https://www.bing.com/chat and log in

2. Open console with `F12`

3. Open `Application` tab > Cookies

4. Copy the value for `_U` from cookies and paste it into `.env` under `BING_COOKIE`

### Google Gemini Image Generation
1. Go to https://gemini.google.com/app and log in

2. Open console with `F12`

3. Open `Application` tab > Cookies

4. Copy the value for `__Secure-1PSID` from cookies and paste it into `.env` under `GOOGLE_PSID`

## Optional: Setup system prompt

* A system prompt would be invoked when the bot is first started or reset
* You can set it up by modifying the content in `system_prompt.txt`
* All the text in the file will be fired as a prompt to the bot
* Get the first message from ChatGPT in your discord channel!
* Go Discord setting turn `developer mode` on

   1. Right-click the channel you want to recieve the message, `Copy  ID`

        ![channel-id](https://user-images.githubusercontent.com/89479282/207697217-e03357b3-3b3d-44d0-b880-163217ed4a49.PNG)

   2. paste it into `.env` under `DISCORD_CHANNEL_ID`

## Optional: Disable logging

* Set the value of `LOGGING` in the `.env` to False

------
>  [**中文設置教學**](https://zero6992.me/2023/03/08/chatGPT-discord-bot-chinese/)
------
## Commands

* `/chat [message]` Chat with ChatGPT/Gemini
* `/draw [prompt]` Generate an image with Gemini/OpenAI/Bing
* `/switchpersona [persona]` Switch between optional chatGPT jailbreaks
   * `random`: Picks a random persona
   * `standard`: Standard chatGPT mode
   * `dan`: DAN 13.5 (Latest Working ChatGPT Jailbreak prompt)
   * `Smart mode`: AIM (Always Intelligent and Machiavellian)
   * `Developer Mode`: software developer who specializes in the AI's area

* `/private` ChatGPT switch to private mode
* `/public` ChatGPT switch to public mode
* `/replyall` ChatGPT switch between replyAll mode and default mode
* `/reset` Clear ChatGPT conversation history
* `/chat-model` Switch different chat model
   * `gpt-4`: GPT-4 model
   * `Gemini`: Google Gemini Model
### Special Features

#### Switch Persona

> **Warning**
>
> Certain personas may generate vulgar or disturbing content. Use at your own risk.

![image](https://user-images.githubusercontent.com/91911303/223772334-7aece61f-ead7-4119-bcd4-7274979c4702.png)


#### Mode

* `public mode (default)`  the bot directly reply on the channel

  ![image](https://user-images.githubusercontent.com/89479282/206565977-d7c5d405-fdb4-4202-bbdd-715b7c8e8415.gif)

* `private mode` the bot's reply can only be seen by the person who used the command

  ![image](https://user-images.githubusercontent.com/89479282/206565873-b181e600-e793-4a94-a978-47f806b986da.gif)

* `replyall mode` the bot will reply to all messages in the channel without using slash commands (`/chat` will also be unavailable)

   > **Warning**
   > The bot will easily be triggered in `replyall` mode, which could cause program failures
 ---
