import unittest
from unittest.mock import patch
from unittest.mock import Mock
from src.log import setup_logger, CustomFormatter
import logging

class TestLogger(unittest.TestCase):

    @patch('src.log.os')
    @patch('src.log.logging')
    def test_setup_logger(self, logging_mock, os_mock):
        print('\n==== Testing for setup_logger() ====')
        os_mock.getenv.return_value = "True"
        module_name = 'bot.py'
        setup_logger(module_name)
        logger_mock = logging_mock.getLogger.return_value
        logging_mock.getLogger.assert_called_with('bot')
        logger_mock.setLevel.assert_called_once()

        logging_mock.getLevelName.assert_called_with('INFO')

        logging_mock.StreamHandler.assert_called_once()

        os_mock.getenv.assert_called_with("LOGGING")
        logging_mock.handlers.RotatingFileHandler.assert_called_once()


class TestFormator(unittest.TestCase):

    def test_formatter(self):
        print('\n==== Testing for formatter() ====')
        formator = CustomFormatter()
        record_attr = {"levelno": 20, "levelname": "INFO", "name": "mytest"}
        record = logging.makeLogRecord(record_attr)
        ret = formator.format(record)
        self.assertIn("INFO", ret)
        self.assertIn("mytest", ret)

if __name__ == "__main__":
    unittest.main() #pragma: no cover
