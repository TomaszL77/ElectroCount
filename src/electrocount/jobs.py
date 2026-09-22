"""A bounded render queue and an independent cancellable analysis process."""
import json
import logging
import sys
from collections import deque
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTemporaryDir, Signal


class JobManager(QObject):
    foreground_started = Signal(str)
    foreground_finished = Signal(str)
    progress = Signal(int)
    status = Signal(str)
    busy_changed = Signal(bool)
    failed = Signal(str)
    performance_fallback = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp = QTemporaryDir()
        self.queue = deque()
        self.performance_plan = {}
        self.render_process = None
        self.analysis_process = None

    def submit(self, request, callback, analysis=False):
        if analysis:
            if self.analysis_process:
                return
            self.busy_changed.emit(True)
            self.analysis_process = self.start(request, callback, True)
        else:
            self.queue.append((request, callback))
            self.pump()

    def pump(self):
        if not self.render_process and self.queue:
            request, callback = self.queue.popleft()
            self.render_process = self.start(request, callback, False)

    def start(self, request, callback, analysis):
        token = uuid4().hex
        request = dict(request)
        request.setdefault("performance",self.performance_plan)
        request["cache_dir"] = str(Path(self.temp.path())/"pdf-cache")
        request["output"] = str(Path(self.temp.path()) / (token + ".png"))
        filename = Path(self.temp.path()) / (token + ".json")
        filename.write_text(json.dumps(request), encoding="utf-8")
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(Path(__file__).parent.parent))
        process.setProcessEnvironment(env)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "electrocount.worker", str(filename)])
        process.buffer = b""
        process.outcome = None
        process.cancelled = False
        process.handled = False
        foreground = request["kind"] in ("import","template","batch_match","match","self_test")

        def read():
            process.buffer += bytes(process.readAllStandardOutput())
            while b"\n" in process.buffer:
                line, process.buffer = process.buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                    if "performance_fallback" in message:
                        self.performance_fallback.emit(message["performance_fallback"])
                    if "status" in message:
                        self.status.emit(message["status"])
                    if "progress" in message:
                        self.progress.emit(message["progress"])
                    elif "result" in message or "error" in message:
                        process.outcome = message
                except (ValueError, UnicodeError):
                    logging.warning("Invalid worker response")

        def finished(code, status):
            if process.handled:
                return
            process.handled = True
            read()
            outcome = process.outcome
            if analysis:
                self.analysis_process = None
                self.busy_changed.emit(False)
            else:
                self.render_process = None
            if foreground:
                self.foreground_finished.emit(request["kind"])
            if not process.cancelled:
                if outcome and "result" in outcome:
                    logging.info("%s completed in %.2fs; results=%s", request["kind"],
                                 outcome["seconds"], len(outcome["result"]))
                    try:
                        callback(outcome["result"])
                    except Exception as exc:
                        logging.exception("Applying worker result")
                        self.failed.emit(str(exc))
                else:
                    error = (outcome or {}).get("error", "Proces roboczy nie zakończył zadania.")
                    logging.error("%s\n%s", error, (outcome or {}).get("trace", bytes(process.readAllStandardError())))
                    self.failed.emit(error)
            filename.unlink(missing_ok=True)
            # The receiver creates an independent QPixmap. No persistent PNG cache.
            Path(request["output"]).unlink(missing_ok=True)
            process.deleteLater()
            self.pump()

        process.readyReadStandardOutput.connect(read)
        process.finished.connect(finished)
        process.errorOccurred.connect(lambda error: finished(-1, QProcess.ExitStatus.CrashExit) if error == QProcess.ProcessError.FailedToStart else None)
        if foreground:
            self.foreground_started.emit(request["kind"])
        process.start()
        return process

    def cancel_analysis(self):
        if self.analysis_process:
            self.analysis_process.cancelled = True
            self.analysis_process.kill()

    def clear_render_queue(self):
        self.queue.clear()
        if self.render_process:
            self.render_process.cancelled = True
            self.render_process.kill()

    def close(self):
        self.queue.clear()
        for process in (self.render_process, self.analysis_process):
            if process:
                process.cancelled = True
                process.kill()
                process.waitForFinished(3000)

