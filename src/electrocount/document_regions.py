"""Conservative legend regions: a heading inside an explicitly drawn rectangle."""
from .vector_engine import contains


def legend_regions(native, items):
    regions=[]
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
