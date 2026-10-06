"""Independent, cached coarse page scan; neural work is restricted to proposals."""
import cv2
import numpy as np
from ..matcher import template_variant
from ..text_engine import mask_text
from ..domain import overlap_metrics
from ..foreground import matching_scores, placed_symbol_rect, graphic_box, ink_mask


def propose(pdf, path, page, template, source, items, reference_items, threshold):
    meta = pdf.inspect(path)[page]
    width, height = meta['width'], meta['height']
    scale = min(2., 3200 / max(width, height))
    box = template.get('raster_rect', template['rect'])
    if min(box[2:]) * scale < 5:
        return [], ['Drobne symbole: skan podglądu nie obejmuje ich wiarygodnie; sprawdź pominięcia lub użyj pełnej analizy.']
    # Render through the underlying bounded cache, shared across GUI searches.
    base = getattr(pdf, 'pdf', pdf)
    rgb = base.render(path, page, scale)
    gray = cv2.cvtColor(mask_text(rgb, items, [0, 0, width, height], scale), cv2.COLOR_RGB2GRAY)
    ref = mask_text(pdf.render(source, template['page'], scale, box), reference_items, box, scale)
    ref = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY)
    if np.count_nonzero(ink_mask(ref)) < 12:
        return [], ['Wzorzec jest mało czytelny w podglądzie; podstawą pozostaje geometria i lokalna analiza.']
    found = []
    symbol=graphic_box(ref,box,scale)
    if min(symbol[2:])*scale<5:
        return [], ['Drobne detale symbolu: skan podglądu nie rozróżnia ich wiarygodnie; użyto dokładnej geometrii i lokalnej analizy.']
    warning = []
    for size in (.85, 1., 1.15):
        for angle in (0, 90, 180, 270):
            pattern = template_variant(ref, size, angle)
            h, w = pattern.shape
            if h > gray.shape[0] or w > gray.shape[1]: continue
            scores = matching_scores(gray, pattern)
            peaks = cv2.dilate(scores, np.ones((3, 3), np.uint8))
            ys, xs = np.where((scores >= max(.86, threshold)) & (scores >= peaks))
            if len(found) + len(xs) > 6000:
                warning = ['Skan podglądu ma zbyt wiele propozycji; nie potwierdza kompletności. Użyj pełnej analizy lub dokładniejszego wzorca.']
                return [], warning
            for y, x in zip(ys, xs):
                rect = [float(x) / scale, float(y) / scale, w / scale, h / scale]
                core = placed_symbol_rect(symbol,box,rect,size,angle)
                found.append({'rect': core, 'verification_rect': rect, 'score': float(scores[y, x]),
                              'template_score': float(scores[y, x]), 'scale': size,
                              'rotation': -angle, 'raster_angle': angle, 'source': 'coarse_page'})
    # Nearby maxima at the same pose add no independent evidence.
    kept, grid = [], {}
    cell = max(1., min(template['rect'][2:]) / 2)
    for hit in sorted(found, key=lambda c: c['score'], reverse=True):
        x, y, w, h = hit['rect']; col, row = int((x + w / 2) // cell), int((y + h / 2) // cell)
        pose = (hit['scale'], hit['rotation'])
        neighbors = [other for dx in range(-2, 3) for dy in range(-2, 3)
                     for other in grid.get((pose, col + dx, row + dy), [])]
        if any(overlap_metrics(hit['rect'], other['rect'])[0] > .3 for other in neighbors): continue
        kept.append(hit); grid.setdefault((pose, col, row), []).append(hit)
    return kept, warning
