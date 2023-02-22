import openai


class ModelInterface:
    def text_completion(self, prompt: str) -> str:
        pass

    def image_generation(self, prompt: str) -> str:
        pass


class OpenAIModel(ModelInterface):
    def __init__(self, api_key: str, model_engine: str, max_tokens: int = 128, image_size: str = '512x512'):
        openai.api_key = api_key
        self.model_engine = model_engine
        self.max_tokens = max_tokens
        self.image_size = image_size

    def text_completion(self, prompt: str) -> str:
        response = openai.Completion.create(
            engine=self.model_engine,
            prompt=prompt,
            max_tokens=self.max_tokens,
            stop=None,
            temperature=0.5,
        )
        text = response.choices[0].text.strip()
        return text

    def image_generation(self, prompt: str) -> str:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size=self.image_size
        )
        image_url = response.data[0].url
        return image_url