"""Desktop import interaction. The manager owns all format routing."""
import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QFileDialog
from .domain import Project
from .file_import_manager import FileImportManager


class ImportWindowMixin:
    def init_import_ui(self):
        self.import_manager = FileImportManager()
        self.setAcceptDrops(True)
        for widget in (self.view, self.view.viewport(), self.pages, self.groups, self.results, self.conflict_list):
            widget.setAcceptDrops(False)
        self.drop_overlay = QLabel("Upuść, aby otworzyć", self)
        self.drop_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drop_overlay.setStyleSheet("background: rgba(20,50,65,235); color: #8ce4d0; border: 3px dashed #55bda9; border-radius: 12px; font-size: 28px;")
        self.drop_overlay.hide()

    @staticmethod
    def dropped_paths(event):
        return [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]

    def dragEnterEvent(self, event):
        if not self.busy and not self.loading and self.import_manager.accepts(self.dropped_paths(event)):
            self.drop_overlay.setGeometry(self.rect().adjusted(14, 14, -14, -14))
            self.drop_overlay.raise_()
            self.drop_overlay.show()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self.busy and not self.loading and self.import_manager.accepts(self.dropped_paths(event)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()
        event.accept()

    def dropEvent(self, event):
        self.drop_overlay.hide()
        if self.busy or self.loading:
            event.ignore()
            return
        paths = self.dropped_paths(event)
        if self.import_manager.accepts(paths):
            event.acceptProposedAction()
            self.import_paths(paths)
        else:
            event.ignore()

    def choose_import_mode(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Import plików")
        dialog.setText("Projekt jest już otwarty. Jak zaimportować pliki?")
        add = dialog.addButton("Dodaj do obecnego projektu", QMessageBox.ButtonRole.AcceptRole)
        new = dialog.addButton("Otwórz jako nowy projekt", QMessageBox.ButtonRole.ActionRole)
        cancel = dialog.addButton("Anuluj", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        return "add" if dialog.clickedButton() is add else "new" if dialog.clickedButton() is new else "cancel"

    def import_paths(self, paths, mode=None):
        if self.busy or self.loading:
            return
        mode = mode or (self.choose_import_mode() if self.project.documents else "new")
        if mode == "cancel":
            return
        if mode == "new" and not self.maybe_save():
            return
        existing = [d.path for d in self.project.documents] if mode == "add" else []
        plan = self.import_manager.plan(paths, existing)
        if not plan.paths:
            if plan.errors:
                self.failure("\n".join(plan.errors))
            return
        self.loading = True
        self.registry.refresh()
        self.statusBar().showMessage(f"Importowanie plików: {len(plan.paths)}…")
        generation = self.generation
        def imported(result):
            self.loading = False
            if generation != self.generation:
                return
            errors = plan.errors + result["errors"]
            if result["documents"]:
                if mode == "new":
                    project = Project(name=Path(result["documents"][0]["name"]).stem)
                    self.import_manager.apply(project, result)
                    self.replace_project(project, None)
                else:
                    # Import is undoable together with its page/document references.
                    self.checkpoint()
                    self.import_manager.apply(self.project, result)
                    self.rebuild_page_list()
                    self.load_thumbnails()
                    self.refresh()
                self.dirty = True
                self.refresh()
                self.statusBar().showMessage(f"Zaimportowano {len(result['documents'])} plików. Razem {len(self.project.pages)} stron.", 10000)
                logging.info("Imported %d documents", len(result["documents"]))
            self.registry.refresh()
            if errors:
                self.failure("\n".join(errors))
        self.jobs.submit({"kind": "import", "paths": plan.paths}, imported)

    def open_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Otwórz dokumenty lub projekt", "",
            "Dokumenty / projekt (*.pdf *.dwg *.dxf *.sqlite);;Wszystkie pliki (*)")
        if len(paths) == 1 and Path(paths[0]).suffix.lower() == ".sqlite":
            self.open_path(paths[0])
        elif paths:
            self.import_paths(paths)

    def rebuild_page_list(self):
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QListWidgetItem
        self.pages.blockSignals(True)
        self.pages.clear()
        documents = {d.id: d for d in self.project.documents}
        for index, page in enumerate(self.project.pages):
            item = QListWidgetItem(f"{index+1:02}  {page['name']}")
            item.setSizeHint(QSize(180, 150))
            document = documents.get(page.get("document_id"))
            item.setToolTip((document.name+"\n" if document else "")+page["name"])
            self.pages.addItem(item)
        self.pages.setCurrentRow(self.project.page if self.project.pages else -1)
        self.pages.blockSignals(False)
        self.pages_sidebar.set_count(len(self.project.pages))
        self.thumb_loaded.clear()
        self.thumb_pending.clear()

