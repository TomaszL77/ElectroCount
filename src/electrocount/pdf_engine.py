import math
import ctypes
import numpy as np
from .text_engine import PdfTextItem, normalize_text
import pypdfium2 as pdfium


class PdfiumEngine:
    def __init__(self, vector_segment_limit=40000):
        self.vector_segment_limit = vector_segment_limit
        self.cache_namespace = f"pdfium-v6-local-vector-limit-{vector_segment_limit}"

    def inspect(self, path):
        with pdfium.PdfDocument(path) as doc:
            pages = []
            for index in range(len(doc)):
                page = doc[index]
                width, height = page.get_size()
                pages.append({"name": f"Strona {index+1:02}", "width": width, "height": height})
                page.close()
            return pages

    def render(self, path, page_index, scale, rect=None):
        with pdfium.PdfDocument(path) as doc:
            page = doc[page_index]
            width, height = page.get_size()
            crop = (0, 0, 0, 0)
            if rect is not None:
                x, y, w, h = rect
                crop = (x, height-y-h, width-x-w, y)
                crop = tuple(max(0, v) for v in crop)
            bitmap = page.render(scale=scale, crop=crop, rev_byteorder=True)
            array = np.array(bitmap.to_numpy(), copy=True)
            bitmap.close()
            page.close()
            return array[:, :, :3]

    def extract_text(self, path, page_index):
        """Extract native glyphs and word boxes. PDFium performs crop/rotation mapping."""
        with pdfium.PdfDocument(path) as doc:
            page = doc[page_index]
            textpage = page.get_textpage()
            width, height = page.get_size()
            precision = 1000
            converter = pdfium.PdfPosConv(page, (0, 0, round(width*precision), round(height*precision), 0))
            items, chars, boxes = [], [], []

            def flush():
                if not chars:
                    return
                text = "".join(chars)
                left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
                right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
                items.append(PdfTextItem(text, normalize_text(text), page_index,
                    [left, top, right-left, bottom-top], [(left+right)/2, (top+bottom)/2]))
                chars.clear()
                boxes.clear()

            previous_object = None
            for index in range(textpage.count_chars()):
                text_object = pdfium.raw.FPDFText_GetTextObject(textpage,index)
                object_id = ctypes.cast(text_object,ctypes.c_void_p).value
                if previous_object is not None and object_id != previous_object:
                    flush()
                previous_object = object_id
                code = pdfium.raw.FPDFText_GetUnicode(textpage, index)
                char = chr(code) if code else ""
                if not char or char.isspace() or not char.isprintable():
                    flush()
                    continue
                left, bottom, right, top = textpage.get_charbox(index)
                points = [converter.to_bitmap(x, y) for x, y in
                          ((left, bottom), (left, top), (right, bottom), (right, top))]
                box = [min(p[0] for p in points)/precision, min(p[1] for p in points)/precision,
                       max(p[0] for p in points)/precision, max(p[1] for p in points)/precision]
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                if boxes:
                    prev = boxes[-1]
                    distance = math.hypot((box[0]+box[2]-prev[0]-prev[2])/2,
                                          (box[1]+box[3]-prev[1]-prev[3])/2)
                    size = max(box[2]-box[0], box[3]-box[1], prev[2]-prev[0], prev[3]-prev[1])
                    if distance > size*2.5:
                        flush()
                chars.append(char)
                boxes.append(box)
            flush()
            textpage.close()
            page.close()
            return items

    def extract_vectors(self, path, page_index):
        from .vector_engine import extract_vectors
        return extract_vectors(path,page_index,self.vector_segment_limit)

    def open_vector_page(self, path, page_index, cache_directory=None):
        from .native_geometry import NativeVectorPage
        return NativeVectorPage(path, page_index, self.vector_segment_limit,cache_directory=cache_directory)
