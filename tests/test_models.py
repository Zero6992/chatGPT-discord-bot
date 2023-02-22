import unittest
from unittest.mock import patch
from utils.models import OpenAIModel


class TestOpenAIModel(unittest.TestCase):
    def setUp(self):
        self.api_key = 'test_api_key'
        self.model_engine = 'test_engine'
        self.max_tokens = 128
        self.image_size = '512x512'
        self.model = OpenAIModel(self.api_key, self.model_engine, self.max_tokens, self.image_size)

    @patch('openai.Completion.create')
    def test_text_completion(self, mock_create):
        mock_create.return_value.choices[0].text = 'Test response'
        prompt = 'Test prompt'
        result = self.model.text_completion(prompt)
        mock_create.assert_called_once_with(engine=self.model_engine,
                                            prompt=prompt,
                                            max_tokens=self.max_tokens,
                                            stop=None,
                                            temperature=0.5)
        self.assertEqual(result, 'Test response')

    @patch('openai.Image.create')
    def test_image_generation(self, mock_create):
        mock_create.return_value.data[0].url = 'Test URL'
        prompt = 'Test prompt'
        result = self.model.image_generation(prompt)
        mock_create.assert_called_once_with(prompt=prompt, n=1, size=self.image_size)
        self.assertEqual(result, 'Test URL')