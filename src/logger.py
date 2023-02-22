import os
import logging
import logging.handlers


class CustomFormatter(logging.Formatter):
    __LEVEL_COLORS = [
        (logging.DEBUG, '\x1b[40;1m'),
        (logging.INFO, '\x1b[34;1m'),
        (logging.WARNING, '\x1b[33;1m'),
        (logging.ERROR, '\x1b[31m'),
        (logging.CRITICAL, '\x1b[41m'),
    ]
    __FORMATS = None

    @classmethod
    def get_formats(cls):
        if cls.__FORMATS is None:
            cls.__FORMATS = {
                level: logging.Formatter(
                    f'\x1b[30;1m%(asctime)s\x1b[0m {color}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m -> %(message)s',
                    '%Y-%m-%d %H:%M:%S'
                )
                for level, color in cls.__LEVEL_COLORS
            }
        return cls.__FORMATS

    def format(self, record):
        formatter = self.get_formats().get(record.levelno)
        if formatter is None:
            formatter = self.get_formats()[logging.DEBUG]
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f'\x1b[31m{text}\x1b[0m'

        output = formatter.format(record)
        record.exc_text = None
        return output


class LoggerFactory:
    @staticmethod
    def create_logger(formatter, handlers):
        logger = logging.getLogger('chatgpt_logger')
        logger.setLevel(logging.INFO)
        for handler in handlers:
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger


class FileHandler(logging.FileHandler):
    def __init__(self, log_file):
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        super().__init__(log_file)


class ConsoleHandler(logging.StreamHandler):
    pass


formatter = CustomFormatter()
file_handler = FileHandler('./logs')
console_handler = ConsoleHandler()
logger = LoggerFactory.create_logger(formatter, [file_handler, console_handler])