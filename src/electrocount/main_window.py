import logging
import os
from collections import OrderedDict
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QTransform
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QSplitter, QToolBar,
    QApplication, QFileDialog, QInputDialog, QMessageBox, QColorDialog, QProgressBar, QDoubleSpinBox,
    QCheckBox, QPushButton, QTabWidget, QMenu, QListView)
from .commands import Command, CommandRegistry
from .domain import Project, Group, Detection, ConflictEngine, counts, near
from .drawing_view import DrawingView
from .history import History
from .jobs import JobManager
from .project_manager import ProjectManager
from .import_ui import ImportWindowMixin
from .results_manager import ResultsManager
from .text_engine import normalize_text
from .settings import Settings
from .panels import CollapsiblePanel
from .detection_debug import DetectionDebug
from .profiling_service import PerformanceController
from .performance_dialog import PerformanceDialog
from .operation_progress import OperationProgress
from .diagnostics import data_dir, new_debug_run, runtime_info, write_json
from . import __version__

STYLE = """
QMenuBar { background: #192435; color: #dce4ef; }
QMenuBar::item:selected { background: #293d52; }
QMainWindow, QDialog { background: #111a27; color: #dce4ef; }
QWidget { font-family: 'Segoe UI'; font-size: 12px; color: #dce4ef; }
QToolBar { background: #192435; border: none; spacing: 5px; padding: 6px; }
QToolBar::separator { background: #344359; width: 1px; margin: 5px; }
QToolButton, QPushButton { background: transparent; border: 1px solid transparent; border-radius: 5px; padding: 7px; }
QToolButton:hover, QPushButton:hover { background: #293d52; }
QToolButton:checked { background: #254b50; border-color: #439e93; }
QToolButton:disabled { color: #627185; }
QListWidget, QTreeWidget { background: #172232; border: none; outline: none; }
QListWidget::item { padding: 8px; border-bottom: 1px solid #223044; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #254154; }
QTreeWidget::item { padding: 6px 2px; }
QHeaderView::section { background: #1d2b3f; padding: 8px; border: none; color: #98adc2; }
QLabel#section { color: #84a0ba; font-weight: 600; padding: 12px 8px; }
QComboBox QAbstractItemView { background: #223246; color: #dce4ef; selection-background-color: #33546a; }
QPlainTextEdit { background: #172232; color: #dce4ef; }
QLineEdit, QDoubleSpinBox, QComboBox { background: #223246; border: 1px solid #3b5169; border-radius: 4px; padding: 5px; }
QStatusBar { background: #192435; }
QProgressBar { border: none; background: #28394e; height: 12px; }
QProgressBar::chunk { background: #45b9a8; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #192435; padding: 10px; }
QTabBar::tab:selected { color: #78d4c5; border-bottom: 2px solid #45b9a8; }
QMenu { background: #223246; padding: 5px; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #33546a; }
QSplitter::handle { background: #0e1621; width: 4px; }
"""


class MainWindow(ImportWindowMixin, QMainWindow):
    PALETTE = ["#42b8ac", "#629df6", "#be8be8", "#e4ae5b", "#e78096", "#9acb67"]

    def __init__(self):
        super().__init__()
        self.project, self.folder, self.dirty = Project(), None, False
        self.history, self.conflict_engine = History(), ConflictEngine()
        self.settings_store = Settings()
        self.conflicts, self.conflict_ids = [], set()
        self.selected, self.generation = "", 0
        self.busy = self.loading = self.refreshing = False
        self.preview_cache = OrderedDict()
        self.thumb_loaded, self.thumb_pending = set(), set()
        self.detail_key = None
        self.jobs = JobManager(self)
        self.jobs.failed.connect(self.failure)
        self.jobs.busy_changed.connect(self.busy_changed)
        self.jobs.progress.connect(lambda v: self.operation_progress.set_progress(v))
        self.jobs.foreground_started.connect(lambda kind: self.operation_progress.start(kind))
        self.jobs.foreground_finished.connect(lambda kind: self.operation_progress.finish(kind))
        self.jobs.status.connect(self.job_status)
        self.resize(1560, 940)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(STYLE)
        self.registry = CommandRegistry(self)
        self.register_commands()
        self.build_ui()
        self.init_import_ui()
        self.view.viewport_changed.connect(lambda:self.view.draw_detections(self.project,self.conflict_ids,self.selected,self.review_only.isChecked(),self.active_group_only.isChecked()))
        self.refresh()
        self.performance = PerformanceController(self.settings_store,self)
        self.performance.changed.connect(self.update_performance)
        self.performance.notice.connect(lambda message:self.statusBar().showMessage(message,20000))
        self.jobs.performance_fallback.connect(self.performance.apply_fallback)
        self.update_performance()
        self.startup_runtime=runtime_info(QApplication.instance())
        write_json(data_dir()/"logs"/"runtime_info.json",self.startup_runtime)
        if not os.environ.get("ELECTROCOUNT_SKIP_PROFILE"):
            QTimer.singleShot(500,self.performance.start)

    def update_performance(self):
        if hasattr(self,'startup_runtime') and self.performance.report:
            self.startup_runtime['hardware_profile']=self.performance.report
            write_json(data_dir()/"logs"/"runtime_info.json",self.startup_runtime)
        plan = self.performance.plan
        self.jobs.performance_plan = plan.to_dict()
        self.performance_button.setText({'hybrid_base':'AI Base · CPU','hybrid':'AI Small · CPU','classic':'Klasyczny · CPU'}[self.engine_mode()])
        self.performance_button.setToolTip(f"{plan.reason}\n{self.performance.state}\nJednakowa analiza na każdym komputerze.")

    def toggle_artifacts(self):
        enabled=not self.settings_store.get("debug/artifacts",False)
        self.settings_store.set("debug/artifacts",enabled)
        self.statusBar().showMessage("Zapis wycinków diagnostycznych "+("włączony" if enabled else "wyłączony"),10000)

    def open_debug_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        folder=data_dir();folder.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def run_self_test(self):
        directory=new_debug_run()
        def ready(report):
            self.last_self_test=report
            self.statusBar().showMessage(f"Test diagnostyczny: {report['status']} · {report['actual']} / {report['expected']} · {directory}",60000)
        self.jobs.submit({"kind":"self_test","debug_dir":str(directory)},ready,analysis=True)

    def toggle_template_legend(self):
        group=self.project.active_group()
        if not group or not group.template:return
        self.checkpoint()
        legend=group.template.get('source')!='LEGEND'
        group.template['source']='LEGEND' if legend else 'DRAWING'
        if group.template.get('signature'):group.template['signature']['source_legend']=legend
        if group.template.get('representation'):group.template['representation']['source']=group.template['source']
        self.statusBar().showMessage('Zmieniono źródło wzorca. Naciśnij Znajdź, aby przeliczyć wyniki.',12000)
        self.registry.refresh()

    def engine_mode(self):
        from .ai.model_catalog import model_for_mode
        mode=self.settings_store.text('detection/engine_mode_073','hybrid_base')
        model_for_mode(mode)
        return mode

    def toggle_hybrid(self):
        modes={'AI Base — większy model':'hybrid_base','AI Small — lżejszy model':'hybrid',
               'Klasyczny — geometria PDF':'classic'}
        labels=list(modes)
        current=list(modes.values()).index(self.engine_mode())
        selected,ok=QInputDialog.getItem(self,'Tryb analizy','Wybierz model do kolejnego wyszukiwania:',labels,current,False)
        if not ok:return
        self.settings_store.set('detection/engine_mode_073',modes[selected])
        self.statusBar().showMessage('Wybrano '+selected+'. Kliknij Znajdź, aby przeliczyć wyniki.',15000)
        self.update_performance()
        self.registry.refresh()

    def show_performance(self):
        PerformanceDialog(self.performance,self).exec()

    def register_commands(self):
        editable = lambda: bool(self.project.source) and not self.busy and not self.loading
        active = lambda: editable() and self.project.active_group() is not None
        selected = lambda: active() and self.selected_detection() is not None
        commands = [
            Command("new", "Nowy", "new", self.new_project, lambda: not self.busy and not self.loading, "Ctrl+N"),
            Command("open", "Otwórz", "open", self.open_dialog, lambda: not self.busy and not self.loading, "Ctrl+O"),
            Command("save", "Zapisz", "save", self.save_project, editable, "Ctrl+S"),
            Command("pan", "Przesuwaj", "pan", lambda: self.set_mode("pan"), editable, checked=lambda: hasattr(self, "view") and self.view.mode == "pan"),
            Command("fit", "Dopasuj", "fit", lambda: self.view.fit(), editable, "F"),
            Command("group", "Nowa grupa", "new", self.add_group, editable),
            Command("template", "Wzorzec", "template", lambda: self.set_mode("template"), editable, description="Zaznacz symbol wraz z oznaczeniem tekstowym", checked=lambda: hasattr(self, "view") and self.view.mode == "template"),
            Command("find", "Znajdź", "search", self.find_matches, lambda: active() and bool(self.project.active_group().template)),
            Command("manual", "Dodaj ręcznie", "manual", lambda: self.set_mode("manual"), active, checked=lambda: hasattr(self, "view") and self.view.mode == "manual"),
            Command("undo", "Cofnij", "undo", self.undo, lambda: editable() and bool(self.history.undo_stack), "Ctrl+Z"),
            Command("redo", "Ponów", "redo", self.redo, lambda: editable() and bool(self.history.redo_stack), "Ctrl+Y"),
            Command("previous", "Poprzedni", "previous", lambda: self.navigate(-1), active, "P"),
            Command("next", "Następny", "next", lambda: self.navigate(1), active, "N"),
            Command("conflicts", "Konflikty", "conflict", self.show_conflicts, lambda: bool(self.conflicts)),
            Command("show", "Pokaż wszystkie", "eye", lambda: self.visibility("all"), editable),
            Command("hide", "Ukryj wszystkie", "layers", lambda: self.visibility("none"), editable),
            Command("only", "Tylko aktywna", "layers", lambda: self.visibility("active"), active),
            Command("accept", "Akceptuj", "check", lambda: self.decide("accepted"), lambda: selected() and bool(self.selected_detection().group)),
            Command("reject", "Odrzuć", "delete", lambda: self.decide("rejected"), selected),
            Command("delete", "Usuń", "delete", lambda: self.decide("rejected"), selected, "Delete"),
            Command("assign", "Przypisz do grupy", "layers", self.reassign, selected),
            Command("escape", "Anuluj narzędzie", "pan", lambda: self.set_mode("pan"), shortcut="Esc"),
            Command("debug", "Detection Debug", "settings", self.toggle_debug, checked=lambda: hasattr(self,"debug_panel") and self.debug_panel.isVisible()),
            Command("artifacts", "Tryb diagnostyczny: zapisuj wycinki", "settings", self.toggle_artifacts,
                checked=lambda:self.settings_store.get("debug/artifacts",False)),
            Command("diagnostic_test", "Uruchom test diagnostyczny", "check", self.run_self_test,
                lambda:not self.busy and not self.loading),
            Command("debug_folder", "Otwórz logi i wycinki", "open", self.open_debug_folder),
            Command("template_legend", "Wzorzec pochodzi z legendy", "template", self.toggle_template_legend,
                lambda:active() and bool(self.project.active_group().template),
                checked=lambda:bool(self.project.active_group() and self.project.active_group().template and self.project.active_group().template.get('source')=='LEGEND')),
            Command("hybrid", "Model analizy: Base / Small / klasyczny…", "settings", self.toggle_hybrid,
                lambda:not self.busy and not self.loading),
            Command("performance", "Wydajność i sprzęt", "settings", self.show_performance),
            Command("settings", "Próg konfliktu", "settings", self.settings, lambda: not self.busy),
        ]
        for command in commands:
            self.registry.register(command)

    def build_ui(self):
        toolbar = QToolBar("Główne narzędzia", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        self.current_page_only = QCheckBox("Tylko bieżąca strona")
        self.current_page_only.setChecked(self.settings_store.get("search/current_page_only",False))
        self.current_page_only.setToolTip("Gdy wyłączone: wszystkie strony wszystkich dokumentów projektu.")
        self.current_page_only.toggled.connect(lambda value: self.settings_store.set("search/current_page_only",value))
        sections = [("Projekt", ["new", "open", "save"]), ("Widok", ["pan", "fit"]),
                    ("Zliczanie", ["group", "template", "find", "manual"]),
                    ("Edycja", ["undo", "redo"]), ("Ustawienia", ["settings", "debug", "artifacts", "diagnostic_test", "debug_folder", "template_legend", "hybrid", "performance"])]
        for title, keys in sections:
            menu = self.menuBar().addMenu(title)
            if toolbar.actions():
                toolbar.addSeparator()
            for key in keys:
                if key not in ("debug","artifacts","diagnostic_test","debug_folder","template_legend","hybrid","performance"):
                    toolbar.addAction(self.registry.actions[key])
                if key=="find":
                    toolbar.addWidget(self.current_page_only)
                menu.addAction(self.registry.actions[key])
        context = QToolBar("Weryfikacja", self)
        context.setMovable(False)
        context.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBarBreak()
        self.addToolBar(context)
        for key in ["accept", "reject", "assign", "previous", "next", "conflicts"]:
            context.addAction(self.registry.actions[key])
        context.addSeparator()
        self.hint = QLabel("Otwórz PDF i utwórz pierwszą grupę.")
        context.addWidget(self.hint)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0,0,0,0)
        center_layout.setSpacing(5)
        self.operation_progress = OperationProgress()
        self.operation_progress.cancel_requested.connect(self.jobs.cancel_analysis)
        center_layout.addWidget(self.operation_progress)
        splitter = QSplitter()
        center_layout.addWidget(splitter,1)
        self.setCentralWidget(center)
        self.splitter = splitter
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        brand = QLabel("ElectroCount")
        brand.setStyleSheet("font-size: 20px; font-weight: 700; padding: 14px;")
        layout.addWidget(brand)
        label = QLabel("PROJEKT / STRONY")
        label.setObjectName("section")
        layout.addWidget(label)
        self.pages = QListWidget()
        self.pages.setIconSize(QSize(145, 108))
        self.pages.setViewMode(QListView.ViewMode.IconMode)
        self.pages.setResizeMode(QListView.ResizeMode.Adjust)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setWordWrap(True)
        self.pages.setSpacing(4)
        self.pages.currentRowChanged.connect(self.change_page)
        self.pages.itemDoubleClicked.connect(self.rename_page)
        self.pages.verticalScrollBar().valueChanged.connect(lambda _: self.load_thumbnails())
        layout.addWidget(self.pages)
        note = QLabel(f"Lokalnie · bez chmury\nWersja {__version__} · lokalna analiza PDF")
        note.setStyleSheet("color: #8096ad; padding: 12px;")
        layout.addWidget(note)
        self.pages_sidebar = CollapsiblePanel("Strony",left,190,260)
        self.pages_sidebar.changed.connect(lambda value: self.settings_store.set("pages/collapsed",value))
        splitter.addWidget(self.pages_sidebar)
        self.view = DrawingView()
        self.view.rectangle_selected.connect(self.rectangle_selected)
        self.view.detection_selected.connect(self.select_detection)
        self.view.viewport_changed.connect(self.render_detail)
        splitter.addWidget(self.view)
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(8, 0, 8, 8)
        label = QLabel("GRUPY ZLICZANIA")
        label.setObjectName("section")
        layout.addWidget(label)
        self.groups = QTreeWidget()
        self.groups.setHeaderLabels(["Grupa", "Znaleziono", "OK", "Sprawdź", "Konflikt"])
        self.groups.setRootIsDecorated(False)
        self.groups.setColumnWidth(0, 80)
        for col in (1, 2, 3, 4):
            self.groups.setColumnWidth(col, 55)
        self.groups.setColumnWidth(1, 85)
        self.groups.setColumnWidth(2, 35)
        self.groups.setColumnWidth(3, 65)
        self.groups.currentItemChanged.connect(self.activate_group)
        self.groups.itemChanged.connect(self.group_changed)
        self.groups.itemDoubleClicked.connect(self.edit_group)
        self.groups.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups.customContextMenuRequested.connect(self.group_menu)
        layout.addWidget(self.groups, 2)
        visibility = QToolBar()
        for key in ["show", "hide", "only"]:
            visibility.addAction(self.registry.actions[key])
        layout.addWidget(visibility)
        from .template_preview import TemplatePreview
        self.template_preview=TemplatePreview()
        layout.addWidget(self.template_preview)
        row = QHBoxLayout()
        row.addWidget(QLabel("Próg podobieństwa"))
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.50, 0.99)
        self.threshold.setSingleStep(0.01)
        self.threshold.setValue(self.project.threshold)
        self.threshold.valueChanged.connect(self.threshold_changed)
        row.addWidget(self.threshold)
        layout.addLayout(row)
        self.review_only = QCheckBox("Tylko do weryfikacji i konflikty")
        self.review_only.toggled.connect(lambda _: self.refresh_results())
        layout.addWidget(self.review_only)
        self.active_group_only = QCheckBox("Na rysunku tylko aktywna grupa")
        self.active_group_only.setChecked(self.settings_store.get("view/active_group_only",False))
        self.active_group_only.toggled.connect(self.active_group_filter_changed)
        layout.addWidget(self.active_group_only)
        self.found_count = QLabel("Znaleziono: 0")
        self.found_count.setWordWrap(True)
        self.found_count.setStyleSheet("font-size: 18px; font-weight: bold; padding: 6px;")
        layout.addWidget(self.found_count)
        self.tabs = QTabWidget()
        self.results, self.conflict_list = QListWidget(), QListWidget()
        self.results.currentItemChanged.connect(self.result_selected)
        self.conflict_list.currentItemChanged.connect(self.conflict_selected)
        self.conflict_list.itemDoubleClicked.connect(self.resolve_conflict)
        self.tabs.addTab(self.results, "Wykrycia")
        self.tabs.addTab(self.conflict_list, "Konflikty")
        layout.addWidget(self.tabs, 3)
        self.resolve_button = QPushButton("Rozwiąż wybrany konflikt…")
        self.resolve_button.clicked.connect(self.resolve_conflict)
        layout.addWidget(self.resolve_button)
        self.summary = QLabel("Brak wyników")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("padding: 10px; color: #92adc2;")
        layout.addWidget(self.summary)
        self.results_sidebar = CollapsiblePanel("Grupy i wyniki",right,355,490)
        self.results_sidebar.changed.connect(lambda value: self.settings_store.set("results/collapsed",value))
        self.results_sidebar.set_collapsed(self.settings_store.get("results/collapsed"),emit=False)
        splitter.addWidget(self.results_sidebar)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([205, 970, 385])
        self.progress = self.operation_progress.bar
        self.cancel_button = self.operation_progress.cancel
        self.performance_button = QPushButton("Stała jakość · CPU")
        self.performance_button.clicked.connect(self.show_performance)
        self.statusBar().addPermanentWidget(self.performance_button)
        self.statusBar().showMessage("Gotowe · dokumenty pozostają na tym komputerze")
        self.debug_panel=DetectionDebug(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,self.debug_panel)
        self.debug_panel.setVisible(self.settings_store.get("detection/debug"))
        self.debug_panel.visibilityChanged.connect(lambda value:self.settings_store.set("detection/debug",value))

    def toggle_debug(self):
        self.debug_panel.setVisible(not self.debug_panel.isVisible())
        self.debug_panel.inspect(self.selected_detection(),self.project)



    def failure(self, message):
        self.loading = False
        self.registry.refresh()
        QMessageBox.warning(self, "Nie udało się wykonać operacji", message)

    def job_status(self, text):
        self.statusBar().showMessage(text)
        self.operation_progress.set_stage(text)

    def busy_changed(self, busy):
        self.busy = busy
        if not hasattr(self,'find_spinner'):
            self.find_spinner=QTimer(self);self.find_spinner.setInterval(120);self.find_spinner_frame=0
            self.find_spinner.timeout.connect(self.animate_find)
        if busy:self.find_spinner.start()
        else:self.find_spinner.stop()
        self.registry.actions["find"].setText("Analizuję…" if busy else "Znajdź")
        self.threshold.setEnabled(not busy)
        self.current_page_only.setEnabled(not busy)
        self.registry.refresh()

    def animate_find(self):
        self.find_spinner_frame=(self.find_spinner_frame+1)%4
        self.registry.actions['find'].setText('◐◓◑◒'[self.find_spinner_frame]+' Analizuję…')

    def checkpoint(self):
        self.history.record(self.project)
        self.dirty = True

    def maybe_save(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, "Niezapisane zmiany", "Zapisać zmiany projektu?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.StandardButton.Save else True

    def new_project(self):
        if self.maybe_save():
            self.replace_project(Project(), None)

    def open_path(self, path):
        if self.busy or self.loading:
            return
        if Path(path).suffix.lower() == ".sqlite":
            if not self.maybe_save():
                return
            try:
                self.replace_project(ProjectManager().load(path), str(Path(path).parent))
            except Exception as exc:
                logging.exception("Project load")
                self.failure(str(exc))
        else:
            self.import_paths([path])

    def replace_project(self, project, folder):
        self.jobs.clear_render_queue()
        self.generation += 1
        self.project, self.folder = project, folder
        self.history, self.dirty, self.selected = History(), False, ""
        self.view.set_mode("pan")
        self.preview_cache.clear()
        self.thumb_loaded.clear()
        self.thumb_pending.clear()
        self.detail_key = None
        saved_view = dict(project.view)
        self.pages_sidebar.set_count(len(project.pages))
        collapsed = self.settings_store.get("pages/collapsed") if self.settings_store.has("pages/collapsed") else len(project.pages)<=1
        self.pages_sidebar.set_collapsed(collapsed,emit=False)
        self.pages.blockSignals(True)
        self.pages.clear()
        for index, page in enumerate(project.pages):
            item = QListWidgetItem(f"{index+1:02}  {page['name']}")
            item.setSizeHint(QSize(180, 150))
            item.setToolTip(page["name"])
            self.pages.addItem(item)
        self.pages.blockSignals(False)
        self.threshold.blockSignals(True)
        self.threshold.setValue(project.threshold)
        self.threshold.blockSignals(False)
        if project.pages:
            self.pages.setCurrentRow(min(project.page, len(project.pages)-1))
            if saved_view:
                scale = saved_view.get("scale", 1)
                self.view.setTransform(QTransform.fromScale(scale, scale))
                self.view.centerOn(saved_view.get("x", 0), saved_view.get("y", 0))
        else:
            self.view.set_page(800, 600)
        self.dirty = False
        self.refresh()

    def save_project(self):
        self.capture_view()
        folder = self.folder
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "Wybierz pusty folder projektu")
            if not folder:
                return False
            if (Path(folder)/"project.sqlite").exists():
                self.failure("Ten folder zawiera już projekt. Wybierz nowy folder.")
                return False
        try:
            ProjectManager().save(self.project, folder)
            self.folder, self.dirty = folder, False
            self.refresh()
            self.statusBar().showMessage("Projekt zapisany wraz z kopią źródłowego PDF", 6000)
            return True
        except Exception as exc:
            logging.exception("Project save")
            self.failure(str(exc))
            return False

    def capture_view(self):
        if self.project.pages:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            self.project.view = {"scale": self.view.transform().m11(), "x": center.x(), "y": center.y()}

    def change_page(self, index):
        if not 0 <= index < len(self.project.pages):
            return
        self.project.page = index
        self.dirty = True
        page = self.project.pages[index]
        self.view.set_page(page["width"], page["height"])
        self.detail_key = None
        generation = self.generation
        if index in self.preview_cache:
            self.view.set_preview(self.preview_cache[index])
        else:
            scale = min(1.5, 1600/max(page["width"], page["height"]))
            def ready(path):
                if generation != self.generation:
                    return
                pixmap = QPixmap(path)
                self.preview_cache[index] = pixmap
                while len(self.preview_cache) > 6:
                    self.preview_cache.popitem(last=False)
                if index == self.project.page:
                    self.view.set_preview(pixmap)
            path, source_page = self.project.page_location(index)
            self.jobs.submit({"kind": "render", "path": path, "page": source_page, "scale": scale}, ready)
        self.refresh_results()
        self.load_thumbnails()
        self.statusBar().showMessage(f"{page['name']} · {index+1}/{len(self.project.pages)}")

    def load_thumbnails(self):
        if not self.project.pages:
            return
        visible = [i for i in range(self.pages.count()) if self.pages.visualItemRect(self.pages.item(i)).intersects(self.pages.viewport().rect())]
        generation = self.generation
        for index in visible:
            if index in self.thumb_loaded or index in self.thumb_pending:
                continue
            self.thumb_pending.add(index)
            page = self.project.pages[index]
            def ready(path, index=index):
                if generation == self.generation:
                    self.thumb_pending.discard(index)
                    self.thumb_loaded.add(index)
                    self.pages.item(index).setIcon(QIcon(QPixmap(path)))
            path, source_page = self.project.page_location(index)
            self.jobs.submit({"kind": "render", "path": path, "page": source_page,
                              "scale": 128/max(page["width"], page["height"])}, ready)

    def render_detail(self):
        if not self.project.pages:
            return
        old_view = dict(self.project.view)
        self.capture_view()
        if old_view != self.project.view:
            self.dirty = True
            self.setWindowTitle(f"ElectroCount {__version__} · {self.project.name} *")
        scale = min(4.0, max(1.0, round(self.view.transform().m11()*2)/2))
        rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect().intersected(self.view.page_rect)
        if rect.isEmpty():
            return
        scale = min(scale, 2400/max(rect.width(), rect.height()))
        box = [rect.x(), rect.y(), rect.width(), rect.height()]
        key = (self.generation, self.project.page, round(scale, 2), *[round(v, 1) for v in box])
        if key == self.detail_key:
            return
        self.detail_key = key
        generation, page = self.generation, self.project.page
        def ready(path):
            if generation == self.generation and page == self.project.page and key == self.detail_key:
                self.view.set_detail(QPixmap(path), box, scale)
        self.jobs.queue = type(self.jobs.queue)((r, c) for r, c in self.jobs.queue if not (r["kind"] == "render" and "rect" in r))
        path, source_page = self.project.page_location(page)
        self.jobs.submit({"kind": "render", "path": path, "page": source_page, "scale": scale, "rect": box}, ready)

    def rename_page(self, item):
        if self.busy:
            return
        index = self.pages.row(item)
        name, ok = QInputDialog.getText(self, "Nazwa strony", "Kondygnacja / nazwa:", text=self.project.pages[index]["name"])
        if ok and name.strip():
            self.checkpoint()
            self.project.pages[index]["name"] = name.strip()
            self.refresh()

    def add_group(self):
        name, ok = QInputDialog.getText(self, "Nowa grupa zliczania", "Kod / nazwa grupy:")
        if ok and name.strip():
            self.checkpoint()
            group = Group(name=name.strip(), color=self.PALETTE[len(self.project.groups)%len(self.PALETTE)])
            self.project.groups.append(group)
            self.project.active = group.id
            self.refresh()

    def group_menu(self, position):
        item = self.groups.itemAt(position)
        if not item:
            return
        self.groups.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Zmień nazwę / opis", self.edit_group)
        menu.addAction("Zmień kolor", self.change_color)
        group=self.project.active_group()
        if group and group.possible_label:
            menu.addAction("Akceptuj możliwe oznaczenie "+group.possible_label,self.accept_possible_label)
        menu.addAction("Duplikuj konfigurację", self.duplicate_group)
        menu.addAction(self.registry.actions["find"])
        menu.addSeparator()
        menu.addAction("Usuń grupę", self.delete_group)
        menu.exec(self.groups.viewport().mapToGlobal(position))

    def edit_group(self, *_):
        group = self.project.active_group()
        if not group or self.busy or self.loading:
            return
        name, ok = QInputDialog.getText(self, "Edytuj grupę", "Kod / nazwa:", text=group.name)
        if ok and name.strip():
            description, confirmed = QInputDialog.getText(self, "Opis grupy", "Opis (opcjonalnie):", text=group.description)
            if confirmed:
                self.checkpoint()
                group.name, group.description = name.strip(), description
                self.refresh()

    def accept_possible_label(self):
        group=self.project.active_group()
        if group and group.possible_label and not self.busy and not self.loading:
            self.checkpoint()
            self.invalidate_label(group.id)
            group.label=normalize_text(group.possible_label)
            group.name=group.label
            group.possible_label=""
            group.template["label"]=group.label
            self.refresh()

    def change_color(self):
        group = self.project.active_group()
        if group and not self.busy and not self.loading:
            color = QColorDialog.getColor(QColor(group.color), self, "Kolor grupy")
            if color.isValid():
                self.checkpoint()
                group.color = color.name()
                self.refresh()

    def duplicate_group(self):
        from copy import deepcopy
        group = self.project.active_group()
        if group and not self.busy and not self.loading:
            self.checkpoint()
            copy = Group(group.name+" — kopia", self.PALETTE[len(self.project.groups)%len(self.PALETTE)],
                         group.description, True, deepcopy(group.template))
            copy.label = group.label
            self.project.groups.append(copy)
            self.project.active = copy.id
            self.refresh()

    def delete_group(self):
        group = self.project.active_group()
        if group and not self.busy and not self.loading and QMessageBox.question(self, "Usuń grupę", f"Usunąć grupę {group.name} i jej wyniki? Operację można cofnąć.") == QMessageBox.StandardButton.Yes:
            self.checkpoint()
            self.project.groups.remove(group)
            self.project.discoveries = [d for d in self.project.discoveries if d["requested_group"] != group.id]
            self.project.detections = [d for d in self.project.detections if d.group != group.id and d.requested_group != group.id]
            self.project.active = self.project.groups[0].id if self.project.groups else ""
            self.selected = ""
            self.refresh()

    def activate_group(self, item, previous):
        if item and not self.refreshing:
            self.project.active = item.data(0, Qt.ItemDataRole.UserRole)
            self.selected, self.dirty = "", True
            self.refresh_results()
            self.registry.refresh()

    def group_changed(self, item, column):
        if self.refreshing or column != 0:
            return
        group = next(g for g in self.project.groups if g.id == item.data(0, Qt.ItemDataRole.UserRole))
        group.visible = item.checkState(0) == Qt.CheckState.Checked
        self.dirty = True
        self.refresh_results()

    def visibility(self, mode):
        for group in self.project.groups:
            group.visible = mode == "all" or (mode == "active" and group.id == self.project.active)
        self.dirty = True
        self.refresh()

    def threshold_changed(self, value):
        self.project.threshold, self.dirty = value, True

    def set_mode(self, mode):
        self.view.set_mode(mode)
        self.hint.setText({"pan": "Rolka: zoom · przeciągnij: przesuwanie",
                          "template": "Zaznacz symbol + typ + IP / EX / fazy, jeśli podane · Esc: anuluj",
                          "manual": "Zaznacz prostokątem element do dodania"}[mode])
        self.registry.refresh()

    def rectangle_selected(self, rect):
        if self.busy or self.loading:
            return
        group = self.project.active_group()
        if self.view.mode == "template":
            page, generation = self.project.page, self.generation
            group_id = group.id if group else None
            path, source_page = self.project.page_location(page)
            self.loading = True
            self.registry.refresh()
            def prepared(template):
                self.loading = False
                self.registry.refresh()
                if generation != self.generation:
                    return
                template["page"] = page
                detected = template.get("label", "")
                self.checkpoint()
                target = next((g for g in self.project.groups if g.id == group_id), None)
                if target and (target.template or any(d.group==target.id for d in self.project.detections)):
                    target = None
                if not detected:
                    self.project.symbol_serial += 1
                    while any(g.name == f"Symbol {self.project.symbol_serial:02}" for g in self.project.groups):
                        self.project.symbol_serial += 1
                    name = f"Symbol {self.project.symbol_serial:02}"
                else:
                    name = detected
                from .electrical_profile import display_label
                name=display_label(name,template.get('electrical_profile',{}))
                if target is None:
                    target = Group(name, self.PALETTE[len(self.project.groups)%len(self.PALETTE)])
                    self.project.groups.append(target)
                target.name, target.label, target.template = name, detected, template
                target.possible_label = template.get("possible_label", "")
                self.project.active = target.id
                info = f"Wykryte oznaczenie: {detected}" if detected else f"Utworzono {name}"
                if target.possible_label:
                    info += f" · Możliwe oznaczenie: {target.possible_label}"
                self.statusBar().showMessage(info,15000)
                self.set_mode("pan")
                self.refresh()
            self.jobs.submit({"kind": "template", "path": path, "page": source_page, "rect": rect,
                "selection_context":self.view.last_selection_context,
                "ocr_enabled":self.engine_mode()!='classic',
                "model_name":'base' if self.engine_mode()=='hybrid_base' else 'small',
                "debug_dir":str(new_debug_run()) if self.settings_store.get("debug/artifacts",False) else None}, prepared)
        elif self.view.mode == "manual" and group:
            self.checkpoint()
            detection = Detection(group.id, self.project.page, rect, decision="accepted", source="manual")
            self.project.detections.append(detection)
            self.selected = detection.id
            self.set_mode("pan")
            self.refresh()

    def invalidate_label(self, group_id):
        for detection in self.project.detections:
            if detection.group == group_id and detection.source == "automatic" and detection.decision != "rejected":
                detection.previous_decision = detection.decision
                detection.group, detection.requested_group = "", group_id
                detection.decision, detection.reason = "review", "target_label_changed"


    def find_matches(self):
        from copy import deepcopy
        group = self.project.active_group()
        if not group or not group.template or self.loading:
            return
        group_id, generation = group.id, self.generation
        template = deepcopy(group.template)
        template_path, template_page = self.project.page_location(template["page"])
        template["page"] = template_page
        document_id = self.project.pages[self.project.page]["document_id"]
        indices = [self.project.page] if self.current_page_only.isChecked() else list(range(len(self.project.pages)))
        pages = [{"page": i, "path": self.project.page_location(i)[0],
                  "source_page": self.project.page_location(i)[1]} for i in indices]
        def ready(batch):
            if generation != self.generation:
                return
            self.checkpoint()
            for entry in batch["pages"]:
                ResultsManager().apply(self.project, group_id, entry["page"], entry["result"])
            self.refresh()
            total = sum(len(entry["result"]["matches"]) for entry in batch["pages"])
            tiled = any(e["result"].get("stages",{}).get("vector_limit_reached") for e in batch["pages"])
            suffix = " · duży rysunek: analiza kafelkowa" if tiled else ""
            warnings=[w for e in batch["pages"] for w in e["result"].get("coverage_warnings",[])]
            if warnings:suffix=" · "+warnings[0]
            self.statusBar().showMessage(f"Przeanalizowano {len(pages)} stron · zgodnych kandydatów: {total}"+suffix,20000)
        self.jobs.submit({"kind": "batch_match", "pages": pages,
            "template": template, "template_path": template_path, "label": group.label,
            "threshold": self.project.threshold,
            "config":{"search_scope":"current_page" if self.current_page_only.isChecked() else "all_pages",
                "engine_mode":self.engine_mode(),
                "pages":indices,"text_filter":"exact_native","ai_mode":"deterministic_cpu","gui_runtime":self.startup_runtime},
            "debug_dir":str(new_debug_run()) if self.settings_store.get("debug/artifacts",False) else None}, ready, analysis=True)


    def selected_detection(self):
        return next((d for d in self.project.detections if d.id == self.selected and
                     (d.group == self.project.active or (not d.group and d.requested_group == self.project.active))), None)


    def select_detection(self, identifier):
        detection = next((d for d in self.project.detections if d.id == identifier), None)
        if detection and (detection.group == self.project.active or (not detection.group and detection.requested_group == self.project.active)):
            self.selected = identifier
            self.refresh_results()
            self.registry.refresh()


    def result_selected(self, item, previous):
        if not item or self.refreshing:
            return
        self.selected = item.data(Qt.ItemDataRole.UserRole)
        detection = self.selected_detection()
        if detection:
            if detection.page != self.project.page:
                self.pages.setCurrentRow(detection.page)
            self.view.focus_rect(detection.rect)
            self.view.draw_detections(self.project, self.conflict_ids, self.selected, self.review_only.isChecked(), self.active_group_only.isChecked())
            self.debug_panel.inspect(self.selected_detection(),self.project)
            self.registry.refresh()

    def decide(self, decision):
        detection = self.selected_detection()
        if detection:
            self.checkpoint()
            if decision == "accepted" and not detection.group:
                return
            detection.decision = decision
            self.refresh()

    def reassign(self):
        detection = self.selected_detection()
        if not detection:
            return
        labels = [f"{i+1}. {g.name}" for i, g in enumerate(self.project.groups)]
        choice, ok = QInputDialog.getItem(self, "Przypisz wykrycie", "Grupa docelowa:", labels, editable=False)
        if ok:
            self.checkpoint()
            group = self.project.groups[labels.index(choice)]
            detection.group, self.project.active = group.id, group.id
            self.refresh()

    def navigate(self, direction):
        if self.results.count():
            self.results.setCurrentRow((self.results.currentRow()+direction)%self.results.count())

    def show_conflicts(self):
        self.tabs.setCurrentIndex(1)
        if self.conflict_list.count():
            self.conflict_list.setCurrentRow(0)

    def conflict_selected(self, item, previous):
        if not item or self.refreshing:
            return
        ids = item.data(Qt.ItemDataRole.UserRole)
        detection = next((d for d in self.project.detections if d.id in ids), None)
        if detection:
            if detection.page != self.project.page:
                self.pages.setCurrentRow(detection.page)
            self.view.focus_rect(detection.rect)
            from PySide6.QtGui import QPen
            from PySide6.QtCore import QRectF
            pen = QPen(QColor("#fa6076"), 3)
            pen.setCosmetic(True)
            marker = self.view.scene().addRect(QRectF(*detection.rect), pen)
            marker.setZValue(15)
            self.view.overlays.append(marker)

    def resolve_conflict(self, *_):
        item = self.conflict_list.currentItem()
        if not item or self.busy:
            return
        ids = item.data(Qt.ItemDataRole.UserRole)
        participants = [d for d in self.project.detections if d.id in ids]
        groups = {g.id: g for g in self.project.groups}
        options = [f"Przypisz do {(groups[d.group].name if d.group in groups else "Bez przypisania")} · {d.id[:6]}" for d in participants]
        options += ["Odrzuć wszystkie", "Zezwól na nakładanie — to różne elementy", "Przypisz jako inny typ"]
        choice, ok = QInputDialog.getItem(self, "Rozwiąż konflikt", "Wybierz decyzję:", options, editable=False)
        if not ok:
            return
        index = options.index(choice)
        new_name = None
        if index == len(participants)+2:
            new_name, ok = QInputDialog.getText(self, "Inny typ", "Nazwa nowej grupy:")
            if not ok or not new_name.strip():
                return
        self.checkpoint()
        row = self.conflict_list.currentRow()
        if index < len(participants):
            for d in participants:
                d.decision = ("accepted" if d.group else "review") if d is participants[index] else "rejected"
        elif index == len(participants):
            for d in participants:
                d.decision = "rejected"
        elif index == len(participants)+1:
            for i, a in enumerate(participants):
                for b in participants[i+1:]:
                    self.project.allowed.append(sorted([a.id, b.id]))
        else:
            group = Group(new_name.strip(), self.PALETTE[len(self.project.groups)%len(self.PALETTE)])
            self.project.groups.append(group)
            for d in participants:
                d.decision = "rejected"
            self.project.detections.append(Detection(group.id, participants[0].page,
                list(participants[0].rect), decision="accepted", source="manual"))
        self.project.resolutions.append({"participants": sorted(ids), "decision": choice})
        self.refresh()
        if self.conflict_list.count():
            self.conflict_list.setCurrentRow(min(row, self.conflict_list.count()-1))

    def undo(self):
        self.project = self.history.undo(self.project)
        self.dirty = True
        self.sync_after_history()

    def redo(self):
        self.project = self.history.redo(self.project)
        self.dirty = True
        self.sync_after_history()

    def sync_after_history(self):
        self.jobs.clear_render_queue()
        self.generation += 1
        self.preview_cache.clear()
        self.rebuild_page_list()
        if self.project.pages:
            self.project.page = min(self.project.page, len(self.project.pages)-1)
            self.change_page(self.project.page)
        else:
            self.view.set_page(800, 600)
        self.threshold.blockSignals(True)
        self.threshold.setValue(self.project.threshold)
        self.threshold.blockSignals(False)
        self.refresh()


    def settings(self):
        overlap, ok = QInputDialog.getDouble(self, "Próg konfliktu", "IoU (0,05–0,95):",
                                            self.project.overlap, 0.05, 0.95, 2)
        if ok:
            proximity, ok = QInputDialog.getDouble(self, "Odległość środków",
                "Odległość / mniejszy bok symbolu (0,05–0,95):", self.project.proximity, 0.05, 0.95, 2)
            if ok:
                self.checkpoint()
                self.project.overlap, self.project.proximity = overlap, proximity
                self.refresh()

    def refresh(self):
        self.refreshing = True
        self.conflicts = self.conflict_engine.components(self.project)
        self.conflict_ids = set().union(*self.conflicts) if self.conflicts else set()
        self.groups.clear()
        for group in self.project.groups:
            numbers = counts(self.project, group.id, self.conflict_ids)
            pending = sum(not d.group and d.requested_group==group.id and d.decision!='rejected'
                          for d in self.project.detections)
            item = QTreeWidgetItem([group.name, str(sum(numbers)+pending), *map(str, numbers)])
            item.setData(0, Qt.ItemDataRole.UserRole, group.id)
            item.setCheckState(0, Qt.CheckState.Checked if group.visible else Qt.CheckState.Unchecked)
            item.setForeground(0, QColor(group.color))
            item.setToolTip(0, f"Możliwe oznaczenie: {group.possible_label or 'brak'}\nOznaczenie porównywane dokładnie: {group.label or 'brak'}\n{group.description}")
            self.groups.addTopLevelItem(item)
            if group.id == self.project.active:
                self.groups.setCurrentItem(item)
        self.conflict_list.clear()
        names = {g.id: g.name for g in self.project.groups}
        for index, ids in enumerate(self.conflicts):
            participants = [d for d in self.project.detections if d.id in ids]
            item = QListWidgetItem(f"{index+1}. " + " / ".join(dict.fromkeys(names.get(d.group, "Bez przypisania") for d in participants)))
            item.setData(Qt.ItemDataRole.UserRole, ids)
            self.conflict_list.addItem(item)
        self.resolve_button.setEnabled(bool(self.conflicts) and not self.busy)
        if self.view.mode == "pan":
            self.hint.setText("Rolka: zoom · przeciągnij: przesuwanie" if self.project.source else "Otwórz PDF i utwórz pierwszą grupę.")
        self.tabs.setTabText(1, f"Konflikty ({len(self.conflicts)})")
        self.registry.actions["conflicts"].setText(f"Konflikty ({len(self.conflicts)})" if self.conflicts else "Konflikty")
        self.setWindowTitle(f"ElectroCount {__version__} · {self.project.name}" + (" *" if self.dirty else ""))
        for index, page in enumerate(self.project.pages):
            if index < self.pages.count():
                self.pages.item(index).setText(f"{index+1:02}  {page['name']}")
        self.refreshing = False
        self.refresh_results()
        self.registry.refresh()

    def refresh_results(self):
        from collections import Counter
        self.refreshing = True
        self.results.clear()
        for d in self.project.detections:
            if d.group != self.project.active and not (not d.group and d.requested_group == self.project.active):
                continue
            conflict = d.id in self.conflict_ids
            if self.review_only.isChecked() and d.decision != "review" and not conflict:
                continue
            status = "KONFLIKT" if conflict else {"review": "Sprawdź", "accepted": "OK", "rejected": "Odrzucony"}[d.decision]
            if not d.group:
                status = "BEZ PRZYPISANIA · " + status
            origin = "ręczny" if d.source == "manual" else f"kształt {d.graphic_score or d.score:.0%}"
            rating_reason={'missing_electrical_rating':'brak wymaganego IP / EX / faz',
                           'ambiguous_electrical_rating':'niejednoznaczne IP / EX / fazy'}.get(d.reason)
            if rating_reason:origin=rating_reason
            item = QListWidgetItem(f"{status} · {d.label or '?'} · {origin} | {d.page+1:02} · {self.project.pages[d.page]['name']}")
            item.setToolTip(f"Kształt: {d.graphic_score:.1%}\nZgodność tekstu: {d.text_score:.0%}\nPowiązanie przestrzenne: {d.spatial_association_score:.1%}\nOcena łączna: {d.confidence:.1%} (nie prawdopodobieństwo)\nŹródło: warstwa tekstowa PDF\nPowód: {d.reason}")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            self.results.addItem(item)
            if d.id == self.selected:
                self.results.setCurrentItem(item)
        group = self.project.active_group()
        self.template_preview.set_template(group.template if group else None,group.label if group else "")
        if group:
            accepted, review, conflict = counts(self.project, group.id, self.conflict_ids)
            on_page = sum((d.group or d.requested_group)==group.id and d.page==self.project.page
                          and d.decision!='rejected' for d in self.project.detections)
            pending = sum(not d.group and d.requested_group == group.id and d.decision != "rejected" for d in self.project.detections)
            self.found_count.setText(f"Znaleziono: {accepted+review+conflict+pending} · na stronie: {on_page}")
            others = Counter(d["label"] for d in self.project.discoveries if d["requested_group"] == group.id)
            other_text = ", ".join(f"{code}: {number}" for code, number in others.items()) or "brak"
            legend=sum(r.get("counts",{}).get("legend_matches",0) for key,r in self.project.analysis_reports.items() if key.startswith(group.id+":"))
            self.summary.setText(f"Znaleziono {accepted+review+conflict+pending} · {legend} w legendzie / uwagach (nie doliczono)\n{group.name} · oznaczenie: {group.label or ('możliwe '+group.possible_label if group.possible_label else 'brak — wzorzec graficzny')}\n{accepted} zatwierdzonych · {review} do sprawdzenia · {conflict} w konflikcie\nBez przypisania: {pending}\nInne oznaczenia: {other_text}")
        else:
            self.found_count.setText("Znaleziono: 0")
            self.summary.setText("Zaznacz wzorzec z oznaczeniem lub utwórz grupę.")
        self.view.draw_detections(self.project, self.conflict_ids, self.selected, self.review_only.isChecked(), self.active_group_only.isChecked())
        self.refreshing = False


    def active_group_filter_changed(self, checked):
        self.settings_store.set("view/active_group_only",checked)
        self.refresh_results()


    def closeEvent(self, event):
        if self.busy or self.loading:
            QMessageBox.information(self, "Trwa operacja", "Poczekaj na import / przygotowanie wzorca lub anuluj analizę.")
            event.ignore()
            return
        if not self.maybe_save():
            event.ignore()
            return
        self.performance.close()
        self.jobs.close()
        event.accept()

