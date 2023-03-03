from revChatGPT.V1 import AsyncChatbot
from dotenv import load_dotenv
import os

load_dotenv()
access_token = os.getenv("SESSION_TOKEN")
openai_email = os.getenv("OPENAI_EMAIL")
chatbot = AsyncChatbot(config={"email":openai_email, "access_token":access_token})

async def handle_response(message) -> str:
    async for response in chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage
