"""Explicit ratings stay separate from device codes and circuit references.

This takeoff profile does not infer ratings from appearance or absence of text.
Uncertain/missing annotations require review, even with high AI similarity.
"""
import math
import re


def modifier(text):
    value=''.join(text.upper().split())
    if re.fullmatch(r'IP\d{2}[A-Z]?',value):return 'IP',value
    if value=='EX':return 'EX','EX'
    if value in ('1~','3~'):return 'PHASE',value
    return None


def gap(a,b):
    return math.hypot(max(a[0]-b[0]-b[2],b[0]-a[0]-a[2],0),
                      max(a[1]-b[1]-b[3],b[1]-a[1]-a[3],0))


def build_profile(rect, items, peer_rects=()):
    radius=max(12.,max(rect[2:])*.75)
    values={};uncertain=set();evidence=[];seen=set()
    for item in items:
        data=item.to_dict() if hasattr(item,'to_dict') else item
        code=modifier(data.get('normalized_text',data.get('text','')))
        if not code:continue
        key,value=code;box=data['bbox'];distance=gap(rect,box)
        if distance>radius:continue
        identity=(value,*box)
        if identity in seen:continue
        seen.add(identity)
        others=[gap(peer,box) for peer in peer_rects if peer!=rect]
        if others and min(others)<distance-2:continue
        shared=bool(others and min(others)<=distance+2)
        weak=data.get('source')=='ocr' and data.get('confidence',0)<.95
        if shared or weak:uncertain.add(key)
        values.setdefault(key,set()).add(value)
        evidence.append({'kind':key,'value':value,'bbox':box,'source':data.get('source','pdf_native'),
                         'confidence':data.get('confidence',1.),'shared':shared})
    uncertain.update(k for k,v in values.items() if len(v)>1)
    return {'version':1,'values':{k:next(iter(v)) for k,v in sorted(values.items()) if len(v)==1 and k not in uncertain},
            'uncertain':sorted(uncertain),'evidence':evidence}


def compare_profiles(reference, candidate):
    if reference.get('uncertain') or candidate.get('uncertain'):
        return 'REVIEW','ambiguous_electrical_rating'
    expected=reference.get('values',{});actual=candidate.get('values',{})
    # Explicit disagreement takes priority over another missing rating.
    if any(k in actual and expected.get(k)!=actual[k] for k in set(expected)|set(actual)):
        return 'OTHER_VARIANT','different_electrical_rating'
    if any(k not in actual for k in expected):return 'REVIEW','missing_electrical_rating'
    return 'MATCH','electrical_ratings_consistent'


def display_label(label, profile):
    ratings=profile.get('values',{})
    parts=[label] if label else []
    parts.extend(ratings[k] for k in ('IP','EX','PHASE') if k in ratings)
    parts.extend(k+'?' for k in profile.get('uncertain',[]))
    return ' · '.join(parts)
