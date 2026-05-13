"""Централизованное логирование TMUS Tunnel Manager."""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.expanduser("~"), ".tmus_tunnel_manager", "logs")


def setup_logger(name: str = "TMUS") -> logging.Logger:
    """Создаёт и возвращает настроенный логгер."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # Формат
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Файловый handler с ротацией (5 МБ, 3 бэкапа)
    log_file = os.path.join(LOG_DIR, f"tmus_{datetime.now().strftime('%Y%m%d')}.log")
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Консольный handler (только INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logger()
