"""Focused data/training/inference/GUI checks, fresh examples only."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from electrocount.ai.learning_store import LearningStore, decode
from electrocount.ai.tiny_model import TinyPairModel, pair_features
from electrocount.ai.learning_training import train
from electrocount.domain import Group, Detection, Document, Project
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection, run_detection
from electrocount.main_window import MainWindow
from test_render_0772 import wait


def symbol(variant=False, offset=0):
    image = np.full((64, 64, 3), 255, np.uint8)
    if variant:
        cv2.rectangle(image, (15 + offset, 17), (49 + offset, 47), (0, 0, 0), 2)
    else:
        cv2.circle(image, (32 + offset, 32), 17, (0, 0, 0), 2)
        cv2.line(image, (18 + offset, 32), (46 + offset, 32), (0, 0, 0), 2)
    return image


def seed(store):
    for doc in range(4):
        minimum = 10 if doc < 2 else 5
        for positive in (True, False):
            for i in range(minimum):
                store.record(dict(document=hashlib.sha256(f'doc-{doc}'.encode()).hexdigest(),
                    document_name=f'drawing-{doc}.pdf', page=0, group_id=f'g-{doc}', group_name='Oprawa',
                    rect=[i * 10, 10 if positive else 40, 8, 8],
                    outcome='correct' if positive else 'wrong', metadata={'detection_id':f'{doc}-{positive}-{i}'}),
                    symbol(), symbol(not positive, (i % 3) - 1))


def test_feedback_dedup_portable_import_document_splits_and_reconcile(tmp_path):
    store = LearningStore(tmp_path / 'a'); seed(store)
    assert store.readiness()[0]
    rows = store.examples(); assert len(rows) == 60
    assert all(len({r['split'] for r in rows if r['document'] == doc}) == 1 for doc in {r['document'] for r in rows})
    row = rows[0]
    store.record({**row, 'outcome':'uncertain'}, row['reference'], row['crop'])
    assert len(store.examples()) == 60
    package = tmp_path / 'examples.zip'; store.export_data(package)
    restored = LearningStore(tmp_path / 'b'); assert restored.import_data(package) == 60
    assert restored.counts() == store.counts()
    assert np.array_equal(decode(restored.examples()[0]['reference']), decode(row['reference']))
    restored.split_document(row['document'], 'train')
    assert all(r['split'] == 'train' for r in restored.examples() if r['document'] == row['document'])
    restored.reconcile({rows[1]['metadata']['detection_id']:'uncertain'})
    assert next(r for r in restored.examples() if r['id'] == rows[1]['id'])['outcome'] == 'uncertain'


def test_real_training_weights_heldout_report_and_portable_predictions(tmp_path):
    store = LearningStore(tmp_path / 'data'); seed(store)
    progress = []; report = train(store.directory, progress.append, epochs=45)
    assert progress[-1] == 100
    splits = report['documents']
    assert not set(splits['train']) & set(splits['test'])
    assert not set(splits['train']) & set(splits['validation'])
    assert not set(splits['validation']) & set(splits['test'])
    path = store.directory / 'models' / report['model_file']
    model = TinyPairModel.load(path)
    assert not np.array_equal(model.w1, TinyPairModel().w1)
    assert model.score(symbol(), symbol()) > model.score(symbol(), symbol(True))
    assert report['comparisons']['model']['count'] == 10
    assert report['comparisons']['model']['precision'] >= .9
    copied = tmp_path / 'other-pc.ecmodel'; copied.write_bytes(path.read_bytes())
    assert TinyPairModel.load(copied).score(symbol(), symbol(True)) == model.score(symbol(), symbol(True))
    assert path.stat().st_size < 500_000


def test_training_refuses_incomplete_and_uncertain_examples(tmp_path):
    store = LearningStore(tmp_path); assert not store.readiness()[0]
    with pytest.raises(ValueError): train(tmp_path, epochs=1)
    seed(store)
    for row in store.examples(False):
        if row['split'] == 'test': store.assess(row['id'], 'uncertain')
    assert not store.readiness()[0]
    with pytest.raises(ValueError): train(tmp_path, epochs=1)


def test_no_large_encoder_in_fast_mode_and_existing_native_hits_are_preserved(document, monkeypatch):
    path, selection = document
    pdf = PdfiumEngine(); template = prepare_detection(pdf, str(path), 0, selection['rect'])
    from electrocount.ai.model_manager import ModelManager
    monkeypatch.setattr(ModelManager, 'load_visual_encoder', lambda *a, **k: (_ for _ in ()).throw(AssertionError('Large model loaded')))
    classic = run_detection(pdf, str(path), 0, template, 'A1', config={'engine_mode':'classic'})
    fast = run_detection(pdf, str(path), 0, template, 'A1', config={'engine_mode':'learned'})
    assert len(classic['matches']) == len(fast['matches']) == 8
    assert classic['result_sha256'] == fast['result_sha256']
    assert not fast['stages']['ai_retrieval']
    assert fast['pipeline']['engine_mode'] == 'learned'


def test_failed_geometry_recovered_by_model_requires_review_and_other_labels_stay_other(document, monkeypatch):
    from electrocount.detection_engine import DetectionEngine
    from electrocount.feature_matcher import OpenCVFeatureMatcher
    path, selection = document; pdf = PdfiumEngine()
    template = prepare_detection(pdf, str(path), 0, selection['rect'])
    class Proposals:
        def find(self, *args, **kwargs):
            return [dict(rect=[110, 458, 28, 12], score=.95), dict(rect=[110, 178, 28, 12], score=.95)]
    class Features:
        def verify(self, *args):
            return dict(verified=False, geometry_score=.4, feature_score=.4)
    class Model:
        metadata={'threshold':.9}
        def score(self,*args): return .99
    result = DetectionEngine(pdf, matcher=Proposals(), feature_matcher=Features(), learned_model=Model()).find(str(path),0,template,'A1')
    assert not result['matches']
    assert any(h['reason'] == 'learned_pair_review' for h in result['review'])
    assert any(h['label'] == 'QP14' for h in result['discovered_other_label'])
    assert result['stages']['learned_recovered'] == 2


def test_fast_scan_preserves_native_symbols_when_selection_contains_label(tmp_path):
    from electrocount.self_test_pdf import create_pdf
    path = tmp_path / 'native-labels.pdf'; create_pdf(path)
    pdf = PdfiumEngine()
    template = prepare_detection(pdf, str(path), 0, [36, 36, 55, 25])
    assert template['rect'] != template['raster_rect']
    classic = run_detection(pdf, str(path), 0, template, 'EC12', config={'engine_mode':'classic'})
    fast = run_detection(pdf, str(path), 0, template, 'EC12', config={'engine_mode':'learned'})
    assert len(classic['matches']) == len(fast['matches']) == 12
    assert not fast['review']
    assert classic['result_sha256'] == fast['result_sha256']


def test_gui_collection_worker_review_panel_and_undo(app, document, tmp_path):
    path, selection = document; pdf = PdfiumEngine()
    project = Project(); project.append_document(Document(str(path), 'Drawing'), pdf.inspect(str(path)))
    template = prepare_detection(pdf, str(path), 0, selection['rect'])
    group = Group('A1', template=template, label='A1'); project.groups=[group]; project.active=group.id
    detection = Detection(group.id,0,[110,458,28,12],label='A1'); project.detections=[detection]
    window = MainWindow(); window.show(); errors=[]; window.learning.failed.connect(errors.append)
    try:
        window.replace_project(project, None); window.selected=detection.id
        assert window.engine_mode() == 'learned'
        assert not window.learning_store.examples()
        window.decide('accepted'); wait(app, lambda:not window.learning.busy)
        rows=window.learning_store.examples(); assert len(rows)==1 and rows[0]['outcome']=='correct'
        window.undo(); wait(app,lambda:not window.learning.busy)
        assert window.learning_store.examples()[0]['outcome']=='uncertain'
        window.selected=detection.id; window.redo(); wait(app,lambda:not window.learning.busy)
        assert window.learning_store.examples()[0]['outcome']=='correct'
        window.show_learning(); app.processEvents()
        assert window.learning_panel.table.rowCount()==1
        assert not window.learning_panel.train_button.isEnabled()
        assert not errors
    finally:
        wait(app,lambda:not window.learning.busy)
        window.dirty=False;window.close()
    assert window.learning.process is None


def test_reassign_feedback_history_does_not_teach_both_groups_as_correct(app, document, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    path, selection = document; pdf=PdfiumEngine(); project=Project()
    project.append_document(Document(str(path),'Drawing'),pdf.inspect(str(path)))
    template=prepare_detection(pdf,str(path),0,selection['rect'])
    a,b=Group('A',template=template,label='A1'),Group('B',template=template,label='A1')
    project.groups=[a,b];project.active=a.id
    detection=Detection(a.id,0,[110,458,28,12],decision='accepted',label='A1')
    project.detections=[detection]
    window=MainWindow();window.show()
    try:
        window.replace_project(project,None);window.selected=detection.id
        monkeypatch.setattr(QInputDialog,'getItem',lambda *args,**kwargs:('2. B',True))
        window.reassign();wait(app,lambda:not window.learning.busy)
        outcomes=lambda:{r['group_id']:r['outcome'] for r in window.learning_store.examples(False)}
        assert outcomes()=={a.id:'variant',b.id:'correct'}
        window.undo();wait(app,lambda:not window.learning.busy)
        assert outcomes()=={a.id:'correct',b.id:'variant'}
        window.redo();wait(app,lambda:not window.learning.busy)
        assert outcomes()=={a.id:'variant',b.id:'correct'}
    finally:
        wait(app,lambda:not window.learning.busy);window.dirty=False;window.close()


def test_training_cancellation_keeps_data_previous_model_and_pending_assessments(app,tmp_path):
    from electrocount.learning_service import LearningService
    store=LearningStore(tmp_path);seed(store)
    previous=tmp_path/'previous.ecmodel';TinyPairModel().save(previous);before=previous.read_bytes()
    service=LearningService(tmp_path);errors=[];service.failed.connect(errors.append)
    try:
        identifier=store.examples(False)[0]['metadata']['detection_id']
        service.submit({'kind':'train'})
        service.submit({'kind':'reconcile','assessments':{identifier:'uncertain'}})
        wait(app,lambda:bool(service.current and service.current['kind']=='train'))
        service.cancel_training();wait(app,lambda:not service.busy)
        assert len(store.examples(False))==60 and previous.read_bytes()==before
        assert next(r for r in store.examples(False) if r['metadata']['detection_id']==identifier)['outcome']=='uncertain'
        assert not errors
    finally:
        service.close()
