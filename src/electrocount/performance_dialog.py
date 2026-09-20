"""Resource settings; clear separation between detected hardware and active inference."""
import json
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QComboBox,QPushButton,QPlainTextEdit,QDialogButtonBox
from .performance import PerformanceMode


class PerformanceDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Wydajność i sprzęt")
        self.resize(720,650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Tryb wydajności (dotyczy kolejnych operacji):"))
        self.mode = QComboBox()
        for mode in PerformanceMode:
            self.mode.addItem(mode.value.title() if mode!=PerformanceMode.AUTO else "AUTO — dobór na podstawie pomiaru",mode.value)
        self.mode.setCurrentIndex(self.mode.findData(controller.mode.value))
        self.mode.currentIndexChanged.connect(lambda _:controller.set_mode(self.mode.currentData()))
        layout.addWidget(self.mode)
        self.summary = QLabel(); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        note = QLabel("Aktywna analiza: PDF, tekst natywny i geometria na CPU.\n"
            "Modele neuronowe, Context AI i zbieranie datasetu: nieaktywne.\n"
            "W tym etapie profile zmieniają liczbę wątków i cache; kryteria zliczania pozostają takie same.")
        note.setWordWrap(True); layout.addWidget(note)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); layout.addWidget(self.details)
        self.rerun = QPushButton("Zmierz ponownie (maks. 15 s)")
        self.rerun.clicked.connect(lambda:controller.start(force=True)); layout.addWidget(self.rerun)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject); layout.addWidget(close)
        controller.changed.connect(self.refresh)
        self.finished.connect(lambda _:controller.changed.disconnect(self.refresh))
        self.refresh()

    def refresh(self):
        c = self.controller
        self.summary.setText(f"Aktywny profil: {c.plan.effective.title()} · {c.plan.cpu_threads} wątków · cache {c.plan.memory_cache_mb} MB\n{c.plan.reason}\n{c.state}")
        self.rerun.setEnabled(c.process is None)
        self.details.setPlainText(json.dumps(c.report,ensure_ascii=False,indent=2) if c.report else "Pomiar jeszcze nie jest dostępny.")
