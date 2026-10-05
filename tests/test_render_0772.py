"""Small rendering regression suite; no neural inference or saved detections."""
import time
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from PySide6.QtGui import QTransform
from electrocount.viewport_tiles import viewport_tiles
from electrocount.pdf_engine import PdfiumEngine
from electrocount.render_worker import ViewerRenderer
from electrocount.render_service import RenderService
from electrocount.main_window import MainWindow
from electrocount.domain import Document, Project


def wait(app, predicate, timeout=15):
    started = time.monotonic()
    while not predicate():
        app.processEvents()
        if time.monotonic() - started > timeout:
            raise AssertionError('Viewer worker timed out')
        time.sleep(.005)
    app.processEvents()


def make_drawing(path):
    c = canvas.Canvas(str(path), pagesize=(1600.25, 1000.75))
    for page in range(2):
        c.setStrokeColorRGB(1, 0, .7) if page == 0 else c.setStrokeColorRGB(0, .3, 1)
        c.setLineWidth(.3)
        for y in range(20, 980, 17):
            for x in range(20, 1580, 23):
                c.circle(x, y, 3)
                c.line(x - 4, y, x + 4, y)
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica', 5)
        for y in range(30, 980, 80):
            c.drawString(520, y, 'AW4 / 7 / 8 / 9 / 10')
        c.showPage()
    c.save()
    return str(path)


def test_grid_preserves_keys_pan_quality_hidpi_and_high_zoom():
    for zoom, dpr in [(1., 1.), (2.1, 2.), (12., 2.)]:
        before = viewport_tiles(3000, 2000, [600, 500, 400, 250], zoom, dpr)
        after = viewport_tiles(3000, 2000, [620, 510, 400, 250], zoom, dpr)
        assert before[0].visible
        assert all(t.scale >= zoom * dpr for t in before)
        shared = {t.key for t in before} & {t.key for t in after}
        assert shared
        assert {t.key: t.rect for t in before if t.key in shared} == {
            t.key: t.rect for t in after if t.key in shared}


def test_fractional_grid_matches_full_render_pixels_and_retains_pages(tmp_path):
    path = make_drawing(tmp_path / 'drawing.pdf')
    engine = PdfiumEngine()
    renderer = ViewerRenderer()
    try:
        for zoom in (1., 2.1):
            plan = viewport_tiles(1600.25, 1000.75, [490, 250, 550, 400], zoom)
            scale = plan[0].scale
            full = engine.render(path, 0, scale)
            for tile in plan:
                output = tmp_path / 'tile.png'
                renderer.render({'path': path, 'page': 0, 'scale': scale,
                                 'rect': tile.rect, 'output': str(output)})
                with Image.open(output) as image:
                    actual = np.asarray(image.convert('RGB'))
                left, top = round(tile.rect[0] * scale), round(tile.rect[1] * scale)
                expected = full[top:top + actual.shape[0], left:left + actual.shape[1]]
                # PDFium may differ by 2/255 in anti-aliasing after translating
                # the page origin. Geometry and original colors must agree.
                assert actual.shape == expected.shape
                difference = np.abs(actual.astype(int) - expected.astype(int))
                assert difference.max() <= 2 and difference.mean() < .01
            assert len(renderer.pages) == 1
        renderer.render({'path': path, 'page': 1, 'scale': 1.,
                         'rect': [0, 0, 100, 100], 'output': str(output)})
        assert len(renderer.pages) == 2
    finally:
        renderer.close()


def test_continuous_pan_schedules_frames_and_keeps_sharp_tiles(app):
    from electrocount.drawing_view import DrawingView
    from PySide6.QtGui import QPixmap
    view = DrawingView()
    view.resize(800, 600)
    view.set_page(2000, 2000)
    view.show()
    app.processEvents()
    calls = []
    view.viewport_changed.connect(lambda: calls.append(True))
    try:
        pixmap = QPixmap(513, 513)
        pixmap.fill()
        view.set_tile((1, 0, 1., 0, 0), pixmap, [0, 0, 513, 513], 1.)
        item = next(iter(view.tiles.values()))[0]
        view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + 20)
        assert next(iter(view.tiles.values()))[0] is item
        started = time.monotonic()
        while time.monotonic() - started < .15:
            view.schedule_detail()
            app.processEvents()
            time.sleep(.003)
        assert len(calls) >= 3  # Old 220ms debounce emits nothing during motion.
        view.set_page(2000, 2000)
        assert not view.tiles and view.tile_bytes == 0
    finally:
        view.close()


def test_raster_rotated_page_keeps_colors_and_coordinates(tmp_path):
    from reportlab.lib.utils import ImageReader
    from PIL import ImageDraw
    image = Image.new('RGB', (600, 800), 'white')
    pen = ImageDraw.Draw(image)
    pen.rectangle((110, 240, 490, 640), fill=(223, 17, 181))
    pen.line((0, 0, 590, 790), fill='black', width=3)
    path = tmp_path / 'scan-rotated.pdf'
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    c.setPageRotation(90)
    c.drawImage(ImageReader(image), 0, 0, 800, 600)
    c.save()
    engine, renderer = PdfiumEngine(), ViewerRenderer()
    try:
        page = engine.inspect(str(path))[0]
        full = engine.render(str(path), 0, 2.)
        plan = viewport_tiles(page['width'], page['height'],
                              [0, 0, page['width'], page['height']], 2.)
        for tile in plan:
            output = tmp_path / 'raster-tile.png'
            renderer.render({'path': str(path), 'page': 0, 'scale': 2.,
                             'rect': tile.rect, 'output': str(output)})
            with Image.open(output) as part:
                actual = np.asarray(part.convert('RGB'))
            x, y = round(tile.rect[0] * 2), round(tile.rect[1] * 2)
            assert np.array_equal(actual, full[y:y + actual.shape[0], x:x + actual.shape[1]])
        assert np.any(np.all(full == [223, 17, 181], axis=2))
    finally:
        renderer.close()


def test_service_reuses_process_cancels_stale_queue_cache_and_cleanup(app, tmp_path):
    path = make_drawing(tmp_path / 'service.pdf')
    service = RenderService(cache_limit=2 * 1024 * 1024)
    errors, received = [], []
    service.failed.connect(errors.append)
    request = {'path': path, 'page': 0, 'scale': 1., 'rect': [0, 0, 512, 512]}
    try:
        wait(app, lambda: service.process.state() == service.process.ProcessState.Running)
        pid = service.process.processId()
        service.set_tiles([(request, lambda p: received.append('first'), ('first',)),
                           (request, lambda p: received.append('stale'), ('stale',))])
        service.set_tiles([(request, lambda p: received.append('latest'), ('latest',))])
        wait(app, lambda: len(received) == 2)
        assert received == ['first', 'latest']
        assert service.process.processId() == pid and service.metrics['starts'] == 1
        assert service.get(('latest',)) is not None
        assert service.cache_bytes <= service.cache_limit
        service.set_tiles([(request, lambda p: received.append('discarded'), ('discarded',))])
        service.clear()
        wait(app, lambda: service.current is None)
        assert received == ['first', 'latest'] and not service.cache
        assert not list(__import__('pathlib').Path(service.temp.path()).glob('*.png'))
        assert not errors
    finally:
        service.close()
    assert service.process is None


def test_window_pan_reuses_tiles_page_changes_stale_callback_and_high_zoom(app, tmp_path, monkeypatch):
    path = make_drawing(tmp_path / 'window.pdf')
    project = Project()
    project.append_document(Document(path, 'drawing'), PdfiumEngine().inspect(path))
    window = MainWindow()
    errors = []
    window.renderer.failed.disconnect()
    window.renderer.failed.connect(errors.append)
    window.show()
    try:
        window.replace_project(project, None)
        window.view.setTransform(QTransform.fromScale(1., 1.))
        window.view.centerOn(800, 500)
        window.render_detail()
        wait(app, lambda: window.view.preview is not None and not window.renderer.tiles
             and window.renderer.current is None and not window.renderer.background)
        first_count = window.renderer.metrics['renders']
        window.refresh_view_overlays()
        overlay_calls = []
        monkeypatch.setattr(window.view, 'draw_detections', lambda *args: overlay_calls.append(True))
        window.view.centerOn(830, 500)
        window.render_detail()
        assert not window.renderer.tiles and window.renderer.current is None
        assert window.renderer.metrics['renders'] == first_count
        window.refresh_view_overlays()
        assert not overlay_calls
        # Return to the same page while its earlier request is in flight.
        window.change_page(1)
        window.render_detail()
        window.change_page(0)
        window.render_detail()
        wait(app, lambda: window.view.preview is not None and not window.renderer.tiles
             and window.renderer.current is None and not window.renderer.background)
        assert all(k[1] == 0 for k in window.view.tiles)
        window.view.setTransform(QTransform.fromScale(8., 8.))
        window.render_detail()
        wait(app, lambda: not window.renderer.tiles and window.renderer.current is None)
        assert any(k[2] >= 8 for k in window.view.tiles)
        assert not errors
    finally:
        window.dirty = False
        window.close()
