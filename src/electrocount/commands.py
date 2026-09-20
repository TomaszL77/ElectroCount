"""All UI entry points share the same command and availability predicate."""
from dataclasses import dataclass
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QAbstractSpinBox


# Original, consistent 24-unit outline icons. Replace centrally to change the set.
PATHS = {
    "new": '<path d="M12 5v14M5 12h14"/>',
    "open": '<path d="M3 7h7l2 3h9l-3 10H3zM3 7V4h7l2 3h7v3"/>',
    "save": '<path d="M4 3h13l3 3v15H4zM8 3v6h8V3M8 21v-8h8v8"/>',
    "fit": '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6M8 8h8v8H8z"/>',
    "pan": '<path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/>',
    "template": '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 8h8v8H8z"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    "manual": '<path d="m4 16 12-12 4 4-12 12H4zM13 7l4 4"/>',
    "delete": '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "conflict": '<path d="m12 3 10 18H2zM12 9v5m0 3v1"/>',
    "layers": '<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    "undo": '<path d="m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12"/>',
    "redo": '<path d="m16 4 5 5-5 5m5-5H10a6 6 0 0 0 0 12"/>',
    "next": '<path d="m9 5 7 7-7 7"/>',
    "previous": '<path d="m15 5-7 7 7 7"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12"/><circle cx="12" cy="12" r="3"/>',
    "settings": '<path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6"/>',
}


class IconRegistry:
    def __init__(self):
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                   'fill="none" stroke="#78d4c5" stroke-width="1.7" stroke-linecap="round" '
                   'stroke-linejoin="round">' + PATHS.get(name, PATHS["settings"]) + '</svg>')
            pixmap = QPixmap(48, 48)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            QSvgRenderer(svg.encode()).render(painter)
            painter.end()
            self.cache[name] = QIcon(pixmap)
        return self.cache[name]


@dataclass
class Command:
    id: str
    title: str
    icon: str
    execute: object
    enabled: object = lambda: True
    shortcut: str = ""
    description: str = ""
    checked: object = None


class CommandRegistry:
    def __init__(self, window):
        self.window = window
        self.icons = IconRegistry()
        self.commands = {}
        self.actions = {}

    def register(self, command):
        if command.id in self.commands:
            raise ValueError("Duplicate command: " + command.id)
        self.commands[command.id] = command
        action = QAction(self.icons.get(command.icon), command.title, self.window)
        if command.shortcut:
            action.setShortcut(command.shortcut)
        action.setToolTip(command.title + (f" ({command.shortcut})" if command.shortcut else "")
                          + ("\n" + command.description if command.description else ""))
        action.setCheckable(command.checked is not None)
        action.triggered.connect(lambda checked=False, key=command.id: self.invoke(key))
        self.window.addAction(action)
        self.actions[command.id] = action
        return action

    def invoke(self, key):
        command = self.commands[key]
        focus = QApplication.focusWidget()
        if command.shortcut in ("N", "P", "F", "Delete") and isinstance(focus, (QLineEdit, QTextEdit, QAbstractSpinBox)):
            return
        if command.enabled():
            command.execute()
        self.refresh()

    def refresh(self):
        for key, command in self.commands.items():
            action = self.actions[key]
            action.setEnabled(bool(command.enabled()))
            if command.checked:
                action.setChecked(bool(command.checked()))

