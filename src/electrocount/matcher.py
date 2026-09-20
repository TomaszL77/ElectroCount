"""Same-scale, same-orientation raster matcher. Scores are NOT probabilities."""
import math
import cv2
import numpy as np
from .domain import overlap_metrics
from .text_engine import mask_text


class SimpleSymbolMatcher:
    SCALE = 2.0
    TILE = 1024

    def find(self, engine, path, page, template, threshold, progress=lambda v: None, text_items=None, template_items=None, template_path=None):
        scale = self.SCALE
        box = template["rect"]
        if min(box[2:]) < 3 or max(box[2:])*scale > 512:
            raise ValueError("Wzorzec musi mieć 3–256 punktów na bok. Zaznacz sam symbol.")
        pattern_image = engine.render(template_path or path, template["page"], scale, box)
        if template_items is not None:
            pattern_image = mask_text(pattern_image, template_items, box, scale)
        pattern = cv2.cvtColor(pattern_image, cv2.COLOR_RGB2GRAY)
        if pattern.std() < 8 or np.count_nonzero(pattern < 180) < 12:
            raise ValueError("Zaznaczenie jest puste lub zbyt mało charakterystyczne.")
        meta = engine.inspect(path)[page]
        pw, ph = meta["width"], meta["height"]
        tw, th = pattern.shape[1], pattern.shape[0]
        step_x, step_y = (self.TILE-tw)/scale, (self.TILE-th)/scale
        columns, rows = math.ceil(pw/step_x), math.ceil(ph/step_y)
        candidates = []
        total = columns*rows
        for row in range(rows):
            for column in range(columns):
                x, y = column*step_x, row*step_y
                rect = [x, y, min(self.TILE/scale, pw-x), min(self.TILE/scale, ph-y)]
                image_rgb = engine.render(path, page, scale, rect)
                if text_items is not None:
                    image_rgb = mask_text(image_rgb, text_items, rect, scale)
                image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
                if image.shape[0] >= th and image.shape[1] >= tw:
                    scores = cv2.matchTemplate(image, pattern, cv2.TM_CCOEFF_NORMED)
                    maxima = cv2.dilate(scores, np.ones((3, 3), np.uint8))
                    ys, xs = np.where((scores >= threshold) & (scores >= maxima))
                    if len(xs)+len(candidates) > 20000:
                        raise ValueError("Zbyt wiele kandydatów. Podnieś próg lub wybierz bardziej charakterystyczny wzorzec.")
                    candidates.extend({"rect": [x+float(xx)/scale, y+float(yy)/scale, box[2], box[3]],
                                       "score": float(scores[yy, xx])} for yy, xx in zip(ys, xs))
                progress(round(100*(row*columns+column+1)/total))
        kept = []
        for candidate in sorted(candidates, key=lambda d: d["score"], reverse=True):
            if not any(overlap_metrics(candidate["rect"], other["rect"])[0] > 0.3 for other in kept):
                kept.append(candidate)
        return sorted(kept, key=lambda d: (d["rect"][1], d["rect"][0]))

def template_variant(image,scale,angle):
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    if abs(angle/90-round(angle/90))<1e-8:
        return np.rot90(image,int(round(angle/90))%4).copy()
    h,w=image.shape[:2]
    rotation=cv2.getRotationMatrix2D((w/2,h/2),angle,1)
    cosine,sine=abs(rotation[0,0]),abs(rotation[0,1])
    width,height=math.ceil(h*sine+w*cosine),math.ceil(h*cosine+w*sine)
    rotation[0,2]+=(width-w)/2;rotation[1,2]+=(height-h)/2
    return cv2.warpAffine(image,rotation,(width,height),flags=cv2.INTER_CUBIC,borderValue=255)


class TemplateMatcher:
    """Multi-scale proposal generator. Every proposal still requires verification."""
    SCALE=2.0
    TILE=1024
    SCALES=(.85,.925,1.0,1.075,1.15)
    ANGLES=(-8.0,0.0,8.0,90.0,180.0,270.0)

    def find(self,engine,path,page,template,threshold,progress=lambda p:None,
             text_items=None,template_items=None,template_path=None):
        scale=self.SCALE;box=template.get("raster_rect",template["rect"])
        if min(box[2:])<3 or max(box[2:])>256:
            raise ValueError("Wzorzec musi mieć 3–256 punktów na bok.")
        reference=engine.render(template_path or path,template["page"],scale,box)
        reference=mask_text(reference,template_items or [],box,scale)
        reference=cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY)
        if reference.std()<8:
            raise ValueError("Wzorzec nie zawiera wystarczającej grafiki.")
        variants=[(s,a,template_variant(reference,s,a)) for s in self.SCALES for a in self.ANGLES]
        max_w=max(v.shape[1] for _,_,v in variants);max_h=max(v.shape[0] for _,_,v in variants)
        meta=engine.inspect(path)[page]
        pw,ph=meta["width"],meta["height"]
        step_x,step_y=(self.TILE-max_w)/scale,(self.TILE-max_h)/scale
        cols,rows=math.ceil(pw/step_x),math.ceil(ph/step_y)
        candidates=[]
        for row in range(rows):
            for col in range(cols):
                x,y=col*step_x,row*step_y
                rect=[x,y,min(self.TILE/scale,pw-x),min(self.TILE/scale,ph-y)]
                image=engine.render(path,page,scale,rect)
                image=cv2.cvtColor(mask_text(image,text_items or [],rect,scale),cv2.COLOR_RGB2GRAY)
                for size,angle,pattern in variants:
                    th,tw=pattern.shape
                    if image.shape[0]<th or image.shape[1]<tw:
                        continue
                    scores=cv2.matchTemplate(image,pattern,cv2.TM_CCOEFF_NORMED)
                    maxima=cv2.dilate(scores,np.ones((3,3),np.uint8))
                    ys,xs=np.where((scores>=threshold)&(scores>=maxima))
                    if len(xs)+len(candidates)>30000:
                        raise ValueError("Zbyt wiele kandydatów. Wybierz bardziej charakterystyczny wzorzec.")
                    for yy,xx in zip(ys,xs):
                        patch=[x+float(xx)/scale,y+float(yy)/scale,tw/scale,th/scale]
                        core=patch
                        if box!=template["rect"]:
                            cw,ch=template["rect"][2:];a=math.radians(angle)
                            cw,ch=size*(abs(math.cos(a))*cw+abs(math.sin(a))*ch),size*(abs(math.sin(a))*cw+abs(math.cos(a))*ch)
                            core=[patch[0]+(patch[2]-cw)/2,patch[1]+(patch[3]-ch)/2,cw,ch]
                        candidates.append({"rect":core,"verification_rect":patch,
                            "score":float(scores[yy,xx]),"template_score":float(scores[yy,xx]),
                            "scale":size,"rotation":-angle,"raster_angle":angle,"source":"raster"})
                progress(round((row*cols+col+1)*100/(rows*cols)))
        kept=[]
        for candidate in sorted(candidates,key=lambda c:c["score"],reverse=True):
            # Keep alternative scales/orientations until the geometry gate.
            # A high bitmap score can otherwise suppress the correct pose.
            if not any(candidate["scale"]==other["scale"] and candidate["rotation"]==other["rotation"]
                       and overlap_metrics(candidate["rect"],other["rect"])[0]>.3 for other in kept):
                kept.append(candidate)
        return kept

