"""Visible-only verification: proven occluders, never reconstructed pixels.

Recovered proposals are always REVIEW downstream, never automatic quantities.
"""
import math
import cv2
import numpy as np
from .text_engine import intersection, transformed_layout
from .matcher import template_variant


def label_proposals(template, expected, items, meta):
    layout=template.get('association')
    if not expected or not layout or not layout.get('offset') or template.get('source')=='LEGEND':return []
    w,h=template['rect'][2:]
    if min(w,h)<=0 or max(w,h)>150:return []
    result=[];seen=set()
    for item in items:
        if item.source!='pdf_native' or item.normalized_text!=expected:continue
        ratio=min(item.bbox[2:])/max(layout.get('glyph_size',min(item.bbox[2:])),.1)
        if not .8<=ratio<=1.25:continue
        for angle in (0,90,180,270):
            sw,sh=(h*ratio,w*ratio) if angle%180 else (w*ratio,h*ratio)
            for label_angle in (0,-angle):
                offset=transformed_layout(layout,label_angle)['offset']
                cx=item.center[0]-offset[0]*max(sw,sh)
                cy=item.center[1]-offset[1]*max(sw,sh)
                rect=[cx-sw/2,cy-sh/2,sw,sh]
                if rect[0]<0 or rect[1]<0 or rect[0]+sw>meta['width'] or rect[1]+sh>meta['height']:continue
                key=(*[round(v,2) for v in rect],angle)
                if key in seen:continue
                seen.add(key)
                result.append(dict(rect=rect,verification_rect=rect,score=0.,scale=ratio,
                    rotation=-angle,raster_angle=angle,source='label_geometry_probe',recovery_only=(min(w,h)>=5 or min(w,h)/max(w,h)<.35)))
    return result


def native_text_mask(shape, box, items, scale):
    mask=np.zeros(shape,np.uint8);evidence=[]
    for item in items:
        if item.source!='pdf_native' or not intersection(box,item.bbox):continue
        x,y,w,h=item.bbox
        l=max(0,math.floor((x-box[0])*scale)-2);r=min(shape[1],math.ceil((x+w-box[0])*scale)+2)
        t=max(0,math.floor((y-box[1])*scale)-2);b=min(shape[0],math.ceil((y+h-box[1])*scale)+2)
        if l<r and t<b:
            mask[t:b,l:r]=1
            evidence.append({'kind':'native_text','bbox':item.bbox,'text':item.normalized_text})
    return mask,evidence


def external_line_mask(context, shape, padding):
    gray=cv2.cvtColor(context,cv2.COLOR_RGB2GRAY)
    ink=(gray<180).astype(np.uint8);h,w=shape
    mask=np.zeros(shape,np.uint8);evidence=[]
    min_length=max(12,round(min(w,h)+2*padding*.8))
    lines=cv2.HoughLinesP(ink*255,1,np.pi/180,threshold=max(10,min_length//2),
                         minLineLength=min_length,maxLineGap=3)
    distance=cv2.distanceTransform(1-ink,cv2.DIST_L2,3)
    for raw in (() if lines is None else np.asarray(lines).reshape(-1,4)[:200]):
        x1,y1,x2,y2=map(int,raw)
        a=np.array([x1-padding,y1-padding],float);b=np.array([x2-padding,y2-padding],float)
        direction=b-a;length=np.linalg.norm(direction)
        if length<min_length:continue
        unit=direction/length;normal=np.array([-unit[1],unit[0]])
        # Extend a hypothesis across intersections, requiring observed ink in
        # BOTH outside margins. Internal distinguishing strokes stay visible.
        extent=max(ink.shape)*2
        points=a[None,:]+np.arange(-extent,length+extent,.5)[:,None]*unit
        bounded=(points[:,0]>=-padding)&(points[:,0]<w+padding)&(points[:,1]>=-padding)&(points[:,1]<h+padding)
        points=points[bounded]
        inside=(points[:,0]>=0)&(points[:,0]<w)&(points[:,1]>=0)&(points[:,1]<h)
        indices=np.flatnonzero(inside)
        if len(indices)<6:continue
        before=points[:indices[0]];after=points[indices[-1]+1:]
        needed=max(6,padding)
        if min(len(before),len(after))<needed:continue
        supported=True
        for outside in (before[-needed:],after[:needed]):
            q=np.rint(outside+padding).astype(int)
            q[:,0]=np.clip(q[:,0],0,ink.shape[1]-1);q[:,1]=np.clip(q[:,1],0,ink.shape[0]-1)
            if np.mean(distance[q[:,1],q[:,0]]<=1.25)<.85:supported=False
        if not supported:continue
        a,b=points[0],points[-1]
        width=max(1,round(min(w,h)*.035))
        outer=points[~inside]+padding;broad=[]
        for side in (-1,1):
            q=np.rint(outer+normal*(width+2)*side).astype(int)
            valid=(q[:,0]>=0)&(q[:,0]<ink.shape[1])&(q[:,1]>=0)&(q[:,1]<ink.shape[0])
            if valid.any():broad.append(float(ink[q[valid,1],q[valid,0]].mean()))
        if broad and min(broad)>.5:continue
        cv2.line(mask,tuple(np.rint(a).astype(int)),tuple(np.rint(b).astype(int)),1,width*2+1)
        evidence.append({'kind':'external_line','endpoints':[a.tolist(),b.tolist()]})
    return mask,evidence


def visible_evidence(reference, candidate, unknown):
    if reference.shape[:2]!=candidate.shape[:2]:return None
    expected=cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY)<190
    actual=cv2.cvtColor(candidate,cv2.COLOR_RGB2GRAY)<190
    mask=unknown.astype(bool)
    if expected.sum()<25:return None
    hidden=float((expected&mask).sum()/expected.sum());area=float(mask.mean())
    if not .015<=hidden<=.28 or area>.28:return None
    known=~mask;ref=expected&known;obs=actual&known
    if obs.sum()<20:return None
    dt_obs=cv2.distanceTransform((~obs).astype(np.uint8),cv2.DIST_L2,3)
    dt_ref=cv2.distanceTransform((~ref).astype(np.uint8),cv2.DIST_L2,3)
    coverage=float((dt_obs[ref]<=1.25).mean());precision=float((dt_ref[obs]<=1.25).mean())
    h,w=ref.shape;quadrants=[]
    for ys in (slice(0,h//2),slice(h//2,h)):
        for xs in (slice(0,w//2),slice(w//2,w)):
            visible=ref[ys,xs];matched=(dt_obs[ys,xs]<=1.25)[visible]
            quadrants.append(bool(visible.sum()>=4 and len(matched) and matched.mean()>=.9))
    if coverage<.94 or precision<.94 or sum(quadrants)<3:return None
    return {'visible_coverage':coverage,'visible_precision':precision,'hidden_reference_fraction':hidden,
            'unknown_area_fraction':area,'supported_quadrants':sum(quadrants),
            'policy':'review_only','reconstructed_pixels':False}


def verify_partial(pdf,path,page,template,reference,candidate,items):
    box=candidate.get('verification_rect',candidate['rect']);x,y,w,h=box
    if min(w,h)<=0 or max(w,h)>150:return None
    angle=candidate.get('raster_angle',candidate.get('rotation',0))
    if abs(angle/90-round(angle/90))>.01:return None
    scale=candidate.get('verification_scale',2.);meta=pdf.inspect(path)[page]
    pixels=math.ceil(max(4.,min(w,h)*.35)*scale);pad=pixels/scale
    if x<pad or y<pad or x+w+pad>meta['width'] or y+h+pad>meta['height']:return None
    patch=pdf.render(path,page,scale,box)
    pattern=template_variant(reference,candidate.get('scale',1),angle)
    if pattern.shape[:2]!=patch.shape[:2]:
        if max(abs(a-b) for a,b in zip(pattern.shape[:2],patch.shape[:2]))>2:return None
        pattern=cv2.resize(pattern,(patch.shape[1],patch.shape[0]),interpolation=cv2.INTER_CUBIC)
    text_mask,text_evidence=native_text_mask(patch.shape[:2],box,items,scale)
    outer=pdf.render(path,page,scale,[x-pad,y-pad,w+2*pad,h+2*pad])
    line_mask,line_evidence=external_line_mask(outer,patch.shape[:2],pixels)
    unknown=text_mask|line_mask
    if not unknown.any():return None
    evidence=visible_evidence(pattern,patch,unknown)
    if evidence is None:return None
    evidence['occluders']=text_evidence+line_evidence
    return dict(verified=True,partial_occlusion=True,occlusion=evidence,
        geometry_score=evidence['visible_coverage'],feature_score=evidence['visible_precision'],
        graphic_score=min(evidence['visible_coverage'],evidence['visible_precision']),
        verification_method='visible_fragments_review',verification_reason='partial_occlusion_review')
