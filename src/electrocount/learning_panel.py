"""Human review, dataset portability and model versions in one local panel."""
import json
import shutil
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QFileDialog, QMessageBox, QProgressBar,
    QCheckBox, QHeaderView)
from .ai.learning_store import OUTCOMES, SPLITS
from .ai.tiny_model import TinyPairModel

NAMES = {'correct': 'Poprawny', 'wrong': 'Błędny kształt', 'variant': 'Inny wariant / oznaczenie',
         'uncertain': 'Niepewny', 'train': 'Uczenie', 'validation': 'Walidacja', 'test': 'Test'}


class LearningPanel(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.store, self.service = window, window.learning_store, window.learning
        self.setWindowTitle('Uczenie i kontrola modelu')
        self.resize(1120, 820)
        layout = QVBoxLayout(self)
        help_text = QLabel('Otwórz PDF, zaznacz wzorzec i wyszukaj. Akceptuj poprawne trafienia, odrzucaj błędne '
                          'i dodawaj pominięcia ręcznie. Tylko Twoje oceny trafiają do nauki. '
                          '„Inny wariant” i „Niepewny” są przechowywane, ale nie uczą geometrii.')
        help_text.setWordWrap(True); layout.addWidget(help_text)
        row = QHBoxLayout(); layout.addLayout(row)
        self.collect = QCheckBox('Zapisuj moje oceny'); self.collect.setChecked(window.settings_store.get('learning/collect', True))
        self.collect.toggled.connect(lambda value: window.settings_store.set('learning/collect', value)); row.addWidget(self.collect)
        open_pdf = QPushButton('Dodaj dokument PDF'); open_pdf.clicked.connect(self.open_document); row.addWidget(open_pdf)
        self.summary = QLabel(); layout.addWidget(self.summary)
        self.table = QTableWidget(0, 5)
        self.table.setStyleSheet('QTableWidget {background:#172232;color:#dce4ef;gridline-color:#344359;border:none;}'
                                'QTableWidget::item:selected {background:#254154;color:#ffffff;}')
        self.table.setHorizontalHeaderLabels(['Dokument / strona', 'Grupa', 'Ocena', 'Podział PDF', 'Aktualizacja'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_pair); layout.addWidget(self.table, 1)
        previews = QHBoxLayout(); layout.addLayout(previews)
        self.reference, self.crop = QLabel('Wzorzec'), QLabel('Oceniany element')
        for label in (self.reference, self.crop):
            label.setFixedHeight(130); label.setAlignment(Qt.AlignmentFlag.AlignCenter); previews.addWidget(label)
        row = QHBoxLayout(); layout.addLayout(row)
        self.assessment = QComboBox(); self.assessment.addItems([NAMES[x] for x in OUTCOMES]); row.addWidget(self.assessment)
        save = QPushButton('Zmień ocenę'); save.clicked.connect(self.change_assessment); row.addWidget(save)
        self.split = QComboBox(); self.split.addItems([NAMES[x] for x in SPLITS]); row.addWidget(self.split)
        split = QPushButton('Zmień podział całego PDF'); split.clicked.connect(self.change_split); row.addWidget(split)
        self.ready = QLabel(); self.ready.setWordWrap(True); layout.addWidget(self.ready)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); layout.addWidget(self.progress)
        self.status = QLabel(); layout.addWidget(self.status)
        row = QHBoxLayout(); layout.addLayout(row)
        self.train_button = QPushButton('Wytrenuj model'); self.train_button.clicked.connect(self.train); row.addWidget(self.train_button)
        self.cancel_button = QPushButton('Przerwij trening'); self.cancel_button.clicked.connect(self.service.cancel_training); row.addWidget(self.cancel_button)
        self.versions = QComboBox(); row.addWidget(self.versions, 1)
        self.versions.currentIndexChanged.connect(self.show_report)
        activate = QPushButton('Użyj tego modelu'); activate.clicked.connect(self.activate); row.addWidget(activate)
        self.results = QLabel(); self.results.setWordWrap(True); layout.addWidget(self.results)
        row = QHBoxLayout(); layout.addLayout(row)
        self.file_buttons = []
        for text, callback in [('Eksportuj dane', self.export_data), ('Importuj dane', self.import_data),
                               ('Eksportuj model', self.export_model), ('Importuj model', self.import_model),
                               ('Eksportuj raport', self.export_report)]:
            button = QPushButton(text); button.clicked.connect(callback); row.addWidget(button); self.file_buttons.append(button)
        self.service.changed.connect(lambda: self.refresh() if self.isVisible() else None)
        window.jobs.busy_changed.connect(lambda _: self.refresh() if self.isVisible() else None)
        self.service.progress.connect(self.progress.setValue)
        self.service.status.connect(self.status.setText)
        self.service.failed.connect(self.status.setText)
        self.service.trained.connect(lambda _: self.refresh() if self.isVisible() else None)
        self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def open_document(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Dodaj dokument do oceny', '', 'PDF (*.pdf)')
        if path:
            self.hide(); self.window.open_path(path)

    def refresh(self):
        selected = self.selected_row()
        selected_id = selected['id'] if selected else None
        self.rows = self.store.examples(False)
        self.table.blockSignals(True); self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            values = [f"{row['document_name']} / {row['page'] + 1}", row['group_name'],
                      NAMES[row['outcome']], NAMES[row['split']], __import__('time').strftime('%H:%M:%S', __import__('time').localtime(row['updated']))]
            for j, value in enumerate(values): self.table.setItem(i, j, QTableWidgetItem(value))
            if row['id'] == selected_id: self.table.selectRow(i)
        self.table.blockSignals(False)
        counts = self.store.counts()
        self.summary.setText(' · '.join(f"{NAMES[s]}: {counts[s]['correct']} poprawnych, {counts[s]['wrong']} błędnych" for s in SPLITS))
        ready, reason = self.store.readiness()
        self.ready.setText(reason + ' Każdy PDF należy w całości do jednego podziału. Zalecane: co najmniej 4 różne dokumenty.')
        self.train_button.setEnabled(ready and not self.service.busy and not self.window.busy and not self.window.loading)
        self.cancel_button.setEnabled(bool(self.service.current and self.service.current['kind']=='train'))
        for button in self.file_buttons: button.setEnabled(not self.service.busy)
        current = self.versions.currentData()
        self.reports = self.store.reports()
        self.versions.blockSignals(True); self.versions.clear()
        for report in self.reports: self.versions.addItem(report['id'], report['model_file'])
        index = self.versions.findData(current)
        if index >= 0: self.versions.setCurrentIndex(index)
        self.versions.blockSignals(False)
        self.show_pair(); self.show_report()
        if self.service.busy: self.status.setText('Zapis ocen lub trening w toku…')
        elif self.progress.value()==100:self.status.setText('Trening zakończony. Sprawdź porównanie i wybierz model do kolejnego wyszukiwania.')

    def selected_row(self):
        index = self.table.currentRow()
        return self.rows[index] if hasattr(self, 'rows') and 0 <= index < len(self.rows) else None

    def show_pair(self):
        row = self.selected_row()
        if not row: return
        reference, crop = self.store.images(row['id'])
        for label, blob in [(self.reference, reference), (self.crop, crop)]:
            pixmap = QPixmap(); pixmap.loadFromData(blob)
            label.setPixmap(pixmap.scaled(350, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.assessment.setCurrentIndex(OUTCOMES.index(row['outcome']))
        self.split.setCurrentIndex(SPLITS.index(row['split']))

    def change_assessment(self):
        if self.service.busy: return
        row = self.selected_row()
        if row:
            self.store.assess(row['id'], OUTCOMES[self.assessment.currentIndex()]); self.refresh()

    def change_split(self):
        if self.service.busy: return
        row = self.selected_row()
        if row:
            self.store.split_document(row['document'], SPLITS[self.split.currentIndex()]); self.refresh()

    def train(self):
        self.progress.setValue(0); self.service.submit({'kind': 'train'})

    def selected_model(self):
        filename = self.versions.currentData()
        return self.store.directory / 'models' / filename if filename else None

    def show_report(self):
        path = self.selected_model()
        if not path:
            self.results.setText('Model nie został jeszcze wytrenowany. Szybkie wyszukiwanie działa; zbieraj własne oceny.')
            return
        report = next((r for r in self.reports if r['model_file'] == path.name), None)
        if not report: return
        labels = {'classic': 'Geometria obrazu', 'model': 'Mały model', 'combined': 'Suma propozycji'}
        text = 'PORÓWNANIE OCENIONYCH WYCINKÓW — nie kompletność całego rysunku\n'
        for key, metric in report['comparisons'].items():
            text += (f"{labels[key]}: poprawnie {metric['tp']}, pominięte {metric['fn']}, fałszywe {metric['fp']}; "
                     f"precyzja {metric['precision']:.1%}, wykrycie poprawnych par {metric['recall']:.1%}\n")
        active = Path(self.window.settings_store.text('learning/active_model', '')).name
        text += ('Aktywny model: ' + active if active else 'Brak aktywnego modelu.')
        text += ' Wynik modelu pomaga wskazywać przypadki do kontroli; oznaczenie urządzenia nadal musi się zgadzać.'
        self.results.setText(text)

    def activate(self):
        if self.service.busy: return
        path = self.selected_model()
        if path:
            TinyPairModel.load(path)
            self.window.settings_store.set('learning/active_model', str(path))
            self.window.settings_store.set('detection/engine_mode_078', 'learned')
            self.window.update_performance(); self.show_report()
            self.status.setText('Wybrano model. Kolejne wyszukiwanie użyje tej wersji. Poprzednie modele pozostają dostępne.')

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Eksport danych', 'ElectroCount-przyklady.zip', 'ZIP (*.zip)')
        if path: self.store.export_data(path)

    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import danych', '', 'ZIP (*.zip)')
        if path:
            try:
                count = self.store.import_data(path); self.refresh(); self.status.setText(f'Wczytano {count} ocen.')
            except Exception as exc: QMessageBox.warning(self, 'Import', str(exc))

    def export_model(self):
        source = self.selected_model()
        if not source: return
        path, _ = QFileDialog.getSaveFileName(self, 'Eksport modelu', source.name, 'Model (*.ecmodel)')
        if path and Path(path).resolve() != source.resolve(): shutil.copyfile(source, path)

    def import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import modelu', '', 'Model (*.ecmodel)')
        if not path: return
        try:
            model = TinyPairModel.load(path)
            report = model.metadata['report']
            # Use a digest filename, never an incoming archive/path identifier.
            import hashlib
            name = 'import-' + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16] + '.ecmodel'
            target = self.store.directory / 'models' / name
            model.save(target); report['model_file'] = name
            self.store.save_report(report); self.refresh()
        except Exception as exc: QMessageBox.warning(self, 'Model', str(exc))

    def export_report(self):
        path = self.selected_model()
        if not path: return
        report = next(r for r in self.reports if r['model_file'] == path.name)
        filename, _ = QFileDialog.getSaveFileName(self, 'Eksport raportu', 'Raport-modelu.json', 'JSON (*.json)')
        if filename: Path(filename).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
