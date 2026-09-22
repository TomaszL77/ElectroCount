"""Independent full-page dense DINO retrieval, then local alignment and geometry.

Every overlapping tile is encoded; classical candidate generation never gates
which page regions the encoder sees. This experimental branch does not count
embedding peaks directly as devices.
"""
import math
import cv2
import numpy as np
from ..text_engine import mask_text
from ..matcher import template_variant


class VisualRetrieval:
    TILE = 224
    STEP = 168
    TOKEN_THRESHOLD = .72

    def __init__(self, encoder):
        self.encoder = encoder

    def find(self,pdf,path,page,template,reference,items,progress=lambda p:None):
        # Foreground patch descriptors provide a dense retrieval seed. Color,
        # text, local features and geometry still decide the final bucket.
        import PIL.Image
        square = np.full((max(reference.shape[:2]),)*2+(3,),255,np.uint8)
        h,w=reference.shape[:2];y=(len(square)-h)//2;x=(len(square)-w)//2
        square[y:y+h,x:x+w]=reference
        thumb=np.array(PIL.Image.fromarray(square).resize((224,224)))
        fg=cv2.cvtColor(thumb,cv2.COLOR_RGB2GRAY)<210
        weights=fg.reshape(16,14,16,14).mean(axis=(1,3)).ravel()
        tokens=self.encoder.tokens(square)[1:]
        query=np.average(tokens,axis=0,weights=np.maximum(weights,.001))
        query=query/max(np.linalg.norm(query),1e-12)
        meta=pdf.inspect(path)[page];pw,ph=meta['width'],meta['height']
        cols,rows=math.ceil(pw/self.STEP),math.ceil(ph/self.STEP)
        # Fixed scale set is identical on every machine; legend references may
        # be twice the drawing size. No per-tile top-k truncation.
        variants=[(s,a,template_variant(cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY),s/2,a))
            for s in ((.5,1.,2.) if template.get('source')=='LEGEND' else (1.,))
            for a in (0,90,180,270)]
        found=[];encoded=0;peaks=0
        for row in range(rows):
            for col in range(cols):
                x,y=col*self.STEP,row*self.STEP
                box=[x,y,min(self.TILE,pw-x),min(self.TILE,ph-y)]
                image=mask_text(pdf.render(path,page,1.,box),items,box,1.)
                tile=np.full((224,224,3),255,np.uint8)
                tile[:image.shape[0],:image.shape[1]]=image
                features=self.encoder.tokens(tile)[1:]
                features=features/np.maximum(np.linalg.norm(features,axis=1,keepdims=True),1e-12)
                scores=(features@query).reshape(16,16)
                maxima=cv2.dilate(scores,np.ones((3,3),np.uint8))
                yy,xx=np.where((scores>=self.TOKEN_THRESHOLD)&(scores>=maxima))
                encoded+=1;peaks+=len(xx)
                gray=cv2.cvtColor(tile,cv2.COLOR_RGB2GRAY)
                for py,px in zip(yy,xx):
                    py,px=int(py),int(px)
                    cx,cy=px*14+7,py*14+7
                    for size,angle,pattern in variants:
                        th,tw=pattern.shape
                        left,top=max(0,cx-tw//2-21),max(0,cy-th//2-21)
                        right,bottom=min(image.shape[1],cx+tw//2+22),min(image.shape[0],cy+th//2+22)
                        roi=gray[top:bottom,left:right]
                        if min(pattern.shape)<2 or roi.shape[0]<th or roi.shape[1]<tw:continue
                        aligned=cv2.matchTemplate(roi,pattern,cv2.TM_CCOEFF_NORMED)
                        _,score,_,location=cv2.minMaxLoc(aligned)
                        if score<.55:continue
                        ax,ay=location;patch=[x+left+ax,y+top+ay,float(tw),float(th)]
                        core=patch
                        if template.get('raster_rect',template['rect'])!=template['rect']:
                            cw,ch=template['rect'][2:]
                            if angle%180:cw,ch=ch,cw
                            cw*=size;ch*=size
                            core=[patch[0]+(tw-cw)/2,patch[1]+(th-ch)/2,cw,ch]
                        found.append({'rect':core,'verification_rect':patch,'score':score,
                            'template_score':score,'retrieval_score':float(scores[py,px]),
                            'scale':size,'rotation':-angle,'raster_angle':angle,'source':'ai_tile'})
                progress(round(encoded*100/(rows*cols)))
        # Exact dedup only here; pose alternatives survive until verification.
        unique={}
        for hit in found:
            key=(*[round(v,2) for v in hit['rect']],hit['scale'],hit['rotation'])
            if key not in unique or hit['score']>unique[key]['score']:unique[key]=hit
        return list(unique.values()),{'tiles_encoded':encoded,'embedding_peaks':peaks,
            'candidates':len(unique),'coverage':'entire_page','token_threshold':self.TOKEN_THRESHOLD}
