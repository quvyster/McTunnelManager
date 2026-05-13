"""Build TMUS Tunnel Manager into single .exe with PyInstaller."""

import os
import subprocess
import sys


def build():
    base = os.path.dirname(os.path.abspath(__file__))
    print("=== Building TMUS Tunnel Manager Ultra Super ===")
    icon_path = os.path.join(base, "icon.ico")
    icon_args = [f"--icon={icon_path}"] if os.path.exists(icon_path) else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "TMUS_Tunnel_Manager",
        "--clean",
        "--noconfirm",
        "--uac-admin",
        "--add-data", f"src{os.pathsep}src",
        *icon_args,
        "--hidden-import", "paramiko",
        "--hidden-import", "cryptography",
        "--hidden-import", "customtkinter",
        "--collect-all", "paramiko",
        "--collect-all", "customtkinter",
        "main.py",
    ]
    result = subprocess.run(cmd, cwd=base)
    if result.returncode != 0:
        print(f"--- ERROR {result.returncode}")
        sys.exit(result.returncode)
    print("--- SUCCESS:", os.path.join(base, "dist", "TMUS_Tunnel_Manager.exe"))


if __name__ == "__main__":
    build()
