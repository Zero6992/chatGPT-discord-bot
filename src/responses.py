import os
from revChatGPT.V1 import AsyncChatbot
from dotenv import load_dotenv

load_dotenv()
session_token = os.getenv("SESSION_TOKEN")
openai_email = os.getenv("OPENAI_EMAIL")
chatbot = AsyncChatbot(config={"email":openai_email, "session_token":session_token})


async def handle_response(message) -> str:
    async for response in chatbot.ask(message):
        responseMessage = response["message"]

    return responseMessage


# resets conversation and asks chatGPT the prompt for a persona
async def switch_persona(persona) -> None:
    chatbot.reset_chat()
    async for response in chatbot.ask(persona):
        pass

