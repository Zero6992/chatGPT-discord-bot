from revChatGPT.V1 import AsyncChatbot
from dotenv import load_dotenv
import os

load_dotenv()
openAI_email = os.getenv("OPENAI_ENAIL")
openAI_password = os.getenv("OPENAI_PASSWORD")
chatbot = AsyncChatbot(config={"email":openAI_email, "password":openAI_password})

async def handle_response(message) -> str:
    async for response in chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage