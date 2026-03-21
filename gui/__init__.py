import sys
from PyQt6.QtWidgets import QApplication
from .main_window import WhoIsSpyApp

def run_gui():
    app = QApplication(sys.argv)
    window = WhoIsSpyApp()
    window.show()
    sys.exit(app.exec())
