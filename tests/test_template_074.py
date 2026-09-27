"""Real PDF regression: identical 7/8 geometry, RGB, context and missing labels."""
import base64
import copy
from pathlib import Path
import cv2
import numpy as np
import pytest
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection


def scene(path):
    c=canvas.Canvas(str(path),pagesize=(420,320))
    entries=[('7',(1,0,1)),('8',(1,0,1)),('7',(0,0,1)),('7',(0,0,0)),('',(1,0,1))]
    boxes=[]
    for i,(label,color) in enumerate(entries):
        x,y=50+(i%2)*200,265-(i//2)*100
        c.setStrokeColorRGB(*color);c.setLineWidth(.8)
        c.circle(x,y,10);c.line(x-7,y-7,x+7,y+7);c.line(x-7,y+7,x+7,y-7)
        c.setFillColorRGB(0,0,0);c.setFont('Helvetica',10)
        if label:c.drawCentredString(x,y+16,label)
        c.setFillColorRGB(0,0,1);c.setFont('Helvetica',7)
        c.saveState();c.translate(x+16,y+8);c.rotate(-90);c.drawString(0,0,'O:RRA1.2/11.4');c.restoreState()
        c.drawString(x-10,y-20,'W:CR-55.1')
        boxes.append([x-10,320-y-10,20,20])
    c.save()
    return [38,43,24,24],boxes


def decode(record):
    b=np.frombuffer(base64.b64decode(record['png_base64']),np.uint8)
    return cv2.cvtColor(cv2.imdecode(b,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)


@pytest.mark.parametrize('mode',['classic','hybrid','hybrid_base'])
def test_identical_7_8_geometry_color_and_missing_label(tmp_path,mode):
    from electrocount.ai.model_catalog import MODELS
    model={'hybrid':'small','hybrid_base':'base'}.get(mode)
    if model and not (Path(__file__).parents[1]/'models'/MODELS[model].relative_path).exists():pytest.skip('Install models')
    path=tmp_path/'7-8.pdf';selection,boxes=scene(path)
    pdf=PdfiumEngine();t=prepare_detection(pdf,str(path),0,selection)
    assert t['label']=='7'  # outside the selected symbol, not the blue circuit
    r=run_detection(pdf,str(path),0,t,config={'engine_mode':mode})
    assert len(r['matches'])==3 and {h['label'] for h in r['matches']}=={'7'}
    assert len(r['discovered_other_label'])==1
    other=r['discovered_other_label'][0]
    assert other['label']=='8' and other['status']=='OTHER_VARIANT' and other['label_score']==0
    assert len(r['review'])==1 and r['review'][0]['label']==''
    by_y={round(h['rect'][0]):h for h in r['matches'] if h['rect'][1]>100}
    target=next(h for h in r['matches'] if h['rect'][1]<100)
    blue=by_y[40];mono=by_y[240]
    assert target['signals']['color_score']>.95
    assert blue['signals']['color_score']<.4 and blue['confidence']<target['confidence']
    assert mono['signals']['color_score'] is None
    assert target['shape_score']>.9 and other['shape_score']>.9
    assert all(h['label_score']==1 for h in r['matches'])
    assert all(h['text_source']=='pdf_native' for h in r['matches'])


@pytest.mark.parametrize('position',['ABOVE','BELOW','LEFT','RIGHT','ROTATED'])
def test_native_context_any_side_and_rotation(tmp_path,position):
    p=tmp_path/'side.pdf';c=canvas.Canvas(str(p),pagesize=(220,200))
    c.setStrokeColorRGB(1,0,1);c.rect(90,90,24,12);c.line(90,90,114,102);c.line(114,90,90,102)
    c.setFont('Helvetica',8)
    x,y={'ABOVE':(99,110),'BELOW':(99,78),'LEFT':(78,93),'RIGHT':(122,93),'ROTATED':(126,91)}[position]
    c.saveState();c.translate(x,y)
    if position=='ROTATED':c.rotate(90)
    c.drawString(0,0,'7');c.restoreState()
    c.setFont('Helvetica',5);c.drawString(90,68,'TP04/47');c.save()
    t=prepare_detection(PdfiumEngine(),str(p),0,[88,96,28,16]);r=t['representation']
    assert r['detected_label']=='7'
    assert r['label_position']==('RIGHT' if position=='ROTATED' else position)
    assert r['label_rotation']==(270. if position=='ROTATED' else 0.)
    assert {a['role'] for a in r['associated_texts']} >= {'DEVICE_LABEL','CIRCUIT_REFERENCE'}
    assert all({'text','bbox','center','distance','position','rotation','source','confidence'}<=a.keys() for a in r['associated_texts'])


def test_rgb_original_normalized_preview_and_project_roundtrip(app,tmp_path):
    from electrocount.template_preview import TemplatePreview
    from electrocount.domain import Group,Project
    from electrocount.project_manager import ProjectManager
    from electrocount.color_features import color_name
    path=tmp_path/'rgb.pdf';selection,_=scene(path);pdf=PdfiumEngine()
    t=prepare_detection(pdf,str(path),0,selection);r=t['representation']
    raw=decode(r['original_rgb_crop']);normalized=decode(r['normalized_visual_crop'])
    assert np.array_equal(raw,pdf.render(str(path),0,2.,t['raster_rect']))
    assert np.array_equal(normalized[:,:,0],normalized[:,:,1])
    assert np.any((raw[:,:,0]>200)&(raw[:,:,1]<50)&(raw[:,:,2]>200))
    assert r['symbol_bbox']==t['rect'] and r['context_bbox'][2]>r['symbol_bbox'][2]
    assert color_name(r['color_signature'])=='magenta'
    assert len(r['color_signature']['foreground_pixel_distribution'])==64
    assert r['color_signature']['mean_saturation']>.5
    g=Group('7',label='7',template=t);r['group_id']=g.id
    project=Project(source=str(path),pages=pdf.inspect(str(path)),groups=[g],active=g.id)
    folder=tmp_path/'saved';manager=ProjectManager();manager.save(project,folder)
    restored=manager.load(folder/'project.sqlite')
    assert restored.groups[0].template['representation']==r
    widget=TemplatePreview();widget.resize(340,82);widget.set_template(t,'7');widget.show();app.processEvents()
    image=widget.grab().toImage()
    count=sum(image.pixelColor(x,y).red()>200 and image.pixelColor(x,y).blue()>200 and image.pixelColor(x,y).green()<80 for y in range(80) for x in range(88))
    assert count>30
    widget.close()


def test_colored_variant_alone_never_rejects():
    from electrocount.final_decision import FinalDecisionEngine
    signals=dict(geometry_score=.88,feature_score=.85,visual_ai_score=.72,device_label_score=1.,spatial_text_score=.8,text_role_confidence=.9)
    a=FinalDecisionEngine().decide('7','7',{**signals,'color_score':1.})
    b=FinalDecisionEngine().decide('7','7',{**signals,'color_score':0.})
    assert a[0]==b[0]=='MATCH' and b[1]<a[1]


def test_pending_is_not_in_group_quantity_and_debug_shows_variants(app):
    from electrocount.main_window import MainWindow
    from electrocount.domain import Group,Detection
    w=MainWindow()
    try:
        g=Group('7',label='7');w.project.groups=[g];w.project.active=g.id
        w.project.pages=[{'name':'Parter'}]
        w.project.detections=[Detection(g.id,0,[0,0,10,10]),Detection('',0,[30,0,10,10],requested_group=g.id)]
        w.project.discoveries=[{'requested_group':g.id,'page':0,'label':'8','graphic_score':1.,'text_score':0.,'confidence':.65,'signals':{'color_score':1.}}]
        w.refresh()
        assert w.found_count.text()=='Znaleziono: 1 · na stronie: 1'
        assert w.groups.topLevelItem(0).text(1)=='1'
        assert 'Osobno, bez przypisania: 1' in w.summary.text()
        assert 'Label: 8' in w.debug_panel.text.toPlainText() and 'OTHER_VARIANT' in w.debug_panel.text.toPlainText()
    finally:w.jobs.close();w.dirty=False;w.close()


def test_symbol_rotation_does_not_force_text_rotation(tmp_path):
    p=tmp_path/'rotated-device.pdf';c=canvas.Canvas(str(p),pagesize=(360,200))
    for x,angle in [(60,0),(240,90)]:
        c.saveState();c.translate(x,90);c.rotate(angle);c.setStrokeColorRGB(1,0,1)
        c.rect(-13,-6,26,12);c.line(-13,-6,13,6);c.line(-13,6,13,-6);c.restoreState()
        c.setFont('Helvetica',8);c.drawString(x+20,87,'QP14')
    c.save();pdf=PdfiumEngine()
    t=prepare_detection(pdf,str(p),0,[45,102,60,16])
    r=run_detection(pdf,str(p),0,t)
    assert t['label']=='QP14' and len(r['matches'])==2
    assert all(h['verification_details']['label_rotation']==0 for h in r['matches'])


def test_selected_circuit_does_not_hide_label_outside_selection(tmp_path,monkeypatch):
    from electrocount.ocr_engine import OCREngine
    p=tmp_path/'circuit.pdf';scene(p)
    monkeypatch.setattr(OCREngine,'read_region',lambda *a,**k:pytest.fail('OCR attempted despite confident native label'))
    # Select symbol and blue references below/right; 7 remains above selection.
    t=prepare_detection(PdfiumEngine(),str(p),0,[38,43,75,47],ocr_enabled=True)
    assert t['label']=='7' and t['representation']['text_source']=='pdf_native'
    assert any(a['role']=='CIRCUIT_REFERENCE' for a in t['representation']['associated_texts'])


def test_old_template_migrates_rgb_and_keeps_explicit_legend(tmp_path):
    p=tmp_path/'legacy.pdf';selection,_=scene(p);pdf=PdfiumEngine()
    old=prepare_detection(pdf,str(p),0,selection);identity=old['representation']['id']
    old['source']='LEGEND';old['definition_version']=8;old['group_id']='group-7'
    old['representation'].pop('original_rgb_crop')
    r=run_detection(pdf,str(p),0,old)
    updated=r['template']
    assert updated['definition_version']==9 and updated['source']=='LEGEND'
    assert updated['representation']['id']==identity and updated['representation']['group_id']=='group-7'
    assert 'original_rgb_crop' in updated['representation']
    assert not any(h['rect'][1]<100 for h in r['matches'])
    assert any(h['status']=='SOURCE_TEMPLATE' for h in r['legend_matches'])
