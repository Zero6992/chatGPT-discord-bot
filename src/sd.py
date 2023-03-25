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

load_dotenv()

stability_api = client.StabilityInference(
    key=os.environ['STABILITY_KEY'], # API Key reference.
    verbose=True, # Print debug messages.
    engine=os.environ['STABILITY_ENGINE'], # Set the engine to use for generation.
    # Available engines: stable-diffusion-v1 stable-diffusion-v1-5 stable-diffusion-512-v2-0 stable-diffusion-768-v2-0
    # stable-diffusion-512-v2-1 stable-diffusion-768-v2-1 stable-inpainting-v1-0 stable-inpainting-512-v2-0
)


async def draw(prompt, negative_prompt) -> str:
    prompts = prompt.split(",")
    negative_prompts = negative_prompt.split(",")
    multi_prompts = []
    for p in prompts:
        random_number = round(random.uniform(0.8, 1.2), 1)
        multi_prompts.append(generation.Prompt(text=p, parameters=generation.PromptParameters(weight=random_number)))
    for p in negative_prompts:
        random_number = round(random.uniform(-1.2, -0.8), 1)
        multi_prompts.append(generation.Prompt(text=p, parameters=generation.PromptParameters(weight=random_number)))

    answers = stability_api.generate(
        prompt=multi_prompts,
        # seed=992446758,  # If a seed is provided, the resulting generated image will be deterministic.
        # What this means is that as long as all generation parameters remain the same, you can always recall the same image simply by generating it again.
        # Note: This isn't quite the case for Clip Guided generations, which we'll tackle in a future example notebook.
        steps=30,  # Amount of inference steps performed on image generation. Defaults to 30.
        cfg_scale=8.0,  # Influences how strongly your generation is guided to match your prompt.
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


