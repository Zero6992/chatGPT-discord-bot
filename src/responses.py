from asyncChatGPT.asyncChatGPT import Chatbot
import json


async def handle_response(prompt) -> str:
    chatbot.refresh_session()
    response = await chatbot.get_chat_response(prompt, output="text")
    responseMessage = response['message']

    return responseMessage


def get_config() -> dict:
    import os
    # get config.json path
    script_dir = os.path.abspath(__file__ + "/../../")
    file_name = 'config.json'
    config_path = os.path.join(script_dir, file_name)

    with open(config_path, 'r') as f:
        data = json.load(f)

    return data


data = get_config()

config = {
    "email": data['email'],
    "password": data['password'],
}

if data['session_token']:
    config.update(session_token = data['session_token'])

chatbot = Chatbot(config, conversation_id=None)
