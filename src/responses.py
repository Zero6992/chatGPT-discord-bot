import openai
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
openai.api_key = config['openAI_key']

async def handle_response(message) -> str:
    response = await sync_to_async(openai.Completion.create)(
        model="text-davinci-003",
        prompt=message,
        temperature=0.7,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.0,
    )

    responseMessage = response.choices[0].text

    return responseMessage