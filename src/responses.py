import os
from revChatGPT.V1 import AsyncChatbot
from revChatGPT.V3 import Chatbot
from dotenv import load_dotenv
from src import personas
from typing import Union

load_dotenv()
OPENAI_EMAIL = os.getenv("OPENAI_EMAIL")
OPENAI_PASSWORD = os.getenv("OPENAI_PASSWORD")
SESSION_TOKEN = os.getenv("SESSION_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENGINE = os.getenv("OPENAI_ENGINE")
CHAT_MODEL = os.getenv("CHAT_MODEL")

def get_chatbot_model(model_name: str) -> Union[AsyncChatbot, Chatbot]:
    if model_name == "UNOFFICIAL":
        openai_email = os.getenv("OPENAI_EMAIL")
        openai_password = os.getenv("OPENAI_PASSWORD")
        session_token = os.getenv("SESSION_TOKEN")
        return AsyncChatbot(config={"email": openai_email, "password": openai_password, "session_token": session_token})
    elif model_name == "OFFICIAL":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        print(openai_api_key)
        engine = os.getenv("OPENAI_ENGINE")
        return Chatbot(api_key=openai_api_key, engine=engine)

chatbot = get_chatbot_model(CHAT_MODEL)

async def official_handle_response(message) -> str:
    return chatbot.ask(message)

async def unofficial_handle_response(message) -> str:
    async for response in chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage

# resets conversation and asks chatGPT the prompt for a persona
async def switch_persona(persona) -> None:
    if CHAT_MODEL ==  "UNOFFICIAL":
        chatbot.reset_chat()
        async for response in chatbot.ask(personas.PERSONAS.get(persona)):
            pass

    elif CHAT_MODEL == "OFFICIAL":
        chatbot.reset()
        for response in chatbot.ask(personas.PERSONAS.get(persona)):
            pass

