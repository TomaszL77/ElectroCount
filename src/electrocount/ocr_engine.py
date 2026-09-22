"""Local PP-OCRv4 fallback. Native PDF text always has priority."""
import cv2
import numpy as np
from .text_engine import PdfTextItem,normalize_text,intersection,TextEngine


class OCREngine:
    def __init__(self):
        self.cache={}
        from rapidocr_onnxruntime import RapidOCR
        self.backend=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1,
            det_use_cuda=False,cls_use_cuda=False,rec_use_cuda=False,
            det_use_dml=False,cls_use_dml=False,rec_use_dml=False)

    def read_region(self,pdf,path,page,rect,native_items=()):
        # Never OCR a region that already has a native associated device code.
        native=TextEngine().associate(rect,native_items)
        if native['item'] is not None or any(a['role']=='DEVICE_LABEL' and a['spatial_score']>=.6 for a in native.get('associated_texts',[])):return []
        key=(str(path),page,*[round(v,1) for v in rect])
        if key in self.cache:return self.cache[key]
        meta=pdf.inspect(path)[page];x,y,w,h=rect
        radius=max(24,max(w,h)*1.5)
        left,top=max(0,x-radius),max(0,y-radius)
        box=[left,top,min(meta['width'],x+w+radius)-left,min(meta['height'],y+h+radius)-top]
        image=pdf.render(path,page,3.,box)
        output,_=self.backend(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
        result=[]
        for polygon,text,confidence in output or []:
            if confidence<.80:continue
            points=np.asarray(polygon)/3+np.array([left,top])
            start=points.min(axis=0);end=points.max(axis=0)
            bbox=[*start.tolist(),*(end-start).tolist()]
            if any(intersection(bbox,i.bbox)>.3*bbox[2]*bbox[3] for i in native_items):continue
            result.append(PdfTextItem(text,normalize_text(text),page,bbox,((start+end)/2).tolist(),
                source='ocr',confidence=float(confidence)))
        self.cache[key]=result
        return result


class TextOverridePDF:
    def __init__(self,pdf,path,page,items):
        self.pdf,self.path,self.page,self.items=pdf,path,page,items
    def extract_text(self,path,page):
        return self.items if path==self.path and page==self.page else self.pdf.extract_text(path,page)
    def __getattr__(self,name):return getattr(self.pdf,name)
