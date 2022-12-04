from revChatGPT.revChatGPT import Chatbot


config = {
        # Put your OPENAI Bearer token here
        "Authorization": ""
    }

chatbot = Chatbot(config, conversation_id=None)

def handle_response(message) -> str:
    prompt = message
    response = chatbot.get_chat_response(prompt)
    responseMessage = response["message"]

    return responseMessage