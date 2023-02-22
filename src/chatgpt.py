from src.models import ModelInterface
from src.memory import MemoryInterface


class ChatGPT:
    def __init__(self, model: ModelInterface, memory: MemoryInterface = None):
        self.model = model
        self.memory = memory

    def get_response(self, user_id: str, text: str) -> str:
        prompt = text if self.memory is None else f'{self.memory.get(user_id)}\n\n{text}'
        response = self.model.text_completion(f'{prompt} <|endoftext|>')
        if self.memory is not None:
            self.memory.append(user_id, prompt)
            self.memory.append(user_id, response)
        return response

    def clean_history(self, user_id: str) -> None:
        self.memory.remove(user_id)


class DALLE:
    def __init__(self, model: ModelInterface):
        self.model = model

    def generate(self, text: str) -> str:
        return self.model.image_generation(text)