import os

from g4f.client import Client
from openai import AsyncOpenAI
from asgiref.sync import sync_to_async

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))
g4f_client = Client()

async def draw(model: str, prompt: str) -> str:
    if os.getenv("OPENAI_ENABLED") == "False":
        async_generate = sync_to_async(g4f_client.images.generate, thread_sensitive=True)
        response = await async_generate(model = model, prompt = prompt)
    else:
        response = await openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            n=1,
        )
    image_url = response.data[0].url

    return image_url


async def imitate(model: str, image) -> str:
    async_generate = sync_to_async(g4f_client.images.create_variation, thread_sensitive=True)
    response = await async_generate(model = model, image = image)
    image_url = response.data[0].url

    return image_url
