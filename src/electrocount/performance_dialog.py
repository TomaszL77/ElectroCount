"""Execution information without quality profiles."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QDialogButtonBox

class PerformanceDialog(QDialog):
    def __init__(self,controller,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Analiza dokumentów')
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Jedna jakość na każdym komputerze.\n'
            'Sprzęt wpływa na czas wykonania, nie na model, progi i dokładność.\n'
            'Silnik klasyczny pozostaje domyślny do potwierdzenia przewagi hybrydy.'))
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject);layout.addWidget(close)
