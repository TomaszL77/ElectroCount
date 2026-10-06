"""Regression: legend captions, equivalent CAD paint, and model abstention."""
import math
import numpy as np
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection
from electrocount.text_engine import PdfTextItem
from electrocount.ocr_engine import TextOverridePDF
from electrocount.vector_engine import bbox,signature,VectorCandidateGenerator
from electrocount.foreground import learned_pair_compatible
from electrocount.search_diagnostics import export_comparison


def table_pdf(tmp_path):
    p=tmp_path/'legend.pdf';c=canvas.Canvas(str(p),pagesize=(750,500))
    for x in (30,90,145,250):
        c.line(x,100,x,300);c.line(x,300,x,340)
    for y in range(100,341,20):c.line(30,y,250,y)
    c.rect(45,248,28,4,stroke=1,fill=0)
    c.save();return p


def test_ocr_caption_does_not_erase_legend_or_require_floor_plan_code(tmp_path):
    p=table_pdf(tmp_path);pdf=PdfiumEngine()
    caption=PdfTextItem('L2','L2',0,[102,245,12,8],[108,249],source='ocr')
    wrapped=TextOverridePDF(pdf,str(p),0,[caption])
    t=prepare_detection(wrapped,str(p),0,[43,245,34,10],visual_embedding=False)
    assert t['source']=='LEGEND' and t['label']=='L2'
    assert t['match_mode']=='shape' and t['label_role']=='legend_caption'
    assert t['selection_bbox']==[43,245,34,10]
    # A deliberately included code remains part of the full template.
    explicit=prepare_detection(wrapped,str(p),0,[43,243,74,13],visual_embedding=False)
    assert explicit.get('match_mode','full')=='full'


def line(a,b,identifier):
    return {'id':identifier,'segments':[{'kind':'line','points':[a,b]}],
        'bbox':bbox([a,b]),'fill':False,'stroke':True,'stroke_width':.3,'color':[0,0,0,255]}


def test_subdivision_equivalence_does_not_bridge_a_gap_or_drop_an_extra_feature():
    corners=[[0,0],[20,0],[20,5],[0,5],[0,0]]
    whole={'id':1,'bbox':[0,0,20,5],'segments':[{'kind':'line','points':[a,b]}for a,b in zip(corners,corners[1:])],
        'fill':False,'stroke':True,'stroke_width':.3,'color':[0,0,0,255]}
    pieces=[]
    for i,(a,b) in enumerate(zip(corners,corners[1:])):
        m=[(a[0]+b[0])/2,(a[1]+b[1])/2]
        pieces += [line(a,m,i*2),line(m,b,i*2+1)]
    ref=signature(pieces,preserve_selection=True);v=VectorCandidateGenerator()
    assert v.verify(ref,[whole],np.eye(2),np.zeros(2),ref['bbox'])['verified']
    assert not v.verify(ref,[whole,line([10,0],[10,5],99)],np.eye(2),np.zeros(2),ref['bbox'])['verified']
    missing=pieces.copy();missing[0]=line([0,0],[9,0],99)
    assert not v.verify(signature(missing,preserve_selection=True),[whole],np.eye(2),np.zeros(2),ref['bbox'])['verified']


def test_model_cannot_recover_hollow_vs_filled_or_isolated_dot():
    import cv2
    a=np.full((80,240),255,np.uint8);cv2.rectangle(a,(10,20),(230,60),0,2);cv2.circle(a,(120,40),18,0,2)
    same=a.copy();filled=a.copy();cv2.circle(filled,(120,40),17,0,-1)
    dot=np.full_like(a,255);cv2.circle(dot,(120,40),18,0,-1)
    assert learned_pair_compatible(a,same)
    assert not learned_pair_compatible(a,filled)
    assert not learned_pair_compatible(a,dot)


def test_diagnostics_export_keeps_actual_model_and_search_settings(tmp_path):
    import json,zipfile
    from electrocount.domain import Project
    project=Project();project.analysis_reports={'group:0':{'diagnostics':{'model':{'loaded':True,'sha256':'abc'},'match_mode':'shape'}}}
    path=export_comparison(tmp_path/'diagnosis.zip',project,{'code':{'version':'0.7.8.5'}})
    with zipfile.ZipFile(path) as z:
        data=json.loads(z.read('searches.json'))
        assert data['group:0']['diagnostics']['model']['sha256']=='abc'
        assert data['group:0']['diagnostics']['match_mode']=='shape'


def test_hidden_hollow_geometry_cannot_count_a_visibly_filled_body(tmp_path):
    from electrocount.detection_engine import DetectionEngine
    p=tmp_path/'overprint.pdf';c=canvas.Canvas(str(p),pagesize=(400,200))
    for x in (20,100,180):
        c.rect(x,150,24,6,stroke=1,fill=0);c.circle(x+12,153,3,stroke=1,fill=0)
    c.setFillColorRGB(.5,.5,.5);c.circle(192,153,3,stroke=0,fill=1);c.save()
    pdf=PdfiumEngine();t=prepare_detection(pdf,str(p),0,[18,42,28,10],visual_embedding=False);t['match_mode']='shape'
    r=DetectionEngine(pdf).find(str(p),0,t)
    assert any(95<h['rect'][0]<110 for h in r['matches'])
    assert not any(175<h['rect'][0]<190 for h in r['matches'])


def test_identical_nested_ink_island_is_not_a_filled_hole():
    import cv2
    from electrocount.feature_matcher import contour_evidence
    image=np.full((120,240),255,np.uint8)
    cv2.rectangle(image,(10,10),(230,110),0,2);cv2.line(image,(70,60),(170,60),0,3)
    evidence=contour_evidence(image,image)
    assert evidence['fill_consistent'] and evidence['verified']
