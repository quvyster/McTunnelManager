"""SSH-клиент для взаимодействия с VPS."""

import time
from typing import Callable

import paramiko

from ..utils.logger import log


class SSHClient:
    """Обёртка над paramiko для удобного выполнения команд на VPS."""

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        password: str = "",
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client: paramiko.SSHClient | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.get_transport() is not None and self._client.get_transport().is_active()

    def connect(self) -> bool:
        """Устанавливает SSH-соединение. Возвращает True при успехе."""
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )
            log.info(f"SSH подключён к {self._host}:{self._port}")
            return True
        except paramiko.AuthenticationException:
            log.error("SSH: ошибка аутентификации — неверный логин/пароль.")
        except Exception as e:
            log.error(f"SSH: ошибка подключения — {e}")
        self._client = None
        return False

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            log.info("SSH отключён.")

    def exec(self, command: str, sudo: bool = False) -> tuple[int, str, str]:
        """Выполняет команду. Возвращает (код_выхода, stdout, stderr)."""
        if not self.connected:
            return -1, "", "SSH не подключён"
        if sudo:
            command = f"sudo {command}"
        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            return exit_code, out, err
        except Exception as e:
            log.error(f"SSH exec error: {e}")
            return -1, "", str(e)

    def exec_stream(self, command: str, callback: Callable[[str], None]) -> int:
        """Выполняет команду с потоковым чтением stdout. Вызывает callback для каждой строки."""
        if not self.connected:
            return -1
        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=300)
            for line in iter(stdout.readline, ""):
                if line:
                    callback(line.strip())
            return stdout.channel.recv_exit_status()
        except Exception as e:
            log.error(f"SSH exec_stream error: {e}")
            return -1

    def test_connection(self) -> tuple[bool, str]:
        """Проверяет соединение + базовые возможности VPS."""
        if not self.connected:
            return False, "SSH не подключён"
        code, out, err = self.exec("whoami && uname -a")
        if code == 0:
            return True, out
        return False, err or out
