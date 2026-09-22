"""Reuse PDFium page handles during one operation without changing raster inputs."""
from collections import OrderedDict
import numpy as np
import pypdfium2 as pdfium

class RenderSession:
    def __init__(self,pdf):
        self.pdf=pdf;self.pages=OrderedDict()
    def __getattr__(self,name):return getattr(self.pdf,name)
    def render(self,path,page_index,scale,rect=None):
        key=(str(path),page_index)
        if key not in self.pages:
            doc=pdfium.PdfDocument(path)
            try:page=doc[page_index]
            except Exception:doc.close();raise
            self.pages[key]=(doc,page)
            while len(self.pages)>2:
                _,(old_doc,old_page)=self.pages.popitem(last=False)
                old_page.close();old_doc.close()
        self.pages.move_to_end(key)
        doc,page=self.pages[key]
        width,height=page.get_size();crop=(0,0,0,0)
        if rect is not None:
            x,y,w,h=rect
            crop=tuple(max(0,v) for v in (x,height-y-h,width-x-w,y))
        bitmap=page.render(scale=scale,crop=crop,rev_byteorder=True)
        try:return np.array(bitmap.to_numpy(),copy=True)[:,:,:3]
        finally:bitmap.close()
    def close(self):
        for doc,page in self.pages.values():page.close();doc.close()
        self.pages.clear()
