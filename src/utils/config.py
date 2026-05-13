"""Управление конфигурацией приложения."""

import json
import os
from typing import Any

from .logger import log

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tmus_tunnel_manager")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "vps_ip": "",
    "vps_ssh_user": "root",
    "vps_ssh_password": "",
    "vps_ssh_port": 22,
    "wg_interface": "wg0",
    "wg_port": 51820,
    "forwarded_ports": [],  # [{"local_port": 8080, "remote_ip": "0.0.0.0", "remote_port": 80}, ...]
    "auto_reconnect": True,
    "reconnect_delay_sec": 5,
    "max_reconnect_attempts": 0,  # 0 = бесконечно
    "autostart": False,
    "minimize_to_tray": True,
    "keep_logs_days": 30,
}


def load_config() -> dict[str, Any]:
    """Загружает конфигурацию из JSON-файла."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Мержим с дефолтом — подтягиваем новые ключи
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Не удалось загрузить конфиг: {e}. Использую значения по умолчанию.")
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict[str, Any]) -> None:
    """Сохраняет конфигурацию в JSON-файл."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        log.debug("Конфигурация сохранена.")
    except OSError as e:
        log.error(f"Ошибка сохранения конфигурации: {e}")
