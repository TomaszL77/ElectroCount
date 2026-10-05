"""Viewer-only process, latest-viewport queue, and bounded shared pixmap cache."""
import json
import logging
import sys
from collections import OrderedDict, deque
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTemporaryDir, Signal
from PySide6.QtGui import QPixmap


class RenderService(QObject):
    failed = Signal(str)

    def __init__(self, parent=None, cache_limit=96 * 1024 * 1024):
        super().__init__(parent)
        self.temp = QTemporaryDir()
        self.process = None
        self.buffer = b''
        self.current = None
        self.tiles = deque()
        self.background = OrderedDict()
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.cache_limit = cache_limit
        self.closed = False
        self.metrics = {'renders': 0, 'cache_hits': 0, 'seconds': 0., 'starts': 0}
        self.start()

    def start(self):
        if self.closed or self.process:
            return
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONPATH', str(Path(__file__).parent.parent))
        process.setProcessEnvironment(env)
        process.setProgram(sys.executable)
        process.setArguments(['-m', 'electrocount.render_worker'])
        process.readyReadStandardOutput.connect(self.read)
        process.started.connect(self.pump)
        process.finished.connect(lambda *_: self.stopped(process))
        process.errorOccurred.connect(lambda error: self.stopped(process)
            if error == QProcess.ProcessError.FailedToStart else None)
        self.process = process
        self.metrics['starts'] += 1
        process.start()

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        self.metrics['cache_hits'] += 1
        return self.cache[key][0]

    def submit(self, request, callback, key):
        """Small previews/thumbnails run after visible tiles and before prefetch."""
        self.background[key] = (request, callback, key)
        self.pump()

    def set_tiles(self, entries):
        # Replace stale queued work on every viewport change, never interrupt an
        # in-flight tile: its result can still be cached for a return pan.
        active_key = self.current[2] if self.current else None
        self.tiles = deque(e for e in entries if e[2] != active_key)
        self.pump()

    def clear(self):
        self.tiles.clear()
        self.background.clear()
        self.cache.clear()
        self.cache_bytes = 0
        # Invalidate the active callback, but finish rendering outside the GUI.
        if self.current:
            request, _, key = self.current
            self.current = (request, None, key)

    def pump(self):
        if self.closed or self.current:
            return
        if not self.tiles and not self.background:
            return
        if not self.process:
            self.start()
        if self.process.state() != QProcess.ProcessState.Running:
            return
        if self.tiles and (self.tiles[0][0].get('visible', True) or not self.background):
            request, callback, key = self.tiles.popleft()
        else:
            _, (request, callback, key) = self.background.popitem(last=False)
        request = dict(request)
        request['id'] = uuid4().hex
        request['output'] = str(Path(self.temp.path()) / (request['id'] + '.png'))
        self.current = (request, callback, key)
        self.process.write((json.dumps(request, ensure_ascii=True) + '\n').encode())

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                outcome = json.loads(line)
            except ValueError:
                logging.warning('Invalid viewer renderer response')
                continue
            if not self.current or self.current[0]['id'] != outcome.get('id'):
                continue
            request, callback, key = self.current
            self.current = None
            try:
                if callback and 'error' not in outcome:
                    pixmap = QPixmap(outcome['output'])
                    if pixmap.isNull():
                        raise ValueError('Nie udało się wczytać renderu strony.')
                    self.metrics['renders'] += 1
                    self.metrics['seconds'] += outcome['seconds']
                    if request.get('rect'):
                        size = pixmap.width() * pixmap.height() * 4
                        previous = self.cache.pop(key, None)
                        if previous:
                            self.cache_bytes -= previous[1]
                        self.cache[key] = (pixmap, size)
                        self.cache_bytes += size
                        while self.cache_bytes > self.cache_limit and self.cache:
                            _, (_, old_size) = self.cache.popitem(last=False)
                            self.cache_bytes -= old_size
                    callback(pixmap)
                elif callback:
                    self.failed.emit(outcome['error'])
            except Exception as exc:
                logging.exception('Applying viewer render')
                self.failed.emit(str(exc))
            finally:
                Path(request['output']).unlink(missing_ok=True)
            self.pump()

    def stopped(self, process):
        if self.process is not process:
            return
        self.process = None
        self.buffer = b''
        if self.current:
            Path(self.current[0]['output']).unlink(missing_ok=True)
        self.current = None
        self.tiles.clear()
        self.background.clear()
        process.deleteLater()
        if not self.closed:
            self.failed.emit('Proces renderowania został przerwany. Przesuń widok, aby ponowić.')

    def close(self):
        self.closed = True
        self.clear()
        if self.process:
            self.process.kill()
            self.process.waitForFinished(3000)
