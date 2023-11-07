import os
import openai

from dotenv import load_dotenv
from asgiref.sync import sync_to_async

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

async def draw(prompt) -> list[str]:

    response = await sync_to_async(openai.images.generate)(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="standard",
    )
    image_url = response.data[0].url

    return image_url
