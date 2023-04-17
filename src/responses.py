from src import personas
from asgiref.sync import sync_to_async

async def official_handle_response(message, client) -> str:
    return await sync_to_async(client.chatbot.ask)(message)

async def unofficial_handle_response(message, client) -> str:
    async for response in client.chatbot.ask(message):
        responseMessage = response["message"]
    return responseMessage

async def bard_handle_response(message, client) -> str:
    response = await sync_to_async(client.chatbot.ask)(message)
    responseMessage = response["content"]
    return responseMessage

async def bing_handle_response(message, client) -> str:
    async for response in client.chatbot.ask_stream(message):
        responseMessage = response
    print(responseMessage[1])
    if len(responseMessage[1]["item"]["messages"]) > 1:
        return responseMessage[1]["item"]["messages"][1]["text"]
    else:
        raise Exception("Bing cannot continue this conversation, use `/reset` to start the next conversation.")

# resets conversation and asks chatGPT the prompt for a persona
async def switch_persona(persona, client) -> None:
    if client.chat_model ==  "UNOFFICIAL":
        client.chatbot.reset_chat()
        async for _ in client.chatbot.ask(personas.PERSONAS.get(persona)):
            pass
    elif client.chat_model == "OFFICIAL":
        client.chatbot = client.get_chatbot_model(prompt=personas.PERSONAS.get(persona))
    elif client.chat_model == "Bard":
        client.chatbot = client.get_chatbot_model()
        await sync_to_async(client.chatbot.ask)(personas.PERSONAS.get(persona))
    elif client.chat_model == "Bing":
        client.chatbot = client.get_chatbot_model()
        async for _ in client.chatbot.ask_stream(personas.PERSONAS.get(persona)):
            pass
