import json
from dataclasses import asdict,replace
from pathlib import Path
import pytest
from electrocount.performance import execution_plan,auto_profile,BackendResourceError
from electrocount.runtime_runner import run_with_fallback
from electrocount.hardware_profiler import HardwareProfiler,benchmark_pdf
from electrocount.ai.engine import AIEngine
from electrocount.ai.model_manager import ModelManager
from electrocount.ai.context_engine import ContextEngine
from electrocount.ai.training_dataset import TrainingDatasetManager
from electrocount.ai.contracts import DocumentEntity
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_engine import DetectionEngine
from electrocount.text_engine import prepare_template,TextEngine
from electrocount.domain import Project,Group
from electrocount.results_manager import ResultsManager
from electrocount.project_manager import ProjectManager

FIXTURES=Path(__file__).parent/'fixtures'


def measured_report(ram=8000):
    return {"hardware":{"available_ram_mb":ram,"total_ram_mb":16000,
            "cpu":{"logical_cores":8,"physical_cores":4},"gpus":[{"name":"Top GPU","dedicated_vram_mb":48000}]},
            "benchmarks":{"pdf_render":{"status":"measured","median_ms":25},
                          "feature_extraction":{"status":"measured","median_ms":25}}}


def test_fixed_execution_ignores_hardware():
    assert execution_plan('MAXIMUM',measured_report())==execution_plan('ECO',measured_report(500))


def test_profiler_cache_keeps_live_available_ram_and_invalidates_hardware(tmp_path,monkeypatch):
    profiler=HardwareProfiler();hardware=measured_report()['hardware']
    monkeypatch.setattr(profiler,'collect',lambda:dict(hardware))
    cache=tmp_path/'profile.json'
    first=profiler.run(cache)
    assert first['benchmarks']['pdf_render']['status']=='measured'
    assert first['benchmarks']['feature_extraction']['status']=='measured'
    assert first['benchmarks']['embedding_inference']['status']=='skipped'
    assert first['benchmarks']['gpu_inference']['status']=='skipped'
    hardware['available_ram_mb']=400
    second=profiler.run(cache)
    assert second['cached'] and second['hardware']['available_ram_mb']==400
    assert execution_plan('AUTO',second).effective=='DETERMINISTIC'
    hardware['cpu']={'logical_cores':2,'physical_cores':2}
    assert not profiler.run(cache)['cached']
    cache.write_text('broken',encoding='utf-8')
    assert not profiler.run(cache)['cached']


def test_profiler_exhausted_budget_is_explicit_not_fake_measurement(tmp_path,monkeypatch):
    profiler=HardwareProfiler();monkeypatch.setattr(profiler,'collect',lambda:measured_report()['hardware'])
    report=profiler.run(tmp_path/'cache.json',budget_seconds=0)
    assert report['benchmarks']['pdf_render']['status']=='skipped'
    assert execution_plan('AUTO',report).effective=='DETERMINISTIC'


def test_local_model_registry_checksum_and_traversal(tmp_path):
    import hashlib
    root=tmp_path/'models';manager=ModelManager(root)
    assert manager.list_models()==[] and not root.exists()
    folder=root/'encoder'/'v001';folder.mkdir(parents=True)
    artifact=folder/'weights.bin';artifact.write_bytes(b'test-only-weights')
    manifest=dict(name='encoder',version='v001',role='symbol_encoder',filename='weights.bin',
        checksum=hashlib.sha256(artifact.read_bytes()).hexdigest(),required_ram_mb=100,required_vram_mb=0,backends=['CPU','WinML'])
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    assert manager.list_models()[0]['status']=='unverified'
    assert manager.inspect('encoder','v001')['status']=='verified'
    assert not manager.inspect('encoder','v001')['active']
    artifact.write_bytes(b'changed')
    assert manager.inspect('encoder','v001')['status']=='checksum_mismatch'
    manifest['filename']='../../../outside.bin'
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    assert manager.list_models()[0]['status']=='invalid'


def test_context_and_training_are_inactive_no_fake_scores(tmp_path):
    entity=DocumentEntity('candidate','document',0,'symbol',(10,10,20,10),(20,15))
    evidence=ContextEngine().evaluate(entity)
    assert evidence.score is None and evidence.ambiguous
    assert TrainingDatasetManager().record(None,None) is False
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('mode',['ECO','STANDARD','ENHANCED','MAXIMUM'])
def test_ai_facade_preserves_exact_counts_and_save(mode,tmp_path):
    import cv2
    engine=PdfiumEngine();path=str(FIXTURES/'rzut-testowy-demo.pdf')
    plan=execution_plan(mode,measured_report());cv2.setNumThreads(plan.cpu_threads)
    template=prepare_template(engine,path,0,[106,175,67,21])
    classic=DetectionEngine(engine).find(path,0,template,'QP14')
    result=AIEngine(engine).find(path,0,template,'QP14')
    for bucket in ('matches','review','discovered_other_label'):
        assert result[bucket]==classic[bucket]
    assert len(result['matches'])==4 and len(result['discovered_other_label'])==8
    assert result['stages']['vector_first'] and not result['stages']['raster_used']
    assert all(h['signals']['embedding_score'] is None for h in result['matches'])
    group=Group('QP14',label='QP14',template=template)
    project=Project(source=path,pages=engine.inspect(path),groups=[group])
    ResultsManager().apply(project,group.id,0,result)
    project.detections[0].decision='accepted'
    project.detections[1].decision='rejected'
    ProjectManager().save(project,tmp_path/'saved')
    restored=ProjectManager().load(tmp_path/'saved'/'project.sqlite')
    assert restored.groups==project.groups and restored.detections==project.detections
    assert restored.analysis_reports==project.analysis_reports


def test_advanced_pdf_native_labels_stay_distinct():
    engine=PdfiumEngine();path=str(FIXTURES/'electrocount_test_advanced.pdf')
    assert len(engine.inspect(path))==3
    for page in range(3):
        items=engine.extract_text(path,page)
        texts={i.normalized_text for i in items}
        assert {'A1','A11','A1.1','AI','QP14'}<=texts
        assert not ({'A1A11','QP14A1','A1QP14','AW1EW1'} & texts)
        assert engine.render(path,page,.4).size>0
        assert engine.extract_vectors(path,page)['paths']
    label=next(i for i in engine.extract_text(path,0) if i.normalized_text=='A1.1')
    x,y,w,h=label.bbox
    assert TextEngine().associate([x-30,y-3,20,12],[label])['item'].normalized_text=='A1.1'


def test_vector_budget_discards_partial_evidence_and_switches_to_raster():
    engine=PdfiumEngine(vector_segment_limit=3)
    path=str(FIXTURES/'rzut-testowy-demo.pdf')
    vectors=engine.extract_vectors(path,0)
    assert vectors['truncated'] and not vectors['paths'] and vectors['unsupported']>0
    template=prepare_template(engine,path,0,[106,175,67,21])
    assert template['signature'] is None and template['label']=='QP14'
    result=AIEngine(engine).find(path,0,template,'QP14')
    assert result['stages']['raster_used'] and result['stages']['vector_limit_reached']
    assert len(result['matches'])==4 and len(result['discovered_other_label'])==8


def test_feature_verification_requires_reference_strokes_not_just_box():
    import cv2,numpy as np
    from electrocount.feature_matcher import OpenCVFeatureMatcher
    a=np.full((64,120),255,np.uint8)
    cv2.rectangle(a,(12,12),(108,52),0,2)
    cv2.line(a,(12,12),(108,52),0,2);cv2.line(a,(108,12),(12,52),0,2)
    empty=np.full_like(a,255);cv2.rectangle(empty,(12,12),(108,52),0,2)
    missing=empty.copy();cv2.line(missing,(12,12),(108,52),0,2)
    matcher=OpenCVFeatureMatcher()
    assert matcher.verify(a,a)['verified']
    assert not matcher.verify(a,empty)['verified']
    assert not matcher.verify(a,missing)['verified']
