"""Resolution-aware sampling for tiny symbols; no change to acceptance thresholds."""
import cv2
from .text_engine import mask_text
from .matcher import template_variant


def verification_images(pdf, source, path, page, template, candidate, template_items, items, cache):
    box=candidate.get('verification_rect',candidate['rect'])
    ref_box=template.get('raster_rect',template['rect']) if candidate.get('verification_rect')!=candidate['rect'] and candidate.get('verification_rect') else template['rect']
    short=min(*box[2:],*ref_box[2:])
    scale=round(min(12.,max(2.,32/max(short,.1))),3) if short<6 else 2.
    key=(tuple(ref_box),scale)
    if key not in cache:
        cache[key]=mask_text(pdf.render(source,template['page'],scale,ref_box),template_items,ref_box,scale)
    reference=cache[key]
    angle=candidate.get('raster_angle',candidate.get('rotation',0))
    transformed=template_variant(cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY),candidate.get('scale',1),angle)
    patch=mask_text(pdf.render(path,page,scale,box),items,box,scale)
    return transformed,patch,scale,reference
