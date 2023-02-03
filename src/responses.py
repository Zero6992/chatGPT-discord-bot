from revChatGPT.Official import Chatbot
import json
from asgiref.sync import sync_to_async


def get_config() -> dict:
    import os
    # get config.json path
    config_dir = os.path.abspath(__file__ + "/../../")
    config_name = 'config.json'
    config_path = os.path.join(config_dir, config_name)

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config


config = get_config()
chatbot = Chatbot(api_key=config['openAI_key'])

async def handle_response(message) -> str:
    response = await sync_to_async(chatbot.ask)(message)
    responseMessage = response["choices"][0]["text"]

    return responseMessage