"""Four fresh, same-quality tile timings: old worker vs persistent viewer.

Run with QT_QPA_PLATFORM=offscreen and PYTHONPATH=src. Optional input PDF is
never stored in the repository. Default drawing is freshly generated in /tmp.
"""
import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from reportlab.pdfgen import canvas
from electrocount.jobs import JobManager
from electrocount.render_service import RenderService


def wait(app, predicate):
    started = time.monotonic()
    while not predicate():
        app.processEvents()
        if time.monotonic() - started > 30:
            raise TimeoutError('Renderer did not finish')
        time.sleep(.005)


def synthetic(path):
    c = canvas.Canvas(str(path), pagesize=(1600.25, 1000.75))
    c.setStrokeColorRGB(1, 0, .7)
    c.setLineWidth(.3)
    for y in range(20, 980, 17):
        for x in range(20, 1580, 23):
            c.circle(x, y, 3)
            c.line(x - 4, y, x + 4, y)
    c.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', nargs='?')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='electrocount-render-') as folder:
        path = Path(args.pdf).resolve() if args.pdf else Path(folder) / 'synthetic.pdf'
        if not args.pdf:
            synthetic(path)
        old, new = JobManager(), RenderService()
        errors, samples = [], []
        old.failed.connect(errors.append)
        new.failed.connect(errors.append)
        try:
            for i, rect in enumerate(([0, 0, 256, 256], [256, 0, 256, 256],
                                       [512, 0, 256, 256], [256, 256, 256, 256])):
                request = {'path': str(path), 'page': 0, 'scale': 2., 'rect': rect}
                timings = {}
                for name, service in [('old', old), ('new', new)]:
                    received = []
                    started = time.perf_counter()
                    callback = lambda result: received.append(result)
                    if name == 'old':
                        service.submit({'kind': 'render', **request}, callback)
                    else:
                        service.set_tiles([(request, callback, ('tile', i))])
                    wait(app, lambda: bool(received) or bool(errors))
                    if errors:
                        raise RuntimeError(errors[-1])
                    timings[name + '_ms'] = round((time.perf_counter() - started) * 1000, 2)
                started = time.perf_counter()
                assert new.get(('tile', i)) is not None
                timings['cache_ms'] = round((time.perf_counter() - started) * 1000, 3)
                samples.append(timings)
            print(json.dumps({'source': 'user PDF' if args.pdf else 'fresh synthetic drawing',
                              'tile_pixels': [512, 512], 'samples': samples,
                              'median_old_ms': statistics.median(r['old_ms'] for r in samples),
                              'median_new_ms': statistics.median(r['new_ms'] for r in samples),
                              'viewer_process_starts': new.metrics['starts']}, indent=2))
        finally:
            old.close()
            new.close()


if __name__ == '__main__':
    main()
