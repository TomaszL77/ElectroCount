"""Bounded native path index. Detailed segments are decoded only near a query."""
import ctypes
import math
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pypdfium2 as pdfium
from .vector_engine import bbox, contains, signature, sample_segment, VectorCandidateGenerator, without_paint_caps, painted_fill, canonical_path


def _style(obj):
    fill, stroke = ctypes.c_int(), ctypes.c_int()
    pdfium.raw.FPDFPath_GetDrawMode(obj, fill, stroke)
    width = ctypes.c_float()
    pdfium.raw.FPDFPageObj_GetStrokeWidth(obj, width)
    color=[]
    reader=pdfium.raw.FPDFPageObj_GetFillColor if fill.value else pdfium.raw.FPDFPageObj_GetStrokeColor
    channels=[ctypes.c_uint() for _ in range(4)]
    if reader(obj,*channels):color=[v.value for v in channels]
    return {"fill": bool(fill.value), "stroke": bool(stroke.value), "stroke_width": width.value,"color":color}


def chromatic(path):
    color=path.get('color',[])
    return len(color)==4 and color[3]>0 and max(color[:3])-min(color[:3])>=45


def _decode(obj, converter):
    chain=[]; current=obj
    while current is not None:
        chain.append(current.get_matrix()); current=current.container
    def point(x,y):
        for matrix in chain: x,y=matrix.on_point(x,y)
        a,b=converter.to_bitmap(x,y)
        return [a/1000,b/1000]
    segments=[]; previous=start=None; controls=[]
    for index in range(pdfium.raw.FPDFPath_CountSegments(obj)):
        segment=pdfium.raw.FPDFPath_GetPathSegment(obj,index)
        x,y=ctypes.c_float(),ctypes.c_float()
        if not pdfium.raw.FPDFPathSegment_GetPoint(segment,x,y): continue
        target=point(x.value,y.value); kind=pdfium.raw.FPDFPathSegment_GetType(segment)
        if kind==pdfium.raw.FPDF_SEGMENT_MOVETO:
            previous=start=target; controls=[]
        elif kind==pdfium.raw.FPDF_SEGMENT_LINETO and previous is not None:
            segments.append({"kind":"line","points":[previous,target]}); previous=target
        elif kind==pdfium.raw.FPDF_SEGMENT_BEZIERTO and previous is not None:
            controls.append(target)
            if len(controls)==3:
                segments.append({"kind":"curve","points":[previous,*controls]});previous=controls[-1];controls=[]
        if pdfium.raw.FPDFPathSegment_GetClose(segment) and previous and start:
            if math.dist(previous,start)>.001: segments.append({"kind":"line","points":[previous,start]})
            previous=start
    if not segments: return None
    return canonical_path({"bbox":bbox([pt for s in segments for pt in s["points"]]),"segments":segments,**_style(obj)})


def _clip_preserves_geometry(obj,value,converter):
    """Accept enclosing rectangular Form clips; never ignore a cutting clip."""
    import cv2
    clip=pdfium.raw.FPDFPageObj_GetClipPath(obj)
    count=pdfium.raw.FPDFClipPath_CountPaths(clip) if clip else 0
    if count<=0:return True
    for index in range(count):
        n=pdfium.raw.FPDFClipPath_CountPathSegments(clip,index)
        # CAD exporters often repeat collinear vertices along a rectangular
        # page clip. Segment count is not the polygon's number of corners.
        if n<4 or n>512:return False
        points=[]
        for j in range(n):
            segment=pdfium.raw.FPDFClipPath_GetPathSegment(clip,index,j)
            if j and pdfium.raw.FPDFPathSegment_GetType(segment)==pdfium.raw.FPDF_SEGMENT_MOVETO:return False
            if pdfium.raw.FPDFPathSegment_GetType(segment)==pdfium.raw.FPDF_SEGMENT_BEZIERTO:return False
            x,y=ctypes.c_float(),ctypes.c_float()
            if not pdfium.raw.FPDFPathSegment_GetPoint(segment,x,y):return False
            x,y=x.value,y.value;parent=obj.container
            while parent is not None:
                x,y=parent.get_matrix().on_point(x,y);parent=parent.container
            a,b=converter.to_bitmap(x,y);points.append((a/1000,b/1000))
        if points[-1]==points[0]:points.pop()
        polygon=cv2.approxPolyDP(np.asarray(points,np.float32),.001,True).reshape(-1,2)
        if not cv2.isContourConvex(polygon):return False
        if any(cv2.pointPolygonTest(polygon,tuple(pt),True)<-.002
               for segment in value['segments'] for pt in segment['points']):return False
    return True


def _path_key(path):
    # Repeated CAD overprints must not become additional geometric features.
    edges=[]
    for s in path['segments']:
        points=tuple(tuple(round(v,2) for v in p) for p in s['points'])
        edges.append((s['kind'],min(points,points[::-1])))
    return tuple(sorted(edges))


def deduplicate(paths):
    unique={}
    for p in paths:
        key=_path_key(p)
        if key not in unique or p.get('fill'): unique[key]=p
    return list(unique.values())


def intersects_selection(path,rect):
    """An enclosing stroked frame's bounds do not mean it paints the selection."""
    x,y,w,h=rect
    pad=path.get('stroke_width',0)/2 if path.get('stroke') else 0
    left,top,right,bottom=x-pad,y-pad,x+w+pad,y+h+pad
    def line(a,b):
        lo,hi=0.,1.
        for start,end,lower,upper in zip(a,b,(left,top),(right,bottom)):
            delta=end-start
            if abs(delta)<1e-12:
                if start<lower or start>upper:return False
            else:
                u,v=(lower-start)/delta,(upper-start)/delta
                lo=max(lo,min(u,v));hi=min(hi,max(u,v))
                if lo>hi:return False
        return True
    def curve(points,depth=0):
        p=np.asarray(points)
        if p[:,0].max()<left or p[:,0].min()>right or p[:,1].max()<top or p[:,1].min()>bottom:return False
        if depth>=12:return True  # conservative: unresolved contact keeps the path
        if all(left<=v[0]<=right and top<=v[1]<=bottom for v in p):return True
        a=(p[:-1]+p[1:])/2;b=(a[:-1]+a[1:])/2;c=(b[0]+b[1])/2
        return curve([p[0],a[0],b[0],c],depth+1) or curve([c,b[1],a[2],p[3]],depth+1)
    for segment in path['segments']:
        if segment['kind']=='curve':
            if curve(segment['points']):return True
        elif line(segment['points'][0],segment['points'][-1]):return True
    if path.get('fill'):
        import cv2
        # CAD frames may be one path made of separate filled triangles.
        # Joining their contours invents filled diagonals across the page.
        contours=[];current=[]
        for segment in path['segments']:
            points=sample_segment(segment).tolist()
            if current and math.dist(current[-1],points[0])>.001:
                contours.append(current);current=[]
            current.extend(points if not current else points[1:])
            if len(current)>=3 and math.dist(current[0],current[-1])<.001:
                contours.append(current);current=[]
        if current:contours.append(current)
        for contour in contours:
            if len(contour)<3:continue
            polygon=np.asarray(contour,np.float32)
            if any(cv2.pointPolygonTest(polygon,p,False)>=0 for p in ((x,y),(x+w,y),(x,y+h),(x+w,y+h))):return True
    return False


class NativeVectorPage:
    """Owns native handles for one operation; no handles survive page.close().

    The index uses 56 bytes/path plus container handles for nested forms. Paths
    with thousands of points cost the same as rectangles until queried.
    """
    def __init__(self,path,page_index,max_segments=40000,max_paths=1000000,cache_directory=None):
        self.source_path=str(Path(path).resolve());self.page_index=page_index
        self.doc=pdfium.PdfDocument(path);self.page=self.doc[page_index]
        self.max_segments=max_segments;self.max_paths=max_paths
        w,h=self.page.get_size();self.size=(w,h)
        self.converter=pdfium.PdfPosConv(self.page,(0,0,round(w*1000),round(h*1000),0))
        self.parents={};self.nested={};self.image_regions=[];self.has_images=False;self.truncated=False;self.decoded=0;self.index_cache_hit=False
        self.cache={};self.cache_segments=0;self.clipped_geometry_segments=0;self.limited_queries=0;self.clipped=set();self.clipped_info={}
        source=Path(path);stat=source.stat()
        key=hashlib.sha256(json.dumps(['native-v077-selection',str(source.resolve()),stat.st_size,stat.st_mtime_ns,page_index,max_paths]).encode()).hexdigest()
        self.cache_file=Path(cache_directory)/(key+'.npz') if cache_directory else None
        try:
            if not self._load_index():
                self._index();self._save_index()
            self.x_order=np.argsort(self.bounds[:,0],kind="stable")
            self.x_sorted=self.bounds[self.x_order,0]
        except BaseException: self.close();raise

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):
        self.cache.clear();self.parents.clear();self.nested.clear();self.page.close();self.doc.close()

    def _load_index(self):
        if not self.cache_file or not self.cache_file.is_file():return False
        try:
            with np.load(self.cache_file,allow_pickle=False) as cached:
                index=cached['index']
                if index.ndim!=2 or index.shape[1]!=7 or len(index)>self.max_paths or not np.isfinite(index).all():return False
                count=pdfium.raw.FPDFPage_CountObjects(self.page)
                if len(index) and (index[:,4].min()<0 or index[:,4].max()>=count or not np.equal(index[:,4],np.floor(index[:,4])).all()):return False
                self.index=index;self.bounds=index[:,:4]
                self.image_regions=cached['image_regions'].tolist()
                self.has_images=bool(cached['has_images']);self.truncated=bool(cached['truncated'])
            self.index_cache_hit=True;return True
        except (OSError,ValueError,KeyError):return False

    def _save_index(self):
        # Store stable top-level object numbers, NEVER process-local pointers.
        # Nested Forms currently rebuild their index; their handles are local.
        if not self.cache_file or self.parents:return
        temporary=self.cache_file.with_suffix(f'.{os.getpid()}.tmp')
        try:
            self.cache_file.parent.mkdir(parents=True,exist_ok=True)
            with temporary.open('wb') as stream:
                np.savez_compressed(stream,index=self.index,has_images=self.has_images,truncated=self.truncated,image_regions=np.asarray(self.image_regions).reshape(-1,4))
            temporary.replace(self.cache_file)
        except OSError:temporary.unlink(missing_ok=True)

    def _index(self):
        chunks=[];rows=[];n=0;root_index=-1
        for obj in self.page.get_objects():
            if obj.level==0:root_index+=1
            if obj.type==pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                self.has_images=True
                l,b,r,t=obj.get_bounds();points=[(l,b),(l,t),(r,b),(r,t)]
                parent=obj.container
                while parent is not None:
                    matrix=parent.get_matrix();points=[matrix.on_point(*p) for p in points];parent=parent.container
                pixels=np.asarray([self.converter.to_bitmap(*p) for p in points])/1000
                self.image_regions.append(bbox(pixels))
            if obj.type!=pdfium.raw.FPDF_PAGEOBJ_PATH:continue
            if n>=self.max_paths:self.truncated=True;break
            l,b,r,t=obj.get_bounds();points=[(l,b),(l,t),(r,b),(r,t)]
            parent=obj.container
            while parent is not None:
                matrix=parent.get_matrix();points=[matrix.on_point(*p) for p in points];parent=parent.container
            pixels=[self.converter.to_bitmap(*p) for p in points]
            x=min(p[0] for p in pixels)/1000;y=min(p[1] for p in pixels)/1000
            right=max(p[0] for p in pixels)/1000;bottom=max(p[1] for p in pixels)/1000
            rows.append((x,y,right-x,bottom-y,root_index,pdfium.raw.FPDFPath_CountSegments(obj),int(chromatic(_style(obj)))))
            if obj.container is not None:
                self.parents[n]=obj.container;self.nested[n]=obj.raw
            n+=1
            if len(rows)==4096:chunks.append(np.asarray(rows,dtype=np.float64));rows=[]
        if rows:chunks.append(np.asarray(rows,dtype=np.float64))
        self.index=np.concatenate(chunks) if chunks else np.empty((0,7))
        self.bounds=self.index[:,:4]

    def query(self,rect,tolerance=.6):
        x,y,w,h=rect;b=self.bounds
        lo=np.searchsorted(self.x_sorted,x-tolerance,'left')
        hi=np.searchsorted(self.x_sorted,x+w+tolerance,'right')
        ids=self.x_order[lo:hi];local=b[ids]
        valid=(local[:,1]>=y-tolerance)&(local[:,0]+local[:,2]<=x+w+tolerance)&(local[:,1]+local[:,3]<=y+h+tolerance)
        return np.sort(ids[valid])

    def decode(self,ids,*,preserve=False):
        if sum(self.index[int(i),5] for i in ids)>self.max_segments:
            self.limited_queries+=1;return None
        result=[]
        for i in ids:
            i=int(i)
            if i not in self.cache:
                raw=self.nested[i] if i in self.nested else pdfium.raw.FPDFPage_GetObject(self.page,int(self.index[i,4]))
                obj=pdfium.PdfObject(raw,page=self.page,container=self.parents.get(i))
                value=_decode(obj,self.converter);self.decoded+=1
                if value and not _clip_preserves_geometry(obj,value,self.converter):
                    keep_geometry=len(value['segments'])<=512 and self.clipped_geometry_segments+len(value['segments'])<=min(40000,self.max_segments)
                    self.clipped_info[i]={'segment_count':len(value['segments']),'bbox':value['bbox'],
                                          'chromatic':chromatic(value),
                                          'geometry':value if keep_geometry else None}
                    if keep_geometry:self.clipped_geometry_segments+=len(value['segments'])
                    value=None;self.clipped.add(i)
                if value:value['id']=i
                if self.cache_segments+self.index[i,5]>self.max_segments:
                    self.cache.clear();self.cache_segments=0
                self.cache[i]=value;self.cache_segments+=self.index[i,5]
            if self.cache[i] is not None:result.append(self.cache[i])
        return result if preserve else deduplicate(result)

    def template_signature(self,selection,items=()):
        # A selection is authoritative. Partial/clipped geometry uses the full
        # selection raster rather than silently retaining only complete paths.
        b=self.bounds;x,y,w,h=selection
        ids=np.flatnonzero((b[:,0]<x+w)&(b[:,1]<y+h)&
            (b[:,0]+b[:,2]>x)&(b[:,1]+b[:,3]>y))
        paths=self.decode(ids,preserve=True)
        if paths is not None:paths=[p for p in paths if intersects_selection(p,selection)]
        from .text_engine import intersection
        if any(intersection(selection,r)>0 for r in self.image_regions):return None
        relevant_clips=[int(i) for i in ids if int(i) in self.clipped and
            (not self.clipped_info[int(i)].get('geometry') or
             intersects_selection(self.clipped_info[int(i)]['geometry'],selection))]
        if not paths or self.truncated or relevant_clips:return None
        if any(not contains(selection,p['bbox'],.001) for p in paths):return None
        value=signature(paths,preserve_selection=True)
        if value:
            value.update(native_local=True,context_paths=[],foreground='all',core_fill=False,
                         preserved_paths=len(paths),removed_paths=0)
        return value

    def find(self,reference,items=(),expected='',progress=lambda p:None):
        anchor_pool=[p for p in reference['paths'] if len(p['segments'])>=3] or reference['paths']
        anchor=max(anchor_pool,key=lambda p:max(p['bbox'][2:])*math.sqrt(min(64,len(p['segments']))))
        # Bounds include stroke expansion. Use a generous coarse filter; the
        # full native contour and dimensions are verified below.
        aw,ah=sorted(anchor['bbox'][2:]);dims=np.sort(self.bounds[:,2:4],axis=1)
        mask=(dims[:,1]>=ah*.75)&(dims[:,1]<=ah*1.3+2)&(dims[:,0]>=max(0,aw*.65-2))&\
             (dims[:,0]<=aw*1.35+2)&(self.index[:,5]<=len(anchor['segments'])*4+8)
        from .document_regions import legend_regions, region_for, reference_frames
        regions=legend_regions(self,items)
        # Legend exemplars may deliberately use a different drawing scale.
        # Broaden scale only in a verified legend table; never in the takeoff area.
        legend_ids=set()
        for region in regions:
            legend_ids.update(map(int,self.query(region['rect'])))
        for i in legend_ids:
            if ah*.35<=dims[i,1]<=ah*3+2 and dims[i,0]<=aw*3+2:mask[i]=True
        if reference.get('source_legend'):
            mask=(dims[:,1]>=ah*.35)&(dims[:,1]<=ah*3+2)&(dims[:,0]<=aw*3+2)&(self.index[:,5]<=len(anchor['segments'])*4+8)
        ids=list(np.flatnonzero(mask));seeded=set()
        # Exact native labels prioritize local shape hypotheses, never become
        # detections themselves and never replace the independent text gate.
        radius=max(reference['bbox'][2:])*3+24
        for item in items:
            if item.normalized_text==expected:
                x,y=item.center
                seeded.update(int(i) for i in ids if abs(self.bounds[i,0]-x)<radius and abs(self.bounds[i,1]-y)<radius)
        ids.sort(key=lambda i:int(i) not in seeded)
        generator=VectorCandidateGenerator();hits=[];seen=set();rejected=0;clipped_relevant=0
        reference_points=np.concatenate([sample_segment(s) for p in reference['paths'] for s in p['segments']])
        for k,i in enumerate(ids):
            paths=self.decode([i])
            if not paths:
                clipped=self.clipped_info.get(int(i))
                if clipped and clipped['segment_count']==len(anchor['segments']):
                    clipped_relevant+=1
                continue
            path=paths[0]
            if painted_fill(anchor)!=painted_fill(path):continue
            if reference.get('core_fill') and not path.get('fill'):continue
            from .vector_engine import circle_geometry
            circular_pair=circle_geometry(anchor) is not None and circle_geometry(path) is not None
            if not circular_pair:
                if len(path['segments'])!=len(anchor['segments']):continue
                if sorted(e['kind'] for e in path['segments'])!=sorted(e['kind'] for e in anchor['segments']):continue
            for rotation,translation,scale,angle in native_transforms(anchor,path,(.35,3.0) if reference.get('source_legend') or int(i) in legend_ids else (.80,1.25)):
                box=bbox(reference_points@rotation.T+translation)
                if not contains([0,0,*self.size],box,.01):continue
                key=(*[round(v,2) for v in box],round(angle,1))
                if key in seen:continue
                seen.add(key)
                if reference.get('core_fill'):
                    nearby=[path]
                else:
                    nearby_ids=self.query(box,max(3,min(box[2:])*.1))
                    if reference.get('foreground')=='chromatic' and chromatic(path):
                        nearby_ids=[j for j in nearby_ids if self.index[j,6]]
                    nearby=self.decode(nearby_ids,preserve=reference.get("preserve_selection",False))
                    if nearby is not None:nearby=[p for p in nearby if contains(box,p['bbox'],max(.2,min(box[2:])*.02))]
                if nearby is None:continue
                if reference.get('foreground')=='chromatic' and chromatic(path):
                    colored=[p for p in nearby if chromatic(p)]
                    if colored:nearby=colored
                evidence=generator.verify(reference,nearby,rotation,translation,box)
                if not evidence['verified'] and len(nearby)>len(reference['paths']):
                    connected=connected_geometry(reference,nearby,path)
                    if len(connected)<len(nearby):
                        alternative=generator.verify(reference,connected,rotation,translation,box)
                        if alternative['verified']:
                            evidence=alternative
                            evidence['verification_method']='native_connected_geometry'
                            evidence['ignored_background_paths']=len(nearby)-len(connected)
                            nearby=connected
                    if not evidence['verified'] and len(reference['paths'])>1:
                        group=paint_group(reference,nearby,path)
                        alternative=generator.verify(reference,group,rotation,translation,box)
                        if alternative['verified']:
                            evidence=alternative
                            evidence['verification_method']='native_paint_group'
                            evidence['ignored_background_paths']=len(nearby)-len(group)
                            nearby=group
                if evidence['verified']:
                    from .color_features import native_color_signature
                    hits.append({'rect':box,'score':evidence['graphic_score'],'rotation':angle,'scale':scale,
                        'color_signature':native_color_signature(nearby),
                        'source':'native_text_anchor' if int(i) in seeded else 'native_shape',**evidence})
                else:rejected+=1
            if k%25==0:progress(round(100*k/max(1,len(ids))))
        progress(100)
        return hits,{'anchor_candidates':len(ids),'verified_poses':len(hits),'indexed_paths':len(self.index),'decoded_paths':self.decoded,
                     'text_seeded_paths':len(seeded),'geometry_rejected':rejected,'index_bytes':self.index.nbytes,
                     'truncated':self.truncated,'has_images':self.has_images,'image_regions':self.image_regions,'index_cache_hit':self.index_cache_hit,
                     'limited_queries':self.limited_queries,'clipped_paths':len(self.clipped),
                     'clipped_anchor_paths':clipped_relevant,'regions':regions,'annotation_frames':reference_frames(self)}


def native_transforms(anchor,path,scale_range=(.80,1.25)):
    # Fit cardinal transforms to complete bounds before short-edge hypotheses.
    # Tiny polygonal circles/outlined glyphs have quantized short chords, which
    # are poor rotation estimators. Every hypothesis still needs full verification.
    aw,ah=anchor['bbox'][2:];bw,bh=path['bbox'][2:]
    if min(aw,ah,bw,bh)>.1:
        ac=np.array(anchor['bbox'][:2])+np.array([aw,ah])/2
        bc=np.array(path['bbox'][:2])+np.array([bw,bh])/2
        for angle in (0,90,180,270):
            rw,rh=(ah,aw) if angle%180 else (aw,ah)
            scale=(bw+bh)/(rw+rh)
            if not scale_range[0]<=scale<=scale_range[1]:continue
            if max(abs(rw*scale-bw),abs(rh*scale-bh))>max(.15,.025*max(bw,bh)):continue
            rad=math.radians(angle)
            rotation=np.array([[math.cos(rad),-math.sin(rad)],[math.sin(rad),math.cos(rad)]])*scale
            yield rotation,bc-rotation@ac,float(scale),float(angle)
            if max(abs(rw-bw),abs(rh-bh))<=.15 and abs(scale-1)>.0001 and scale_range[0]<=1<=scale_range[1]:
                rigid=rotation/scale
                yield rigid,bc-rigid@ac,1.,float(angle)
    # A circular anchor has no privileged quarter-curve chord. PDF rounding
    # can tilt that chord and shift the far end of an elongated device.
    if all(len(p['segments'])==4 and all(e['kind']=='curve' for e in p['segments']) and
           min(p['bbox'][2:])/max(p['bbox'][2:])>.94 for p in (anchor,path)):
        aw,ah=anchor['bbox'][2:];bw,bh=path['bbox'][2:]
        scale=(bw+bh)/(aw+ah)
        if scale_range[0]<=scale<=scale_range[1]:
            ac=np.array(anchor['bbox'][:2])+np.array([aw,ah])/2
            bc=np.array(path['bbox'][:2])+np.array([bw,bh])/2
            for angle in (0,90,180,270):
                rad=math.radians(angle);rotation=np.array([[math.cos(rad),-math.sin(rad)],[math.sin(rad),math.cos(rad)]])*scale
                yield rotation,bc-rotation@ac,float(scale),float(angle)
    # Longest edge avoids unstable rotations from sub-pixel short edges.
    line=max(anchor['segments'],key=lambda s:math.dist(s['points'][0],s['points'][-1]))
    p0,p1=np.array(line['points'])[[0,-1]];delta=p1-p0;length=np.linalg.norm(delta)
    if length<.05:return
    for edge in path['segments']:
        if edge['kind']!=line['kind']:continue
        for reverse in (False,True):
            q0,q1=np.array(edge['points'])[[0,-1]][::-1 if reverse else 1]
            target=q1-q0;scale=np.linalg.norm(target)/length
            if not scale_range[0]<=scale<=scale_range[1]:continue
            angle=math.atan2(target[1],target[0])-math.atan2(delta[1],delta[0])
            rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])*scale
            translation=q0-rotation@p0
            # Check complete anchor geometry, not a matching subsegment of a
            # longer body. Thin-width error is normalized by its own dimension.
            expected=bbox(np.concatenate([sample_segment(s) for s in anchor['segments']])@rotation.T+translation)
            if any(abs(a-b)>max(.15,.08*max(a,b)) for a,b in zip(expected[2:],path['bbox'][2:])):continue
            if any(abs(a-b)>max(.15,.02*max(path['bbox'][2:])) for a,b in zip(expected[:2],path['bbox'][:2])):continue
            yield rotation,translation,float(scale),math.degrees(angle)%360


def connected_geometry(reference,paths,anchor):
    """Separate complete connected symbols from contained, unrelated CAD clutter.

    This only proposes a subset: full geometry and filled-area validation still
    run afterwards. Endpoint attachment is required, not a crossing mid-line.
    """
    original_paths=paths
    ref_colors={tuple(p.get('color',[])[:3]) for p in reference['paths']}
    ref_widths=[p.get('stroke_width',0) for p in reference['paths'] if p.get('stroke')]
    uniform=len(ref_colors)==1 and (not ref_widths or max(ref_widths)-min(ref_widths)<.02)
    candidates=[]
    for p in paths:
        same_style=(p.get('color',[])[:3]==anchor.get('color',[])[:3] and
            abs(p.get('stroke_width',0)-anchor.get('stroke_width',0))<max(.02,anchor.get('stroke_width',0)*.08))
        if not uniform or same_style:candidates.append(p)
    paths=without_paint_caps(candidates)
    candidates=paths
    if len(candidates)<=len(reference['paths']):return candidates
    selected=[p for p in candidates if p is anchor or p.get('id')==anchor.get('id')]
    if not selected:return paths
    def near(points,edges):
        for edge in edges:
            samples=sample_segment(edge);a=samples[:-1];v=samples[1:]-a
            delta=points[:,None,:]-a[None,:,:]
            t=np.clip(np.sum(delta*v,axis=2)/np.maximum(np.sum(v*v,axis=1),1e-12),0,1)
            if np.min(np.linalg.norm(delta-t[:,:,None]*v,axis=2))<=.18:return True
        return False
    # Traverse each path pair at most once. Rebuilding all selected edges at
    # every iteration became quadratic work inside another quadratic loop on
    # dense architectural hatching.
    pending=[p for p in candidates if not any(p is q for q in selected)]
    frontier=list(selected)
    while frontier:
        q=frontier.pop();qx,qy,qw,qh=q['bbox']
        qends=np.asarray([pt for e in q['segments'] for pt in (e['points'][0],e['points'][-1])])
        remaining=[]
        for p in pending:
            px,py,pw,ph=p['bbox']
            if px>qx+qw+.18 or qx>px+pw+.18 or py>qy+qh+.18 or qy>py+ph+.18:
                remaining.append(p);continue
            pends=np.asarray([pt for e in p['segments'] for pt in (e['points'][0],e['points'][-1])])
            if near(pends,q['segments']) or near(qends,p['segments']):selected.append(p);frontier.append(p)
            else:remaining.append(p)
        pending=remaining
    # A later filled overprint of a matched circle/body cannot be hidden by
    # the style grouping. Keep it so the fill gate sees the effective variant.
    for p in without_paint_caps(original_paths):
        if p.get('fill') and not any(p is q for q in selected) and any(max(abs(a-b) for a,b in zip(p['bbox'],q['bbox']))<.15 for q in selected):selected.append(p)
        # A disconnected inner arc/stroke of the same device paint is a
        # variant feature, not background. Keep it even without endpoint contact.
        if (not any(p is q for q in selected) and contains(anchor['bbox'],p['bbox'],.15)
                and p.get('color',[])[:3]==anchor.get('color',[])[:3]
                and abs(p.get('stroke_width',0)-anchor.get('stroke_width',0))<.02):selected.append(p)
    return deduplicate(selected)


def paint_group(reference,paths,anchor):
    """CAD entity command runs can separate touching architectural clutter.

    Complete shape verification remains mandatory. Preserve simple closed areas
    and connecting strokes even outside the run, so fill/inner-line variants
    cannot disappear merely because their paint commands were emitted later.
    """
    paths=without_paint_caps(paths)
    if 'id' not in anchor:return paths
    source_ids=[p['id'] for p in reference['paths'] if 'id' in p]
    window=max(16,(max(source_ids)-min(source_ids))*2) if source_ids else 64
    group=[p for p in paths if abs(p.get('id',anchor['id'])-anchor['id'])<=window]
    if not group:return paths
    samples=[sample_segment(e) for p in group for e in p['segments']]
    segments=np.concatenate([np.stack((a[:-1],a[1:]),axis=1) for a in samples])
    def attached(point):
        a=segments[:,0];v=segments[:,1]-a;delta=np.asarray(point)-a
        t=np.clip(np.sum(delta*v,axis=1)/np.maximum(np.sum(v*v,axis=1),1e-12),0,1)
        return np.min(np.linalg.norm(delta-t[:,None]*v,axis=1))<=.18
    for p in paths:
        if any(p is q for q in group):continue
        es=p['segments']
        closed=3<=len(es)<=8 and np.linalg.norm(np.array(es[0]['points'][0])-es[-1]['points'][-1])<.15
        link=len(es)==1 and all(attached(pt) for pt in (es[0]['points'][0],es[0]['points'][-1]))
        inner=(contains(anchor['bbox'],p['bbox'],.15) and
               p.get('color',[])[:3]==anchor.get('color',[])[:3] and
               abs(p.get('stroke_width',0)-anchor.get('stroke_width',0))<.02)
        if closed or link or inner:group.append(p)
    return deduplicate(group)
