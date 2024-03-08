from g4f.client import Client
from asgiref.sync import sync_to_async

g4f_client = Client()

async def draw(model: str, prompt: str) -> str:
    async_generate = sync_to_async(g4f_client.images.generate, thread_sensitive=True)
    response = await async_generate(model = model, prompt = prompt)
    image_url = response.data[0].url

    return image_url


async def imitate(model: str, image) -> str:
    async_generate = sync_to_async(g4f_client.images.create_variation, thread_sensitive=True)
    response = await async_generate(model = model, image = image)
    image_url = response.data[0].url

    return image_url
