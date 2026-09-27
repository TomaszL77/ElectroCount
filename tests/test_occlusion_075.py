"""Occlusion recovery adds review evidence without weakening quantities."""
import cv2
import numpy as np
import pytest
from electrocount.occlusion import visible_evidence,external_line_mask
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection
from occlusion_fixture import symbol,scene


def test_visible_only_requires_distributed_support_and_small_mask():
    ref=symbol();mask=np.zeros(ref.shape[:2],np.uint8);mask[:,53:62]=1
    patch=ref.copy();patch[mask>0]=255
    e=visible_evidence(ref,patch,mask)
    assert e and e['supported_quadrants']==4 and e['policy']=='review_only'
    assert visible_evidence(ref,patch,np.zeros_like(mask)) is None
    huge=mask.copy();huge[:,:75]=1
    assert visible_evidence(ref,patch,huge) is None
    assert visible_evidence(ref,symbol(True),mask) is None
    filled=ref.copy();filled[4:55,4:116]=0
    assert visible_evidence(ref,filled,mask) is None
    assert visible_evidence(ref,np.full_like(ref,255),mask) is None


def test_external_diagonal_is_proven_outside_both_sides():
    ref=symbol();h,w=ref.shape[:2];pad=22
    context=np.full((h+2*pad,w+2*pad,3),255,np.uint8);context[pad:pad+h,pad:pad+w]=ref
    cv2.line(context,(0,pad+8),(w+2*pad-1,pad+h-8),(0,0,0),2)
    mask,e=external_line_mask(context,(h,w),pad)
    assert e and mask.any()
    assert visible_evidence(ref,context[pad:pad+h,pad:pad+w],mask)
    internal=np.full_like(context,255);internal[pad:pad+h,pad:pad+w]=ref
    cv2.line(internal,(pad+10,pad+8),(pad+w-10,pad+h-8),(0,0,0),2)
    mask,e=external_line_mask(internal,(h,w),pad)
    assert not e and not mask.any()


@pytest.mark.parametrize('mode',['classic','hybrid','hybrid_base'])
def test_pdf_recovers_text_and_diagonal_only_as_review(tmp_path,mode):
    p=tmp_path/'occluded.pdf';selection,boxes=scene(p);pdf=PdfiumEngine()
    t=prepare_detection(pdf,str(p),0,selection)
    assert t['label']=='7'
    r=run_detection(pdf,str(p),0,t,config={'engine_mode':mode})
    recovered=[h for h in r['review'] if h['reason']=='partial_occlusion_review']
    assert any(h['rect'][0]>200 and h['rect'][1]<100 for h in recovered)
    assert any(h['rect'][0]<150 and 120<h['rect'][1]<200 for h in recovered)
    assert not any(h['rect'][1]>230 for h in recovered+r['matches'])
    assert all(h['label']!='8' for h in r['matches'])
    assert any(h['label']=='8' for h in r['discovered_other_label'])
    assert all(h['verification_details']['occlusion']['policy']=='review_only' for h in recovered)
    assert r['stages']['occlusion_label_probes']>0
    from electrocount.domain import Project,Group
    from electrocount.results_manager import ResultsManager
    from electrocount.project_manager import ProjectManager
    group=Group('7',label='7',template=t)
    project=Project(source=str(p),pages=pdf.inspect(str(p)),groups=[group],active=group.id)
    ResultsManager().apply(project,group.id,0,r)
    assert len([d for d in project.detections if d.group==group.id])==1
    assert len([d for d in project.detections if not d.group and d.reason=='partial_occlusion_review'])==2
    manager=ProjectManager();manager.save(project,tmp_path/'saved')
    restored=manager.load(tmp_path/'saved/project.sqlite')
    assert restored.detections==project.detections


def test_replace_clean_reference_keeps_group_and_requires_recheck(app,tmp_path,monkeypatch):
    from copy import deepcopy
    from electrocount.main_window import MainWindow
    from electrocount.domain import Group,Detection
    from test_ui import wait
    p=tmp_path/'occluded.pdf';selection,_=scene(p)
    template=prepare_detection(PdfiumEngine(),str(p),0,selection)
    window=MainWindow();window.show()
    try:
        window.open_path(str(p));wait(app,lambda: bool(window.project.pages) and not window.loading)
        old=deepcopy(template);old['id']='old-reference'
        group=Group('7',label='7',template=old)
        window.project.groups=[group];window.project.active=group.id
        window.project.detections=[Detection(group.id,0,old['rect'],decision='accepted')]
        window.refresh();prepared=deepcopy(template)
        submit=window.jobs.submit
        monkeypatch.setattr(window.jobs,'submit',lambda task,callback: callback(deepcopy(prepared)) if task['kind']=='template' else submit(task,callback))
        window.registry.invoke('replace_template');window.rectangle_selected(selection)
        assert len(window.project.groups)==1 and window.project.active==group.id
        assert group.template['id']==template['id']
        d=window.project.detections[0]
        assert d.decision=='review' and not d.group and d.requested_group==group.id
        window.undo();wait(app,lambda: not window.loading)
        assert window.project.active_group().template['id']=='old-reference'
        assert window.project.detections[0].group==group.id
        prepared['label']='8'
        window.replace_template();window.rectangle_selected(selection)
        assert window.project.active_group().template['id']=='old-reference'
        assert 'Nie zmieniono' in window.statusBar().currentMessage()
        window.replace_template();window.set_mode('pan')
        assert window.replacing_group is None
    finally:
        window.jobs.close();window.dirty=False;window.close()
