from revChatGPT.Official import AsyncChatbot
from dotenv import load_dotenv
import os
import openai

load_dotenv()
openAI_key = os.getenv("OPENAI_KEY")
openAI_model = os.getenv("ENGINE")

openai.api_key = "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"

async def handle_response(message) -> str:
    response = openai.Completion.create(
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