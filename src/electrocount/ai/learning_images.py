"""The same visual input in feedback capture and model inference."""
from ..text_engine import mask_text


def symbol_crop(pdf, path, page, rect, items=None):
    scale = min(12., max(2., 48 / max(1., min(rect[2:]))))
    if items is None:
        items = pdf.extract_text(path, page)
    return mask_text(pdf.render(path, page, scale, rect), items, rect, scale)
