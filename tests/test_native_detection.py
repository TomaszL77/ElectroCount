"""Regression cases use arbitrary query shapes, never a catalog of known codes."""
import os
from contextlib import nullcontext
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.text_engine import prepare_template, PdfTextItem, TextEngine
from electrocount.detection_engine import DetectionEngine
from electrocount.operation_progress import OperationProgress


def asymmetric_pdf(path):
    c=canvas.Canvas(str(path),pagesize=(600,600))
    for x,y,angle,label,missing in [(90,480,0,'ZX7',False),(300,480,90,'ZX7',False),
            (90,280,180,'ZX7',False),(300,280,270,'ZX7',False),
            (450,100,0,'ZX8',False),(90,100,0,'ZX7',True)]:
        c.saveState();c.translate(x,y);c.rotate(angle)
        c.rect(0,0,24,16,stroke=1,fill=0)
        if not missing:c.line(0,0,24,16);c.circle(6,8,2,stroke=1,fill=0)
        c.setFont('Helvetica',8);c.drawString(30,4,label);c.restoreState()
    c.setFont('Helvetica',8);c.drawString(350,100,'ZX7');c.save()


@pytest.mark.parametrize("budget",[40000,0])
def test_unseen_composite_rotations_require_full_shape_and_exact_label(tmp_path,budget):
    path=str(tmp_path/'arbitrary.pdf');asymmetric_pdf(path);pdf=PdfiumEngine(vector_segment_limit=budget)
    template=prepare_template(pdf,path,0,[85,98,61,28])
    result=DetectionEngine(pdf).find(path,0,template,'ZX7')
    assert len(result['matches'])==4
    assert len(result['discovered_other_label'])==1
    assert result['discovered_other_label'][0]['label']=='ZX8'
    assert not result['review']
    assert {round(h['verification_details']['rotation'])%360 for h in result['matches']}=={0,90,180,270}
    if budget:assert result['stages']['native_local']['text_seeded_paths']>0
    else:assert result['stages']['raster_used']
    assert all(h['graphic_score']>.95 and h['text_score']==1 for h in result['matches'])


def test_local_geometry_survives_global_budget_without_partial_evidence():
    path=str(Path(__file__).parent/'fixtures'/'rzut-testowy-demo.pdf')
    pdf=PdfiumEngine(vector_segment_limit=10)
    assert pdf.extract_vectors(path,0)['truncated']
    template=prepare_template(pdf,path,0,[106,175,67,21])
    assert template['signature']['native_local']
    result=DetectionEngine(pdf).find(path,0,template,'QP14')
    assert len(result['matches'])==4 and len(result['discovered_other_label'])==8
    assert not result['stages']['raster_used']


def test_thin_complete_bodies_ignore_wires_and_do_not_match_longer_body(tmp_path):
    path=str(tmp_path/'thin.pdf');c=canvas.Canvas(path,pagesize=(600,400))
    for x,length,label in [(80,26,'K92'),(220,26,'K92'),(360,52,'K92'),(480,26,'K93')]:
        c.setLineWidth(.1);c.line(x+.4,250,x+.4,350)
        c.rect(x,280,.8,length,fill=1,stroke=0)
        c.setFont('Helvetica',3.2 if x==220 else 8);c.drawString(x+4,289,label)
        c.setFont('Helvetica',1);c.drawString(x+2,276,'117W')
    c.save();pdf=PdfiumEngine()
    a=prepare_template(pdf,path,0,[77,91,30,32]);b=prepare_template(pdf,path,0,[75,88,36,48])
    assert a['label']==b['label']=='K92' and a['rect']==pytest.approx(b['rect'])
    assert a['rect'][2:]==pytest.approx([.8,26],abs=.002)
    r=DetectionEngine(pdf).find(path,0,b,'K92')
    assert len(r['matches'])==2 and len(r['discovered_other_label'])==1
    assert all(abs(h['rect'][0]-360)>10 for h in r['matches'])


def test_nested_form_and_rotated_label(tmp_path):
    path=str(tmp_path/'forms.pdf');c=canvas.Canvas(path,pagesize=(400,400))
    c.beginForm('device');c.rect(0,0,24,16);c.line(0,0,24,16);c.circle(6,8,2)
    c.setFont('Helvetica',8);c.drawString(30,4,'N84');c.endForm()
    for x,y,a in [(60,300,0),(240,160,90)]:
        c.saveState();c.translate(x,y);c.rotate(a);c.doForm('device');c.restoreState()
    c.save();pdf=PdfiumEngine();t=prepare_template(pdf,path,0,[56,80,66,24])
    r=DetectionEngine(pdf).find(path,0,t,'N84')
    assert len(r['matches'])==2 and not r['review']


def test_duplicate_text_and_power_annotation_are_not_label_ambiguity():
    label=PdfTextItem('R8','R8',0,[107,105,8,6],[111,108])
    watts=PdfTextItem('117W','117W',0,[101,115,3,1],[102.5,115.5])
    result=TextEngine().associate([100,100,2,26],[label,label,watts])
    assert result['item']==label


def test_compact_progress_keeps_status_percent_and_cancel(app):
    panel=OperationProgress();panel.resize(1000,60);panel.start('batch_match');app.processEvents()
    panel.set_progress(40);panel.set_stage('Strona 1/2 · Weryfikacja geometrii')
    assert panel.sizeHint().height()<80
    assert panel.bar.value()==40 and panel.cancel.isVisible() and panel.stage.text()
    panel.finish('batch_match');assert not panel.isVisible()


def test_real_hall_both_neighbor_templates_with_three_selection_margins():
    path=os.environ.get('ELECTROCOUNT_TEST_HALA')
    if not path:pytest.skip('Set ELECTROCOUNT_TEST_HALA to the supplied lighting PDF')
    pdf=PdfiumEngine();items=pdf.extract_text(path,0)
    with pdf.open_vector_page(path,0) as native:
        class ReusedPage(PdfiumEngine):
            def open_vector_page(self,*args):return nullcontext(native)
            def extract_text(self,*args):return items
        engine=ReusedPage()
        for x in (3153,3289.08):
            templates=[prepare_template(engine,path,0,[x,1389,16,h]) for h in (28,36,46)]
            assert all(t['label']=='L3' for t in templates)
            assert all(t['rect']==pytest.approx(templates[0]['rect']) for t in templates)
            result=DetectionEngine(engine).find(path,0,templates[-1],'L3')
            pair=[hit for hit in result['matches'] if 3150<hit['rect'][0]<3310 and 1385<hit['rect'][1]<1420]
            assert len(pair)==2
            assert all(hit['label']=='L3' for hit in result['matches'])
            assert all(hit['label']!='L3' for hit in result['discovered_other_label'])
            assert result['stages']['native_local']['index_bytes']<8*1024*1024
            assert not result['stages']['vector_limit_reached']


def test_colored_symbol_isolated_from_dense_gray_background(tmp_path):
    path=str(tmp_path/'foreground.pdf');c=canvas.Canvas(path,pagesize=(400,240))
    for x in (60,240):
        c.setStrokeColorRGB(.7,.7,.7)
        for offset in range(2,20):c.line(x+offset,110,x+offset,125)
        c.setStrokeColorRGB(.95,.3,.05);c.circle(x+12,120,12)
        c.line(x+5,114,x+19,123);c.line(x+19,123,x+19,115)
    c.save();pdf=PdfiumEngine();template=prepare_template(pdf,path,0,[45,105,51,31])
    assert template['signature']['foreground']=='chromatic'
    assert template['signature']['segment_count']==6
    result=DetectionEngine(pdf).find(path,0,template)
    assert len(result['matches'])==2


def test_clipped_shape_is_not_verified_as_an_unclipped_symbol(tmp_path):
    path=str(tmp_path/'clip.pdf');c=canvas.Canvas(path,pagesize=(400,250))
    for x,clipped in [(50,False),(230,True)]:
        c.saveState()
        if clipped:
            clip=c.beginPath();clip.rect(x,100,12,20);c.clipPath(clip,stroke=0,fill=0)
        c.rect(x,100,24,16);c.line(x,100,x+24,116);c.line(x+24,100,x,116)
        c.restoreState();c.setFont('Helvetica',8);c.drawString(x+30,104,'X9')
    c.save();pdf=PdfiumEngine();t=prepare_template(pdf,path,0,[46,130,66,26])
    r=DetectionEngine(pdf).find(path,0,t,'X9')
    assert len(r['matches'])==1
    assert r['stages']['raster_used']


def test_old_template_upgrades_on_search_and_preserves_project_page(tmp_path):
    from electrocount.domain import Group,Project
    from electrocount.results_manager import ResultsManager
    path=str(Path(__file__).parent/'fixtures'/'rzut-testowy-demo.pdf')
    legacy={'page':0,'rect':[106,175,67,21],'selection_rect':[106,175,67,21],
            'label':'QP14','text_aware':True,'signature':None}
    pdf=PdfiumEngine();result=DetectionEngine(pdf).find(path,0,legacy,'QP14')
    assert result['template']['definition_version']==4 and len(result['matches'])==4
    group=Group('Własna nazwa',label='QP14',template={**legacy,'page':7})
    project=Project(groups=[group]);ResultsManager().apply(project,group.id,7,result)
    assert group.name=='Własna nazwa' and group.template['page']==7
    assert group.template['signature']['native_local']


def test_native_index_cache_reopens_without_persisting_handles(tmp_path):
    from electrocount.pdf_cache import CachedPDFEngine
    path=str(tmp_path/'cached.pdf');asymmetric_pdf(path)
    cache=tmp_path/'cache';first=CachedPDFEngine(PdfiumEngine(),cache)
    t=prepare_template(first,path,0,[85,98,61,28])
    assert list(cache.glob('*.npz'))
    # A new adapter/document owns entirely new native handles.
    second=CachedPDFEngine(PdfiumEngine(),cache)
    r=DetectionEngine(second).find(path,0,t,'ZX7')
    assert r['stages']['native_local']['index_cache_hit']
    assert len(r['matches'])==4 and len(r['discovered_other_label'])==1
    import time
    stat=Path(path).stat();os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1000000))
    with second.open_vector_page(path,0) as page:
        assert not page.index_cache_hit
