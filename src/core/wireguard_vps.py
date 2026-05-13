"""Автоматическая настройка WireGuard на VPS через SSH."""

import re

from ..utils.logger import log
from .ssh_client import SSHClient


class WireGuardVPS:
    """Управляет WireGuard сервером на удалённом VPS."""

    def __init__(self, ssh: SSHClient):
        self._ssh = ssh
        self._server_private: str = ""
        self._server_public: str = ""

    # ------------------------------------------------------------------
    #  Установка и базовая настройка
    # ------------------------------------------------------------------

    def detect_os(self) -> str | None:
        """Определяет ОС VPS. Возвращает 'debian', 'ubuntu', 'centos', 'fedora' или None."""
        code, out, _ = self._ssh.exec("cat /etc/os-release 2>/dev/null")
        if code != 0:
            return None
        low = out.lower()
        if "ubuntu" in low:
            return "ubuntu"
        if "debian" in low:
            return "debian"
        if "centos" in low:
            return "centos"
        if "fedora" in low:
            return "fedora"
        if "rhel" in low or "red hat" in low:
            return "centos"
        return None

    def install_wireguard(self, progress_callback=None) -> bool:
        """Устанавливает WireGuard на VPS, если ещё не установлен."""
        code, out, _ = self._ssh.exec("which wg")
        if code == 0 and out.strip():
            log.info("WireGuard уже установлен на VPS.")
            if progress_callback:
                progress_callback("WireGuard уже установлен на VPS")
            return True

        os_type = self.detect_os()
        if not os_type:
            log.error("Не удалось определить ОС VPS.")
            return False

        log.info(f"Определена ОС VPS: {os_type}. Устанавливаю WireGuard...")
        if progress_callback:
            progress_callback(f"Установка WireGuard ({os_type})...")

        if os_type in ("ubuntu", "debian"):
            cmds = [
                "apt-get update -y",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard iptables resolvconf",
            ]
        else:  # centos / fedora
            cmds = [
                "dnf install -y epel-release 2>/dev/null || yum install -y epel-release 2>/dev/null",
                "dnf install -y wireguard-tools iptables 2>/dev/null || yum install -y wireguard-tools iptables 2>/dev/null",
            ]

        for cmd in cmds:
            code, out, err = self._ssh.exec(cmd)
            if code != 0:
                log.error(f"Ошибка установки: {err or out}")
                return False

        # Проверяем, что wg доступен
        code, _, _ = self._ssh.exec("which wg")
        if code != 0:
            log.error("wg не найден после установки.")
            return False
        log.info("WireGuard успешно установлен на VPS.")
        return True

    def enable_ip_forwarding(self) -> bool:
        """Включает IP forwarding на VPS."""
        cmds = [
            "sysctl -w net.ipv4.ip_forward=1",
            "sysctl -w net.ipv6.conf.all.forwarding=1 2>/dev/null || true",
        ]
        for cmd in cmds:
            self._ssh.exec(cmd)

        # Делаем постоянным
        self._ssh.exec(
            "grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf"
        )
        log.info("IP forwarding включён на VPS.")
        return True

    def generate_server_keys(self) -> tuple[str, str]:
        """Генерирует ключи сервера. Возвращает (private, public)."""
        code_p, priv, _ = self._ssh.exec("wg genkey")
        if code_p != 0:
            log.error("Не удалось сгенерировать приватный ключ сервера.")
            return "", ""
        priv = priv.strip()
        # Получаем публичный ключ
        code_u, pub, _ = self._ssh.exec(f"echo '{priv}' | wg pubkey")
        if code_u != 0:
            return "", ""
        pub = pub.strip()
        self._server_private = priv
        self._server_public = pub
        log.info("Ключи сервера WireGuard сгенерированы.")
        return priv, pub

    def create_server_config(
        self,
        interface: str = "wg0",
        listen_port: int = 51820,
        server_vpn_ip: str = "10.99.0.1/24",
    ) -> bool:
        """Создаёт конфигурационный файл сервера."""
        if not self._server_private:
            self.generate_server_keys()
        if not self._server_private:
            return False

        config = f"""[Interface]
PrivateKey = {self._server_private}
Address = {server_vpn_ip}
ListenPort = {listen_port}

# iptables будет настроен отдельно
PostUp = iptables -A FORWARD -i {interface} -j ACCEPT; iptables -A FORWARD -o {interface} -j ACCEPT; iptables -t nat -A POSTROUTING -o $(ip route | grep default | awk '{{print $5}}' | head -1) -j MASQUERADE
PostDown = iptables -D FORWARD -i {interface} -j ACCEPT; iptables -D FORWARD -o {interface} -j ACCEPT; iptables -t nat -D POSTROUTING -o $(ip route | grep default | awk '{{print $5}}' | head -1) -j MASQUERADE
"""

        # Записываем конфиг
        escaped = config.replace("'", "'\\''")
        self._ssh.exec(f"mkdir -p /etc/wireguard")
        code, _, err = self._ssh.exec(
            f"cat > /etc/wireguard/{interface}.conf << 'TMUS_EOF'\n{config}\nTMUS_EOF"
        )
        if code != 0:
            log.error(f"Ошибка записи конфига сервера: {err}")
            return False
        log.info(f"Конфигурация сервера записана: /etc/wireguard/{interface}.conf")
        return True

    def start_server(self, interface: str = "wg0") -> bool:
        """Запускает WireGuard интерфейс на VPS."""
        self._ssh.exec(f"systemctl enable wg-quick@{interface} 2>/dev/null || true")
        code, out, err = self._ssh.exec(f"wg-quick up {interface}")
        if code != 0:
            # Возможно, уже запущен
            code2, out2, _ = self._ssh.exec(f"wg show {interface}")
            if code2 == 0:
                log.info(f"Интерфейс {interface} уже активен.")
                return True
            log.error(f"Не удалось запустить WireGuard: {err or out}")
            return False
        log.info(f"WireGuard интерфейс {interface} запущен.")
        return True

    def add_peer(
        self,
        client_public_key: str,
        client_vpn_ip: str = "10.99.0.2/32",
        interface: str = "wg0",
    ) -> bool:
        """Добавляет пир (клиента) в WireGuard сервер."""
        code, out, err = self._ssh.exec(
            f"wg set {interface} peer {client_public_key} allowed-ips {client_vpn_ip.split('/')[0]}/32"
        )
        if code != 0:
            log.error(f"Ошибка добавления пира: {err or out}")
            return False

        # Сохраняем конфигурацию
        self._ssh.exec(f"wg-quick save {interface}")
        log.info(f"Пир {client_public_key[:12]}... добавлен на сервер.")
        return True

    # ------------------------------------------------------------------
    #  Проброс портов (iptables DNAT)
    # ------------------------------------------------------------------

    def add_port_forward(
        self,
        external_port: int,
        target_ip: str,  # IP клиента в туннеле
        target_port: int,
        interface: str = "wg0",
    ) -> bool:
        """Добавляет правило iptables для проброса порта с VPS -> туннельный IP клиента."""
        # DNAT: всё, что приходит на внешний порт VPS, перенаправляем на клиента
        rules = [
            f"iptables -t nat -C PREROUTING -p tcp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port} 2>/dev/null || iptables -t nat -A PREROUTING -p tcp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port}",
            f"iptables -t nat -C PREROUTING -p udp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port} 2>/dev/null || iptables -t nat -A PREROUTING -p udp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port}",
            f"iptables -C FORWARD -p tcp -d {target_ip} --dport {target_port} -j ACCEPT 2>/dev/null || iptables -A FORWARD -p tcp -d {target_ip} --dport {target_port} -j ACCEPT",
            f"iptables -C FORWARD -p udp -d {target_ip} --dport {target_port} -j ACCEPT 2>/dev/null || iptables -A FORWARD -p udp -d {target_ip} --dport {target_port} -j ACCEPT",
        ]
        for rule in rules:
            code, _, err = self._ssh.exec(rule)
            if code != 0:
                log.warning(f"Правило iptables: {err}")

        # Сохраняем правила (по возможности)
        self._ssh.exec("iptables-save > /etc/iptables/rules.v4 2>/dev/null || iptables-save > /etc/sysconfig/iptables 2>/dev/null || true")
        log.info(f"Проброс порта {external_port} -> {target_ip}:{target_port} добавлен.")
        return True

    def remove_port_forward(
        self,
        external_port: int,
        target_ip: str,
        target_port: int,
    ) -> None:
        """Удаляет правила проброса порта."""
        rules = [
            f"iptables -t nat -D PREROUTING -p tcp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port} 2>/dev/null || true",
            f"iptables -t nat -D PREROUTING -p udp --dport {external_port} -j DNAT --to-destination {target_ip}:{target_port} 2>/dev/null || true",
            f"iptables -D FORWARD -p tcp -d {target_ip} --dport {target_port} -j ACCEPT 2>/dev/null || true",
            f"iptables -D FORWARD -p udp -d {target_ip} --dport {target_port} -j ACCEPT 2>/dev/null || true",
        ]
        for rule in rules:
            self._ssh.exec(rule)
        log.info(f"Проброс порта {external_port} -> {target_ip}:{target_port} удалён.")

    def clear_all_forwards(self, target_ip: str) -> None:
        """Удаляет ВСЕ правила проброса для указанного IP."""
        # Получаем список правил
        code, out, _ = self._ssh.exec("iptables -t nat -L PREROUTING -n --line-numbers")
        if code == 0:
            for line in reversed(out.split("\n")):
                if target_ip in line and "DNAT" in line:
                    num = line.strip().split()[0]
                    self._ssh.exec(f"iptables -t nat -D PREROUTING {num} 2>/dev/null || true")
        code, out, _ = self._ssh.exec("iptables -L FORWARD -n --line-numbers")
        if code == 0:
            for line in reversed(out.split("\n")):
                if target_ip in line and "ACCEPT" in line:
                    num = line.strip().split()[0]
                    self._ssh.exec(f"iptables -D FORWARD {num} 2>/dev/null || true")

    # ------------------------------------------------------------------
    #  Комплексная настройка
    # ------------------------------------------------------------------

    def full_setup(
        self,
        client_public_key: str,
        client_vpn_ip: str = "10.99.0.2/32",
        interface: str = "wg0",
        listen_port: int = 51820,
        progress_callback=None,
    ) -> bool:
        """Полный цикл настройки сервера WireGuard на VPS."""
        steps = [
            ("Установка WireGuard", self.install_wireguard),
            ("Включение IP forwarding", self.enable_ip_forwarding),
            ("Генерация ключей сервера", self.generate_server_keys),
            ("Создание конфигурации сервера", lambda: self.create_server_config(interface, listen_port)),
            ("Запуск сервера", lambda: self.start_server(interface)),
            ("Добавление клиента", lambda: self.add_peer(client_public_key, client_vpn_ip, interface)),
        ]

        for name, step_fn in steps:
            if progress_callback:
                progress_callback(name)
            if not step_fn():
                log.error(f"Шаг «{name}» провален.")
                return False

        log.info("Полная настройка WireGuard на VPS завершена успешно!")
        return True

    def get_listen_port(self) -> int:
        """Возвращает порт, на котором слушает WireGuard."""
        code, out, _ = self._ssh.exec("wg show wg0 listen-port")
        if code == 0:
            m = re.search(r"(\d+)", out)
            if m:
                return int(m.group(1))
        return 51820

    def get_endpoint_ip(self) -> str:
        """Возвращает публичный IP VPS."""
        code, out, _ = self._ssh.exec("curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}'")
        if code == 0 and out.strip():
            return out.strip().split("\n")[0].strip()
        return self._ssh._host
