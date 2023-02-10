from revChatGPT.Official import AsyncChatbot

async def handle_response(message) -> str:
    import os

    openAI_key = os.getenv("OPENAI_KEY")
    openAI_model = os.getenv("ENGINE")
    chatbot = AsyncChatbot(api_key=openAI_key, engine=openAI_model)
    response = await chatbot.ask(message)
    responseMessage = response["choices"][0]["text"]

    return responseMessage