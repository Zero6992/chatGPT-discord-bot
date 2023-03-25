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

load_dotenv()

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
            weighted_prompts.append(generation.Prompt(text=p, parameters=generation.PromptParameters(weight=weight)))
    return weighted_prompts


async def draw(prompt, negative_prompt, seed, steps, scale) -> str:
    multi_prompts = []
    multi_prompts += get_weighted_prompts(prompt) + get_weighted_prompts(negative_prompt)

    answers = stability_api.generate(
        prompt=multi_prompts,
        seed=seed,  # If a seed is provided, the resulting generated image will be deterministic.
        # What this means is that as long as all generation parameters remain the same, you can always recall the same image simply by generating it again.
        # Note: This isn't quite the case for Clip Guided generations, which we'll tackle in a future example notebook.
        steps=steps,  # Amount of inference steps performed on image generation. Defaults to 30.
        cfg_scale=scale,  # Influences how strongly your generation is guided to match your prompt.
        # Setting this value higher increases the strength in which it tries to match your prompt.
        # Defaults to 7.0 if not specified.
        width=512,  # Generation width, defaults to 512 if not included.
        height=512,  # Generation height, defaults to 512 if not included.
        samples=1,  # Number of images to generate, defaults to 1 if not included.
        sampler=generation.SAMPLER_K_EULER_ANCESTRAL  # Choose which sampler we want to denoise our generation with.
        # Defaults to k_dpmpp_2m if not specified. Clip Guidance only supports ancestral samplers.
        # (Available Samplers: ddim, plms, k_euler, k_euler_ancestral, k_heun, k_dpm_2, k_dpm_2_ancestral, k_dpmpp_2s_ancestral, k_lms, k_dpmpp_2m)
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


