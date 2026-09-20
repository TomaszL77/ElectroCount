"""UI-owned resource policy and independent, time-bounded hardware subprocess."""
import json
import logging
import sys
from pathlib import Path
from PySide6.QtCore import QObject,QProcess,QProcessEnvironment,QTimer,Signal
from .performance import PerformanceMode,execution_plan


class PerformanceController(QObject):
    changed = Signal()
    notice = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.report = {}
        self.ceiling = None
        self.process = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.state_dir = Path(settings.store.fileName()).parent
        self.state = "Oczekiwanie na profilowanie"
        try:
            self.mode = PerformanceMode(settings.text("performance/mode","AUTO"))
        except ValueError:
            self.mode = PerformanceMode.AUTO
        self.plan = execution_plan(self.mode,self.report)

    def set_mode(self, mode):
        self.mode = PerformanceMode(mode)
        self.ceiling = None
        self.settings.set("performance/mode",self.mode.value)
        self._replan()

    def _replan(self):
        self.plan = execution_plan(self.mode,self.report,self.ceiling)
        self.changed.emit()

    def apply_fallback(self, plan):
        self.ceiling = plan["effective"]
        self._replan()
        self.notice.emit(f"Profil AI został zmniejszony do {self.plan.effective.title()} ze względu na dostępne zasoby.")

    def start(self, force=False):
        if self.process:
            return
        self.state = "Profilowanie sprzętu w tle…"
        self.changed.emit()
        request = self.state_dir/"hardware-request.json"
        try:
            request.write_text(json.dumps({"cache_path":str(self.state_dir/"hardware-profile.json"),"force":force}),encoding="utf-8")
        except OSError as exc:
            self.state = "Nie udało się zapisać żądania profilowania"
            self.report = {"error":str(exc)}
            self._replan()
            return
        process = QProcess(self)
        self.process = process
        self._timed_out = False
        process.setProgram(sys.executable)
        process.setArguments(["-m","electrocount.hardware_profiler",str(request)])
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH",str(Path(__file__).parent.parent))
        process.setProcessEnvironment(env)
        process.finished.connect(lambda code,status:self._finished(process,code))
        process.errorOccurred.connect(lambda error:self._finished(process,-1) if error==QProcess.ProcessError.FailedToStart else None)
        self.timer.start(15000)
        process.start()

    def _finished(self, process, code):
        if process is not self.process:
            return
        self.timer.stop()
        self.process = None
        try:
            if self._timed_out:
                raise ValueError("Przekroczono limit 15 s. Zachowano profil Eco.")
            if code != 0:
                raise ValueError("Pomiar sprzętu zakończył się błędem. Zachowano profil Eco.")
            report = json.loads(bytes(process.readAllStandardOutput()))
            if not isinstance(report,dict) or "hardware" not in report or "benchmarks" not in report:
                raise ValueError("Niekompletny pomiar sprzętu. Zachowano profil Eco.")
            self.report = report
            self.state = "Pomiar z pamięci podręcznej" if report.get("cached") else "Pomiar zakończony"
        except (ValueError,TypeError) as exc:
            logging.warning("Hardware profile unavailable: %s",exc)
            self.report = {"error":str(exc)}
            self.state = str(exc)
            self.ceiling = "ECO"
        process.deleteLater()
        self._replan()

    def _timeout(self):
        if self.process:
            self._timed_out = True
            self.process.kill()

    def close(self):
        self.timer.stop()
        if self.process:
            process,self.process = self.process,None
            process.kill()
            process.waitForFinished(1000)
            process.deleteLater()
