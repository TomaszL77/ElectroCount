"""Ground-truth electrical variants; use the real pinned Small and Base models."""
from pathlib import Path
from dataclasses import replace
import numpy as np
import pytest
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount.electrical_profile import build_profile,compare_profiles,modifier
from electrocount.text_engine import PdfTextItem
from electrocount.ai.model_catalog import MODELS
from electrocount.ai.model_manager import ModelManager

ROOT=Path(__file__).parents[1]


def electrical_pdf(path,rating='IP44'):
    c=canvas.Canvas(str(path),pagesize=(420,340))
    other={'IP44':'IP20','EX':'IP44','3~':'1~'}[rating]
    entries=[('G1',rating,'TP04/47'),('G1',rating,'TP04/49'),
             ('G1',other,'TP04/47'),('G1','','TP04/50'),
             ('G2',rating,'TP04/47'),('G1',rating,'TP04/51')]
    truth=[]
    for i,(code,mark,circuit) in enumerate(entries):
        x,y=30+(i%2)*200,270-(i//2)*100
        c.setLineWidth(.5);c.rect(x,y,24,12)
        c.line(x,y,x+24,y+12)
        if i!=5:c.line(x+24,y,x,y+12)  # wrong geometry, same text
        c.setFont('Helvetica',8);c.drawString(x+28,y+6,code)
        if mark:c.setFont('Helvetica',7);c.drawString(x+28,y-4,mark)
        c.setFont('Helvetica',4);c.drawString(x,y-12,circuit)
        if i in (0,1):truth.append([x,340-y-12,24,12])
    c.save()
    return [28,54,64,26],truth


@pytest.mark.parametrize('mode',['classic','hybrid','hybrid_base'])
@pytest.mark.parametrize('rating',['IP44','EX','3~'])
def test_electrical_variants_circuits_missing_and_wrong_shape(tmp_path,mode,rating):
    from electrocount.benchmark import metrics
    model={'hybrid':'small','hybrid_base':'base'}.get(mode)
    if model and not (ROOT/'models'/MODELS[model].relative_path).is_file():
        pytest.skip('Install real models with tools/install_models.py --model all')
    path=tmp_path/'electrical.pdf';selection,truth=electrical_pdf(path,rating)
    pdf=PdfiumEngine();template=prepare_detection(pdf,str(path),0,selection)
    assert template['label']=='G1'
    assert rating in template['electrical_profile']['values'].values()
    result=run_detection(pdf,str(path),0,template,'G1',config={'engine_mode':mode})
    metric=metrics([h['rect'] for h in result['matches']],truth,iou=.7)
    assert metric['tp']==2 and metric['false_positives']==metric['false_negatives']==0
    assert len(result['review'])==1 and result['review'][0]['reason']=='missing_electrical_rating'
    assert len(result['discovered_other_label'])==2
    assert not any(h['rect'][0]>200 and h['rect'][1]>240 for h in result['matches'])
    assert result['pipeline']['engine_mode']==mode
    if model:assert result['pipeline']['model']['name']==f'dinov2-{model}-onnx-fp32'


def item(value,box,confidence=1.,source='pdf_native'):
    x,y,w,h=box
    return PdfTextItem(value,value,0,box,[x+w/2,y+h/2],source,confidence)


def test_ratings_are_explicit_nearest_and_uncertain_when_shared():
    a=[0,0,20,10];b=[40,0,20,10]
    shared=item('IP44',[26,3,8,5]);near=item('IP20',[0,13,12,5])
    assert build_profile(a,[shared],[a,b])['uncertain']==['IP']
    assert build_profile(a,[near],[a,b])['values']=={'IP':'IP20'}
    assert not build_profile(b,[near],[a,b])['values']
    weak=build_profile(a,[item('IP44',[0,13,12,5],.85,'ocr')])
    assert compare_profiles({'values':{'IP':'IP44'}},weak)[0]=='REVIEW'
    assert compare_profiles({'values':{'IP':'IP44'}},{'values':{}})[0]=='REVIEW'
    assert modifier('TP04/47') is None and modifier('#A\'') is None


def test_base_real_inference_identity_cache_and_no_cross_model_comparison(monkeypatch):
    from electrocount.ai.visual_encoder import cosine
    if not (ROOT/'models'/MODELS['base'].relative_path).is_file():pytest.skip('Install Base model')
    import urllib.request
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:pytest.fail('Inference attempted a download'))
    manager=ModelManager(ROOT/'models');base=manager.load_visual_encoder('base')
    assert manager.load_visual_encoder('base') is base
    crop=np.full((30,120,3),255,np.uint8);crop[8:22,10:110]=0
    first=base.encode(crop);second=base.encode(crop)
    assert len(first.values)==768 and cosine(first,second)>.999999
    assert base.tokens(crop).shape==(257,768)
    with pytest.raises(ValueError):cosine(first,replace(first,model_name='dinov2-small-onnx-fp32'))


def test_missing_or_corrupt_base_never_silently_uses_small(tmp_path):
    from electrocount.ai.visual_encoder import DinoV2Encoder
    with pytest.raises(RuntimeError,match='Brak modelu'):
        ModelManager(tmp_path).load_visual_encoder('base')
    bad=tmp_path/'bad.onnx';bad.write_bytes(b'incorrect-model')
    with pytest.raises(RuntimeError,match='sum'):
        DinoV2Encoder(bad,model_name='base')


def test_gui_base_default_and_explicit_switch(app,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from electrocount.main_window import MainWindow
    w=MainWindow()
    try:
        assert w.engine_mode()=='hybrid_base'
        assert 'Base' in w.performance_button.text()
        monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:('Klasyczny — geometria PDF',True))
        w.toggle_hybrid();assert w.engine_mode()=='classic'
    finally:w.jobs.close();w.dirty=False;w.close()
