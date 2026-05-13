"""Оркестратор туннеля: связывает VPS, WireGuard и проброс портов."""

import threading
import time

from ..utils.config import load_config, save_config
from ..utils.logger import log
from .ssh_client import SSHClient
from .wireguard_local import (
    create_local_config,
    generate_local_keys,
    get_last_error,
    install_tunnel_service,
    is_tunnel_active,
    is_wireguard_installed,
    ping_vpn_ip,
    uninstall_tunnel_service,
)
from .wireguard_vps import WireGuardVPS


class TunnelSession:
    """Одна сессия туннеля. Хранит состояние."""

    def __init__(self):
        self.ssh: SSHClient | None = None
        self.wg_vps: WireGuardVPS | None = None
        self.local_private: str = ""
        self.local_public: str = ""
        self.local_vpn_ip: str = "10.99.0.2"
        self.config_path: str = ""
        self._connected = False
        self._reconnect_thread: threading.Thread | None = None
        self._stop_reconnect = threading.Event()

    @property
    def connected(self) -> bool:
        return self._connected


# Глобальная сессия
_session: TunnelSession | None = None


def get_session() -> TunnelSession:
    global _session
    if _session is None:
        _session = TunnelSession()
    return _session


def connect(
    progress_callback=None,
    vps_ip: str = "",
    vps_ssh_user: str = "root",
    vps_ssh_password: str = "",
    vps_ssh_port: int = 22,
    forwarded_ports: list | None = None,
) -> bool:
    """
    Полный цикл подключения:
    1. SSH на VPS
    2. Проверка/установка WireGuard на VPS
    3. Генерация ключей (локально + сервер)
    4. Конфигурация сервера и клиента
    5. Запуск туннеля
    6. Проброс портов
    """
    cfg = load_config()
    vps_ip = vps_ip or cfg.get("vps_ip", "")
    vps_ssh_user = vps_ssh_user or cfg.get("vps_ssh_user", "root")
    vps_ssh_password = vps_ssh_password or cfg.get("vps_ssh_password", "")
    vps_ssh_port = vps_ssh_port or cfg.get("vps_ssh_port", 22)
    forwarded_ports = forwarded_ports or cfg.get("forwarded_ports", [])

    if not vps_ip:
        log.error("IP VPS не указан.")
        if progress_callback:
            progress_callback("Ошибка: IP VPS не указан", "error")
        return False

    if not is_wireguard_installed():
        log.error("WireGuard не установлен на вашем ПК. Скачайте: https://www.wireguard.com/install/")
        if progress_callback:
            progress_callback("WireGuard не установлен локально!", "error")
        return False

    s = get_session()

    # --- Шаг 1: SSH ---
    if progress_callback:
        progress_callback(f"Подключение по SSH к {vps_ip}:{vps_ssh_port}...")
    s.ssh = SSHClient(vps_ip, vps_ssh_port, vps_ssh_user, vps_ssh_password)
    if not s.ssh.connect():
        if progress_callback:
            progress_callback("Ошибка SSH-подключения. Проверьте данные.", "error")
        return False

    ok, msg = s.ssh.test_connection()
    if not ok:
        log.error(f"SSH тест провален: {msg}")
        if progress_callback:
            progress_callback(f"Ошибка SSH: {msg}", "error")
        return False
    if progress_callback:
        progress_callback(f"SSH подключён: {msg.split(chr(10))[0]}")

    # --- Шаг 2: WireGuard на VPS ---
    s.wg_vps = WireGuardVPS(s.ssh)
    if not s.wg_vps.install_wireguard(lambda msg: progress_callback(msg) if progress_callback else None):
        if progress_callback:
            progress_callback("Не удалось установить WireGuard на VPS", "error")
        return False
    s.wg_vps.enable_ip_forwarding()

    # --- Шаг 3: Ключи ---
    if progress_callback:
        progress_callback("Генерация ключей WireGuard...")
    priv, pub = generate_local_keys()
    if not priv:
        if progress_callback:
            progress_callback("Не удалось сгенерировать локальные ключи", "error")
        return False
    s.local_private = priv
    s.local_public = pub

    # --- Шаг 4: Конфигурация сервера ---
    s.wg_vps.generate_server_keys()
    s.wg_vps.create_server_config()
    s.wg_vps.start_server()
    s.wg_vps.add_peer(s.local_public, f"{s.local_vpn_ip}/32")

    server_pub = s.wg_vps._server_public
    server_endpoint = s.wg_vps.get_endpoint_ip()
    listen_port = s.wg_vps.get_listen_port()

    if progress_callback:
        progress_callback(f"Сервер WireGuard настроен (endpoint: {server_endpoint}:{listen_port})")

    # --- Шаг 5: Конфигурация клиента и запуск туннеля ---
    if progress_callback:
        progress_callback("Создание конфигурации клиента...")
    s.config_path = create_local_config(
        private_key=s.local_private,
        local_vpn_ip=f"{s.local_vpn_ip}/32",
        server_public_key=server_pub,
        server_endpoint=server_endpoint,
        server_port=listen_port,
    )

    # Сначала удалим старый сервис, если есть
    uninstall_tunnel_service(s.config_path)
    time.sleep(1)

    if not install_tunnel_service(s.config_path):
        details = get_last_error() or "неизвестная ошибка"
        if progress_callback:
            progress_callback(f"Не удалось установить сервис туннеля: {details}", "error")
            progress_callback("Подсказка: WireGuard-туннель требует прав администратора Windows. Запустите программу от имени администратора.", "warn")
        return False

    # Ждём поднятия туннеля
    if progress_callback:
        progress_callback("Ожидание активации туннеля...")
    for i in range(15):
        time.sleep(1)
        if is_tunnel_active():
            break

    if not is_tunnel_active():
        log.error("Туннель не активировался.")
        if progress_callback:
            progress_callback("Туннель не активировался за отведённое время", "error")
        return False

    # Проверяем связность
    if progress_callback:
        progress_callback("Проверка связности туннеля...")
    if not ping_vpn_ip("10.99.0.1", timeout=5):
        log.warning("Пинг сервера туннеля не удался, но туннель может работать.")

    if progress_callback:
        progress_callback("Туннель активен! Пинг до сервера успешен." if ping_vpn_ip("10.99.0.1") else "Туннель активен (пинг нестабилен).")

    # --- Шаг 6: Проброс портов ---
    s.wg_vps.clear_all_forwards(s.local_vpn_ip)
    for fwd in forwarded_ports:
        try:
            local_port = int(fwd.get("local_port", 0))
            remote_port = int(fwd.get("remote_port", local_port))
            if local_port <= 0 or local_port > 65535:
                continue
            if remote_port <= 0 or remote_port > 65535:
                remote_port = local_port
            if progress_callback:
                progress_callback(f"Проброс порта: внешний {remote_port} -> {s.local_vpn_ip}:{local_port}")
            s.wg_vps.add_port_forward(
                external_port=remote_port,
                target_ip=s.local_vpn_ip,
                target_port=local_port,
            )
        except (ValueError, TypeError) as e:
            log.error(f"Некорректный порт в настройках: {fwd} — {e}")

    s._connected = True
    if progress_callback:
        progress_callback("Подключение завершено!", "success")
    log.info("TMUS Tunnel успешно подключён и настроен.")
    return True


def disconnect() -> bool:
    """Отключает туннель и очищает ресурсы."""
    s = get_session()
    s._stop_reconnect.set()

    # Удаляем пробросы портов
    if s.wg_vps and s.ssh and s.ssh.connected:
        try:
            s.wg_vps.clear_all_forwards(s.local_vpn_ip)
        except Exception as e:
            log.warning(f"Не удалось очистить пробросы портов: {e}")

    # Удаляем клиентский туннель
    if s.config_path:
        uninstall_tunnel_service(s.config_path)

    # Отключаем SSH
    if s.ssh:
        s.ssh.disconnect()

    s._connected = False
    log.info("TMUS Tunnel отключён.")
    return True


def start_auto_reconnect():
    """Запускает фоновый поток автопереподключения."""
    cfg = load_config()
    if not cfg.get("auto_reconnect", True):
        return

    s = get_session()
    s._stop_reconnect.clear()

    def _reconnect_loop():
        delay = cfg.get("reconnect_delay_sec", 5)
        max_attempts = cfg.get("max_reconnect_attempts", 0)
        attempts = 0
        while not s._stop_reconnect.is_set():
            time.sleep(delay)
            if s._stop_reconnect.is_set():
                break
            if not s._connected or not is_tunnel_active():
                attempts += 1
                log.warning(f"Обрыв туннеля. Попытка переподключения #{attempts}...")
                try:
                    disconnect()
                    connect()
                except Exception as e:
                    log.error(f"Ошибка переподключения: {e}")
                if max_attempts > 0 and attempts >= max_attempts:
                    log.error("Достигнут лимит попыток переподключения.")
                    break

    s._reconnect_thread = threading.Thread(target=_reconnect_loop, daemon=True)
    s._reconnect_thread.start()
    log.info("Автопереподключение запущено.")


def stop_auto_reconnect():
    """Останавливает автопереподключение."""
    s = get_session()
    s._stop_reconnect.set()
    if s._reconnect_thread and s._reconnect_thread.is_alive():
        s._reconnect_thread.join(timeout=3)
    log.info("Автопереподключение остановлено.")
