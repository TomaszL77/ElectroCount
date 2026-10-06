"""Workflows for outlined labels, retained originals, and cumulative feedback."""
import numpy as np
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.ocr_engine import TextOverridePDF
from electrocount.text_engine import PdfTextItem,prepare_template
from electrocount.detection_engine import DetectionEngine
from electrocount.ai.learning_store import LearningStore
from electrocount.ai.learning_training import train
from electrocount.domain import Document,Group,Project
from electrocount.main_window import MainWindow
from test_learning_078 import symbol


def test_white_backing_and_external_outline_code_keep_original_parts(tmp_path):
    path=str(tmp_path/'paths.pdf');c=canvas.Canvas(path,pagesize=(300,200))
    c.setFillColorRGB(1,1,1);c.rect(0,0,300,200,fill=1,stroke=0)
    for x in (40,140):
        c.setStrokeColorRGB(1,0,0);c.setFillColorRGB(1,0,0)
        c.rect(x,100,16,8,stroke=1,fill=0)
        c.circle(x+8,104,1.5,stroke=0,fill=1)
        c.rect(x,115,12,3,stroke=0,fill=1)
    c.save();pdf=PdfiumEngine()
    items=[PdfTextItem(code,code,0,[x,82,12,3],[x+6,83.5],source='pdf_outline')
           for x,code in [(40,'AW3'),(140,'AW5')]]
    wrapped=TextOverridePDF(pdf,path,0,items)
    selection=[37,79,23,24];t=prepare_template(wrapped,path,0,selection)
    assert t['label']=='AW3' and t['geometry_source']=='native_local'
    assert len(t['signature']['paths'])==3 and len(t['analysis_signature']['paths'])==2
    assert t['selection_bbox']==t['matching_bbox']==t['raster_rect']==selection
    r=DetectionEngine(wrapped).find(path,0,t,'AW3')
    assert len(r['matches'])==1 and r['matches'][0]['label']=='AW3'
    assert any(h['label']=='AW5' for h in r['discovered_other_label'])
    assert r['template']['selection_bbox']==selection
    from electrocount.learning_worker import capture
    from electrocount.ai.learning_store import decode
    capture(dict(template=t,template_path=path,template_page=0,path=path,page=0,
        rect=r['matches'][0]['rect'],group_id='A',group_name='AW3',outcome='correct',
        directory=str(tmp_path/'feedback')),wrapped)
    feedback=LearningStore(tmp_path/'feedback').examples()[0]
    reference=decode(feedback['reference'])
    assert reference.shape[1]/reference.shape[0]>1.7
    # Explicitly reviewed parts remain the source of truth when opening an old project.
    t['definition_version']=11;t['extraction_mode']='reviewed_apparatus_parts'
    preserved=DetectionEngine(wrapped).find(path,0,t,'AW3')
    assert preserved['template']['extraction_mode']=='reviewed_apparatus_parts'
    assert preserved['template']['signature']==t['signature']
    from electrocount.results_manager import ResultsManager
    group=Group('LEGENDA',label='LEGENDA',template=t);project=Project(groups=[group])
    ResultsManager().apply(project,group.id,0,r)
    assert group.name==group.label=='AW3'


def test_closed_cell_legend_and_heading_are_not_device_codes(tmp_path):
    from electrocount.document_regions import legend_regions
    from electrocount.text_roles import TextRoleClassifier
    p=str(tmp_path/'cells.pdf');c=canvas.Canvas(p,pagesize=(900,450))
    for y in range(100,340,20):
        c.rect(30,y,45,20);c.rect(75,y,180,20)
    c.rect(44,304,14,6);c.save();pdf=PdfiumEngine()
    with pdf.open_vector_page(p,0) as native:
        regions=legend_regions(native,[])
    assert any(r.get('layout')=='symbol_description' for r in regions)
    assert prepare_template(pdf,p,0,[42,138,18,10])['source']=='LEGEND'
    assert TextRoleClassifier().classify('LEGENDA')[0]=='DESCRIPTION'


def test_import_retains_user_correction_and_prior_examples(tmp_path):
    original=LearningStore(tmp_path/'local');incoming=LearningStore(tmp_path/'incoming')
    row=dict(document='old-pdf',page=0,group_id='A',group_name='A',rect=[1,2,8,8],
        outcome='correct',metadata={'assessment_origin':'assistant_visual_review'},split='train')
    incoming.record(row,symbol(),symbol());archive=tmp_path/'update.zip';incoming.export_data(archive)
    identifier=original.record({**row,'outcome':'wrong','metadata':{}},symbol(),symbol(True))
    assert original.import_data(archive)==0
    assert original.examples(False)[0]['id']==identifier
    assert original.examples(False)[0]['outcome']=='wrong'


def test_cumulative_training_freezes_control_locations(tmp_path):
    store=LearningStore(tmp_path/'data')
    def add(document):
        for i in range(100):
            good=i%2==0
            store.record(dict(document=document,page=0,group_id='shape',group_name='shape',
                rect=[i*10,10,8,8],outcome='correct' if good else 'wrong',split='train'),
                symbol(),symbol(not good))
    add('first');first=train(store.directory,epochs=1,preliminary=True)
    frozen={r['id']:r['metadata']['preliminary_split'] for r in store.examples(False)}
    edited=store.examples()[0]
    store.record({**edited,'metadata':{}},edited['reference'],edited['crop'])
    add('second');second=train(store.directory,epochs=1,preliminary=True)
    assert sum(second['counts'].values())==200
    assert all(r['metadata']['preliminary_split']==frozen[r['id']] for r in store.examples(False) if r['id'] in frozen)
    assert len(second['source_documents'])==2


def test_explicit_group_name_survives_template_preparation(app,document,monkeypatch):
    path,selection=document;pdf=PdfiumEngine();project=Project()
    project.append_document(Document(str(path),'Drawing'),pdf.inspect(str(path)))
    group=Group('AW3 — własna nazwa');project.groups=[group];project.active=group.id
    window=MainWindow();window.show()
    try:
        window.replace_project(project,None);window.set_mode('template')
        def submit(request,success,failure=None):
            template=prepare_template(pdf,str(path),0,selection['rect'])
            template['label']='';template['representation']={'group_id':None}
            success(template)
        monkeypatch.setattr(window.jobs,'submit',submit)
        window.rectangle_selected(selection['rect'])
        assert group.name=='AW3 — własna nazwa' and group.template is not None
    finally:
        window.loading=False;window.dirty=False;window.close()
