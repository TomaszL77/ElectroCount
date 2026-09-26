import json
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from electrocount.color_features import color_signature, color_similarity
from electrocount.text_roles import TextRoleClassifier
from electrocount.text_engine import TextEngine, PdfTextItem
from electrocount.final_decision import FinalDecisionEngine
from electrocount.performance import execution_plan
from electrocount.runtime_runner import run_with_fallback


def text(value,box):
    x,y,w,h=box
    return PdfTextItem(value,value,0,box,[x+w/2,y+h/2])


@pytest.mark.parametrize('label',['D1','AW2','EW1','QP14','AS1','1A','2A','10','7N','CUSTOM-X'])
@pytest.mark.parametrize('box',[[26,9,10,8],[-13,9,10,8],[8,-12,10,8],[8,27,10,8],[8,8,10,8]])
def test_arbitrary_codes_and_context_directions(label,box):
    result=TextEngine().associate([0,0,24,24],[text(label,box),text('TP04/47',[25,1,12,5])])
    assert result['item'].text==label
    assert any(a['role']=='CIRCUIT_REFERENCE' for a in result['associated_texts'])


def test_roles_and_missing_labels_do_not_invent_device_types():
    roles=TextRoleClassifier()
    assert roles.classify('TP04/52')[0]=='CIRCUIT_REFERENCE'
    assert roles.classify('IP44')[0]=='DEVICE_MODIFIER'
    assert roles.classify('117W')[0]=='DESCRIPTION'
    assert TextEngine().associate([0,0,24,24],[text('TP04/47',[25,8,10,8])])['item'] is None


def test_exact_device_text_overrides_graphics_and_color():
    decision=FinalDecisionEngine()
    signals=dict(visual_ai_score=.99,geometry_score=.99,feature_score=.99,color_score=.99,
                 device_label_score=0,spatial_text_score=.95)
    for other in ('EW2','EW11','AW1','EWI'):
        assert decision.decide('EW1',other,signals)[0]=='OTHER_VARIANT'
    assert decision.decide('EW1','',signals)[0]=='REVIEW'
    assert decision.decide('EW1','EW1',{**signals,'device_label_score':1})[0]=='MATCH'


def test_color_soft_evidence_and_monochrome():
    a=np.full((50,80,3),255,np.uint8);a[20:30,10:70]=[230,0,230]
    b=a.copy();b[20:30,10:70]=[225,5,224]
    c=a.copy();c[20:30,10:70]=[0,10,230]
    mono=a.copy();mono[20:30,10:70]=[0,0,0]
    sa=color_signature(a)
    assert color_similarity(sa,color_signature(b))>.95
    assert color_similarity(sa,color_signature(c))<.4
    assert color_similarity(sa,color_signature(mono)) is None


def test_hardware_and_legacy_profiles_do_not_change_pipeline():
    for profile in ('AUTO','ECO','STANDARD','ENHANCED','MAXIMUM'):
        for ram in (300,64000):
            assert execution_plan(profile,{'hardware':{'available_ram_mb':ram}})==execution_plan()
    calls=[]
    def operation(plan):
        calls.append(plan)
        if plan.memory_cache_mb>8:raise MemoryError()
        return 12
    start=replace(execution_plan(),neural_enabled=True)
    assert run_with_fallback(operation,start)==12
    assert all(p.neural_enabled and p.effective=='DETERMINISTIC' for p in calls)


def fixture_pdf(path,label='EW1'):
    from reportlab.pdfgen import canvas
    c=canvas.Canvas(str(path),pagesize=(420,320));boxes=[]
    for i,(code,circuit,color) in enumerate([(label,'TP04/47',(1,0,1)),(label,'TP04/52',(1,0,1)),
            (label,'TP04/59',(0,0,0)),('EW2','TP04/47',(1,0,1))]):
        x,y=45+(i%2)*180,90+(i//2)*130
        c.setStrokeColorRGB(*color);c.setLineWidth(1)
        c.rect(x,y,26,14,fill=0);c.line(x,y,x+26,y+14);c.line(x+26,y,x,y+14)
        c.setFillColorRGB(*color);c.setFont('Helvetica',9);c.drawString(x+32,y+3,code)
        c.setFont('Helvetica',4);c.drawString(x,y-8,circuit)
        if code==label:boxes.append([x,320-y-14,26,14])
    c.save()
    return boxes,[40,211,94,34]


@pytest.mark.parametrize('label',['D1','AW2','EW1','QP14','AS1','1A','2A','10','7N'])
def test_retrieval_preserves_codes_circuits_color_and_monochrome(tmp_path,label):
    from electrocount.pdf_engine import PdfiumEngine
    from electrocount.detection_service import prepare_detection,run_detection
    path=tmp_path/'scene.pdf';boxes,_=fixture_pdf(path,label)
    pdf=PdfiumEngine();template=prepare_detection(pdf,str(path),0,[40,211,94,34])
    assert template['label']==label
    assert template['representation']['color_signature']['saturation']>.8
    result=run_detection(pdf,str(path),0,template,label)
    assert len(result['matches'])==3
    assert len(result['discovered_other_label'])==1
    assert all(h['label']==label for h in result['matches'])
    assert all(h['signals']['geometry_score']>.8 for h in result['matches'])


def test_real_encoder_and_independent_tile_path(tmp_path):
    from electrocount.ai.visual_encoder import DinoV2Encoder,cosine
    from electrocount.ai.retrieval import VisualRetrieval
    from electrocount.pdf_engine import PdfiumEngine
    from electrocount.detection_service import prepare_detection,run_detection
    model=Path(__file__).parents[1]/'models/dinov2-small/8b1f705/model.onnx'
    if not model.exists():pytest.skip('Run Instaluj_AI.cmd to install pinned DINOv2')
    encoder=DinoV2Encoder(model)
    image=np.full((30,60,3),255,np.uint8);image[8:20,8:50]=0
    a=encoder.encode(image);b=encoder.encode(image)
    assert len(a.values)==384 and cosine(a,b)>.999999
    path=tmp_path/'scene.pdf';fixture_pdf(path)
    pdf=PdfiumEngine();template=prepare_detection(pdf,str(path),0,[40,211,94,34])
    result=run_detection(pdf,str(path),0,template,'EW1',config={'engine_mode':'hybrid'})
    assert result['stages']['ai_retrieval']['tiles_encoded']==6
    assert result['pipeline']['engine_mode']=='hybrid'
    assert all(h['signals']['visual_ai_score'] is not None for h in result['matches'])
    assert not any(h['label']=='EW2' for h in result['matches'])


def test_ocr_native_priority_and_real_local_recognition():
    from electrocount.ocr_engine import OCREngine
    from PIL import Image,ImageDraw,ImageFont
    import reportlab
    font_path=Path('C:/Windows/Fonts/arial.ttf')
    if not font_path.exists():font_path=Path(reportlab.__file__).parent/'fonts/Vera.ttf'
    class PDF:
        def inspect(self,path):return [{'width':200,'height':120}]
        def render(self,path,page,scale,rect):
            image=Image.new('RGB',(600,360),'white')
            draw=ImageDraw.Draw(image)
            draw.text((210,135),'EW1',fill='black',font=ImageFont.truetype(str(font_path),36))
            x,y,w,h=rect
            return np.array(image.crop((round(x*3),round(y*3),round((x+w)*3),round((y+h)*3))))
    engine=OCREngine();pdf=PDF()
    words=engine.read_region(pdf,'local',0,[40,40,24,20])
    assert any(w.normalized_text=='EW1' and w.source=='ocr' for w in words)
    def forbidden(*a,**kw):raise AssertionError('OCR ran despite native PDF label')
    engine.backend=forbidden
    assert engine.read_region(pdf,'local',0,[40,40,24,20],[text('EW1',[69,43,24,10])])==[]


def test_benchmark_requires_localization_and_no_regression():
    from electrocount.benchmark import metrics,promotion_allowed
    truth=[[0,0,10,10],[30,0,10,10]]
    r=metrics([[0,0,10,10],[0,0,10,10]],truth)
    assert r['tp']==1 and r['false_positives']==1 and r['false_negatives']==1
    assert r['precision']==r['recall']==r['f1']==.5
    perfect=metrics(truth,truth)
    assert not promotion_allowed([perfect],[perfect])
    assert promotion_allowed([r],[perfect])


def test_explicit_legend_source_without_table_is_not_counted(tmp_path):
    from electrocount.pdf_engine import PdfiumEngine
    from electrocount.detection_service import prepare_detection,run_detection
    path=tmp_path/'scene.pdf';fixture_pdf(path)
    pdf=PdfiumEngine();t=prepare_detection(pdf,str(path),0,[40,211,94,34])
    t['source']='LEGEND';t['signature']['source_legend']=True
    result=run_detection(pdf,str(path),0,t,'EW1')
    assert result['counts']=={'raw_matches':3,'legend_matches':1,'countable_devices':2}
    assert result['legend_matches'][0]['status']=='SOURCE_TEMPLATE'


def test_render_session_matches_pdfium_and_closes(tmp_path):
    from electrocount.render_session import RenderSession
    from electrocount.pdf_engine import PdfiumEngine
    path=tmp_path/'scene.pdf';fixture_pdf(path);pdf=PdfiumEngine();session=RenderSession(pdf)
    try:
        for box in ([40,211,94,34],[42.17,210.38,30.7,23.1]):
            assert np.array_equal(pdf.render(str(path),0,2.,box),session.render(str(path),0,2.,box))
    finally:session.close()
    assert not session.pages


def test_gui_searches_all_project_documents_and_shows_busy_state(app,tmp_path):
    from electrocount.main_window import MainWindow
    from test_ui import wait
    paths=[tmp_path/'one.pdf',tmp_path/'two.pdf']
    for path in paths:fixture_pdf(path)
    window=MainWindow();errors=[]
    window.jobs.failed.disconnect();window.jobs.failed.connect(errors.append)
    try:
        window.import_paths([str(p) for p in paths],mode='new')
        wait(app,lambda:len(window.project.pages)==2 and not window.loading)
        window.set_mode('template');window.rectangle_selected([40,211,94,34])
        wait(app,lambda:len(window.project.groups)==1 and not window.loading)
        assert not window.current_page_only.isChecked()
        window.find_matches()
        assert 'Analizuję' in window.registry.actions['find'].text()
        wait(app,lambda:not window.busy,timeout=40)
        assert not errors and len(window.project.detections)==6
        assert {d.page for d in window.project.detections}=={0,1}
        assert window.registry.actions['find'].text()=='Znajdź'
    finally:
        window.jobs.close();window.dirty=window.busy=window.loading=False;window.close()


def test_visual_embedding_never_vetoes_strong_multimodal_evidence_alone():
    signals=dict(visual_ai_score=.4,geometry_score=.99,feature_score=.99,color_score=1.,
        device_label_score=1.,spatial_text_score=.95,text_role_confidence=.9)
    state,confidence,_=FinalDecisionEngine().decide('CUSTOM','CUSTOM',signals)
    assert state=='MATCH' and confidence<.95
    assert FinalDecisionEngine().decide('CUSTOM','OTHER',signals)[0]=='OTHER_VARIANT'
    weak={**signals,'geometry_score':.65,'feature_score':.5,'color_score':.3}
    assert FinalDecisionEngine().decide('CUSTOM','CUSTOM',weak)[0]=='REVIEW'
