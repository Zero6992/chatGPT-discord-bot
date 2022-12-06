from revChatGPT.revChatGPT import Chatbot
import json

with open('config.json', 'r') as f:
    data = json.load(f)

config = {
    "email": data['email'],
    "password": data['password'],
}

if data['session_token']:
    config.update(session_token = data['session_token'])

chatbot = Chatbot(config, conversation_id=None)
chatbot.refresh_session()

def handle_response(prompt) -> str:
    response = chatbot.get_chat_response(prompt, output="text")
    responseMessage = response['message']

    return responseMessage
