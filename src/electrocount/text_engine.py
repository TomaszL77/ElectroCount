"""Native PDF words and conservative symbol-to-label association. No OCR substitutions."""
from dataclasses import dataclass, asdict
import math
import re


def normalize_text(text):
    return " ".join(text.strip().upper().split())


@dataclass
class PdfTextItem:
    text: str
    normalized_text: str
    page: int
    bbox: list[float]  # x, y, width, height in display-page points
    center: list[float]

    source: str = "pdf_native"
    confidence: float = 1.0
    rotation: float = 0.0

    def to_dict(self):
        return asdict(self)


def as_item(value):
    return value if isinstance(value, PdfTextItem) else PdfTextItem(**value)


def intersection(a, b):
    x, y = max(a[0], b[0]), max(a[1], b[1])
    return max(0, min(a[0]+a[2], b[0]+b[2])-x) * max(0, min(a[1]+a[3], b[1]+b[3])-y)


def mask_text(image, items, rect, scale):
    """Remove native text from both template and search raster, never compare text pixels."""
    clean = image.copy()
    for value in items:
        item = as_item(value)
        if not intersection(rect, item.bbox):
            continue
        x, y, w, h = item.bbox
        x1, y1 = math.floor((x-rect[0])*scale)-2, math.floor((y-rect[1])*scale)-2
        x2, y2 = math.ceil((x+w-rect[0])*scale)+2, math.ceil((y+h-rect[1])*scale)+2
        clean[max(0, y1):min(clean.shape[0], y2), max(0, x1):min(clean.shape[1], x2)] = 255
    return clean


class TextEngine:
    def associate(self, rect, items, layout=None):
        x, y, w, h = rect
        cx, cy = x+w/2, y+h/2
        radius = max(24, max(w, h)*2.5)
        ranked = []
        associated = []
        from .text_roles import TextRoleClassifier
        roles = TextRoleClassifier()
        seen = set()
        for value in (items.near(rect,radius) if hasattr(items,"near") else items):
            item = as_item(value)
            key=(item.normalized_text,*[round(v,2) for v in item.bbox])
            if key in seen: continue
            seen.add(key)
            role, role_confidence = roles.classify(item.normalized_text)
            tx, ty, tw, th = item.bbox
            gap_x = max(x-(tx+tw), tx-(x+w), 0)
            gap_y = max(y-(ty+th), ty-(y+h), 0)
            gap = math.hypot(gap_x, gap_y)
            if gap > radius:
                continue
            dx, dy = (item.center[0]-cx)/max(w, 1), (item.center[1]-cy)/max(h, 1)
            distance = max(0, 1-gap/radius)
            vertical = math.exp(-abs(item.center[1]-cy)/max(h, th, 1))
            horizontal = math.exp(-abs(item.center[0]-cx)/max(w, tw, 1))
            alignment = max(vertical, horizontal)
            right = 1.0 if tx >= x+w-2 and vertical > .6 else .45
            score = .55*distance + .3*alignment + .15*right
            if layout:
                offset_error = math.hypot(dx-layout["dx"], dy-layout["dy"])
                score = .35*distance + .25*alignment + .4*math.exp(-offset_error)
            if layout and layout.get("offset") is not None:
                # Rotation is applied to the learned offset before association.
                size=max(w,h,1)
                error=math.hypot((item.center[0]-cx)/size-layout["offset"][0],
                                 (item.center[1]-cy)/size-layout["offset"][1])
                score=.35*distance+.25*alignment+.40*math.exp(-error*2)
                ratio=min(tw,th)/max(layout.get("glyph_size",min(tw,th)),.1)
                score*=math.exp(-abs(math.log(max(ratio,.01)))*.35)
            elif layout and layout.get("text_height"):
                size_ratio=th/max(h*layout["text_height"],.1)
                score*=math.exp(-abs(math.log(max(size_ratio,.01)))*.15)
            position = ('INSIDE' if intersection(rect,item.bbox) else
                'RIGHT' if tx >= x+w else 'LEFT' if tx+tw <= x else 'ABOVE' if ty+th <= y else 'BELOW')
            associated.append({**item.to_dict(),'distance':gap,'position':position,
                'role':role,'role_score':role_confidence,'spatial_score':score})
            if role != 'DEVICE_LABEL': continue
            if ' ' in item.normalized_text: score *= .8
            ranked.append((score, item, {"dx": dx, "dy": dy, "text_height": th/max(h,1),
                "offset": [(item.center[0]-cx)/max(w,h,1),(item.center[1]-cy)/max(w,h,1)],
                "glyph_size":min(tw,th)}))
        ranked.sort(key=lambda row: (-row[0],row[1].bbox[1],row[1].bbox[0],row[1].normalized_text))
        if not ranked:
            return {"item": None, "score": 0.0, "reason": "missing_label", "associated_texts": associated}
        best = ranked[0]
        if best[0] < .60 or (len(ranked)>1 and best[0]-ranked[1][0] < .10):
            return {"item": None, "score": best[0], "reason": "ambiguous_label",
                    "alternatives": [row[1].to_dict() for row in ranked[:3]], "associated_texts": associated}
        return {"item": best[1], "score": best[0], "layout": best[2], "reason": "ocr_text" if best[1].source=="ocr" else "native_text", "associated_texts": associated, "text_role_confidence": roles.classify(best[1].normalized_text)[1]}


def prepare_template(engine, path, page, selection):
    import cv2
    import numpy as np
    selection=list(selection)
    items = engine.extract_text(path, page)
    scale = 2.0
    if min(selection[2:]) < 3 or max(selection[2:]) > 300:
        raise ValueError("Zaznacz pojedynczy symbol z oznaczeniem (maksymalnie 300 punktów na bok).")
    signature = None
    legend_region = None
    if hasattr(engine,"open_vector_page"):
        try:
            with engine.open_vector_page(path,page) as native:
                signature=native.template_signature(selection,items)
                from .document_regions import legend_regions, region_for
                legend_region=region_for(selection,legend_regions(native,items))
                if signature:
                    if legend_region:
                        signature['source_legend']=True
        except (RuntimeError,AttributeError) as exc:
            import logging
            logging.warning("Native template unavailable; CPU raster fallback: %s",exc)
    elif hasattr(engine,"extract_vectors"):
        from .vector_engine import signature_in_rect
        signature=signature_in_rect(engine.extract_vectors(path,page),selection,preserve_selection=True)
    symbol_bbox=list(signature['bbox']) if signature else None
    # rect is a legacy geometry helper; selection_bbox is never replaced by it.
    rect=list(symbol_bbox or selection)
    if not signature:
        image=engine.render(path,page,scale,selection)
        if np.count_nonzero(cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)<205)<12:
            raise ValueError("Zaznaczenie nie zawiera czytelnego symbolu.")
    selected=[i for i in items if intersection(selection,i.bbox)>.8*i.bbox[2]*i.bbox[3]]
    # An explicitly selected, larger label wins over tiny circuit annotations.
    from .text_roles import TextRoleClassifier
    selected_labels=[i for i in selected if TextRoleClassifier().classify(i.normalized_text)[0]=='DEVICE_LABEL']
    selected_labels.sort(key=lambda i:min(i.bbox[2:]),reverse=True)
    unique=[]
    for item in selected_labels:
        if not any(item.normalized_text==i.normalized_text and item.bbox==i.bbox for i in unique):unique.append(item)
    if unique and (len(unique)==1 or min(unique[0].bbox[2:])>1.6*min(unique[1].bbox[2:])):
        association=TextEngine().associate(rect,unique[:1])
    else:
        association=TextEngine().associate(rect,selected_labels or items)
    # Keep all contextual evidence even when the selection explicitly picks a label.
    association['associated_texts']=TextEngine().associate(rect,items).get('associated_texts',[])
    item = association["item"]
    analysis_signature=None
    if signature and item and item.source in ('ocr','pdf_outline'):
        from .vector_engine import contains,signature as make_signature
        text_paths=[p for p in signature['paths'] if contains(item.bbox,p['bbox'],.65)]
        body=[p for p in signature['paths'] if p not in text_paths]
        # Separate an external inscription only. Interior distinguishing marks
        # remain part of the graphic. The original signature is never replaced.
        if text_paths and body:
            candidate=make_signature(body,preserve_selection=True)
            if candidate and not intersection(candidate['bbox'],item.bbox):
                glyph=make_signature(text_paths,preserve_selection=True)
                if glyph:
                    gx,gy,gw,gh=glyph['bbox']
                    item=PdfTextItem(item.text,item.normalized_text,item.page,list(glyph['bbox']),
                        [gx+gw/2,gy+gh/2],item.source,item.confidence,item.rotation)
                    association=TextEngine().associate(rect,[item])
                analysis_signature={**candidate,'native_local':True,'foreground':'all',
                    'source_legend':bool(legend_region),'context_paths':[],'core_fill':False}
    raster_rect=list(selection)
    from .electrical_profile import build_profile
    caption_bbox=None
    if legend_region and legend_region.get('columns') and legend_region.get('rows'):
        columns=legend_region['columns'];rows=legend_region['rows']
        cy=rect[1]+rect[3]/2
        if rect[0]+rect[2]<=columns[1]+.5:
            row=next(((a,b) for a,b in zip(rows,rows[1:]) if a<=cy<=b),None)
            if row and len(columns)>=3:
                col=0 if legend_region.get('layout')=='symbol_description' else 1
                caption_bbox=[columns[col]+1,row[0]+1,columns[col+1]-columns[col]-2,row[1]-row[0]-2]
    return {"analysis_signature":analysis_signature,"legend_caption_bbox":caption_bbox,"source": "LEGEND" if legend_region else "DRAWING",
            "electrical_profile":build_profile(rect,selected),
            "associated_texts":association.get('associated_texts',[]),
            "text_role_confidence":association.get('text_role_confidence',0),
            "page": page, "raster_rect":raster_rect, "selection_rect": list(selection), "selection_bbox": list(selection),
            "symbol_bbox":symbol_bbox,"matching_bbox":list(selection), "rect": rect, "signature": signature,
            "label": item.normalized_text if item else "",
            "association": association.get("layout"),
            "label_item": item.to_dict() if item else None,
            "spatial_association_score": association["score"],
            "reason": association["reason"], "text_aware": True,
            "definition_version": 14, "geometry_source": "native_local" if signature else "raster",
            "text_bbox":item.bbox if item else None,
            "self_check":False, "extraction_mode":"full_selection",
            "preserved_paths":len(signature["paths"]) if signature else None,"removed_paths":0,
            "possible_label": (association.get("alternatives") or [{}])[0].get("normalized_text", "")}



def transformed_layout(layout,rotation=0,scale=1):
    if not layout or "offset" not in layout:return layout
    angle=math.radians(rotation);x,y=layout["offset"]
    # Axis-aligned bounds of an arbitrary rotation can change the long side.
    return {**layout,"offset":[x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle)],
            "glyph_size":layout.get("glyph_size",1)*scale}


class TextSpatialIndex:
    """Reusable native-text neighborhood lookup for large engineering sheets."""
    def __init__(self,items,cell=64):
        self.items=items;self.cell=cell;self.cells={};self.large=[]
        for index,item in enumerate(items):
            x,y,w,h=item.bbox
            left,top=math.floor(x/cell),math.floor(y/cell)
            right,bottom=math.floor((x+w)/cell),math.floor((y+h)/cell)
            if (right-left+1)*(bottom-top+1)>256:self.large.append(index);continue
            for a in range(left,right+1):
                for b in range(top,bottom+1):self.cells.setdefault((a,b),[]).append(index)

    def near(self,rect,radius):
        x,y,w,h=rect;cell=self.cell;ids=set(self.large)
        for a in range(math.floor((x-radius)/cell),math.floor((x+w+radius)/cell)+1):
            for b in range(math.floor((y-radius)/cell),math.floor((y+h+radius)/cell)+1):
                ids.update(self.cells.get((a,b),()))
        return [self.items[i] for i in sorted(ids)]
