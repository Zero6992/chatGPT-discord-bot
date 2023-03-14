import os
import json
import openai
from pathlib import Path
from base64 import b64decode
from dotenv import load_dotenv
from asgiref.sync import sync_to_async

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


# generate 512x512 image and save to a file
# return the path of the image as a str
async def draw(prompt) -> str:
    DATA_DIR = Path.cwd()
    DATA_DIR.mkdir(exist_ok=True)

    response = await sync_to_async(openai.Image.create)(
        prompt=prompt,
        n=1,
        size="512x512",
        response_format="b64_json",
    )

    file_name = DATA_DIR / f"{prompt[:5]}-{response['created']}.json"

    with open(file_name, mode="w", encoding="utf-8") as file:
        json.dump(response, file)

    path = await convert(file_name)

    return str(path)

# code stolen from https://realpython.com/generate-images-with-dalle-openai-api/
async def convert(path):
    DATA_DIR = Path.cwd() / "responses"
    JSON_FILE = DATA_DIR / path
    IMAGE_DIR = Path.cwd() / "images"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with open(JSON_FILE, mode="r", encoding="utf-8") as file:
        response = json.load(file)

    for index, image_dict in enumerate(response["data"]):
        image_data = b64decode(image_dict["b64_json"])
        image_file = IMAGE_DIR / f"{JSON_FILE.stem}-{index}.png"

        with open(image_file, mode="wb") as png:
            png.write(image_data)

        # delete uneeded json file
        os.remove(path)

    return image_file
