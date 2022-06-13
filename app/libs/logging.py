import os
import sys
import logging

from loguru       import logger


LOG_LEVEL = logging.getLevelName( os.environ.get("LOG_LEVEL", "DEBUG") )
JSON_LOGS = True if os.environ.get("JSON_LOGS", "0") == "1" else False

# Override HTTPX log level in case of DEBUG to avoid redundancy
if LOG_LEVEL == logging.DEBUG:
    logging.getLogger("httpx").setLevel(logging.INFO)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame =  frame.f_back
            depth += 1

        message = record.getMessage()
        logger.opt(depth = depth, exception = record.exc_info).log(level, message)


def setup_logging():
    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(LOG_LEVEL)

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers  = []
        logging.getLogger(name).propagate = True

    # configure loguru
    logger.configure(handlers = [{
        "sink":      sys.stdout,
        "serialize": JSON_LOGS,
        "format":    '<green>{time:YYYY/MM/DD - HH:mm:ss}</green> | <level>{level:5.5}</level> | <cyan>{name:20.20}</cyan>:<cyan>{line: <4}</cyan> | <level>{message}</level>'
    }])
