"""Управление WireGuard-клиентом на локальной Windows-машине."""

import os
import subprocess

from ..utils.logger import log

LAST_ERROR = ""
TUNNEL_NAME = "TMUS"

_WG_PATHS = [
    r"C:\Program Files\WireGuard",
    r"C:\Program Files (x86)\WireGuard",
]


def _find_exe(name: str) -> str | None:
    for base in _WG_PATHS:
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    try:
        result = subprocess.run(["where", name], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def _find_wg() -> str | None:
    return _find_exe("wg.exe")


def _find_wireguard() -> str | None:
    return _find_exe("wireguard.exe")


def is_wireguard_installed() -> bool:
    return (_find_wg() is not None) and (_find_wireguard() is not None)


def generate_local_keys() -> tuple[str, str]:
    """Генерирует ключи через wg.exe. ВАЖНО: genkey/pubkey есть в wg.exe, не в wireguard.exe."""
    wg = _find_wg()
    if not wg:
        log.error("wg.exe не найден. Переустановите WireGuard for Windows: https://www.wireguard.com/install/")
        return "", ""
    try:
        proc = subprocess.run([wg, "genkey"], capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            log.error(f"wg genkey error: {proc.stderr.strip() or proc.stdout.strip()}")
            return "", ""
        private_key = proc.stdout.strip()
        if not private_key:
            log.error("wg genkey вернул пустой приватный ключ")
            return "", ""

        proc = subprocess.run([wg, "pubkey"], input=private_key + "\n", capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            log.error(f"wg pubkey error: {proc.stderr.strip() or proc.stdout.strip()}")
            return "", ""
        public_key = proc.stdout.strip()
        if not public_key:
            log.error("wg pubkey вернул пустой публичный ключ")
            return "", ""
        return private_key, public_key
    except Exception as e:
        log.error(f"Ошибка генерации ключей WireGuard через wg.exe: {e}")
        return "", ""


def get_last_error() -> str:
    return LAST_ERROR


def _set_error(message: str) -> None:
    global LAST_ERROR
    LAST_ERROR = message
    log.error(message)


def create_local_config(
    private_key: str,
    local_vpn_ip: str,
    server_public_key: str,
    server_endpoint: str,
    server_port: int,
    persistent_keepalive: int = 25,
) -> str:
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {local_vpn_ip}
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}:{server_port}
AllowedIPs = 10.99.0.0/24
PersistentKeepalive = {persistent_keepalive}
"""
    config_dir = os.path.join(os.path.expanduser("~"), ".tmus_tunnel_manager", "wg_confs")
    os.makedirs(config_dir, exist_ok=True)
    # Имя файла = имя WireGuard-туннеля/сервиса. Без пробелов и кириллицы.
    config_path = os.path.join(config_dir, f"{TUNNEL_NAME}.conf")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config)
    log.info(f"Клиентский конфиг WireGuard сохранён: {config_path}")
    return config_path


def install_tunnel_service(config_path: str) -> bool:
    global LAST_ERROR
    LAST_ERROR = ""
    wireguard = _find_wireguard()
    if not wireguard:
        _set_error("wireguard.exe не найден.")
        return False
    if not os.path.exists(config_path):
        _set_error(f"Конфиг туннеля не найден: {config_path}")
        return False
    try:
        result = subprocess.run(
            [wireguard, "/installtunnelservice", config_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            details = (result.stderr.strip() or result.stdout.strip() or f"код выхода {result.returncode}")
            _set_error(f"Ошибка установки сервиса WireGuard: {details}")
            return False
        log.info("Сервис туннеля WireGuard установлен.")
        return True
    except Exception as e:
        _set_error(f"Исключение при установке сервиса туннеля: {e}")
        return False


def uninstall_tunnel_service(config_path: str) -> bool:
    wireguard = _find_wireguard()
    if not wireguard:
        return False
    try:
        # wireguard.exe /uninstalltunnelservice принимает имя туннеля, а не путь к .conf
        tunnel_name = os.path.splitext(os.path.basename(config_path))[0] if config_path else TUNNEL_NAME
        result = subprocess.run(
            [wireguard, "/uninstalltunnelservice", tunnel_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.debug(f"Удаление сервиса WireGuard: {result.stderr.strip() or result.stdout.strip()}")
        return result.returncode == 0
    except Exception as e:
        log.error(f"Исключение при удалении сервиса туннеля: {e}")
        return False


def is_tunnel_active() -> bool:
    wg = _find_wg()
    if not wg:
        return False
    try:
        result = subprocess.run([wg, "show"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def get_tunnel_status() -> str:
    wg = _find_wg()
    if not wg:
        return "WireGuard не установлен"
    try:
        result = subprocess.run([wg, "show"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "Туннель не активен"
    except Exception as e:
        return f"Ошибка: {e}"


def ping_vpn_ip(ip: str, timeout: int = 3) -> bool:
    try:
        result = subprocess.run(["ping", "-n", "1", "-w", str(timeout * 1000), ip], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False
