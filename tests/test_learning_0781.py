"""Focused checks for review queue, foreground and shape fallback."""
import cv2
import numpy as np
from electrocount.foreground import matching_scores, matching_mask, shape_evidence, transparent_selection
from electrocount.ai.tiny_model import TinyPairModel, pair_features, LEGACY_SCHEMA
from electrocount.domain import Project, Document, Group, Detection
from electrocount.main_window import MainWindow
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection
from test_render_0772 import wait
from test_learning_078 import symbol


def test_bulk_review_queue_preserves_ratings_and_never_trains_pending(app,document,tmp_path):
    path,selection=document;pdf=PdfiumEngine();project=Project()
    project.append_document(Document(str(path),'Drawing'),pdf.inspect(str(path)))
    template=prepare_detection(pdf,str(path),0,selection['rect'])
    group=Group('A1',template=template,label='A1');project.groups=[group];project.active=group.id
    project.detections=[Detection(group.id,0,[110+i*180,458,28,12],decision='review' if i<3 else 'accepted',label='A1') for i in range(4)]
    window=MainWindow();window.show();errors=[];window.learning.failed.connect(errors.append)
    try:
        window.replace_project(project,None)
        window.record_feedback(project.detections[0],'wrong');wait(app,lambda:not window.learning.busy)
        window.show_learning();app.processEvents()
        window.learning_panel.add_review_button.click();wait(app,lambda:not window.learning.busy)
        rows=window.learning_store.examples(False)
        assert sorted(r['outcome'] for r in rows)==['pending','pending','wrong']
        assert window.add_review_to_learning()==0
        assert all(d.decision=='review' for d in project.detections[:3])
        assert not window.learning_store.readiness()[0]
        pending=next(r for r in rows if r['outcome']=='pending')
        panel=window.learning_panel
        panel.table.selectRow(next(i for i,r in enumerate(panel.rows) if r['id']==pending['id']))
        panel.assessment.setCurrentText('Poprawny');panel.change_assessment()
        assert next(r for r in window.learning_store.examples(False) if r['id']==pending['id'])['outcome']=='correct'
        package=tmp_path/'queue.zip';window.learning_store.export_data(package)
        from electrocount.ai.learning_store import LearningStore
        copy=LearningStore(tmp_path/'portable');copy.import_data(package)
        assert copy.counts()==window.learning_store.counts()
        assert window.add_review_to_learning()==0 and not errors
        # Re-searching creates a fresh detection ID at an already rated place.
        from uuid import uuid4
        project.detections[0].id=uuid4().hex
        assert window.add_review_to_learning()==1
        wait(app,lambda:not window.learning.busy)
        assert len(window.learning_store.examples(False))==3
        assert next(r for r in window.learning_store.examples(False) if r['rect']==project.detections[0].rect)['outcome']=='wrong'
        assert window.add_review_to_learning()==0
    finally:
        wait(app,lambda:not window.learning.busy);window.dirty=False;window.close()


def test_foreground_match_ignores_exterior_ink_but_keeps_hollow_shape(tmp_path):
    pattern=np.full((70,100),255,np.uint8)
    cv2.rectangle(pattern,(30,24),(66,45),0,2)
    candidate=pattern.copy();cv2.line(candidate,(2,5),(92,5),0,2)
    assert matching_scores(candidate,pattern)[0,0]>.999
    assert matching_mask(pattern)[0,0]==0 and matching_mask(pattern)[34,45]==1
    assert shape_evidence(pattern,candidate)
    filled=pattern.copy();cv2.rectangle(filled,(30,24),(66,45),0,-1)
    assert matching_scores(filled,pattern)[0,0]<.7
    assert shape_evidence(pattern,filled) is None
    rgb=np.repeat(pattern[:,:,None],3,axis=2);rgba=transparent_selection(rgb)
    assert np.array_equal(rgba[:,:,:3],rgb) and rgba.shape[:2]==rgb.shape[:2]
    assert rgba[0,0,3]==0 and rgba[24,40,3]==255
    # Full raster page: recover both copies despite exterior clutter, retain
    # tight symbol boxes and the original selection with every selected part.
    from PIL import Image,ImageDraw
    from reportlab.pdfgen import canvas
    from electrocount.detection_service import run_detection
    image=Image.new('RGB',(420,160),'white');draw=ImageDraw.Draw(image)
    for x in (70,270):
        draw.ellipse((x,55,x+40,95),outline='black',width=2)
        draw.line((x+5,75,x+35,75),fill='black',width=2)
    draw.line((255,40,325,40),fill='black',width=2)
    image.save(tmp_path/'symbols.png')
    path=tmp_path/'raster.pdf';c=canvas.Canvas(str(path),pagesize=(420,160))
    c.drawImage(str(tmp_path/'symbols.png'),0,0,420,160);c.setFont('Helvetica',9)
    for x in (70,270):c.drawString(x+46,80,'A1')
    c.save();pdf=PdfiumEngine();box=[55,30,75,80]
    template=prepare_detection(pdf,str(path),0,box)
    result=run_detection(pdf,str(path),0,template,'A1',config={'engine_mode':'learned'})
    assert template['selection_bbox']==box and result['template']['selection_bbox']==box
    hits=result['matches']+result['review']
    assert len(hits)==2 and {h['label'] for h in hits}=={'A1'}
    assert sorted(round(h['rect'][0]) for h in hits)==[70,270]
    assert all(40<=h['rect'][2]<=43 for h in hits)


def test_new_ai_features_ignore_paper_and_legacy_models_keep_their_input(tmp_path):
    image=symbol();padded=cv2.copyMakeBorder(image,17,41,33,11,cv2.BORDER_CONSTANT,value=(255,255,255))
    assert np.array_equal(pair_features(image,image),pair_features(padded,image))
    old=TinyPairModel();old.metadata['schema']=LEGACY_SCHEMA
    old.save(tmp_path/'old.ecmodel');loaded=TinyPairModel.load(tmp_path/'old.ecmodel')
    expected=float(old.predict(pair_features(padded,image,foreground=False)))
    assert loaded.score(padded,image)==expected
    assert TinyPairModel().score(padded,image)==TinyPairModel().score(image,image)


def test_shape_agreement_recovers_failed_geometry_only_to_review_and_keeps_other_label(document):
    from electrocount.detection_engine import DetectionEngine
    path,selection=document;pdf=PdfiumEngine()
    template=prepare_detection(pdf,str(path),0,selection['rect'])
    class Proposals:
        def find(self,*args,**kwargs):
            return [dict(rect=[110,458,28,12],score=1.),dict(rect=[110,178,28,12],score=1.)]
    class StrictFeatures:
        def verify(self,*args):
            return dict(verified=False,geometry_score=.4,feature_score=.4)
    result=DetectionEngine(pdf,matcher=Proposals(),feature_matcher=StrictFeatures(),fast=True).find(str(path),0,template,'A1')
    assert not result['matches']
    assert len(result['review'])==1 and result['review'][0]['reason']=='shape_similarity_review'
    assert result['review'][0]['signals']['foreground_shape_score']>.9
    assert len(result['discovered_other_label'])==1 and result['discovered_other_label'][0]['label']=='QP14'
    assert result['stages']['shape_recovered']==2
