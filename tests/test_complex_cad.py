"""Unseen symbols: paint variants, export caps and overlapping CAD backgrounds."""
from pathlib import Path
import os
import pytest
import numpy as np
import cv2
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.text_engine import prepare_template
from electrocount.detection_engine import DetectionEngine
from electrocount.feature_matcher import OpenCVFeatureMatcher
from electrocount.document_regions import table_regions


def symbol(c,x,y,filled=False,angle=0,scale=1,caps=.4,noise=False,middle=True):
    c.saveState();c.translate(x,y);c.rotate(angle);c.scale(scale,scale)
    c.setStrokeColorRGB(.5,.5,.5);c.setFillColorRGB(.5,.5,.5);c.setLineWidth(.4)
    if noise:
        c.line(5,1,6,1)  # same style, disconnected background fragment
        c.setStrokeColorRGB(.7,.7,0);c.line(1,2,10,2);c.setStrokeColorRGB(.5,.5,.5)
    c.rect(0,0,24,6,stroke=1,fill=0)
    c.circle(12,3,3,stroke=not filled,fill=filled)
    if middle:c.line(0,3,9,3);c.line(15,3,24,3)
    for a,b in [(9,3),(15,3),(12,0),(12,6)]:c.circle(a,b,caps/2,stroke=0,fill=1)
    c.restoreState()


@pytest.mark.parametrize('filled',[False,True])
def test_caps_clutter_rotations_and_fill_variants(tmp_path,filled):
    path=str(tmp_path/'unseen.pdf');c=canvas.Canvas(path,pagesize=(500,400))
    symbol(c,40,350,filled,caps=.8)
    symbol(c,130,280,filled,scale=1.13,caps=.48,noise=True)
    symbol(c,230,230,filled,angle=90,scale=1.13,caps=.48)
    symbol(c,330,170,not filled,caps=.48)
    symbol(c,130,80,filled,caps=.48,middle=False)
    c.save();pdf=PdfiumEngine();t=prepare_template(pdf,path,0,[38,42,28,10])
    r=DetectionEngine(pdf).find(path,0,t)
    assert len(r['matches'])==3
    assert all(h['rect'][0]<300 for h in r['matches'])


def test_empty_rectangle_is_not_composite_fixture(tmp_path):
    p=str(tmp_path/'rect.pdf');c=canvas.Canvas(p,pagesize=(400,300))
    c.rect(30,230,24,6);c.rect(100,230,24,6);symbol(c,200,230,False);symbol(c,300,230,True)
    c.save();pdf=PdfiumEngine();t=prepare_template(pdf,p,0,[28,62,28,10]);r=DetectionEngine(pdf).find(p,0,t)
    assert len(r['matches'])==2


def test_raster_fill_is_not_extra_background_strokes():
    a=np.full((64,240),255,np.uint8);cv2.rectangle(a,(5,5),(234,58),0,2)
    cv2.line(a,(5,32),(99,32),0,2);cv2.line(a,(141,32),(234,32),0,2);cv2.circle(a,(120,32),21,0,2)
    b=a.copy();cv2.circle(b,(120,32),21,0,-1)
    for first,second in [(a,b),(b,a)]:assert not OpenCVFeatureMatcher().verify(first,second)['verified']


def test_outline_table_recognition_without_text(tmp_path):
    p=str(tmp_path/'table.pdf');c=canvas.Canvas(p,pagesize=(800,600))
    for x in (30,80,130,310):c.line(x,60,x,300)
    for y in range(60,301,20):c.line(30,y,310,y)
    symbol(c,42,266);c.save();pdf=PdfiumEngine()
    t=prepare_template(pdf,p,0,[40,326,29,10]);assert t['source']=='LEGEND'
    r=DetectionEngine(pdf).find(p,0,t);assert r['counts']['countable_devices']==0
    assert r['counts']['legend_matches']==1


def test_real_cpp_hollow_filled_and_clutter(tmp_path):
    p=os.environ.get('ELECTROCOUNT_TEST_CPP203')
    if not p:pytest.skip('Set ELECTROCOUNT_TEST_CPP203 to the supplied PDF')
    from electrocount.pdf_cache import CachedPDFEngine
    from electrocount.domain import overlap_metrics
    pdf=CachedPDFEngine(PdfiumEngine(),tmp_path/'cache')
    results=[]
    for y in (1527.84,1548.6):
        t=prepare_template(pdf,p,0,[1493,y-1,20,7]);assert t['source']=='LEGEND'
        r=DetectionEngine(pdf).find(p,0,t);results.append(r)
        assert len(r['matches'])>50
    assert not any(overlap_metrics(a['rect'],b['rect'])[0]>.5 for a in results[0]['matches'] for b in results[1]['matches'])
    # Manually inspected obstructed examples, independent of result totals.
    for r,boxes in zip(results,[[[1658.5,787.4,19,4.8],[1533,864.2,19,4.8]],[[1056,707.9,19,4.8],[1254.8,864.2,19,4.8]]]):
        for box in boxes:assert any(overlap_metrics(box,h['rect'])[0]>.5 for h in r['matches'])


def test_reference_panel_requires_heading_and_keeps_native_priority(monkeypatch):
    from electrocount.document_regions import confirmed_reference_panels
    from electrocount.text_engine import PdfTextItem
    import electrocount.ocr_engine as module
    monkeypatch.setattr(module,'OCREngine',lambda:pytest.fail('Native heading must not use OCR'))
    frames=[[10,30,200,80]];hits=[{'rect':[80,70,20,5]}]
    note=PdfTextItem('NOTE 2','NOTE 2',0,[15,15,30,8],[30,19])
    class NativeOnly:
        def render(self,*args):pytest.fail('Native heading must not be rasterized')
    assert confirmed_reference_panels(NativeOnly(),'unused',0,[note],frames,hits)[0]['kind']=='reference_panel'
    room=PdfTextItem('OFFICE','OFFICE',0,[15,15,30,8],[30,19])
    assert not confirmed_reference_panels(NativeOnly(),'unused',0,[room],frames,hits)


def test_embedded_image_does_not_trigger_whole_vector_page_raster(tmp_path):
    from PIL import Image
    from electrocount.matcher import TemplateMatcher
    from electrocount.detection_engine import DetectionEngine
    from electrocount.pdf_cache import CachedPDFEngine
    p=str(tmp_path/'mixed.pdf');im=tmp_path/'image.png';Image.new('RGB',(30,30),'gray').save(im)
    c=canvas.Canvas(p,pagesize=(500,400));symbol(c,40,350);symbol(c,250,250);c.drawImage(str(im),400,40,20,20);c.save()
    pdf=CachedPDFEngine(PdfiumEngine(),tmp_path/'cache');template=prepare_template(pdf,p,0,[38,42,28,10])
    class TrackingMatcher(TemplateMatcher):
        def find(self,*args,**kwargs):
            self.regions=kwargs.get('search_regions');return super().find(*args,**kwargs)
    matcher=TrackingMatcher();engine=DetectionEngine(pdf);engine.matcher=matcher
    result=engine.find(p,0,template)
    assert len(result['matches'])==2
    assert matcher.regions==[[400.,340.,20.,20.]]
    with pdf.open_vector_page(p,0) as n:assert n.image_regions==matcher.regions and n.index_cache_hit


def test_late_paint_strokes_still_distinguish_inner_line_variant(tmp_path):
    path=str(tmp_path/'late-strokes.pdf');c=canvas.Canvas(path,pagesize=(500,400))
    symbol(c,40,350,middle=False)
    symbol(c,140,250,middle=False)
    symbol(c,260,150,middle=False)
    for i in range(100):c.line(450,10+i,460,10+i)
    c.setStrokeColorRGB(.5,.5,.5);c.setLineWidth(.4)
    c.line(260,153,269,153);c.line(275,153,284,153)
    c.save();pdf=PdfiumEngine();t=prepare_template(pdf,path,0,[38,42,28,10])
    result=DetectionEngine(pdf).find(path,0,t)
    assert len(result['matches'])==2
    assert not any(h['rect'][0]>200 for h in result['matches'])
