from src import personas
from src.log import logger
from asgiref.sync import sync_to_async
from EdgeGPT.EdgeGPT import ConversationStyle


async def official_handle_response(message, client) -> str:
    return await sync_to_async(client.chatbot.ask)(message)

async def unofficial_handle_response(message, client) -> str:
    async for response in client.chatbot.ask(message):
        responseMessage = response["message"]
    return responseMessage

async def bard_handle_response(message, client) -> str:
    response = await sync_to_async(client.chatbot.ask)(message)
    return response

async def bing_handle_response(message, client, conversation_style = ConversationStyle.creative) -> str:
    try:
        response = await client.chatbot.ask(prompt = message,
                                            conversation_style = conversation_style,
                                            simplify_response = True)
        responseMessage = response['text']
    except Exception as e:
        logger.error(f'Error occurred: {e}')
        await client.chatbot.reset()
        raise Exception(f'{e}\nBing is fail to continue the conversation, this conversation will automatically reset.')

    return responseMessage


# prompt engineering
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
        await client.chatbot.reset()
        async for _ in client.chatbot.ask_stream(personas.PERSONAS.get(persona)):
            pass
