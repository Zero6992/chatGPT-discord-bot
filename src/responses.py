from asgiref.sync import sync_to_async
import openai

async def handle_response(message) -> str:
    import os
    openai.api_key = os.getenv("OPENAI_KEY")
    response = await sync_to_async(openai.Completion.create)(
        model="text-davinci-003",
        prompt=message,
        temperature=0.7,
        max_tokens=2048,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.0,
    )
    responseMessage = response["choices"][0]["text"]

    return responseMessage