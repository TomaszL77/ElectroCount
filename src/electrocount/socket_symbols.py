"""Match a socket's complete body and its outlined designation independently.

CAD legends enlarge symbols and change text size. Tessellation and font size
are export details; the inner IP44 arc and the designation are device features.
No page coordinates or device names participate in candidate generation.
"""
import math
from pathlib import Path
import cv2
import numpy as np
from .vector_engine import bbox, contains, sample_segment
from .native_geometry import deduplicate


def socket_frame(path):
    if path.get('fill') or not path.get('stroke') or not 6 <= len(path['segments']) <= 80:
        return None
    samples = np.concatenate([sample_segment(s) for s in path['segments']])
    first, last = samples[0], samples[-1]
    diameter = float(np.linalg.norm(last-first))
    if diameter < 2 or diameter > 60:
        return None
    origin = (first+last)/2
    tangent = (last-first)/diameter
    normal = np.array([-tangent[1], tangent[0]])
    if np.mean((samples-origin)@normal) > 0:
        normal = -normal
    radius = np.linalg.norm(samples-origin, axis=1)
    local = (samples-origin)@np.stack((tangent,normal), axis=1)/diameter
    if np.max(np.abs(radius/diameter-.5)) > .025 or local[:,1].max() > .025 or local[:,1].min() > -.45:
        return None
    return origin, tangent, normal, diameter


def local_paths(paths, frame):
    origin,tangent,normal,diameter = frame
    matrix = np.stack((tangent,normal), axis=1)/diameter
    result=[]
    for p in paths:
        segments=[dict(kind=s['kind'],points=((np.asarray(s['points'])-origin)@matrix).tolist()) for s in p['segments']]
        result.append({**p,'segments':segments,'bbox':bbox([v for s in segments for v in s['points']])})
    return result


def body_and_designation(paths, anchor, frame):
    local = local_paths(paths,frame)
    color=anchor.get('color',[])[:3]
    body=[];designation=[]
    for raw,p in zip(paths,local):
        if raw.get('color',[])[:3] != color:
            continue
        if raw.get('stroke') and not raw.get('fill') and contains([-.52,-1.03,1.04,1.06],p['bbox'],.015):
            body.append(p)
        elif raw.get('fill') and contains([-.85,-.18,1.7,1.05],p['bbox'],.01):
            # Ignore microscopic round line caps, preserve all glyph contours.
            if max(p['bbox'][2:])>.075:
                designation.append(p)
    return deduplicate(body),designation


def closed_frame(path):
    if path.get('fill') or not path.get('stroke') or not 4<=len(path['segments'])<=128:return None
    x,y,w,h=path['bbox']
    if min(w,h)<2 or max(w,h)>60 or not .85<w/h<1.18:return None
    samples=np.concatenate([sample_segment(s) for s in path['segments']])
    if np.linalg.norm(samples[0]-samples[-1])>.02:return None
    center=np.array([x+w/2,y+h/2]);radius=np.linalg.norm(samples-center,axis=1)/(w/2)
    circle=np.max(np.abs(radius-1))<.04
    rectangle=len(path['segments'])==4 and all(s['kind']=='line' for s in path['segments'])
    if not circle and not rectangle:return None
    return np.array([x+w/2,y]),np.array([1.,0.]),np.array([0.,-1.]),w


def closed_parts(paths,anchor,frame):
    local=local_paths(paths,frame);body=[];glyphs=[]
    color=anchor.get('color',[])[:3]
    for raw,p in zip(paths,local):
        if raw.get('stroke') and not raw.get('fill') and raw.get('color',[])[:3]==color and contains([-.53,-1.2,1.06,1.23],p['bbox'],.01):
            body.append(p)
        elif raw.get('fill') and max(raw.get('color',[255,255,255])[:3])>0 and min(raw.get('color',[255,255,255])[:3])>120:
            continue
        elif raw.get('fill') and contains([-.6,-1.1,1.2,1.7],p['bbox'],.01):
            if max(p['bbox'][2:])>.075:glyphs.append(p)
    return deduplicate(body),glyphs


def raster_paths(paths, bounds, size=96, fill=False):
    mask=np.zeros((size,size),np.uint8)
    if not paths:return mask
    x,y,w,h=bounds;scale=(size-8)/max(w,h,.001)
    offset=np.array([4+(size-8-w*scale)/2,4+(size-8-h*scale)/2])
    for p in paths:
        contours=[];current=[];previous=None
        for s in p['segments']:
            points=sample_segment(s)
            if previous is not None and np.linalg.norm(points[0]-previous)>.002:
                contours.append(current);current=[]
            current.extend(points.tolist());previous=points[-1]
        if current:contours.append(current)
        polygons=[np.rint((np.asarray(c)-[x,y])*scale+offset).astype(np.int32) for c in contours if len(c)>1]
        if fill:
            cv2.fillPoly(mask,polygons,255)  # even-odd contours preserve glyph holes
        else:
            for polygon in polygons:cv2.polylines(mask,[polygon],False,255,2,cv2.LINE_8)
    return mask


def mask_agreement(a,b,tolerance=2):
    if not a.any() or not b.any():return 1. if not a.any() and not b.any() else 0.
    da=cv2.distanceTransform((a==0).astype(np.uint8),cv2.DIST_L2,3)
    db=cv2.distanceTransform((b==0).astype(np.uint8),cv2.DIST_L2,3)
    return float(min((db[a>0]<=tolerance).mean(),(da[b>0]<=tolerance).mean()))


def definition(signature):
    if not signature:return None
    if signature.get('socket_kind')=='network':
        body=[p for p in signature['paths'] if p.get('stroke') and not p.get('fill')]
        glyphs=[p for p in signature['paths'] if p.get('fill')]
        if len(body)<3 or not glyphs:return None
        x,y,w,h=bbox([v for p in body for s in p['segments'] for v in s['points']])
        frame=(np.array([x+w/2,y]),np.array([1.,0.]),np.array([0.,-1.]),w)
        local_body=local_paths(body,frame);local_glyphs=local_paths(glyphs,frame)
        gb=bbox([v for p in local_glyphs for s in p['segments'] for v in s['points']])
        return {'body':raster_paths(local_body,[-.55,-1.06,1.1,1.12]),
            'designation':raster_paths(local_glyphs,gb,fill=True),'diameter':w,'has_designation':True,
            'frame':frame,'kind':'network','color':body[0].get('color',[])[:3],
            'glyph_color':glyphs[0].get('color',[])[:3],'glyph_ratio':max(gb[2:]),
            'glyph_center':[gb[0]+gb[2]/2,gb[1]+gb[3]/2]}
    choices=[(p,socket_frame(p)) for p in signature['paths']]
    choices=[(p,f) for p,f in choices if f is not None]
    kind='cup'
    if not choices:
        if signature.get('socket_kind')!='closed':return None
        choices=[(p,closed_frame(p)) for p in signature['paths']]
        choices=[(p,f) for p,f in choices if f is not None]
        if not choices:return None
        kind='closed'
    anchor,frame=max(choices,key=lambda pair:pair[1][3])
    body,designation=(body_and_designation if kind=='cup' else closed_parts)(signature['paths'],anchor,frame)
    if len(body)<(3 if kind=='cup' else 1):return None
    if kind=='closed' and not designation and len(body)<2:return None
    # A dirty selection must remain authoritative. Never silently discard
    # an unrelated symbol or an architectural stroke from a user selection.
    chosen={p.get('id') for p in body+designation if 'id' in p}
    if any(p.get('id') not in chosen and max(p['bbox'][2:])>.15 for p in signature['paths']):return None
    body_mask=raster_paths(body,[-.55,-1.22,1.1,1.28] if kind=='closed' else [-.55,-1.06,1.1,1.12])
    glyph_box=bbox([v for p in designation for s in p['segments'] for v in s['points']]) if designation else [0,0,1,1]
    glyph_mask=raster_paths(designation,glyph_box,fill=True)
    return {'body':body_mask,'designation':glyph_mask,'diameter':frame[3],
            'has_designation':bool(designation),'frame':frame,'kind':kind,'color':anchor.get('color',[])[:3]}


def scan(native,diameter,progress=lambda p:None,closed_colors=()):
    """Decode coarse arc candidates once for a whole legend catalogue."""
    dims=np.sort(native.bounds[:,2:4],axis=1)
    ids=np.flatnonzero((dims[:,1]>=diameter*.3)&(dims[:,1]<=diameter*3.2+2)&
        (dims[:,0]>=diameter*.12)&(dims[:,0]<=diameter*1.8+2)&
        (native.index[:,5]>=4)&(native.index[:,5]<=130))
    candidates=[]
    for count,i in enumerate(ids):
        decoded=native.decode([i])
        if not decoded:continue
        anchor=decoded[0];frame=socket_frame(anchor);kind='cup'
        if frame is None and anchor.get('color',[])[:3] in closed_colors:
            frame=closed_frame(anchor);kind='closed'
        if frame is None:continue
        origin,tangent,normal,d=frame
        corners=np.asarray([[-.9,-1.3],[.9,-1.3],[-.9,.98],[.9,.98]])
        region=bbox(origin+(corners[:,0,None]*tangent+corners[:,1,None]*normal)*d)
        nearby=native.decode(native.query(region,.15),preserve=True)
        if nearby is None:continue
        body,glyphs=(body_and_designation if kind=='cup' else closed_parts)(nearby,anchor,frame)
        if len(body)<(3 if kind=='cup' else 1):continue
        bm=raster_paths(body,[-.55,-1.22,1.1,1.28] if kind=='closed' else [-.55,-1.06,1.1,1.12])
        gb=bbox([v for p in glyphs for s in p['segments'] for v in s['points']]) if glyphs else [0,0,1,1]
        gm=raster_paths(glyphs,gb,fill=True)
        all_paths=[p for p in nearby if p.get('id') in {q.get('id') for q in body+glyphs}]
        rect=bbox([v for p in all_paths for s in p['segments'] for v in s['points']])
        pad=max((p.get('stroke_width',0)/2 for p in all_paths if p.get('stroke')),default=0)+.05
        rect=[rect[0]-pad,rect[1]-pad,rect[2]+2*pad,rect[3]+2*pad]
        candidates.append({'rect':rect,'body':bm,'designation':gm,'has_designation':bool(glyphs),
            'frame':frame,'anchor_id':int(i),'glyph_box':gb,'kind':kind,'color':anchor.get('color',[])[:3]})
        if count%50==0:progress(round(100*count/max(1,len(ids))))
    from .domain import overlap_metrics
    kept=[]
    for c in sorted(candidates,key=lambda v:v['frame'][3],reverse=True):
        if not any(c['kind']==other['kind'] and overlap_metrics(c['rect'],other['rect'])[0]>.55 for other in kept):kept.append(c)
    progress(100)
    return kept


def scan_network(native,references):
    candidates=[];colors=[r['glyph_color'] for r in references]
    unique={}
    for r in references:unique.setdefault((r['body'].tobytes(),round(r['glyph_ratio'],3)),r)
    seeds=list(unique.values())
    dims=native.bounds[:,2:4]
    ids=np.flatnonzero((native.index[:,6]>0)&(native.index[:,5]<=160)&
                      (dims.min(axis=1)>=1)&(dims.max(axis=1)<=21))
    for i in ids:
        decoded=native.decode([i])
        if not decoded:continue
        glyph=decoded[0]
        if not glyph.get('fill') or glyph.get('color',[])[:3] not in colors:continue
        x,y,w,h=glyph['bbox']
        if min(w,h)<1 or max(w,h)>20:continue
        center=np.array([x+w/2,y+h/2])
        for r in seeds:
            for factor in (1.,):
                d=max(w,h)/r['glyph_ratio']*factor
                for angle in (0,90,180,270):
                    rad=math.radians(angle);tangent=np.array([math.cos(rad),math.sin(rad)])
                    normal=np.array([math.sin(rad),-math.cos(rad)])
                    origin=center-(tangent*r['glyph_center'][0]+normal*r['glyph_center'][1])*d
                    frame=(origin,tangent,normal,d)
                    corners=np.asarray([[-.65,-1.1],[.65,-1.1],[-.65,.6],[.65,.6]])
                    region=bbox(origin+(corners[:,0,None]*tangent+corners[:,1,None]*normal)*d)
                    nearby=native.decode(native.query(region,.1),preserve=True) or []
                    body=[]
                    for raw,p in zip(nearby,local_paths(nearby,frame)):
                        if raw.get('stroke') and not raw.get('fill') and raw.get('color',[])[:3]==r['color'] and contains([-.53,-1.03,1.06,1.06],p['bbox'],.01):body.append(p)
                    if len(body)<3:continue
                    local_glyph=local_paths([glyph],frame)
                    bm=raster_paths(body,[-.55,-1.06,1.1,1.12])
                    if mask_agreement(r['body'],bm,2)<.9:continue
                    rawbody=[p for p in nearby if p.get('id') in {q.get('id') for q in body}]
                    rect=bbox([v for p in rawbody+[glyph] for s in p['segments'] for v in s['points']])
                    pad=max((p.get('stroke_width',0)/2 for p in rawbody),default=0)+.05
                    rect=[rect[0]-pad,rect[1]-pad,rect[2]+2*pad,rect[3]+2*pad]
                    gb=local_glyph[0]['bbox']
                    candidates.append({'rect':rect,'body':bm,'designation':raster_paths(local_glyph,gb,fill=True),
                        'has_designation':True,'frame':frame,'anchor_id':int(i),'glyph_box':gb,
                        'kind':'network','color':r['color']})
    # Keep the best full-body hypothesis at each glyph, not the first scale.
    kept={}
    for c in candidates:
        score=max(mask_agreement(r['body'],c['body'],1.5) for r in references)
        if c['anchor_id'] not in kept or score>kept[c['anchor_id']][0]:kept[c['anchor_id']]=(score,c)
    return [c for score,c in kept.values()]


def match_candidate(reference,candidate):
    if reference.get('kind','cup')!=candidate.get('kind','cup'):return 0.,0.
    if reference.get('kind')=='closed' and reference['color']!=candidate['color']:return 0.,0.
    body=mask_agreement(reference['body'],candidate['body'],2 if reference.get('kind')=='network' else 1.5)
    # CAD text can retain the page's orientation while the socket turns.
    glyph=max(mask_agreement(reference['designation'],np.rot90(candidate['designation'],k).copy(),2) for k in range(4))
    if reference['has_designation'] != candidate['has_designation']:glyph=0.
    # Filled glyph agreement also checks ink amount, not only outlines.
    if reference['has_designation'] and candidate['has_designation']:
        ink=min((reference['designation']>0).sum(),(candidate['designation']>0).sum())/max(1,max((reference['designation']>0).sum(),(candidate['designation']>0).sum()))
        glyph=min(glyph,float(ink))
    return body,glyph


def find(native,signature,progress=lambda p:None,candidates=None):
    reference=definition(signature)
    if reference is None:return None
    candidates=scan(native,reference['diameter'],progress) if candidates is None else candidates
    hits=[];review=[]
    for c in candidates:
        body,glyph=match_candidate(reference,c)
        if body<.93 or glyph<.7:continue
        origin,tangent,normal,d=c['frame'];ro,rt,rn,rd=reference['frame']
        matrix=np.stack((tangent,normal),axis=1)@np.stack((rt,rn),axis=1).T*(d/rd)
        translation=origin-matrix@ro
        hit={'rect':c['rect'],'score':min(body,glyph),'graphic_score':min(body,glyph),
            'geometry_score':body,'feature_score':glyph,'verified':True,'source':'native_socket',
            'verification_method':'socket_body_and_designation','verification_reason':'complete_socket_features',
            'designation_score':glyph,'rotation':math.degrees(math.atan2(matrix[1,0],matrix[0,0]))%360,
            'scale':d/rd,'transform':[matrix[0,0],matrix[0,1],translation[0],matrix[1,0],matrix[1,1],translation[1]],
            'color_signature':{'dominant':[0,0,0],'fraction':1.}}
        (hits if glyph>=.9 else review).append(hit)
    return hits,review,{'indexed_paths':len(native.index),'generated_sockets':len(candidates),
                       'decoded_paths':native.decoded,'index_cache_hit':native.index_cache_hit,
                       'truncated':native.truncated,'limited_queries':native.limited_queries,
                       'clipped_paths':len(native.clipped)}


def catalogue_results(native,entries,progress=lambda p:None,strict=False):
    refs=[(e,definition(e['template'].get('signature'))) for e in entries]
    refs=[(e,r) for e,r in refs if r is not None]
    if not refs:raise ValueError('Dodaj wzorce gniazd z legendy wraz z ich oznaczeniami.')
    candidates=scan(native,max(r['diameter'] for e,r in refs),lambda p:progress(round(p*.9)),
                    closed_colors=[r['color'] for e,r in refs if r['kind']=='closed'])
    networks=[r for e,r in refs if r['kind']=='network']
    if networks:candidates.extend(scan_network(native,networks))
    from .domain import overlap_metrics
    sources=[e for e,r in refs if e['template'].get('source')=='LEGEND'
        and e.get('template_path') and str(Path(e['template_path']).resolve())==native.source_path
        and e['template']['page']==native.page_index]
    if any(e['template'].get('reference_page_only') for e in sources):candidates=[]
    else:
        candidates=[c for c in candidates if not any(overlap_metrics(c['rect'],
            e['template'].get('selection_bbox',e['template']['rect']))[1]>.8 for e in sources)]
    progress(100)
    results=[]
    warnings=[]
    if native.truncated or native.limited_queries:
        warnings.append('Niepełny odczyt geometrii strony. Sprawdź pominięte obszary ręcznie.')
    for entry,reference in refs:
        results.append({'group_id':entry['group_id'],'result':{
            'template':entry['template'],'label':entry.get('label',''),
            'matches':[],'review':[],'legend_matches':[],'discovered_other_label':[],
            'rejected_candidates':[],'text_items':[],'coverage_warnings':warnings,
            'counts':{},'stages':{'generated':len(candidates),'verified':0,'rejected':0,
                'vector_first':True,'raster_used':False,'native_local':{'indexed_paths':len(native.index),
                 'index_cache_hit':native.index_cache_hit,'decoded_paths':native.decoded}},
            'pipeline':{'version':'socket-catalogue-v1','local_only':True,
                'active':['native_socket_body','outlined_designation','ip44_inner_features'],
                'confidence_kind':'shape_agreement_not_probability'}}})
    for candidate in candidates:
        ranked=[]
        for index,(entry,reference) in enumerate(refs):
            body,glyph=match_candidate(reference,candidate)
            if body>=.93:ranked.append((glyph,body,index))
        if not ranked:continue
        ranked.sort(reverse=True)
        glyph,body,index=ranked[0]
        margin=glyph-ranked[1][0] if len(ranked)>1 else glyph
        entry,reference=refs[index]
        # Font-weight differences permit a catalogue choice only when it wins
        # clearly against every alternative with the same independently verified body.
        minimum=.7 if reference.get('kind')=='network' else .78
        certain=glyph>=.9 if strict else glyph>=minimum and margin>=.15
        result=results[index]['result']
        origin,tangent,normal,d=candidate['frame'];ro,rt,rn,rd=reference['frame']
        matrix=np.stack((tangent,normal),axis=1)@np.stack((rt,rn),axis=1).T*(d/rd)
        translation=origin-matrix@ro
        reason='socket_type_verified' if certain else 'socket_type_needs_review'
        hit={'rect':candidate['rect'],'label':entry.get('label',''),'label_bbox':None,
            'graphic_score':min(body,glyph),'geometry_score':body,'feature_score':glyph,
            'text_score':glyph,'spatial_association_score':0.,'confidence':min(body,glyph),
            'reason':reason,'status':'MATCH' if certain else 'REVIEW',
            'candidate_source':'native_socket','verification_method':'socket_body_and_designation',
            'verification_details':{'rotation':math.degrees(math.atan2(matrix[1,0],matrix[0,0]))%360,
                'scale':d/rd,'transform':[matrix[0,0],matrix[0,1],translation[0],matrix[1,0],matrix[1,1],translation[1]],
                'body_score':body,'designation_score':glyph,'type_margin':margin,
                'suggested_group':entry['group_id'],'final_decision_reason':reason},
            'signals':{'geometry_score':body,'designation_score':glyph,'type_margin':margin}}
        # A weak designation is still a located socket. Do not discard it or
        # accept an arbitrary circuit number as its device type.
        result['matches' if certain else 'review'].append(hit)
    for row in results:
        result=row['result'];count=len(result['matches'])
        result['counts']={'raw_matches':count,'legend_matches':0,'countable_devices':count}
        result['stages']['verified']=count+len(result['review'])
    return results


def score_review_pairs(pdf,path,page,rows,entries,model):
    """A trained visual model orders uncertain types; it cannot approve them."""
    from .ai.learning_images import symbol_crop
    by_group={e['group_id']:e for e in entries}
    for row in rows:
        result=row['result'];entry=by_group[row['group_id']]
        if not result['review']:continue
        template=entry['template']
        reference=symbol_crop(pdf,entry['template_path'],template['page'],template.get('raster_rect',template['rect']))
        for hit in result['review']:
            score=model.score(reference,symbol_crop(pdf,path,page,hit['rect']))
            hit['verification_details']['learned_pair_score']=score
            hit['signals']['learned_pair_score']=score
        result['review'].sort(key=lambda h:h['signals']['learned_pair_score'],reverse=True)
        result['stages']['learned_scored']=len(result['review'])
        result.setdefault('pipeline',{}).setdefault('active',[]).append('learned_pair_review_ranking')
