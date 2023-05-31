import unittest
from unittest.mock import patch
from unittest.mock import Mock, MagicMock, AsyncMock
from src.responses import *
import asyncio

class ResponseTest(unittest.TestCase):
    def test_official_handle_response(self):
        print('\n==== Testing for official_handle_response() ====')
        client_mock = Mock()

        asyncio.run(official_handle_response("HIHI", client_mock))
        client_mock.chatbot.ask.assert_called()

    def test_unofficial_handle_response(self):
        print('\n==== Testing for unofficial_handle_response() ====')
        msg = "HIHI"
        client_mock = Mock()
        responses = [{"message": "msg1"}, {"message": "msg2"}]
        ask_mock = MagicMock()
        client_mock.chatbot.ask.return_value = ask_mock
        ask_mock.__aiter__.return_value = responses
        ret = asyncio.run(unofficial_handle_response(msg, client_mock))
        client_mock.chatbot.ask.assert_called()
        client_mock.chatbot.ask.assert_called_with(msg)
        self.assertEqual(ret, responses[-1]["message"])

    def test_bard_handle_response(self):
        print('\n==== Testing for bard_handle_response() ====')
        client_mock = Mock()

        response = {"content": "testcontent"}
        client_mock.chatbot.ask.return_value = response
        ret = asyncio.run(bard_handle_response("HIHI", client_mock))
        client_mock.chatbot.ask.assert_called()
        self.assertEqual(response["content"], ret)

    def test_bing_handle_response_suc(self):
        print('\n==== Testing for bing_handle_response_suc() ====')
        msg = "HIHI"
        client_mock = Mock()
        responses = [[None, {"item": {"messages": [None, {"text": "msg1"}]}}]]
        ask_mock = MagicMock()
        client_mock.chatbot.ask_stream.return_value = ask_mock
        ask_mock.__aiter__.return_value = responses
        ret = asyncio.run(bing_handle_response(msg, client_mock))
        client_mock.chatbot.ask_stream.assert_called()
        client_mock.chatbot.ask_stream.assert_called_with(msg)
        self.assertEqual(ret, "msg1")

    def test_bing_handle_response_fail(self):
        print('\n==== Testing for bing_handle_response_fail() ====')
        msg = "HIHI"
        client_mock = Mock()
        responses = [[None, {"item": {"messages": "msg1"}}]]
        ask_mock = MagicMock()

        reset_mock = AsyncMock()
        client_mock.chatbot.reset.return_value= reset_mock()

        client_mock.chatbot.ask_stream.return_value = ask_mock
        ask_mock.__aiter__.return_value = responses
        with self.assertRaises(Exception) as ctx:
            ret = asyncio.run(bing_handle_response(msg, client_mock))

    @patch('src.responses.personas')
    def test_switch_persona_unofficial(self, personas_mock):
        print('\n==== Testing for switch_persona_unofficial() ====')
        client_mock = Mock()
        persona = "HI"

        client_mock.chat_model = "UNOFFICIAL"
        ask_mock = MagicMock()
        client_mock.chatbot.ask.return_value = ask_mock
        ask_mock.__aiter__.return_value = range(3)
        
        ret = asyncio.run(switch_persona(persona, client_mock))
        client_mock.chatbot.reset_chat.assert_called()
        personas_mock.PERSONAS.get.called_with(personas)

    @patch('src.responses.personas')
    def test_switch_persona_official(self, personas_mock):
        print('\n==== Testing for switch_persona_official() ====')
        client_mock = Mock()
        persona = "HI"

        client_mock.chat_model = "OFFICIAL"
        
        ret = asyncio.run(switch_persona(persona, client_mock))
        client_mock.get_chatbot_model.assert_called()
        personas_mock.PERSONAS.get.called_with(personas)

    @patch('src.responses.personas')
    def test_switch_persona_bard(self, personas_mock):
        print('\n==== Testing for switch_persona_bard() ====')
        client_mock = Mock()
        persona = "HI"

        client_mock.chat_model = "Bard"
        chatbot = Mock()
        client_mock.get_chatbot_model.return_value = chatbot
        
        ret = asyncio.run(switch_persona(persona, client_mock))
        client_mock.get_chatbot_model.assert_called()
        personas_mock.PERSONAS.get.called_with(personas)
        chatbot.ask.assert_called()

    @patch('src.responses.personas')
    def test_switch_persona_bing(self, personas_mock):
        print('\n==== Testing for switch_persona_bing() ====')
        client_mock = Mock()
        persona = "HI"

        reset_mock = AsyncMock()
        client_mock.chatbot.reset.return_value= reset_mock()

        client_mock.chat_model = "Bing"
        ask_mock = MagicMock()
        client_mock.chatbot.ask_stream.return_value = ask_mock
        ask_mock.__aiter__.return_value = range(3)
        
        ret = asyncio.run(switch_persona(persona, client_mock))
        reset_mock.assert_awaited()
        personas_mock.PERSONAS.get.called_with(personas)

if __name__ == "__main__":
    unittest.main() #pragma: no cover
