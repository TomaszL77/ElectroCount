"""Short headed legends must allow smaller, unlabelled plan symbols."""
from reportlab.pdfgen import canvas
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection
from electrocount.detection_engine import DetectionEngine
from electrocount.document_regions import legend_regions


def short_table(path, closed=True, headings=True):
    c=canvas.Canvas(str(path),pagesize=(700,500))
    left,right,top,bottom=380,660,450,290
    for y in range(bottom+20,top+1,20):c.line(left,y,right,y)
    p=c.beginPath();p.moveTo(left,top);p.lineTo(left,bottom);p.lineTo(right,bottom)
    c.drawPath(p)
    if closed:c.line(right,top,right,bottom)
    for x in (430,610):c.line(x,top-20,x,bottom)
    if headings:
        c.setFont('Helvetica',8);c.drawString(490,top-13,'LEGENDA')
        c.drawString(388,top-33,'SYMBOL');c.drawString(490,top-33,'OPIS')
    c.rect(392,396,24,8)
    # A second table sharing the exact X bounds must not merge with the legend.
    for y in (30,50,70,90,110):c.line(left,y,right,y)
    c.rect(80,380,12,4);c.rect(180,380,12,12)
    c.save()


def test_merged_heading_and_polyline_border_find_smaller_unlabelled_symbol(tmp_path):
    p=tmp_path/'short.pdf';short_table(p);pdf=PdfiumEngine()
    selection=[390,94,28,12]
    t=prepare_detection(pdf,str(p),0,selection,visual_embedding=False)
    assert t['source']=='LEGEND' and t['match_mode']=='shape'
    assert t['selection_bbox']==selection and t['raster_rect']==selection
    r=DetectionEngine(pdf).find(str(p),0,t)
    assert len(r['matches'])==1 and 79<r['matches'][0]['rect'][0]<81
    assert len(r['legend_matches'])==1
    assert r['regions'][0]['rect'][3]==160
    # An existing project created before short legends were recognized refreshes
    # the definition at search time, preserving the authoritative selection.
    old={**t,'definition_version':13,'source':'DRAWING'}
    old.pop('match_mode');old['signature']={**old['signature'],'source_legend':False}
    migrated=DetectionEngine(pdf).find(str(p),0,old)
    assert migrated['template']['definition_version']==14
    assert migrated['template']['selection_bbox']==selection
    assert migrated['template']['source']=='LEGEND'
    assert len(migrated['matches'])==1


def test_unclosed_or_unheaded_table_does_not_broaden_scale(tmp_path):
    pdf=PdfiumEngine()
    for closed,headings in [(False,True),(True,False)]:
        p=tmp_path/f'table-{closed}-{headings}.pdf';short_table(p,closed,headings)
        with pdf.open_vector_page(str(p),0) as native:
            regions=legend_regions(native,pdf.extract_text(str(p),0))
        assert not regions


def test_learned_model_assesses_native_unlabelled_matches_without_adding_geometry(tmp_path):
    class UnconvincedModel:
        metadata={'threshold':.9}
        def score(self,reference,candidate):return .01
    p=tmp_path/'assess.pdf';short_table(p);pdf=PdfiumEngine()
    t=prepare_detection(pdf,str(p),0,[390,94,28,12],visual_embedding=False)
    r=DetectionEngine(pdf,learned_model=UnconvincedModel()).find(str(p),0,t)
    assert not r['matches']
    h=next(h for h in r['review'] if 79<h['rect'][0]<81)
    assert h['reason']=='insufficient_combined_evidence'
    assert h['verification_details']['learned_pair_score']==.01
    assert not any(179<h['rect'][0]<181 for h in r['review'])
