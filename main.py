"""TMUS Tunnel Manager Ultra Super — точка входа."""

import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui.main_window import MainWindow
from src.utils.logger import log


def main():
    log.info("TMUS Tunnel Manager Ultra Super запущен.")
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
