from revChatGPT.revChatGPT import Chatbot
import json

with open('config.json', 'r') as f:
    data = json.load(f)

config = {
    "Authorization": data['Authorization'],
    "session_token": data['session_token']
}


chatbot = Chatbot(config, conversation_id=None)
chatbot.refresh_session() 

def handle_response(message) -> str:
    prompt = message
    response = chatbot.get_chat_response(prompt)
    responseMessage = response["message"]

    return responseMessage
