"""Queue explicit feedback and run CPU training without blocking interactions."""
from .json_values import dumps as json_dumps
import json
import logging
import sys
from collections import deque
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


class LearningService(QObject):
    changed = Signal()
    failed = Signal(str)
    progress = Signal(int)
    status = Signal(str)
    trained = Signal(dict)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.directory = str(directory)
        self.process = None
        self.queue = deque()
        self.current = None
        self.buffer = b''
        self.closed = False
        self.cancelling = False

    @property
    def busy(self):
        return bool(self.current or self.queue)

    def submit(self, request):
        if self.closed:
            return
        self.queue.append({**request, 'directory': self.directory, 'id': uuid4().hex})
        self.pump()
        self.changed.emit()

    def pump(self):
        if self.current or self.closed or not self.queue:
            return
        if not self.process:
            process = QProcess(self)
            env = QProcessEnvironment.systemEnvironment()
            env.insert('PYTHONPATH', str(Path(__file__).parent.parent))
            for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
                env.insert(key, '1')
            process.setProcessEnvironment(env)
            process.setProgram(sys.executable)
            process.setArguments(['-m', 'electrocount.learning_worker'])
            process.started.connect(self.pump)
            process.readyReadStandardOutput.connect(self.read)
            process.finished.connect(lambda *_: self.stopped(process))
            process.errorOccurred.connect(lambda error: self.stopped(process)
                if error == QProcess.ProcessError.FailedToStart else None)
            self.process = process
            process.start()
            return
        if self.process.state() != QProcess.ProcessState.Running:
            return
        self.current = self.queue.popleft()
        self.process.write((json_dumps(self.current, ensure_ascii=True) + '\n').encode())
        self.changed.emit()

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                message = json.loads(line)
            except (ValueError, UnicodeError):
                logging.warning('Invalid learning worker response')
                continue
            if 'progress' in message: self.progress.emit(message['progress'])
            if 'status' in message: self.status.emit(message['status'])
            if not self.current or message.get('id') != self.current['id']:
                continue
            kind = self.current['kind']; self.current = None
            if 'error' in message:
                self.failed.emit(message['error'])
            elif kind == 'train':
                self.trained.emit(message['result'])
            self.pump(); self.changed.emit()

    def stopped(self, process):
        if self.process is not process:
            return
        lost = self.busy
        cancelled = self.cancelling
        self.cancelling = False
        self.process = None; self.current = None; self.buffer = b''
        if not cancelled: self.queue.clear()
        process.deleteLater()
        if cancelled and not self.closed:
            self.status.emit('Trening przerwany. Zapisane dane i poprzedni model pozostały dostępne.')
            self.pump()
        elif lost and not self.closed:
            self.failed.emit('Przerwano zapis ocen lub trening. Zapisane przykłady pozostały w bazie; ponów ostatnią ocenę.')
        self.changed.emit()

    def cancel_training(self):
        if self.current and self.current['kind'] == 'train' and self.process:
            self.cancelling = True
            self.current = None
            self.process.kill()

    def close(self):
        self.closed = True
        self.queue.clear()
        if self.process:
            self.process.kill()
            self.process.waitForFinished(3000)
