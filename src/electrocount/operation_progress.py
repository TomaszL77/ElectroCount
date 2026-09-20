"""Prominent foreground-operation status, independent of the page zoom and sidebars."""
from PySide6.QtCore import QElapsedTimer,QTimer,Signal
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel,QProgressBar,QPushButton,QSizePolicy


class OperationProgress(QFrame):
    cancel_requested = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('operationProgress')
        self.setStyleSheet('''
            QFrame#operationProgress { background: #203448; border: 2px solid #f2be58; border-radius: 7px; }
            QLabel { color: #f3f7fc; border: none; font-size: 13px; }
            QLabel#operationTitle { font-size: 14px; font-weight: 600; color: #ffda86; }
            QProgressBar { background: #101c29; border: 1px solid #57748e; border-radius: 4px;
                           color: white; font-size: 13px; font-weight: 700; min-height: 15px; }
            QProgressBar::chunk { background: #288c88; border-radius: 3px; }
            QPushButton { background: #f2be58; color: #172232; border-radius: 5px; padding: 4px 12px; font-weight: 600; }
            QPushButton:disabled { background: #566675; color: #d5dee7; }
        ''')
        layout=QVBoxLayout(self);layout.setContentsMargins(10,5,10,6);layout.setSpacing(3)
        row=QHBoxLayout()
        self.title=QLabel();self.title.setObjectName('operationTitle');row.addWidget(self.title)
        self.stage=QLabel();self.stage.setMinimumWidth(0);self.stage.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        row.addSpacing(12);row.addWidget(self.stage,1)
        self.elapsed=QLabel();row.addWidget(self.elapsed)
        self.cancel=QPushButton('Anuluj analizę');self.cancel.clicked.connect(self._cancel);row.addWidget(self.cancel)
        layout.addLayout(row)
        self.bar=QProgressBar();self.bar.setTextVisible(True);self.bar.setFormat('%p%');layout.addWidget(self.bar)
        self.clock=QElapsedTimer();self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self._tick)
        self.active=False;self.kind='';self.last_progress=0
        self.hide()

    def start(self,kind):
        self.active=True;self.kind=kind;self.last_progress=0
        self.title.setText({'import':'Otwieranie dokumentów','template':'Przygotowanie wzorca'}.get(kind,'Wyszukiwanie elementów'))
        self.stage.setText('Uruchamianie analizy…')
        self.bar.setRange(0,0)
        self.cancel.setVisible(kind in ('match','batch_match'));self.cancel.setEnabled(True);self.cancel.setText('Anuluj analizę')
        self.clock.start();self._tick();self.timer.start();self.show()

    def set_progress(self,value):
        if not self.active:return
        self.last_progress=max(self.last_progress,max(0,min(100,int(value))))
        self.bar.setRange(0,100);self.bar.setValue(self.last_progress)

    def set_stage(self,text):
        if self.active:
            self.stage.setText(text);self.stage.setToolTip(text)

    def finish(self,kind):
        if self.kind!=kind:return
        self.active=False;self.timer.stop();self.hide()

    def _tick(self):
        seconds=max(0,self.clock.elapsed()//1000)
        self.elapsed.setText(f'Czas: {seconds//60:02}:{seconds%60:02}')

    def _cancel(self):
        self.cancel.setEnabled(False);self.cancel.setText('Anulowanie…');self.stage.setText('Kończenie procesu — dotychczasowe wyniki pozostają bez zmian.')
        self.cancel_requested.emit()
