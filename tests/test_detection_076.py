"""Quantization is not a variant; exact device codes still are."""
import math
import numpy as np
import pytest
from electrocount.vector_engine import intersections,signature,VectorCandidateGenerator,bbox
from electrocount.final_decision import FinalDecisionEngine
from electrocount.occlusion import label_proposals
from electrocount.text_engine import PdfTextItem


def test_endpoint_contacts_are_not_interior_crossings():
    line=lambda a,b:{'kind':'line','points':[a,b]}
    a=[line([0,0],[4,0]),line([2,-2],[2,2]),line([3.95,-1],[3.95,1])]
    assert intersections(a)==2
    assert intersections(a,.18)==1
    b=[a[0],a[1],line([4.05,-1],[4.05,1])]
    assert intersections(b)==1
    assert intersections(b,.18)==1


@pytest.mark.parametrize('target',['7','8','9','10'])
@pytest.mark.parametrize('actual',['7','8','9','10'])
def test_all_label_pairs(target,actual):
    signals={'geometry_score':1.,'feature_score':1.,'visual_ai_score':1.,'color_score':1.,'device_label_score':float(target==actual),'spatial_text_score':1.}
    decision,_,_=FinalDecisionEngine().decide(target,actual,signals)
    assert decision==('MATCH' if target==actual else 'OTHER_VARIANT')


def test_small_native_label_can_propose_but_is_not_proof():
    t={'rect':[10,10,4.8,4.68],'association':{'offset':[0,-1.2],'glyph_size':2.7,'dx':0,'dy':-1.2},'source':'DRAWING'}
    item=PdfTextItem('8','8',0,[40,30,2.7,4.2],[41.35,32.1])
    proposals=label_proposals(t,'8',[item],{'width':100,'height':100})
    assert proposals and all('verified' not in p for p in proposals)
    assert not label_proposals(t,'7',[item],{'width':100,'height':100})


def test_missing_stroke_still_fails_quantization_tolerance():
    line=lambda a,b:{'kind':'line','points':[a,b]}
    paths=[{'bbox':[0,0,4.8,4.8],'segments':[line([0,0],[4.8,0]),line([4.8,0],[4.8,4.8]),line([4.8,4.8],[0,4.8]),line([0,4.8],[0,0])]},
           {'bbox':[0,0,4.8,4.8],'segments':[line([0,0],[4.8,4.8])]}]
    ref=signature(paths)
    assert VectorCandidateGenerator().verify(ref,paths,np.eye(2),np.zeros(2),ref['bbox'])['verified']
    assert not VectorCandidateGenerator().verify(ref,paths[:1],np.eye(2),np.zeros(2),ref['bbox'])['verified']
