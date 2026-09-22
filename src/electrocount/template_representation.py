"""Portable multimodal one-shot reference persisted with the project."""
from dataclasses import dataclass, asdict
import base64
import cv2
from .color_features import color_signature
from .text_engine import mask_text


@dataclass
class TemplateRepresentation:
    visual_crop: dict
    context_crop: dict
    native_pdf_text: list
    OCR_text: list
    color_signature: dict
    geometry_signature: dict | None
    visual_embedding: dict | None
    associated_labels: list
    source_bbox: list
    source_page: int
    source: str


def crop_record(image, bbox):
    ok, encoded = cv2.imencode('.png', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok: raise ValueError('Nie udało się zapisać wzorca')
    return {'png_base64': base64.b64encode(encoded).decode(), 'bbox': list(bbox), 'scale': 2.0}


def build_representation(pdf, path, page, template):
    items = pdf.extract_text(path,page)
    rect = template.get('raster_rect',template['rect'])
    visual = mask_text(pdf.render(path,page,2.,rect),items,rect,2.)
    x,y,w,h = template['rect']; margin = max(24.,max(w,h)*2.5)
    meta = pdf.inspect(path)[page]
    left,top = max(0,x-margin), max(0,y-margin)
    context = [left,top,min(meta['width'],x+w+margin)-left,min(meta['height'],y+h+margin)-top]
    from .text_engine import intersection
    nearby = [i.to_dict() for i in items if intersection(context,i.bbox)]
    return asdict(TemplateRepresentation(crop_record(visual,rect),
        crop_record(pdf.render(path,page,2.,context),context),
        [i for i in nearby if i.get('source')!='ocr'],[i for i in nearby if i.get('source')=='ocr'],color_signature(visual),
        template.get('signature'),None,template.get('associated_texts',[]),
        template['rect'],page,template.get('source','DRAWING')))
