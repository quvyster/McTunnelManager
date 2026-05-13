"""Окно настроек TMUS Tunnel Manager."""

import customtkinter as ctk

from ..utils.config import load_config, save_config
from ..utils.logger import log


class SettingsWindow(ctk.CTkToplevel):
    """Модальное окно настроек."""

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.title("Настройки")
        self.geometry("500x520")
        self.resizable(False, False)
        self.grab_set()
        self._on_save_cb = on_save
        self._cfg = load_config()

        # Прокручиваемая область
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # --- SSH ---
        ssh_label = ctk.CTkLabel(scroll, text="SSH подключение", font=ctk.CTkFont(size=14, weight="bold"))
        ssh_label.pack(anchor="w", pady=(5, 0))

        ssh_frame = ctk.CTkFrame(scroll)
        ssh_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(ssh_frame, text="SSH порт:").pack(side="left", padx=5)
        self._ssh_port = ctk.CTkEntry(ssh_frame, width=80)
        self._ssh_port.pack(side="left", padx=5)
        self._ssh_port.insert(0, str(self._cfg.get("vps_ssh_port", 22)))

        # --- WireGuard ---
        wg_label = ctk.CTkLabel(scroll, text="WireGuard", font=ctk.CTkFont(size=14, weight="bold"))
        wg_label.pack(anchor="w", pady=(15, 0))

        wg_frame = ctk.CTkFrame(scroll)
        wg_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(wg_frame, text="Порт сервера:").pack(side="left", padx=5)
        self._wg_port = ctk.CTkEntry(wg_frame, width=100)
        self._wg_port.pack(side="left", padx=5)
        self._wg_port.insert(0, str(self._cfg.get("wg_port", 51820)))

        ctk.CTkLabel(wg_frame, text="Интерфейс:").pack(side="left", padx=(15, 5))
        self._wg_iface = ctk.CTkEntry(wg_frame, width=80)
        self._wg_iface.pack(side="left", padx=5)
        self._wg_iface.insert(0, self._cfg.get("wg_interface", "wg0"))

        # --- Автопереподключение ---
        ar_label = ctk.CTkLabel(scroll, text="Автопереподключение", font=ctk.CTkFont(size=14, weight="bold"))
        ar_label.pack(anchor="w", pady=(15, 0))

        self._auto_reconnect = ctk.CTkSwitch(scroll, text="Автоматически переподключаться при обрыве")
        self._auto_reconnect.pack(anchor="w", pady=5)
        if self._cfg.get("auto_reconnect", True):
            self._auto_reconnect.select()

        ar_frame = ctk.CTkFrame(scroll)
        ar_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(ar_frame, text="Задержка переподключения (сек):").pack(side="left", padx=5)
        self._reconnect_delay = ctk.CTkEntry(ar_frame, width=60)
        self._reconnect_delay.pack(side="left", padx=5)
        self._reconnect_delay.insert(0, str(self._cfg.get("reconnect_delay_sec", 5)))

        ctk.CTkLabel(ar_frame, text="Макс. попыток (0=бесконечно):").pack(side="left", padx=(15, 5))
        self._max_attempts = ctk.CTkEntry(ar_frame, width=60)
        self._max_attempts.pack(side="left", padx=5)
        self._max_attempts.insert(0, str(self._cfg.get("max_reconnect_attempts", 0)))

        # --- Автозапуск ---
        self._autostart = ctk.CTkSwitch(scroll, text="Запускать при старте Windows")
        self._autostart.pack(anchor="w", pady=(15, 5))
        if self._cfg.get("autostart", False):
            self._autostart.select()

        # --- Сворачивание в трей ---
        self._tray = ctk.CTkSwitch(scroll, text="Сворачивать в системный трей при закрытии")
        self._tray.pack(anchor="w", pady=5)
        if self._cfg.get("minimize_to_tray", True):
            self._tray.select()

        # --- Логи ---
        log_label = ctk.CTkLabel(scroll, text="Логи", font=ctk.CTkFont(size=14, weight="bold"))
        log_label.pack(anchor="w", pady=(15, 0))

        log_frame = ctk.CTkFrame(scroll)
        log_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(log_frame, text="Хранить логи (дней):").pack(side="left", padx=5)
        self._log_days = ctk.CTkEntry(log_frame, width=60)
        self._log_days.pack(side="left", padx=5)
        self._log_days.insert(0, str(self._cfg.get("keep_logs_days", 30)))

        # --- Кнопки ---
        btn_frame = ctk.CTkFrame(scroll)
        btn_frame.pack(fill="x", pady=(20, 0))

        ctk.CTkButton(btn_frame, text="Сохранить", width=140, command=self._save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Отмена", width=100, fg_color="gray", hover_color="#666", command=self.destroy).pack(side="right", padx=5)

    def _save(self):
        try:
            self._cfg["vps_ssh_port"] = int(self._ssh_port.get().strip() or 22)
            self._cfg["wg_port"] = int(self._wg_port.get().strip() or 51820)
            self._cfg["wg_interface"] = self._wg_iface.get().strip() or "wg0"
            self._cfg["auto_reconnect"] = bool(self._auto_reconnect.get())
            self._cfg["reconnect_delay_sec"] = int(self._reconnect_delay.get().strip() or 5)
            self._cfg["max_reconnect_attempts"] = int(self._max_attempts.get().strip() or 0)
            self._cfg["autostart"] = bool(self._autostart.get())
            self._cfg["minimize_to_tray"] = bool(self._tray.get())
            self._cfg["keep_logs_days"] = int(self._log_days.get().strip() or 30)
        except ValueError:
            log.error("Некорректные значения в настройках.")
            return

        save_config(self._cfg)
        # Автозапуск Windows
        self._apply_autostart()

        if self._on_save_cb:
            self._on_save_cb()
        self.destroy()

    def _apply_autostart(self):
        """Добавляет / удаляет программу из автозапуска Windows (через реестр)."""
        import os
        import sys
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        name = "TMUS_Tunnel_Manager"

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if self._cfg.get("autostart", False):
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{app_path}"')
                log.info("Автозапуск Windows включён.")
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
                log.info("Автозапуск Windows отключён.")
            winreg.CloseKey(key)
        except OSError as e:
            log.error(f"Не удалось изменить реестр автозапуска: {e}")
