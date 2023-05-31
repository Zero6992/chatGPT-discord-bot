from unittest.mock import AsyncMock, Mock
from unittest.mock import patch, MagicMock, PropertyMock
import unittest
from EdgeGPT import Chatbot as EdgeChatbot
from Bard import Chatbot as BardChatbot
from revChatGPT.V1 import AsyncChatbot
from revChatGPT.V3 import Chatbot
from discord import app_commands
from dotenv import load_dotenv
import os
import sys

sys.path.append("..")
from src.aclient import *
from auto_login.AutoLogin import GoogleBardAutoLogin, MicrosoftBingAutoLogin

load_dotenv('../.env')
is_replying_all = os.getenv("REPLYING_ALL")
replying_all_discord_channel_id = os.getenv("REPLYING_ALL_DISCORD_CHANNEL_ID")
discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
openAI_email = os.getenv("OPENAI_EMAIL")
openAI_password = os.getenv("OPENAI_PASSWORD")
openAI_API_key = os.getenv("OPENAI_API_KEY")
openAI_gpt_engine = os.getenv("GPT_ENGINE")
chatgpt_session_token = os.getenv("SESSION_TOKEN")
chatgpt_access_token = os.getenv("ACCESS_TOKEN")
chatgpt_paid = os.getenv("UNOFFICIAL_PAID")
bing_enable_auto_login = os.getenv("bing_enable_auto_login")
bard_enable_auto_login = os.getenv("bard_enable_auto_login")
google_account = os.getenv("google_account")
google_password = os.getenv("google_password")
bing_account = os.getenv("bing_account")
bing_password = os.getenv("bing_password")
chat_model_env = os.getenv("CHAT_MODEL")


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AsyncContextManagerMock(AsyncMock):

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AclientTest(unittest.IsolatedAsyncioTestCase):
    stub_responses_multiLine = '''```
The world is a vast and diverse place, filled with countless cultures, languages, and traditions. From the bustling streets of New York City to the serene landscapes of the Amazon rainforest, each corner of the globe offers its own unique charm and beauty.

In Europe, you can wander through the historic streets of Rome, marvel at the grandeur of the Eiffel Tower in Paris, or explore the picturesque villages of the Swiss Alps. The continent is steeped in history, with ancient ruins and medieval castles scattered throughout its lands.

Asia, on the other hand, is a vibrant tapestry of colors and flavors. From the neon lights of Tokyo to the tranquil temples of Kyoto, there is something for everyone. You can sample spicy street food in Bangkok, cruise along the breathtaking Halong Bay in Vietnam, or trek through the lush tea plantations of Sri Lanka.

Africa is a continent of contrasts, with its vast savannahs, dense jungles, and stunning coastlines. Witness the majesty of the Great Migration in Kenya, encounter gorillas in the misty mountains of Rwanda, or relax on the pristine beaches of Zanzibar.

In the Americas, you can immerse yourself in the rich cultural heritage of the Mayan ruins in Mexico, explore the natural wonders of the Galapagos Islands in Ecuador, or experience the pulsating energy of Carnival in Brazil. The landscapes are as diverse as the people, ranging from the frozen wilderness of Alaska to the tropical rainforests of Costa Rica.

Australia and Oceania beckon with their pristine beauty and laid-back lifestyle. Dive into the Great Barrier Reef in Australia, hike through the lush rainforests of New Zealand, or witness the unique wildlife of the Galapagos Islands.

No matter where you go, travel opens your eyes to new perspectives, broadens your horizons, and fills your heart with a sense of wonder. It is an opportunity to connect with people from different backgrounds, to taste new cuisines, and to create memories that will last a lifetime.

So pack your bags, embrace the unknown, and embark on an adventure of a lifetime. The world is waiting to be discovered.
```'''

    stub_responses_multiLine_short_limit = '''```
The world is a vast and diverse place, filled with countless cultures, languages, and traditions. From the bustling streets of New York City to the serene landscapes of the Amazon rainforest, each corner of the globe offers its own unique charm and beauty.

In Europe, you can wander through the historic streets of Rome, marvel at the grandeur of the Eiffel Tower in Paris, or explore the picturesque villages of the Swiss Alps. The continent is steeped in history, with ancient ruins and medieval castles scattered throughout its lands.

Asia, on the other hand, is a vibrant tapestry of colors and flavors. From the neon lights of Tokyo to the tranquil temples of Kyoto, there is something for everyone. You can sample spicy street food in Bangkok, cruise along the breathtaking Halong Bay in Vietnam, or trek through the lush tea plantations of Sri Lanka.

Africa is a continent of contrasts, with its vast savannahs, dense jungles, and stunning coastlines. Witness the majesty of the Great Migration in Kenya, encounter gorillas in the misty mountains of Rwanda, or relax on the pristine beaches of Zanzibar.

In the Americas, you can immerse yourself in the rich cultural heritage of the Mayan ruins in Mexico, explore the natural wonders of the Galapagos Islands in Ecuador, or experience the pulsating energy of Carnival in Brazil. The landscapes are as diverse as the people, ranging from the frozen wilderness of Alaska to the tropical rainforests of Costa Rica.

Australia and Oceania beckon with their pristine beauty and laid-back lifestyle. Dive into the Great Barrier Reef in Australia, hike through the lush rainforests of New Zealand, or witness the unique wildlife of the Galapagos Islands.

No matter where you go, travel opens your eyes to new perspectives, broadens your horizons, and fills your heart with a sense of wonder. It is an opportunity to connect with people from different backgrounds, to taste new cuisines, and to create memories that will last a lifetime.
```'''

    stub_responses_multiLine_no_codeblock = '''
The world is a vast and diverse place, filled with countless cultures, languages, and traditions. From the bustling streets of New York City to the serene landscapes of the Amazon rainforest, each corner of the globe offers its own unique charm and beauty.

In Europe, you can wander through the historic streets of Rome, marvel at the grandeur of the Eiffel Tower in Paris, or explore the picturesque villages of the Swiss Alps. The continent is steeped in history, with ancient ruins and medieval castles scattered throughout its lands.

Asia, on the other hand, is a vibrant tapestry of colors and flavors. From the neon lights of Tokyo to the tranquil temples of Kyoto, there is something for everyone. You can sample spicy street food in Bangkok, cruise along the breathtaking Halong Bay in Vietnam, or trek through the lush tea plantations of Sri Lanka.

Africa is a continent of contrasts, with its vast savannahs, dense jungles, and stunning coastlines. Witness the majesty of the Great Migration in Kenya, encounter gorillas in the misty mountains of Rwanda, or relax on the pristine beaches of Zanzibar.

In the Americas, you can immerse yourself in the rich cultural heritage of the Mayan ruins in Mexico, explore the natural wonders of the Galapagos Islands in Ecuador, or experience the pulsating energy of Carnival in Brazil. The landscapes are as diverse as the people, ranging from the frozen wilderness of Alaska to the tropical rainforests of Costa Rica.

Australia and Oceania beckon with their pristine beauty and laid-back lifestyle. Dive into the Great Barrier Reef in Australia, hike through the lush rainforests of New Zealand, or witness the unique wildlife of the Galapagos Islands.

No matter where you go, travel opens your eyes to new perspectives, broadens your horizons, and fills your heart with a sense of wonder. It is an opportunity to connect with people from different backgrounds, to taste new cuisines, and to create memories that will last a lifetime.

So pack your bags, embrace the unknown, and embark on an adventure of a lifetime. The world is waiting to be discovered.'''

    stub_responses_oneLine = '''```The world is a vast and diverse place, filled with countless cultures, languages, and traditions. From the bustling streets of New York City to the serene landscapes of the Amazon rainforest, each corner of the globe offers its own unique charm and beauty. In Europe, you can wander through the historic streets of Rome, marvel at the grandeur of the Eiffel Tower in Paris, or explore the picturesque villages of the Swiss Alps. The continent is steeped in history, with ancient ruins and medieval castles scattered throughout its lands. Asia, on the other hand, is a vibrant tapestry of colors and flavors. From the neon lights of Tokyo to the tranquil temples of Kyoto, there is something for everyone. You can sample spicy street food in Bangkok, cruise along the breathtaking Halong Bay in Vietnam, or trek through the lush tea plantations of Sri Lanka. Africa is a continent of contrasts, with its vast savannahs, dense jungles, and stunning coastlines. Witness the majesty of the Great Migration in Kenya, encounter gorillas in the misty mountains of Rwanda, or relax on the pristine beaches of Zanzibar. In the Americas, you can immerse yourself in the rich cultural heritage of the Mayan ruins in Mexico, explore the natural wonders of the Galapagos Islands in Ecuador, or experience the pulsating energy of Carnival in Brazil. The landscapes are as diverse as the people, ranging from the frozen wilderness of Alaska to the tropical rainforests of Costa Rica. Australia and Oceania beckon with their pristine beauty and laid-back lifestyle. Dive into the Great Barrier Reef in Australia, hike through the lush rainforests of New Zealand, or witness the unique wildlife of the Galapagos Islands. No matter where you go, travel opens your eyes to new perspectives, broadens your horizons, and fills your heart with a sense of wonder. It is an opportunity to connect with people from different backgrounds, to taste new cuisines, and to create memories that will last a lifetime. So pack your bags, embrace the unknown, and embark on an adventure of a lifetime. The world is waiting to be discovered.```'''

    stub_responses_short_line = "The world is a vast and diverse place, filled with countless cultures, languages, and traditions. From the bustling streets of New York City to the serene landscapes of the Amazon rainforest, each corner of the globe offers its own unique charm and beauty."

    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        return super().tearDown()

    @patch.dict(os.environ, {"bard_enable_auto_login": "True"})
    @patch.dict(os.environ, {"chrome_version": "113"})
    def test_aclient_init_1_1(self):
        print(
            f"\n==== Testing aclient_inti with {bcolors.OKBLUE}bard{bcolors.ENDC}_enable_auto_login is {bcolors.OKBLUE}True{bcolors.ENDC} ===="
        )

        expected_google_account = google_account
        expected_google_password = google_password
        expected_chrome_version = 113

        with patch('src.aclient.GoogleBardAutoLogin') as mock_GoogleBardAutoLogin:
            mock_instance = MagicMock()
            mock_GoogleBardAutoLogin.return_value = mock_instance
            mock_GoogleBardAutoLogin.return_value.get_cookie.return_value = "mock_cookie"

            client = aclient()

            mock_GoogleBardAutoLogin.assert_called_once_with(expected_google_account,
                                                             expected_google_password,
                                                             expected_chrome_version)
            mock_GoogleBardAutoLogin.return_value.get_cookie.assert_called_once()
            self.assertEqual(client.bard_session_id, "mock_cookie")

    @patch.dict(os.environ, {"bard_enable_auto_login": "False"})
    @patch.dict(os.environ, {"BARD_SESSION_ID": "mock_session_id"})
    def test_aclient_init_1_2(self):
        print(
            f"\n==== Testing aclient inti with {bcolors.OKBLUE}bard{bcolors.ENDC}_enable_auto_login is {bcolors.OKBLUE}False{bcolors.ENDC} ===="
        )

        client = aclient()

        self.assertEqual(client.bard_session_id, "mock_session_id")

    @patch.dict(os.environ, {"bing_enable_auto_login": "True"})
    @patch.dict(os.environ, {"chrome_version": "113"})
    def test_aclient_init_1_3(self):
        print(
            f"\n==== Testing aclient inti with {bcolors.OKBLUE}bing{bcolors.ENDC}_enable_auto_login is {bcolors.OKBLUE}False{bcolors.ENDC} ===="
        )

        expected_google_account = bing_account
        expected_google_password = bing_password
        expected_chrome_version = 113

        with patch('src.aclient.MicrosoftBingAutoLogin') as mock_MicrosoftBingAutoLogin:
            mock_instance = MagicMock()

            mock_MicrosoftBingAutoLogin.return_value = mock_instance
            mock_MicrosoftBingAutoLogin.return_value.dump_cookies.return_value = "mock_cookie"

            client = aclient()

            mock_MicrosoftBingAutoLogin.assert_called_once_with(expected_google_account,
                                                                expected_google_password,
                                                                expected_chrome_version)
            mock_MicrosoftBingAutoLogin.return_value.dump_cookies.assert_called_once()

    def test_get_chatbot_model(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.WARNING}{chat_model_env}{bcolors.ENDC} ===="
        )

        client = aclient()

        ori_chat_model = client.get_chatbot_model()

        # mock aclient chat_model attribute in __init__ method use patch.object with "new" parameter
        with patch.object(client, 'chat_model', new=chat_model_env):
            ret = client.get_chatbot_model()
            self.assertIsInstance(ret, type(ori_chat_model))

    def test_get_chatbot_model_with_invalid_chat_model(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.OKBLUE}INVALID_TEST{bcolors.ENDC} ===="
        )

        client = aclient()

        ori_chat_model = client.get_chatbot_model()

        # mock aclient chat_model attribute in __init__ method to "INVALID_TEST" use patch.object with "new" parameter
        with patch.object(client, 'chat_model', new="INVALID_TEST"):
            ret = client.get_chatbot_model()
            self.assertFalse(isinstance(ret, type(ori_chat_model)),
                             f"chatbot_mode object should not be {type(ori_chat_model)}")

    def test_get_chatbot_model_unofficial(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.OKBLUE}UNOFFICIAL{bcolors.ENDC} ===="
        )

        client = aclient()

        client.chat_model = "UNOFFICIAL"
        expected_config = {
            "email": openAI_email,
            "password": openAI_password,
            "access_token": chatgpt_access_token,
            "model": "text-davinci-002-render-sha"
            if openAI_gpt_engine == "gpt-3.5-turbo" else openAI_gpt_engine,
            "paid": chatgpt_paid
        }

        with patch('src.aclient.AsyncChatbot') as mock_asyncChatbot:
            mock_instance = MagicMock()

            mock_asyncChatbot.return_value = mock_instance

            chatbot = client.get_chatbot_model()

            mock_asyncChatbot.assert_called_once_with(config=expected_config)
            self.assertEqual(chatbot, mock_instance)

    def test_get_chatbot_model_official(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} ===="
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        expected_api_key = openAI_API_key
        expected_engine = openAI_gpt_engine
        expected_prompt = "Hello there"

        with patch('src.aclient.Chatbot') as mock_chatbot:
            mock_instance = MagicMock()

            mock_chatbot.return_value = mock_instance

            chatbot = client.get_chatbot_model()

            mock_chatbot.assert_called_once_with(api_key=expected_api_key,
                                                 engine=expected_engine,
                                                 system_prompt=expected_prompt)
            self.assertEqual(chatbot, mock_instance)

    @patch.dict(os.environ, {"BARD_SESSION_ID": "mock_session_id"})
    def test_get_chatbot_model_bard(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.OKBLUE}Bard{bcolors.ENDC} ===="
        )

        client = aclient()

        client.chat_model = "Bard"
        expected_session_id = "mock_session_id"

        with patch('src.aclient.BardChatbot') as mock_bard_chatbot:
            mock_instance = MagicMock()

            mock_bard_chatbot.return_value = mock_instance

            chatbot = client.get_chatbot_model()

            mock_bard_chatbot.assert_called_once_with(session_id=expected_session_id)
            self.assertEqual(chatbot, mock_instance)

    def test_get_chatbot_model_bing(self):
        print(
            f"\n==== Testing get_chatbot_model with chat_model is {bcolors.OKBLUE}Bing{bcolors.ENDC} ===="
        )

        client = aclient()

        client.chat_model = "Bing"
        expected_cookie_path = './cookies.json'

        with patch('src.aclient.EdgeChatbot') as mock_bing_chatbot:
            mock_instance = MagicMock()

            mock_bing_chatbot.return_value = mock_instance

            chatbot = client.get_chatbot_model()

            mock_bing_chatbot.assert_called_once_with(cookie_path=expected_cookie_path)
            self.assertEqual(chatbot, mock_instance)

    @patch.object(aclient, 'send_message', return_value=None)
    async def test_process_messages_1_1(self, mock_send_message):
        print(
            f"\n==== Testing process_messages with current_channel is {bcolors.OKBLUE}None{bcolors.ENDC} ===="
        )

        # spy on asyncio.sleep() to avoid waiting
        def fake_sleep(*args, **kwargs):
            return asyncio.Future().set_result(None)

        # Throw an exception on the asyncio.sleep() second call
        with patch.object(asyncio, 'sleep', side_effect=[fake_sleep, Exception()]) as mock_sleep:

            client = aclient()

            client.current_channel = None

            with self.assertRaises(Exception):
                await client.process_messages()

            mock_sleep.assert_called()
            mock_sleep.assert_called_with(1)

    @patch.object(aclient, 'send_message', return_value=None)
    async def test_process_messages_1_2(self, mock_send_message):
        print(
            f"\n==== Testing process_messages with current_channel is {bcolors.OKBLUE}not None{bcolors.ENDC} ===="
        )

        client = aclient()
        client.current_channel = MagicMock()
        client.current_channel.typing.return_value = AsyncContextManagerMock()
        # client.current_channel.typing.return_value.__aenter__.return_value = ''

        with patch.object(client, 'message_queue') as mock_message_queue:
            future_1 = asyncio.Future()
            future_1.set_result(('mock_message_1', 'mock_user_message_1'))

            future_2 = asyncio.Future()
            # Throw an exception on the message_queue second call
            future_2.set_exception(StopAsyncIteration)

            # Determine the order of callbacks and exceptions
            mock_message_queue.get.side_effect = [future_1, future_2]

            mock_message_queue.empty.return_value = False

            # Start execution and test
            # Expect an exception to be thrown at the end of the loop
            with self.assertRaises(StopAsyncIteration):
                self.loop.run_until_complete(await client.process_messages())

        mock_send_message.assert_called_once_with('mock_message_1', 'mock_user_message_1')
        mock_message_queue.task_done.assert_called_once()

    @patch('src.aclient.logger')
    @patch.object(aclient, 'send_message')
    async def test_process_messages_2(self, mock_send_message, mock_logger):
        print("\n==== Testing process_messages with send_message exception ====")

        client = aclient()
        client.current_channel = MagicMock()
        client.current_channel.typing.return_value = AsyncContextManagerMock()

        with patch.object(client, 'message_queue') as mock_message_queue:
            future_1 = asyncio.Future()
            future_1.set_result(('mock_message_1', 'mock_user_message_1'))

            future_2 = asyncio.Future()
            future_2.set_exception(StopAsyncIteration)

            mock_message_queue.get.side_effect = [future_1, future_2]

            mock_message_queue.empty.return_value = False

            # Make send_message throw an exception
            mock_send_message.side_effect = Exception('mock exception')

            with self.assertRaises(StopAsyncIteration):
                self.loop.run_until_complete(await client.process_messages())

            mock_send_message.assert_called_once_with('mock_message_1', 'mock_user_message_1')
            mock_logger.exception.assert_called_once()
            mock_logger.exception.assert_called_once_with(
                "Error while processing message: mock exception")
            mock_message_queue.task_done.assert_called_once()

    def test_enqueue_message(self):
        print("\n==== Testing enqueue_message ====")

        client = aclient()
        client.is_replying_all = "False"

        # Create mock message and user_message
        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'

        # Create mock response
        mock_response = AsyncMock()
        mock_message.response = mock_response

        with patch.object(client, 'message_queue') as mock_message_queue:
            # Mock the return value of message_queue.put
            future_1 = asyncio.Future()
            future_1.set_result(None)
            mock_message_queue.put.return_value = future_1

            self.loop.run_until_complete(client.enqueue_message(mock_message, mock_user_message))

        mock_response.defer.assert_called_once_with(ephemeral=client.isPrivate)
        mock_message_queue.put.assert_called_once_with((mock_message, mock_user_message))

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_multiLine)
    @patch('src.responses.unofficial_handle_response', return_value=stub_responses_multiLine)
    @patch('src.responses.bard_handle_response', return_value=stub_responses_multiLine)
    @patch('src.responses.bing_handle_response', return_value=stub_responses_multiLine)
    def test_send_message(self, mock_bing_handle_response, mock_bard_handle_response,
                          mock_unofficial_handle_response, mock_official_handle_response,
                          mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.WARNING}{chat_model_env}{bcolors.ENDC} (use getenv()) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use getenv()) is {bcolors.WARNING}"{is_replying_all}"{bcolors.ENDC}'
        )

        client = aclient()

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        # Create a mock send
        mock_message.channel.send = AsyncMock()
        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        # Verify that handle_response is called
        if client.chat_model == "OFFICIAL":
            mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        elif client.chat_model == "UNOFFICIAL":
            mock_unofficial_handle_response.assert_called_once_with(mock_user_message, client)
        elif client.chat_model == "Bard":
            mock_bard_handle_response.assert_called_once_with(mock_user_message, client)
        elif client.chat_model == "Bing":
            mock_bing_handle_response.assert_called_once_with(mock_user_message, client)

        # Verify that message.channel.send or message.followup.send was called
        if client.is_replying_all == "True":
            mock_message.channel.send.assert_called()
        else:
            mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    def test_send_message_1_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] {bcolors.OKBLUE}respones length shorter than 2000{bcolors.ENDC} / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    def test_send_message_1_2(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] {bcolors.OKBLUE}respones length shorter than 2000{bcolors.ENDC} / is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_multiLine)
    def test_send_message_2_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messagwith {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()  # is_replying_all = True

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.unofficial_handle_response', return_value=stub_responses_multiLine)
    def test_send_message_2_2(self, mock_unofficial_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messagwith {bcolors.OKBLUE}UNOFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "UNOFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_unofficial_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.bard_handle_response', return_value=stub_responses_multiLine)
    def test_send_message_2_3(self, mock_bard_handle_response, mock_logger):
        print(f"\n==== Testing send_messagwith {bcolors.OKBLUE}Bard{bcolors.ENDC} (use mock) ====")
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "Bard"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_bard_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.bing_handle_response', return_value=stub_responses_multiLine)
    def test_send_message_2_4(self, mock_bing_handle_response, mock_logger):
        print(f"\n==== Testing send_messagwith {bcolors.OKBLUE}Bing{bcolors.ENDC} (use mock) ====")
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "Bing"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_bing_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_multiLine)
    def test_send_message_2_1_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}'
        )

        client = aclient()

        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_oneLine)
    def test_send_message_3_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}{chat_model_env}{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / {bcolors.OKBLUE}codeblock single line over char_limit{bcolors.ENDC} / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_oneLine)
    def test_send_message_3_2(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}{chat_model_env}{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / {bcolors.OKBLUE}codeblock single line over char_limit{bcolors.ENDC} / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response',
           return_value=stub_responses_multiLine_short_limit)
    def test_send_message_4_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}{chat_model_env}{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / {bcolors.OKBLUE}formatted_code_block length not over 2000{bcolors.ENDC} / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response',
           return_value=stub_responses_multiLine_short_limit)
    def test_send_message_4_2(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}{chat_model_env}{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] respones have codeblock / respones length over 2000 / codeblock single line not over char_limit / {bcolors.OKBLUE}formatted_code_block length not over 2000{bcolors.ENDC} / is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response',
           return_value=stub_responses_multiLine_no_codeblock)
    def test_send_message_5_1(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] {bcolors.OKBLUE}respones no have codeblock{bcolors.ENDC} / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response',
           return_value=stub_responses_multiLine_no_codeblock)
    def test_send_message_5_2(self, mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_messag with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] {bcolors.OKBLUE}respones no have codeblock{bcolors.ENDC} / respones length over 2000 / codeblock single line not over char_limit / formatted_code_block length over 2000 / is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', side_effect=Exception('mock exception'))
    def test_send_message_6_1(self, mock_official_handle_response, mock_logger):
        print("\n==== Testing send_messag with handle_response exception ====")
        print(f'[+] is_replying_all(use mock) is {bcolors.OKBLUE}"True"{bcolors.ENDC}')

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "True"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.channel.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.channel.send.assert_called()
        mock_message.channel.send.assert_called_once_with(
            "> **ERROR: Something went wrong, please try again later!** \n ```ERROR MESSAGE: mock exception```"
        )
        mock_logger.exception.assert_called_once()
        mock_logger.exception.assert_called_once_with("Error while sending message: mock exception")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', side_effect=Exception('mock exception'))
    def test_send_message_6_2(self, mock_official_handle_response, mock_logger):
        print("\n==== Testing send_messag with handle_response exception ====")
        print(f'[+] is_replying_all(use mock) is {bcolors.OKBLUE}"False"{bcolors.ENDC}')

        client = aclient()

        client.chat_model = "OFFICIAL"
        client.is_replying_all = "False"

        mock_message = MagicMock()
        mock_user_message = 'mock_user_message'
        mock_message.user.id = 'mock_user_id'
        mock_message.author.id = 'mock_author_id'

        mock_message.followup.send = AsyncMock()

        self.loop.run_until_complete(client.send_message(mock_message, mock_user_message))

        mock_official_handle_response.assert_called_once_with(mock_user_message, client)
        mock_message.followup.send.assert_called()
        mock_message.followup.send.assert_called_once_with(
            "> **ERROR: Something went wrong, please try again later!** \n ```ERROR MESSAGE: mock exception```"
        )
        mock_logger.exception.assert_called_once()
        mock_logger.exception.assert_called_once_with("Error while sending message: mock exception")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    @patch('src.responses.unofficial_handle_response', return_value=stub_responses_short_line)
    @patch('src.responses.bard_handle_response', return_value=stub_responses_short_line)
    @patch('src.responses.bing_handle_response', return_value=stub_responses_short_line)
    async def test_send_start_prompt(self, mock_bing_handle_response, mock_bard_handle_response,
                                     mock_unofficial_handle_response, mock_official_handle_response,
                                     mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.WARNING}{chat_model_env}{bcolors.ENDC} (use getenv()) ===="
        )
        print(f'[+] discord_channel_id is {bcolors.WARNING}"{discord_channel_id}"{bcolors.ENDC}')

        config_dir = os.path.abspath(f"{__file__}/../../")
        prompt_name = 'system_prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)
        print(f'[+] system_prompt.txt in {bcolors.WARNING}{prompt_path}{bcolors.ENDC}')

        client = aclient()

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read()

            await client.send_start_prompt()

            mock_logger.info.assert_called_once()

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": ""})
    async def test_send_start_prompt_1_1(self, mock_getsize, mock_isfile,
                                         mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}""{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        await client.send_start_prompt()

        mock_logger.info.assert_called_once()
        mock_logger.info.assert_called_once_with("No Channel selected. Skip sending system prompt.")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=0)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": ""})
    async def test_send_start_prompt_1_2(self, mock_getsize, mock_isfile,
                                         mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}""{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}== 0{bcolors.ENDC}'
        )

        client = aclient()

        await client.send_start_prompt()

        mock_logger.info.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "No system_prompt.txt. Skip sending system prompt.")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value=stub_responses_short_line)
    @patch('os.path.isfile', return_value=False)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": ""})
    async def test_send_start_prompt_1_3(self, mock_isfile, mock_official_handle_response,
                                         mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}""{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}False{bcolors.ENDC}'
        )

        client = aclient()

        await client.send_start_prompt()

        mock_logger.info.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "No system_prompt.txt. Skip sending system prompt.")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', return_value="Mock response")
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": "123456"})
    async def test_send_start_prompt_1_4_1(self, mock_getsize, mock_isfile,
                                           mock_official_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}"123456"{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"
        mock_prompt = 'Hello there'

        # Note:
        # Since `self.get_channel()` has not yet been implemented, and the returned `channel` object is only used in `channel.send()` in subsequent steps,
        # so the return of `self.get_channel()` is not verified here Pass by value
        # Therefore, only need to mock `self.get_channel()`, no need to spy `self.get_channel()` return value and its behavior
        with patch.object(client, 'get_channel') as mock_get_channel:
            mock_channel = MagicMock()
            # channel.send() is an async function, so need to use AsyncMock
            mock_channel.send = AsyncMock()
            mock_get_channel.return_value = mock_channel

            await client.send_start_prompt()

            mock_get_channel.assert_called_once_with(int("123456"))
            mock_channel.send.assert_called_once_with("Mock response")
            mock_logger.info.assert_called()
            mock_logger.info.assert_any_call(f"Send system prompt with size {len(mock_prompt)}")
            mock_logger.info.assert_any_call("System prompt response:Mock response")

    @patch('src.aclient.logger')
    @patch('src.responses.unofficial_handle_response', return_value="Mock response")
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": "123456"})
    async def test_send_start_prompt_1_4_2(self, mock_getsize, mock_isfile,
                                           mock_unofficial_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}UNOFFICIAL{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}"123456"{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "UNOFFICIAL"
        mock_prompt = 'Hello there'

        with patch.object(client, 'get_channel') as mock_get_channel:
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock()
            mock_get_channel.return_value = mock_channel

            await client.send_start_prompt()

            mock_get_channel.assert_called_once_with(int("123456"))
            mock_channel.send.assert_called_once_with("Mock response")
            mock_logger.info.assert_called()
            mock_logger.info.assert_any_call(f"Send system prompt with size {len(mock_prompt)}")
            mock_logger.info.assert_any_call("System prompt response:Mock response")

    @patch('src.aclient.logger')
    @patch('src.responses.bard_handle_response', return_value="Mock response")
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": "123456"})
    async def test_send_start_prompt_1_4_3(self, mock_getsize, mock_isfile,
                                           mock_brad_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}Brad{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}"123456"{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "Bard"
        mock_prompt = 'Hello there'

        with patch.object(client, 'get_channel') as mock_get_channel:
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock()
            mock_get_channel.return_value = mock_channel

            await client.send_start_prompt()

            mock_get_channel.assert_called_once_with(int("123456"))
            mock_channel.send.assert_called_once_with("Mock response")
            mock_logger.info.assert_called()
            mock_logger.info.assert_any_call(f"Send system prompt with size {len(mock_prompt)}")
            mock_logger.info.assert_any_call("System prompt response:Mock response")

    @patch('src.aclient.logger')
    @patch('src.responses.bing_handle_response', return_value="Mock response")
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": "123456"})
    async def test_send_start_prompt_1_4_4(self, mock_getsize, mock_isfile,
                                           mock_bing_handle_response, mock_logger):
        print(
            f"\n==== Testing send_start_prompt with {bcolors.OKBLUE}Bing{bcolors.ENDC} (use mock) ===="
        )
        print(
            f'[+] discord_channel_id is {bcolors.OKBLUE}"123456"{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "Bing"
        mock_prompt = 'Hello there'

        with patch.object(client, 'get_channel') as mock_get_channel:
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock()
            mock_get_channel.return_value = mock_channel

            await client.send_start_prompt()

            mock_get_channel.assert_called_once_with(int("123456"))
            mock_channel.send.assert_called_once_with("Mock response")
            mock_logger.info.assert_called()
            mock_logger.info.assert_any_call(f"Send system prompt with size {len(mock_prompt)}")
            mock_logger.info.assert_any_call("System prompt response:Mock response")

    @patch('src.aclient.logger')
    @patch('src.responses.official_handle_response', side_effect=Exception('mock exception'))
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=11)
    @patch.dict(os.environ, {"DISCORD_CHANNEL_ID": "123456"})
    async def test_send_start_prompt_2(self, mock_getsize, mock_isfile,
                                       mock_official_handle_response, mock_logger):
        print("\n==== Testing send_start_prompt with handle_response exception ====")
        print(
            f'[+] {bcolors.OKBLUE}OFFICIAL{bcolors.ENDC} / discord_channel_id is {bcolors.OKBLUE}"123456"{bcolors.ENDC} /  os.path.isfile() is {bcolors.OKBLUE}True{bcolors.ENDC} / os.path.getsize() {bcolors.OKBLUE}> 0{bcolors.ENDC}'
        )

        client = aclient()

        client.chat_model = "OFFICIAL"

        await client.send_start_prompt()

        mock_logger.exception.assert_called()
        mock_logger.exception.assert_called_once_with(
            "Error while sending system prompt: mock exception")


if __name__ == '__main__':
    unittest.main(verbosity=2)  # pragma: no cover
