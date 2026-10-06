"""Conservative legend regions: a heading inside an explicitly drawn rectangle."""
from .vector_engine import contains


def legend_regions(native, items):
    regions=list(table_regions(native))
    for item in items:
        if item.normalized_text not in ("LEGENDA", "LEGEND"):continue
        options=[]
        for i,b in enumerate(native.bounds):
            if not contains(b,item.bbox,0):continue
            x,y,w,h=b
            if w < item.bbox[2]*2 or h < item.bbox[3]*4:continue
            if w*h > native.size[0]*native.size[1]*.35 or item.center[1]>y+h*.2:continue
            if native.index[i,5]>10000:continue
            paths=native.decode([i]) or []
            for p in paths:
                x,y,w,h=p['bbox'];lengths=[0.,0.,0.,0.];valid=True
                for edge in p['segments']:
                    if edge['kind']!='line':valid=False;break
                    a,b=edge['points'];dx=abs(a[0]-b[0]);dy=abs(a[1]-b[1])
                    if dy<.2 and abs(a[1]-y)<.2:lengths[0]+=dx
                    elif dy<.2 and abs(a[1]-y-h)<.2:lengths[1]+=dx
                    elif dx<.2 and abs(a[0]-x)<.2:lengths[2]+=dy
                    elif dx<.2 and abs(a[0]-x-w)<.2:lengths[3]+=dy
                    else:valid=False;break
                # Solid and dashed rectangular borders; no text/diagonal paths.
                if valid and lengths[0]>=w*.35 and lengths[2]>=h*.35 and lengths[3]>=h*.35:
                    options.append(p['bbox'])
        if options:
            rect=min(options,key=lambda b:b[2]*b[3])
            if not any(r['rect']==rect for r in regions):regions.append({'rect':rect,'kind':'legend','evidence':'heading_in_table_frame','heading':item.to_dict()})
    return regions


def region_for(rect, regions):
    return next((r for r in regions if contains(r['rect'],rect,.5)),None)


def table_regions(native):
    """Outline-only PDFs: repeated ruled cells, not OCR or device-code lists.

    Require >=8 common horizontal rules and >=3 spanning columns. This
    deliberately ignores isolated rectangles and sparse architectural grids.
    """
    import numpy as np
    from collections import defaultdict
    if hasattr(native,'_table_regions'):return native._table_regions
    b=native.bounds
    ids=np.flatnonzero((b[:,2]>100)&(b[:,3]<5)&(native.index[:,5]<=5))
    groups=defaultdict(list)
    for p in native.decode(ids) or []:
        if len(p['segments'])!=1 or p['segments'][0]['kind']!='line':continue
        x,y,w,h=p['bbox']
        if h<.05:groups[(round(x),round(x+w))].append(y)
    regions=[]
    for (left,right),ys in groups.items():
        ys=sorted(set(round(y,2) for y in ys))
        if len(ys)<8:continue
        gaps=np.diff(ys);median=float(np.median(gaps))
        if not 5<median<80 or np.mean(abs(gaps-median)<max(.5,median*.08))<.7:continue
        top,bottom=ys[0],ys[-1]
        if (right-left)*(bottom-top)>native.size[0]*native.size[1]*.15:continue
        vertical=np.flatnonzero((b[:,0]>=left-3)&(b[:,0]<=right+3)&(b[:,2]<5)&(b[:,3]>max(3,median*.8))&(native.index[:,5]<=5))
        columns=defaultdict(list)
        for p in native.decode(vertical) or []:
            x,y,w,h=p['bbox']
            if len(p['segments'])==1 and w<.05:columns[round(x)].append((y,y+h))
        spans=[]
        for x,intervals in columns.items():
            end=top
            for a,z in sorted(intervals):
                if a<=end+.5:end=max(end,z)
            if end>=bottom-.5:spans.append(x)
        spans.sort()
        if len(spans)>=3 and abs(spans[0]-left)<=1 and abs(spans[-1]-right)<=1:
            regions.append({'rect':[left,top,right-left,bottom-top],'kind':'legend',
                'evidence':'repeated_symbol_table','columns':spans,'rows':ys})
    native._table_regions=regions
    return regions


def reference_frames(native):
    """Small explicitly closed panels, candidates only until a heading is read."""
    import numpy as np
    b=native.bounds
    ids=np.flatnonzero((b[:,2]>120)&(b[:,3]>40)&(b[:,2]*b[:,3]<native.size[0]*native.size[1]*.1)&(native.index[:,5]<=5))
    frames=[]
    for p in native.decode(ids) or []:
        x,y,w,h=p['bbox']
        if len(p['segments'])!=4:continue
        sides=set()
        for e in p['segments']:
            if e['kind']!='line':break
            a,z=e['points']
            if abs(a[1]-z[1])<.05 and abs(abs(a[0]-z[0])-w)<.1:sides.add(('h',round(a[1]-y,1)))
            elif abs(a[0]-z[0])<.05 and abs(abs(a[1]-z[1])-h)<.1:sides.add(('v',round(a[0]-x,1)))
        if len(sides)==4:frames.append(p['bbox'])
    return frames


def confirmed_reference_panels(pdf,path,page,items,frames,hits):
    """Exclude note/schematic examples only with a high-confidence heading.

    OCR is local to candidate panel headings and only when native text is absent.
    No DINO model or whole-page OCR is required for this document-layout check.
    """
    import re
    import cv2
    from .text_engine import intersection,normalize_text
    from .ocr_engine import OCREngine
    regions=[];ocr=None
    marker=re.compile(r'^(?:NOTE(?:S)?(?:[\s\d:/-]|$)|UWAGA(?:[\s\d:/-]|$)|UWAGI(?:[\s:/-]|$)|SCHEMAT(?:[\s:/-]|$)|SCHEMATIC(?:[\s:/-]|$))')
    for frame in frames:
        if not any(contains(frame,h['rect']) for h in hits):continue
        x,y,w,h=frame;box=[x,max(0,y-20),min(w,300),38]
        texts=[(i.normalized_text,i.confidence,i.source) for i in items if intersection(box,i.bbox)]
        if not texts:
            if ocr is None:ocr=OCREngine()
            image=pdf.render(path,page,3.,box)
            output,_=ocr.backend(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
            texts=[(normalize_text(text),float(score),'ocr') for _,text,score in output or []]
        heading=next(((text,score,source) for text,score,source in texts if score>=.95 and marker.match(text)),None)
        if heading:regions.append({'rect':frame,'kind':'reference_panel','evidence':'confirmed_note_heading',
            'heading':heading[0],'heading_confidence':heading[1],'heading_source':heading[2]})
    return regions
