from revChatGPT.V1 import AsyncChatbot
from dotenv import load_dotenv
import os

load_dotenv()
openAI_email = os.getenv("OPENAI_EMAIL")
openAI_password = os.getenv("OPENAI_PASSWORD")
session_token = os.getenv("SESSION_TOKEN")
chatbot = AsyncChatbot(config={"email":openAI_email, "password":openAI_password, "session_token":session_token})

async def handle_response(message) -> str:
    async for response in chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage