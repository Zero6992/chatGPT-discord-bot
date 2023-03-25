import io
import os
import warnings
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
import datetime
import random

from dotenv import load_dotenv
from PIL import Image
from stability_sdk import client
from pathlib import Path
from typing import Optional
from src import log

load_dotenv()
logger = log.setup_logger(__name__)

stability_api = client.StabilityInference(
    key=os.environ['STABILITY_KEY'], # API Key reference.
    verbose=True, # Print debug messages.
    engine=os.environ['STABILITY_ENGINE'], # Set the engine to use for generation.
    # Available engines: stable-diffusion-v1 stable-diffusion-v1-5 stable-diffusion-512-v2-0 stable-diffusion-768-v2-0
    # stable-diffusion-512-v2-1 stable-diffusion-768-v2-1 stable-inpainting-v1-0 stable-inpainting-512-v2-0
)


def get_weighted_prompts(prompt_text: Optional[str], negative=False) -> []:
    weighted_prompts = []
    weight = -1 if negative else 1
    if prompt_text:
        for p in prompt_text.split(","):
            # random_number = round(random.uniform(0.8, 1.2), 1)
            weighted_prompts.append(generation.Prompt(text=p.strip(), parameters=generation.PromptParameters(weight=weight)))
    return weighted_prompts


async def draw(prompt, negative_prompt, seed, steps, scale, sampler) -> str:
    multi_prompts = []
    multi_prompts += get_weighted_prompts(prompt_text=prompt) + get_weighted_prompts(prompt_text=negative_prompt, negative=True)
    logger.info(multi_prompts)
    answers = stability_api.generate(
        prompt=multi_prompts,
        seed=seed,
        steps=steps,
        cfg_scale=scale,
        width=512,
        height=512,
        samples=1,
        sampler=sampler
    )

    IMAGE_DIR = Path.cwd() / "images"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().time()

    file_name = IMAGE_DIR / f"{prompt[:5]}-{now}.png"

    # Set up our warning to print to the console if the adult content classifier is tripped.
    # If adult content classifier is not tripped, save generated images.
    for resp in answers:
        for artifact in resp.artifacts:
            if artifact.finish_reason == generation.FILTER:
                warnings.warn(
                    "Your request activated the API's safety filters and could not be processed."
                    "Please modify the prompt and try again.")
            if artifact.type == generation.ARTIFACT_IMAGE:
                img = Image.open(io.BytesIO(artifact.binary))
                img.save(file_name)  # Save our generated images with their seed number as the filename.

    return str(file_name)


