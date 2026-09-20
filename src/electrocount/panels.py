from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QToolButton, QLabel


class CollapsiblePanel(QWidget):
    changed = Signal(bool)

    def __init__(self, title, content, minimum=180, maximum=260, parent=None):
        super().__init__(parent)
        self.title, self.content = title, content
        self.minimum, self.maximum = minimum, maximum
        self.collapsed = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        rail = QWidget()
        rail.setFixedWidth(34)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0,8,0,0)
        self.toggle = QToolButton()
        self.toggle.setFixedSize(32,34)
        self.toggle.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        self.badge = QLabel("")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rail_layout.addWidget(self.toggle)
        rail_layout.addWidget(self.badge)
        rail_layout.addStretch()
        layout.addWidget(rail)
        layout.addWidget(content)
        self.set_collapsed(False, emit=False)

    def set_count(self, count):
        self.badge.setText(str(count))
        self.toggle.setToolTip(f"{self.title}: {count} · rozwiń / zwiń")

    def set_collapsed(self, collapsed, emit=True):
        self.collapsed = collapsed
        self.content.setVisible(not collapsed)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow if collapsed else Qt.ArrowType.LeftArrow)
        self.toggle.setToolTip(self.title+" · rozwiń / zwiń")
        self.setMinimumWidth(34 if collapsed else self.minimum)
        self.setMaximumWidth(34 if collapsed else self.maximum)
        if emit:
            self.changed.emit(collapsed)

