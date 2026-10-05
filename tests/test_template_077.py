"""Focused selection and preview checks. No historical PDF or saved detections."""
import base64
import cv2
import numpy as np
import pytest
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection

SELECTION=[30.,35.,100.,80.]


def document(tmp_path,kind='multi'):
    path=tmp_path/(kind+'.pdf');c=canvas.Canvas(str(path),pagesize=(240,180))
    c.setFont('Helvetica',9);c.drawString(10,15,'fresh stage 1')
    if kind=='raster':
        from PIL import Image,ImageDraw
        im=Image.new('RGB',(180,90),'white');d=ImageDraw.Draw(im)
        d.rectangle((8,8,170,82),outline='magenta',width=4)
        d.line((15,45,125,45),fill='black',width=4);d.ellipse((125,25,165,65),outline='black',width=3)
        file=tmp_path/'fresh.png';im.save(file);c.drawImage(str(file),40,95,75,35)
    else:
        c.setStrokeColorRGB(1,0,1) if kind=='color' else c.setStrokeColorRGB(0,0,0)
        c.rect(40,100,48,25,stroke=1,fill=0)
        c.setStrokeColorRGB(0,0,0);c.setFillColorRGB(0,0,0)
        if kind=='filled':c.rect(42,107,40,3,stroke=0,fill=1)
        else:c.line(42,110,78,110)
        c.circle(100,112,8,stroke=1,fill=0)
        c.setFont('Helvetica',10);c.drawString(115,108,'7')
    c.save();pdf=PdfiumEngine()
    return pdf,str(path)


def test_1_all_selected_parts_survive(tmp_path):
    pdf,path=document(tmp_path);box=SELECTION.copy()
    with pdf.open_vector_page(path,0) as page:
        selected=page.decode(page.query(box),preserve=True)
    t=prepare_detection(pdf,path,0,box)
    assert t['signature']['paths']==selected
    assert t['preserved_paths']==3 and t['removed_paths']==0
    assert t['selection_bbox']==SELECTION and t['label']=='7'
    box[0]=999
    assert t['selection_bbox']==SELECTION


def test_2_coloured_outline_keeps_black_parts(tmp_path):
    pdf,path=document(tmp_path,'color');t=prepare_detection(pdf,path,0,SELECTION)
    colours={tuple(p['color'][:3]) for p in t['signature']['paths']}
    assert (255,0,255) in colours and (0,0,0) in colours
    assert len(t['signature']['paths'])==3 and t['signature']['foreground']=='all'


def test_3_filled_core_keeps_extra_parts(tmp_path):
    pdf,path=document(tmp_path,'filled');t=prepare_detection(pdf,path,0,SELECTION)
    assert len(t['signature']['paths'])==3
    assert sum(bool(p.get('fill')) for p in t['signature']['paths'])==1
    assert not t['signature']['core_fill']


def test_4_original_rgb_and_preview_equal_selection(tmp_path,app):
    from PySide6.QtGui import QImage
    from electrocount.template_preview import TemplatePreview
    pdf,path=document(tmp_path,'raster');debug=tmp_path/'debug'
    t=prepare_detection(pdf,path,0,SELECTION,debug_dir=debug)
    rep=t['representation'];raw=base64.b64decode(rep['original_rgb_crop']['png_base64'])
    decoded=cv2.cvtColor(cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    assert np.array_equal(decoded,pdf.render(path,0,2.,SELECTION))
    assert decoded.shape[:2]==(160,200)
    assert rep['selection_bbox']==rep['matching_bbox']==SELECTION
    assert t['signature'] is None and t['self_match']['passed']
    preview=TemplatePreview();preview.set_template(t)
    assert preview.original==QImage.fromData(raw)
    assert {p.name for p in debug.iterdir()}=={'selection_crop.png','matching_crop.png','template_log.json'}


def test_5_self_match_finds_source_and_rejects_broken_template(tmp_path,monkeypatch):
    from electrocount.detection_engine import DetectionEngine
    from electrocount.domain import overlap_metrics
    from electrocount.template_self_match import validate_self_match
    from electrocount.vector_engine import VectorCandidateGenerator
    pdf,path=document(tmp_path,'color');t=prepare_detection(pdf,path,0,SELECTION)
    t['source']='LEGEND'
    r=DetectionEngine(pdf).find(path,0,t)
    assert t['self_match']=={'passed':True,'method':'local_vector_search'}
    assert any(overlap_metrics(h['rect'],t['symbol_bbox'])[0]>.95 for h in r['legend_matches'])
    assert not r['matches']  # source exemplar isn't added to the takeoff
    monkeypatch.setattr(VectorCandidateGenerator,'find',lambda *a,**kw:[])
    validate_self_match(pdf,path,0,t)
    assert not t['self_match']['passed']
    assert t['preparation_warnings']
    # A failed matcher must not prevent creating a new, exact selection.
    prepared=prepare_detection(pdf,path,0,SELECTION)
    assert prepared['representation']['original_rgb_crop']==t['representation']['original_rgb_crop']
    assert not prepared['self_check']


def test_small_symbol_self_match_failure_keeps_sharp_original(tmp_path,app):
    from electrocount.template_preview import TemplatePreview
    path=tmp_path/'tiny.pdf'
    c=canvas.Canvas(str(path),pagesize=(100,100))
    c.setStrokeColorRGB(1,0,1);c.setLineWidth(.15);c.circle(50,50,.6)
    c.save();pdf=PdfiumEngine();box=[48.125,48.25,3.75,3.5]
    t=prepare_detection(pdf,str(path),0,box)
    # The vector anchor requires a segment >1pt; this valid circle has none.
    assert not t['self_check'] and t['preparation_warnings']
    rep=t['representation'];record=rep['original_rgb_crop']
    raw=base64.b64decode(record['png_base64'])
    decoded=cv2.cvtColor(cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    assert record['scale']==12 and record['bbox']==box
    assert np.array_equal(decoded,pdf.render(str(path),0,record['scale'],box))
    assert np.any((decoded[:,:,0]>200)&(decoded[:,:,1]<100)&(decoded[:,:,2]>200))
    import json
    restored=json.loads(json.dumps(t))
    preview=TemplatePreview();preview.set_template(restored);preview.resize(300,82)
    assert not preview.original.isNull() and preview.grab().width()==300
    assert 'Test rozpoznawania' in preview.toolTip()


@pytest.mark.parametrize('zoom',[.5,2.,8.])
def test_fractional_drag_preserves_exact_scene_selection(app,zoom):
    from PySide6.QtCore import QPointF,Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent
    from electrocount.drawing_view import DrawingView
    view=DrawingView();view.resize(600,500);view.set_page(1000,1000)
    view.resetTransform();view.scale(zoom,zoom);view.set_mode('template')
    view.show();app.processEvents()
    start=QPointF(250.75,230.25);end=QPointF(150.125,130.875)
    inverse=view.viewportTransform().inverted()[0]
    from PySide6.QtCore import QRectF
    expected=QRectF(inverse.map(start),inverse.map(end)).normalized().intersected(view.page_rect)
    emitted=[];view.rectangle_selected.connect(emitted.append)
    view.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress,start,start,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
    # Release without a move event, as can happen on Windows.
    view.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease,end,end,Qt.LeftButton,Qt.NoButton,Qt.NoModifier))
    assert emitted==[[expected.x(),expected.y(),expected.width(),expected.height()]]
    view.close()
