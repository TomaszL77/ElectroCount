"""Portable RGB original plus independent matching and contextual evidence."""
from dataclasses import dataclass, asdict
from uuid import uuid4
from pathlib import Path
import base64
import cv2
import numpy as np
from .color_features import color_signature
from .text_engine import mask_text, TextEngine


@dataclass
class TemplateRepresentation:
    id: str
    group_id: str | None
    selection_bbox: list
    matching_bbox: list
    symbol_bbox: list
    context_bbox: list
    original_rgb_crop: dict
    normalized_visual_crop: dict
    color_signature: dict
    geometry_signature: dict | None
    visual_features: dict
    detected_label: str
    label_bbox: list | None
    label_rotation: float | None
    label_position: str | None
    associated_texts: list
    source_page: int
    source_document: str
    source: str


def crop_record(image, bbox, scale=2.0):
    pixels=cv2.cvtColor(image,cv2.COLOR_GRAY2BGR) if image.ndim==2 else cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode('.png', pixels)
    if not ok: raise ValueError('Nie udało się zapisać wzorca')
    return {'png_base64':base64.b64encode(encoded).decode(),'bbox':list(bbox),'scale':scale,'color_space':'RGB'}


def build_representation(pdf, path, page, template):
    items=pdf.extract_text(path,page)
    selection=template.get('selection_bbox',template.get('selection_rect',template['rect']))
    rect=template.get('matching_bbox',template.get('raster_rect',template['rect']))
    # Render small selections sharply; keep exact bounds and limit memory use.
    original_scale=max(2.,min(12.,152./max(min(selection[2:]),.1),2048./max(selection[2:])))
    original=pdf.render(path,page,original_scale,selection)
    visual=mask_text(pdf.render(path,page,2.,rect),items,rect,2.)
    x,y,w,h=template['rect'];margin=max(24.,max(w,h)*2.5)
    meta=pdf.inspect(path)[page]
    left,top=max(0,x-margin),max(0,y-margin)
    context=[left,top,min(meta['width'],x+w+margin)-left,min(meta['height'],y+h+margin)-top]
    template['context_bbox']=list(context)
    from .text_engine import intersection
    nearby=[i.to_dict() for i in items if intersection(context,i.bbox)]
    associated=TextEngine().associate(template['rect'],items).get('associated_texts',[])
    label=template.get('label_item') or {}
    chosen=next((a for a in associated if a['bbox']==label.get('bbox') and a['normalized_text']==label.get('normalized_text')), {})
    template['id']=template.get('id') or uuid4().hex
    gray=cv2.cvtColor(visual,cv2.COLOR_RGB2GRAY)
    record=asdict(TemplateRepresentation(
        id=template['id'],group_id=template.get('group_id'),selection_bbox=list(selection),
        matching_bbox=list(rect),symbol_bbox=template.get('symbol_bbox'),context_bbox=context,
        original_rgb_crop=crop_record(original,selection,original_scale),normalized_visual_crop=crop_record(gray,rect),
        color_signature=color_signature(visual),geometry_signature=template.get('signature'),
        visual_features={'kind':'shape_summary','embedding':None,
            'hu_moments':cv2.HuMoments(cv2.moments((gray<205).astype(np.uint8))).ravel().tolist(),
            'foreground_fraction':float((gray<205).mean())},detected_label=template.get('label',''),
        label_bbox=label.get('bbox'),label_rotation=label.get('rotation'),label_position=chosen.get('position'),
        associated_texts=associated,source_page=page,source_document=str(Path(path).resolve()),
        source=template.get('source','DRAWING')))
    # Read compatibility for existing matchers, saved projects and diagnostics.
    record.update(visual_crop=crop_record(visual,rect),context_crop=crop_record(pdf.render(path,page,2.,context),context),
        native_pdf_text=[i for i in nearby if i.get('source')!='ocr'],OCR_text=[i for i in nearby if i.get('source')=='ocr'],
        visual_embedding=None,associated_labels=associated,source_bbox=list(template['rect']),
        text_source=label.get('source'),label_confidence=label.get('confidence',0.))
    return record
