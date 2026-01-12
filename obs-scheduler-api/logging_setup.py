import logging
from pathlib import Path

import data_provider as dp

_LOGGER = None


def get_error_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    logger = logging.getLogger("obs_scheduler")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    log_dir = dp.DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "errors.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    _LOGGER = logger
    return logger
