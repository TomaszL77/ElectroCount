"""Local PP-OCRv4 fallback. Native PDF text always has priority."""
import cv2
import numpy as np
from pathlib import Path
from .text_engine import PdfTextItem,normalize_text,intersection,TextEngine


class OCREngine:
    def __init__(self):
        self.cache={}
        from rapidocr_onnxruntime import RapidOCR
        self.backend=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1,
            det_use_cuda=False,cls_use_cuda=False,rec_use_cuda=False,
            det_use_dml=False,cls_use_dml=False,rec_use_dml=False)

    def read_outlined_text(self,pdf,path,page):
        """Read complete coloured CAD inscriptions, independently of the requested type.

        The native bounds avoid a low-resolution whole-sheet OCR scan. Only the
        OCR input is made black on white; source pixels and selected parts stay intact.
        """
        import re
        from .text_roles import TextRoleClassifier
        if not hasattr(pdf,'open_vector_page'):return []
        stat=Path(path).stat();key=(str(Path(path).resolve()),stat.st_size,stat.st_mtime_ns,page)
        if key in _outline_cache:return _outline_cache[key]
        result=[]
        with pdf.open_vector_page(path,page) as native:
            b=native.bounds
            ids=np.flatnonzero((native.index[:,6]>0)&(native.index[:,5]>40)&
                (b[:,2]>4)&(b[:,2]<70)&(b[:,3]>1.5)&(b[:,3]<12)&(b[:,2]>b[:,3]*1.2))
            # A large/unsupported page keeps the usual local OCR fallback.
            if len(ids)>1000:return []
            for index in ids:
                paths=native.decode([index])
                if not paths or not paths[0].get('fill'):continue
                x,y,w,h=paths[0]['bbox'];box=[max(0,x-.4),max(0,y-.4),w+.8,h+.8]
                image=pdf.render(path,page,12.,box)
                rgb=image.astype(np.int16)
                ink=rgb.max(axis=2)-rgb.min(axis=2)>40
                image[:]=255;image[ink]=0
                output,_=self.backend(image,use_det=False,use_cls=False)
                for text,confidence in output or []:
                    code=normalize_text(text)
                    if (confidence<.90 or not re.fullmatch(r'[A-Z][A-Z0-9._-]{1,15}',code) or
                            TextRoleClassifier().classify(code)[0]!='DEVICE_LABEL'):continue
                    result.append(PdfTextItem(text,code,page,[x,y,w,h],[x+w/2,y+h/2],
                        source='pdf_outline',confidence=float(confidence)))
        if len(_outline_cache)>=8:_outline_cache.pop(next(iter(_outline_cache)))
        _outline_cache[key]=result
        return result

    def read_region(self,pdf,path,page,rect,native_items=(),context_rect=None):
        # Never OCR a region that already has a native associated device code.
        native=TextEngine().associate(rect,native_items)
        if native['item'] is not None or any(a['role']=='DEVICE_LABEL' and a['spatial_score']>=.6 for a in native.get('associated_texts',[])):return []
        key=(str(path),page,*[round(v,1) for v in rect],tuple(context_rect or ()))
        if key in self.cache:return self.cache[key]
        meta=pdf.inspect(path)[page];x,y,w,h=rect
        radius=max(24,max(w,h)*1.5)
        left,top=max(0,x-radius),max(0,y-radius)
        box=[left,top,min(meta['width'],x+w+radius)-left,min(meta['height'],y+h+radius)-top]
        if context_rect is not None:
            box=list(context_rect);left,top=box[:2]
        scale=min(12.,max(3.,40/max(min(w,h),1.)))
        image=pdf.render(path,page,scale,box)
        output,_=self.backend(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
        result=[]
        for polygon,text,confidence in output or []:
            if confidence<.80:continue
            points=np.asarray(polygon)/scale+np.array([left,top])
            start=points.min(axis=0);end=points.max(axis=0)
            bbox=[*start.tolist(),*(end-start).tolist()]
            # Symbol strokes can themselves be read as X, (), or a numeral.
            # Only surrounding OCR is promoted to a device code; native text
            # inside a symbol remains available through the native path.
            if intersection(rect,bbox)>.5*bbox[2]*bbox[3]:
                # CAD exports often turn AW3/EW1 labels into paths. Promote a
                # complete alphanumeric code, never an isolated symbol stroke.
                import re
                from .text_roles import TextRoleClassifier
                normalized=normalize_text(text)
                if (not re.fullmatch(r'[A-Z][A-Z0-9._-]{1,15}',normalized) or
                        min(bbox[2:])<1.5 or
                        TextRoleClassifier().classify(normalized)[0]!='DEVICE_LABEL'):
                    continue
            if not any(c.isalnum() for c in text):continue
            if any(intersection(bbox,i.bbox)>.3*bbox[2]*bbox[3] for i in native_items):continue
            result.append(PdfTextItem(text,normalize_text(text),page,bbox,((start+end)/2).tolist(),
                source='ocr',confidence=float(confidence),
                rotation=float(np.degrees(np.arctan2(*(points[1]-points[0])[::-1]))%360)))
        if len(self.cache)>=256:self.cache.pop(next(iter(self.cache)))
        self.cache[key]=result
        return result


class TextOverridePDF:
    def __init__(self,pdf,path,page,items):
        self.pdf,self.path,self.page,self.items=pdf,path,page,items
    def extract_text(self,path,page):
        return self.items if path==self.path and page==self.page else self.pdf.extract_text(path,page)
    def __getattr__(self,name):return getattr(self.pdf,name)


_outline_cache={}
