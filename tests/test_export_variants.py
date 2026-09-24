"""Equivalent CAD exports must match without accepting missing device features."""
import pytest
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection, run_detection
from electrocount.domain import overlap_metrics


def fixture(c, x, y, *, split=False, middle=True, filled=False, frame=True, angle=0):
    c.saveState(); c.translate(x, y); c.rotate(angle)
    c.setLineWidth(.4)
    if frame:
        p = c.beginPath(); p.moveTo(0, 0)
        for start, end in [((0,0),(24,0)),((24,0),(24,8)),((24,8),(0,8)),((0,8),(0,0))]:
            if split: p.lineTo((start[0]+end[0])/2, (start[1]+end[1])/2)
            p.lineTo(*end)
        p.close(); c.drawPath(p)
    c.circle(12,4,3,stroke=1,fill=int(filled))
    if middle:
        for a,b in [(0,9),(15,24)]:
            p=c.beginPath();p.moveTo(a,4)
            if split:p.lineTo((a+b)/2,4)
            p.lineTo(b,4);c.drawPath(p)
    c.restoreState()


@pytest.mark.parametrize('split_template',[False,True])
def test_export_subdivision_keeps_all_devices_and_rejects_variants(tmp_path, split_template):
    path=tmp_path/'exports.pdf';c=canvas.Canvas(str(path),pagesize=(420,360))
    fixture(c,30,310,split=split_template)
    fixture(c,100,250,split=not split_template)
    fixture(c,190,190,split=True,angle=90)
    fixture(c,270,120,split=True,middle=False)
    fixture(c,320,70,split=True,filled=True)
    fixture(c,30,40,split=True,frame=False)
    c.save();pdf=PdfiumEngine()
    template=prepare_detection(pdf,str(path),0,[28,40,28,12])
    result=run_detection(pdf,str(path),0,template)
    truth=[[30,42,24,8],[100,102,24,8],[182,146,8,24]]
    assert len(result['matches'])==3
    assert all(any(overlap_metrics(box,h['rect'])[0]>.9 for h in result['matches']) for box in truth)
    repeated=run_detection(pdf,str(path),0,template)
    assert repeated['result_sha256']==result['result_sha256']


@pytest.mark.parametrize('end,start,final',[
    ([10,0],[10.2,0],[20,0]),  # a gap is part of the symbol
    ([10,0],[10,0],[5,0]),    # a reversal is not a subdivision
    ([10,0],[10,0],[20,.1]),  # an angled detail must remain
])
def test_canonicalization_preserves_distinguishing_strokes(end,start,final):
    from electrocount.vector_engine import canonical_path
    path={'segments':[{'kind':'line','points':[[0,0],end]},
                      {'kind':'line','points':[start,final]}], 'fill':True}
    assert canonical_path(path)==path


def test_closed_path_starting_mid_edge_and_paint_are_preserved():
    from electrocount.vector_engine import canonical_path
    points=[[5,0],[10,0],[10,5],[0,5],[0,0],[5,0]]
    path={'segments':[{'kind':'line','points':[a,b]} for a,b in zip(points,points[1:])],
          'fill':True,'color':[0,0,0,255]}
    result=canonical_path(path)
    assert len(result['segments'])==4 and result['fill'] and result['color']==path['color']
    assert len(path['segments'])==5  # no mutation of a stored template


@pytest.mark.parametrize('rotation',[0,1])
def test_raster_crossing_requires_evidence_outside_symbol(rotation):
    from pathlib import Path
    import numpy as np
    import cv2
    from electrocount.feature_matcher import OpenCVFeatureMatcher
    path=str(Path(__file__).parent/'fixtures/rzut-testowy-demo.pdf')
    pdf=PdfiumEngine();matcher=OpenCVFeatureMatcher()
    a=pdf.render(path,0,2,[108,176,32,16])
    b=pdf.render(path,0,2,[288,176,32,16])
    context=pdf.render(path,0,2,[284,172,40,24])
    a,b,context=[np.rot90(im,rotation).copy() for im in (a,b,context)]
    assert not matcher.verify(a,b)['verified']
    assert matcher.verify_with_context(a,b,context,8)['verified']
    # Identical extra stroke ending at the symbol border is not background.
    no_continuation=np.full_like(context,255);no_continuation[8:-8,8:-8]=b
    assert not matcher.verify_with_context(a,b,no_continuation,8)['verified']
    # A filled body may not use the crossing to bypass variant verification.
    filled=b.copy();cv2.rectangle(filled,(8,8),(filled.shape[1]-9,filled.shape[0]-9),(0,0,0),-1)
    assert not matcher.verify_with_context(a,filled,context,8)['verified']
