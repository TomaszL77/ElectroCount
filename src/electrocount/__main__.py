import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ElectroCount")
    app.setOrganizationName("ElectroCount")
    logs = Path(__file__).resolve().parents[2] / "logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[
        RotatingFileHandler(logs/"electrocount.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")])
    def exception_hook(kind, value, trace):
        logging.error("Unhandled exception", exc_info=(kind, value, trace))
        sys.__excepthook__(kind, value, trace)
    sys.excepthook = exception_hook
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        QTimer.singleShot(0, lambda: window.open_path(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

