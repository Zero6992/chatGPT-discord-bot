from revChatGPT.Official import AsyncChatbot
import json

async def handle_response(message) -> str:
    import os

    openAI_key = os.getenv("OPENAI_KEY")
    chatbot = AsyncChatbot(api_key=openAI_key)
    response = await chatbot.ask(message)
    responseMessage = response["choices"][0]["text"]

    return responseMessage