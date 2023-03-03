from revChatGPT.V1 import AsyncChatbot
from revChatGPT.V3 import Chatbot
from dotenv import load_dotenv
import os

load_dotenv()
openAI_email = os.getenv("OPENAI_EMAIL")
openAI_password = os.getenv("OPENAI_PASSWORD")
session_token = os.getenv("SESSION_TOKEN")
openAI_key = os.getenv("OPENAI_API_KEY")
openAI_engine = os.getenv("OPENAI_ENGINE")

unofficial_chatbot = AsyncChatbot(config={"email":openAI_email, "password":openAI_password, "session_token":session_token})
offical_chatbot = Chatbot(api_key=openAI_key)

async def official_handle_response(message) -> str:
    responseMessage = offical_chatbot.ask(message)

    return responseMessage

async def unofficial_handle_response(message) -> str:
    async for response in unofficial_chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage