import logging
import sys

def setup_logger(name="drake", level=logging.INFO):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Avoid adding handles multiple times.

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger
