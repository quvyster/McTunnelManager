"""Главное окно TMUS Tunnel Manager Ultra Super."""

import threading
import traceback
from datetime import datetime

import customtkinter as ctk

from ..core.tunnel_service import connect, disconnect, start_auto_reconnect, stop_auto_reconnect
from ..core.wireguard_local import is_tunnel_active, is_wireguard_installed
from ..utils.config import load_config, save_config
from ..utils.logger import log
from .settings_window import SettingsWindow


class FixedEntry(ctk.CTkEntry):
    """CTkEntry с нормальными Ctrl+A/C/V/X."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bind("<Control-a>", self._select_all)
        self.bind("<Control-A>", self._select_all)
        self.bind("<Control-c>", self._copy)
        self.bind("<Control-C>", self._copy)
        self.bind("<Control-v>", self._paste)
        self.bind("<Control-V>", self._paste)
        self.bind("<Control-x>", self._cut)
        self.bind("<Control-X>", self._cut)

    def _select_all(self, event=None):
        self.select_range(0, "end")
        self.icursor("end")
        return "break"

    def _copy(self, event=None):
        try:
            text = self.selection_get() if self.selection_present() else self.get()
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass
        return "break"

    def _paste(self, event=None):
        try:
            text = self.clipboard_get()
            if self.selection_present():
                self.delete("sel.first", "sel.last")
            self.insert("insert", text)
        except Exception:
            pass
        return "break"

    def _cut(self, event=None):
        try:
            text = self.selection_get() if self.selection_present() else self.get()
            self.clipboard_clear()
            self.clipboard_append(text)
            if self.selection_present():
                self.delete("sel.first", "sel.last")
            else:
                self.delete(0, "end")
        except Exception:
            pass
        return "break"


class PortEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save, existing=None):
        super().__init__(parent)
        self.title("Редактировать порт" if existing else "Добавить порт")
        self.geometry("350x220")
        self.resizable(False, False)
        self.grab_set()
        self._on_save = on_save

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Локальный порт (на ПК):", anchor="w").pack(fill="x", pady=(5, 0))
        self._local_entry = FixedEntry(frame, placeholder_text="например 8080")
        self._local_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(frame, text="Внешний порт (на VPS):", anchor="w").pack(fill="x", pady=(5, 0))
        self._remote_entry = FixedEntry(frame, placeholder_text="например 80")
        self._remote_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkButton(frame, text="Сохранить", command=self._save).pack(pady=(10, 0))

        if existing:
            self._local_entry.insert(0, str(existing.get("local_port", "")))
            self._remote_entry.insert(0, str(existing.get("remote_port", "")))

    def _save(self):
        try:
            local = int(self._local_entry.get().strip())
            remote = int(self._remote_entry.get().strip() or local)
            if not (1 <= local <= 65535 and 1 <= remote <= 65535):
                raise ValueError
        except ValueError:
            ctk.CTkLabel(self, text="Введите корректные порты 1-65535", text_color="red").pack()
            return
        self._on_save({"local_port": local, "remote_port": remote, "remote_ip": "0.0.0.0"})
        self.destroy()


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TMUS Tunnel Manager Ultra Super")
        self.geometry("750x680")
        self.minsize(600, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._cfg = load_config()
        self._connected = False
        self._log_lines = []

        self._build_ui()
        self._refresh_state()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 0))

        self._entries = {}
        for label, key in [("IP VPS:", "vps_ip"), ("SSH User:", "vps_ssh_user"), ("SSH Pass:", "vps_ssh_password")]:
            col = ctk.CTkFrame(top)
            col.pack(side="left", padx=5)
            ctk.CTkLabel(col, text=label).pack(anchor="w")
            entry = FixedEntry(col, width=180, show="*" if "pass" in key else "")
            entry.pack(fill="x")
            entry.insert(0, self._cfg.get(key, ""))
            self._entries[key] = entry

        buttons = ctk.CTkFrame(self)
        buttons.pack(fill="x", padx=10, pady=(8, 0))

        self._connect_btn = ctk.CTkButton(buttons, text="ПОДКЛЮЧИТЬСЯ", width=180, height=40, font=ctk.CTkFont(size=14, weight="bold"), command=self._toggle_connect)
        self._connect_btn.pack(side="left", padx=5)

        self._status_label = ctk.CTkLabel(buttons, text="Отключено", text_color="gray", font=ctk.CTkFont(size=13))
        self._status_label.pack(side="left", padx=15)

        ctk.CTkButton(buttons, text="Настройки", width=100, command=self._open_settings).pack(side="right", padx=5)

        ports_frame = ctk.CTkFrame(self)
        ports_frame.pack(fill="x", padx=10, pady=(10, 0))
        ports_header = ctk.CTkFrame(ports_frame)
        ports_header.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(ports_header, text="Проброс портов", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(ports_header, text="+ Добавить", width=100, command=self._add_port).pack(side="right", padx=5)
        self._ports_list = ctk.CTkScrollableFrame(ports_frame, height=120)
        self._ports_list.pack(fill="x", padx=5, pady=5)

        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        log_header = ctk.CTkFrame(log_frame)
        log_header.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(log_header, text="Логи", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(log_header, text="Очистить", width=80, command=self._clear_logs).pack(side="right", padx=5)
        ctk.CTkButton(log_header, text="Копировать", width=90, command=self._copy_logs).pack(side="right", padx=5)
        self._log_text = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self._log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self._info_bar = ctk.CTkLabel(self, text="Готов", anchor="w", font=ctk.CTkFont(size=11))
        self._info_bar.pack(fill="x", padx=10, pady=(0, 5))

    def _log(self, msg: str, tag: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"error": "ERR", "success": "OK", "warn": "WARN"}.get(tag, "INFO")
        line = f"[{ts}] [{prefix}] {msg}"
        self._log_lines.append(line)
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        log.info(msg)

    def _clear_logs(self):
        self._log_text.delete("1.0", "end")
        self._log_lines.clear()

    def _copy_logs(self):
        self.clipboard_clear()
        self.clipboard_append("\n".join(self._log_lines))
        self._log("Логи скопированы.")

    def _refresh_ports_list(self):
        for widget in self._ports_list.winfo_children():
            widget.destroy()
        for i, fwd in enumerate(self._cfg.get("forwarded_ports", [])):
            row = ctk.CTkFrame(self._ports_list)
            row.pack(fill="x", pady=2)
            local_port = fwd.get("local_port", "?")
            remote_port = fwd.get("remote_port", local_port)
            ctk.CTkLabel(row, text=f"Локальный :{local_port}  ->  Внешний :{remote_port}", anchor="w").pack(side="left", padx=5)
            ctk.CTkButton(row, text="E", width=30, command=lambda idx=i: self._edit_port(idx)).pack(side="right", padx=2)
            ctk.CTkButton(row, text="X", width=30, fg_color="#c0392b", hover_color="#e74c3c", command=lambda idx=i: self._remove_port(idx)).pack(side="right", padx=2)

    def _add_port(self):
        PortEditDialog(self, on_save=self._on_port_save)

    def _edit_port(self, idx: int):
        PortEditDialog(self, on_save=lambda data: self._on_port_save(data, idx), existing=self._cfg["forwarded_ports"][idx])

    def _remove_port(self, idx: int):
        del self._cfg["forwarded_ports"][idx]
        save_config(self._cfg)
        self._refresh_ports_list()
        self._log("Порт удалён. Переподключитесь для применения.")

    def _on_port_save(self, data: dict, idx: int | None = None):
        if idx is None:
            self._cfg.setdefault("forwarded_ports", []).append(data)
        else:
            self._cfg["forwarded_ports"][idx] = data
        save_config(self._cfg)
        self._refresh_ports_list()
        self._log(f"Порт {data['local_port']}->{data['remote_port']} сохранён.")

    def _toggle_connect(self):
        if self._connected:
            self._disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        for key, entry in self._entries.items():
            self._cfg[key] = entry.get().strip()
        save_config(self._cfg)

        self._connect_btn.configure(text="Подключение...", state="disabled")
        self._status_label.configure(text="Подключение...", text_color="orange")
        self._log("Запуск подключения...")

        def run():
            try:
                ok = connect(
                    progress_callback=self._on_progress,
                    vps_ip=self._cfg.get("vps_ip", ""),
                    vps_ssh_user=self._cfg.get("vps_ssh_user", "root"),
                    vps_ssh_password=self._cfg.get("vps_ssh_password", ""),
                    vps_ssh_port=int(self._cfg.get("vps_ssh_port", 22)),
                    forwarded_ports=self._cfg.get("forwarded_ports", []),
                )
            except Exception as e:
                tb = traceback.format_exc()
                self.after(0, lambda: self._log(f"FATAL: {e}\n{tb}", "error"))
                ok = False
            self.after(0, lambda: self._on_connected(ok))

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, msg: str, tag: str = ""):
        self.after(0, lambda: self._log(msg, tag))
        self.after(0, lambda: self._info_bar.configure(text=msg))

    def _on_connected(self, ok: bool):
        if ok:
            self._connected = True
            self._connect_btn.configure(text="ОТКЛЮЧИТЬСЯ", fg_color="#c0392b", hover_color="#e74c3c", state="normal")
            self._status_label.configure(text="Подключено", text_color="#2ecc71")
            self._info_bar.configure(text="Туннель активен.")
            start_auto_reconnect()
        else:
            self._connect_btn.configure(text="ПОДКЛЮЧИТЬСЯ", fg_color="#2980b9", hover_color="#3498db", state="normal")
            self._status_label.configure(text="Ошибка", text_color="red")
            self._info_bar.configure(text="Ошибка подключения. Смотрите логи.")

    def _disconnect(self):
        self._log("Отключение...")
        stop_auto_reconnect()
        threading.Thread(target=disconnect, daemon=True).start()
        self._connected = False
        self._connect_btn.configure(text="ПОДКЛЮЧИТЬСЯ", fg_color="#2980b9", hover_color="#3498db", state="normal")
        self._status_label.configure(text="Отключено", text_color="gray")
        self._info_bar.configure(text="Отключено.")

    def _open_settings(self):
        SettingsWindow(self, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        self._cfg = load_config()
        self._log("Настройки сохранены.")

    def _refresh_state(self):
        self._refresh_ports_list()
        if not is_wireguard_installed():
            self._log("WireGuard не найден или установлен неполно. Нужны wg.exe и wireguard.exe.", "warn")
        if is_tunnel_active():
            self._connected = True
            self._connect_btn.configure(text="ОТКЛЮЧИТЬСЯ", fg_color="#c0392b", hover_color="#e74c3c")
            self._status_label.configure(text="Подключено", text_color="#2ecc71")

    def _on_close(self):
        if self._connected:
            stop_auto_reconnect()
            threading.Thread(target=disconnect, daemon=True).start()
        self.destroy()
