"""Persistent, isolated PDFium viewer process. No OCR/model/detector imports."""
from .json_values import dumps as json_dumps
import json
import math
import sys
import time
from collections import OrderedDict
from pathlib import Path
import pypdfium2 as pdfium


class ViewerRenderer:
    def __init__(self):
        self.pages = OrderedDict()

    def render(self, request):
        source = Path(request['path'])
        stat = source.stat()
        key = (str(source.resolve()), stat.st_size, stat.st_mtime_ns, request['page'])
        if key not in self.pages:
            doc = pdfium.PdfDocument(str(source))
            try:
                page = doc[request['page']]
            except Exception:
                doc.close()
                raise
            self.pages[key] = (doc, page)
            while len(self.pages) > 3:
                _, (old_doc, old_page) = self.pages.popitem(last=False)
                old_page.close()
                old_doc.close()
        self.pages.move_to_end(key)
        _, page = self.pages[key]
        width, height = page.get_size()
        scale = request['scale']
        crop = (0, 0, 0, 0)
        inner_crop = None
        rect = request.get('rect')
        if rect:
            x, y, w, h = rect
            total_w, total_h = math.ceil(width * scale), math.ceil(height * scale)
            left, top = round(x * scale), round(y * scale)
            right = total_w if x + w >= width - 1e-9 else round((x + w) * scale)
            bottom = total_h if y + h >= height - 1e-9 else round((y + h) * scale)
            # PDFium resamples scans differently on a bitmap boundary. Render a
            # four-pixel gutter, then discard it so tile edges match the image.
            outer_left, outer_top = max(0, left - 4), max(0, top - 4)
            outer_right, outer_bottom = min(total_w, right + 4), min(total_h, bottom + 4)
            inner_crop = (left - outer_left, top - outer_top,
                          right - outer_left, bottom - outer_top)
            # render() uses ceil(crop*scale). A small epsilon prevents floating
            # point roundoff from moving an integral tile origin by one pixel.
            crop = tuple(max(0, value - 1e-7) / scale for value in
                         (outer_left, total_h - outer_bottom,
                          total_w - outer_right, outer_top))
        # PDFium rounds crop distances independently. Supply integer pixel crops
        # explicitly to avoid off-by-one origins at fractional page dimensions.
        if math.ceil(width * scale) * math.ceil(height * scale) <= 0:
            raise ValueError('Nieprawidłowy rozmiar strony.')
        bitmap = page.render(scale=scale, crop=crop, rev_byteorder=True)
        try:
            image = bitmap.to_pil().convert('RGB')
            if inner_crop:
                cropped = image.crop(inner_crop)
                image.close()
                image = cropped
            image.save(request['output'], 'PNG', compress_level=1)
            image.close()
        finally:
            bitmap.close()
        return request['output']

    def close(self):
        for doc, page in self.pages.values():
            page.close()
            doc.close()
        self.pages.clear()


def main():
    renderer = ViewerRenderer()
    try:
        for line in sys.stdin:
            request = json.loads(line)
            started = time.monotonic()
            try:
                message = {'id': request['id'], 'output': renderer.render(request),
                           'seconds': time.monotonic() - started}
            except Exception as exc:
                message = {'id': request['id'], 'error': str(exc)}
            print(json_dumps(message, ensure_ascii=True), flush=True)
    finally:
        renderer.close()


if __name__ == '__main__':
    main()
