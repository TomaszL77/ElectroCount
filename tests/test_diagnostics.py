import json
import os
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection, run_detection, self_test, result_signature
from electrocount.self_test_pdf import create_pdf
from electrocount.drawing_view import DrawingView
from electrocount.domain import Project, Group, Detection


def test_builtin_self_test_exports_actual_evidence(tmp_path):
    report=self_test(PdfiumEngine(),tmp_path/'diagnostic')
    assert report['status']=='PASS' and report['actual']==12
    log=json.loads((tmp_path/'diagnostic/detection_log.json').read_text(encoding='utf-8'))
    assert log['runtime']['renderer']=='PDFium'
    assert log['runtime']['packages']['PyMuPDF'] is None
    assert log['counts']['countable_devices']==12
    assert (tmp_path/'diagnostic/template_crop.png').is_file()
    assert (tmp_path/'diagnostic/page_render.png').is_file()
    assert len(list((tmp_path/'diagnostic').glob('candidate_*.png')))==12
    assert log['actual_matcher_renders']==[]  # native geometry, no fabricated bitmap input


@pytest.mark.parametrize('zoom',[.2,1,5])
def test_selection_release_maps_logical_pixels_to_pdf_once(app,zoom):
    view=DrawingView();view.resize(1000,700);view.show();view.set_page(2000,1500)
    view.resetTransform();view.scale(zoom,zoom);view.centerOn(800,700);view.set_mode('template')
    app.processEvents();selected=[];view.rectangle_selected.connect(selected.append)
    a=view.mapFromScene(QPointF(775,675));b=view.mapFromScene(QPointF(815,730))
    # No mouseMove: final event must determine the crop even when moves coalesce.
    QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=b)
    assert len(selected)==1
    assert selected[0]==pytest.approx([775,675,40,55],abs=1/zoom)
    context=view.last_selection_context
    assert context['pdf_selection_bbox']==selected[0]
    assert context['rendered_image_bbox']==pytest.approx([x*2 for x in selected[0]])
    assert context['devicePixelRatio']==view.devicePixelRatioF()
    view.close()


def test_markers_are_visible_without_changing_measured_boxes(app):
    view=DrawingView();view.set_page(6000,2000);view.resize(1000,700);view.show();view.fit()
    group=Group('L3');d=Detection(group.id,0,[2000,500,.72,25],label='L3',reason='native_text')
    project=Project(groups=[group],detections=[d],active=group.id)
    view.draw_detections(project,set())
    marker=view.overlays[0]
    assert marker.pen().isCosmetic() and marker.pen().widthF()>=2
    assert marker.rect().width()*view.transform().m11()>=7.99
    assert marker.brush().color().alpha() in range(30,51)
    assert d.rect==[2000,500,.72,25]
    view.draw_detections(project,set(),d.id)
    assert view.overlays[0].pen().widthF()>2
    group.visible=False;view.draw_detections(project,set());assert not view.overlays
    view.close()


def test_native_failure_uses_same_cpu_raster_fallback(tmp_path):
    path=tmp_path/'fixture.pdf';create_pdf(path);pdf=PdfiumEngine()
    template=prepare_detection(pdf,str(path),0,[36,36,55,25])
    class BrokenNative(PdfiumEngine):
        def open_vector_page(self,*a,**kw):raise RuntimeError('native backend unavailable')
    result=run_detection(BrokenNative(),str(path),0,template,'EC12')
    assert len(result['matches'])==12
    assert result['stages']['raster_used']
    assert any('CPU' in w for w in result['coverage_warnings'])


def test_stale_gui_cannot_silently_use_new_worker(tmp_path):
    path=tmp_path/'fixture.pdf';create_pdf(path);pdf=PdfiumEngine()
    template=prepare_detection(pdf,str(path),0,[36,36,55,25])
    with pytest.raises(RuntimeError,match='ponownie'):
        run_detection(pdf,str(path),0,template,'EC12',
            config={'gui_runtime':{'code':{'source_sha256':'old-build'}}})


def test_gui_diagnostic_command_uses_worker(app,tmp_path):
    from electrocount.main_window import MainWindow
    from test_ui import wait
    window=MainWindow();errors=[]
    window.jobs.failed.disconnect();window.jobs.failed.connect(errors.append)
    try:
        window.registry.invoke('diagnostic_test')
        wait(app,lambda:hasattr(window,'last_self_test') or bool(errors))
        assert not errors
        assert window.last_self_test['status']=='PASS' and window.last_self_test['actual']==12
    finally:
        window.jobs.close();window.busy=window.loading=window.dirty=False;window.close()


def test_legend_reference_is_separate_from_takeoff(tmp_path):
    from reportlab.pdfgen import canvas
    path=tmp_path/'legend.pdf';c=canvas.Canvas(str(path),pagesize=(600,400))
    c.setStrokeColorRGB(0,0,1);c.setFillColorRGB(0,0,1)
    for x in (40,140):
        c.rect(x,100,1,25,stroke=0,fill=1);c.setFont('Helvetica',8);c.drawString(x+5,110,'T8')
    c.setStrokeColorRGB(0,0,0);c.rect(400,40,170,320,stroke=1,fill=0)
    c.setFont('Helvetica',12);c.drawString(435,340,'LEGEND')
    c.setFillColorRGB(0,0,1);c.rect(445,220,2,50,stroke=0,fill=1)
    c.setFont('Helvetica',16);c.drawString(455,240,'T8');c.save()
    pdf=PdfiumEngine();t=prepare_detection(pdf,str(path),0,[35,270,25,36])
    result=run_detection(pdf,str(path),0,t,'T8')
    assert result['counts']=={'raw_matches':3,'legend_matches':1,'countable_devices':2}


@pytest.mark.skipif(not os.environ.get('ELECTROCOUNT_TEST_HALA'),reason='requires user hall PDF')
def test_real_hall_wide_selection_and_legend(tmp_path):
    from electrocount.pdf_cache import CachedPDFEngine
    path=os.environ['ELECTROCOUNT_TEST_HALA'];pdf=CachedPDFEngine(PdfiumEngine(),tmp_path/'cache')
    templates=[prepare_detection(pdf,path,0,b) for b in (
        [3153,1389,16,46],[3145,1380,40,55],[3140,1370,55,80],[3130,1360,80,100])]
    assert all(t['label']=='L3' and t['rect']==templates[0]['rect'] for t in templates)
    result=run_detection(pdf,path,0,templates[-1],'L3')
    assert result['counts']=={'raw_matches':73,'legend_matches':1,'countable_devices':72}
    assert len({tuple(h['label_bbox']) for h in result['matches']})==72
    assert all(800<h['label_bbox'][1]<1500 for h in result['matches'])
    with pytest.raises(ValueError,match='przecina'):
        prepare_detection(pdf,path,0,[3154,1395,14,20])
