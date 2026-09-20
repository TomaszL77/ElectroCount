from pathlib import Path
from collections import Counter
from dataclasses import asdict
import pytest
from electrocount.pdf_engine import PdfiumEngine
from electrocount.text_engine import PdfTextItem, TextEngine, normalize_text, prepare_template
from electrocount.detection_engine import DetectionEngine
from electrocount.domain import Project, Group, Detection
from electrocount.results_manager import ResultsManager
from electrocount.project_manager import ProjectManager

PDF = Path(__file__).parent/"fixtures"/"rzut-testowy-demo.pdf"


@pytest.mark.parametrize("label,box,expected,other", [
    ("QP14", [106,175,67,21], 4, 8),
    ("A1", [106,455,55,21], 8, 4),
])
def test_supplied_pdf_exact_label_regression(label, box, expected, other):
    engine = PdfiumEngine()
    template = prepare_template(engine, str(PDF), 0, box)
    assert template["label"] == label
    # The template's graphic area no longer includes the lettering.
    assert template["rect"][0]+template["rect"][2] < template["label_item"]["bbox"][0]
    result = DetectionEngine(engine).find(str(PDF), 0, template, label, .88)
    assert len(result["matches"]) == expected
    assert len(result["discovered_other_label"]) == other
    assert not result["review"]
    assert all(h["label"] == label and h["text_score"] == 1 for h in result["matches"])
    assert all(h["label"] != label and h["reason"] == "different_label"
               for h in result["discovered_other_label"])
    assert all(h["graphic_score"] > .88 and h["spatial_association_score"] > .6 for h in result["matches"])


def test_native_text_boxes_counts():
    items = PdfiumEngine().extract_text(str(PDF), 0)
    counts = Counter(item.normalized_text for item in items)
    assert counts["QP14"] == 4 and counts["A1"] == 8
    assert all(item.bbox[2]>0 and item.bbox[3]>0 for item in items)
    assert all(item.center == [item.bbox[0]+item.bbox[2]/2, item.bbox[1]+item.bbox[3]/2] for item in items)


def test_normalization_does_not_confuse_characters():
    assert normalize_text("  qp14  ") == "QP14"
    assert normalize_text(" QP   14 ") == "QP 14"
    assert normalize_text("AOI") != normalize_text("A01")
    assert normalize_text("IO") != normalize_text("10")


def word(text, x, y, w=12, h=8):
    return PdfTextItem(text, normalize_text(text), 0, [x,y,w,h], [x+w/2,y+h/2])


def test_association_supports_left_above_and_ambiguity():
    engine = TextEngine()
    rect = [100,100,20,20]
    assert engine.associate(rect, [word("LEFT", 82,106)])["item"].text == "LEFT"
    assert engine.associate(rect, [word("UP", 104,85)])["item"].text == "UP"
    assert engine.associate(rect, [word("A1",123,104), word("A2",123,108)])["item"] is None
    assert engine.associate(rect, [])["reason"] == "missing_label"


class FakePDF:
    def __init__(self, items):
        self.items = items
    def extract_text(self, path, page):
        return self.items


class FakeMatcher:
    def __init__(self, rects):
        self.rects = rects
    def find(self, *args, **kwargs):
        return [{"rect": r, "score": .97, "graphic_score":.97, "feature_score":.95, "geometry_score":.96, "verified":True} for r in self.rects]


def test_missing_and_shared_text_stay_unassigned():
    template = {"page":0, "rect":[100,100,20,20], "text_aware":True, "label":"QP14"}
    result = DetectionEngine(FakePDF([]), FakeMatcher([[100,100,20,20]])).find("unused",0,template,"QP14")
    assert not result["matches"] and len(result["review"]) == 1
    group = Group("QP14", label="QP14")
    project = Project(groups=[group])
    ResultsManager().apply(project,group.id,0,result)
    assert project.detections[0].group == ""
    assert project.detections[0].decision == "review"
    assert project.detections[0].requested_group == group.id
    result = DetectionEngine(FakePDF([word("QP14",123,117)]),
        FakeMatcher([[100,100,20,20],[100,122,20,20]])).find("unused",0,template,"QP14")
    assert not result["matches"]
    assert len(result["review"]) == 2
    assert all(hit["reason"] == "shared_label" for hit in result["review"])


def test_exact_text_mismatch_is_never_fuzzy_matched():
    template = {"page":0, "rect":[100,100,20,20], "text_aware":True, "label":"AOI"}
    result = DetectionEngine(FakePDF([word("A01",125,105)]),
        FakeMatcher([[100,100,20,20]])).find("unused",0,template,"AOI")
    assert not result["matches"] and not result["review"]
    assert result["discovered_other_label"][0]["label"] == "A01"


def test_reanalysis_removes_legacy_mixed_quantities_and_preserves_correct_decisions(tmp_path):
    pdf = PdfiumEngine()
    template = prepare_template(pdf,str(PDF),0,[106,175,67,21])
    result = DetectionEngine(pdf).find(str(PDF),0,template,"QP14")
    group = Group("QP14",label="QP14",template=template)
    project = Project(source=str(PDF),pages=pdf.inspect(str(PDF)),groups=[group])
    for hit in result["matches"]+result["discovered_other_label"]:
        project.detections.append(Detection(group.id,0,hit["rect"],decision="accepted"))
    ResultsManager().apply(project,group.id,0,result)
    assert len(project.detections) == 4
    assert all(d.group == group.id and d.label == "QP14" and d.decision == "accepted" for d in project.detections)
    assert len(project.discoveries) == 8
    assert all(d["previous_detection"]["decision"] == "accepted" for d in project.discoveries)
    first = project.detections[0]
    first.decision = "rejected"
    ResultsManager().apply(project,group.id,0,result)
    assert next(d for d in project.detections if d.id == first.id).decision == "rejected"
    ProjectManager().save(project,tmp_path/"saved")
    restored=ProjectManager().load(tmp_path/"saved"/"project.sqlite")
    assert restored.detections == project.detections
    assert restored.groups[0].label == "QP14"
    assert restored.text_items == project.text_items


def test_native_text_bbox_respects_rotation_and_crop(tmp_path):
    import numpy as np
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    path=tmp_path/"rotations.pdf"
    c=canvas.Canvas(str(path),pagesize=(400,300))
    for rotation in (0,90,180,270):
        c.setPageRotation(rotation)
        c.setFont("Helvetica",12)
        c.drawString(80,90,"QP14")
        c.showPage()
    c.save()
    engine=PdfiumEngine()
    for page in range(4):
        items=engine.extract_text(str(path),page)
        assert len(items)==1 and items[0].normalized_text=="QP14"
        image=engine.render(str(path),page,2)
        x,y,w,h=items[0].bbox
        clip=image[max(0,int(y*2)):int((y+h)*2)+2,max(0,int(x*2)):int((x+w)*2)+2]
        assert clip.size and np.count_nonzero(clip < 120)>20
    cropped=tmp_path/"cropped.pdf"
    with pdfium.PdfDocument(str(path)) as doc:
        page=doc[0]
        page.set_cropbox(30,20,350,280)
        page.close()
        doc.save(str(cropped))
    items=engine.extract_text(str(cropped),0)
    assert items[0].bbox[0] < engine.extract_text(str(path),0)[0].bbox[0]
    assert items[0].normalized_text=="QP14"



def test_progress_reports_ordered_stages_without_changing_matches():
    from electrocount.ai.engine import AIEngine
    pdf=PdfiumEngine();template=prepare_template(pdf,str(PDF),0,[106,175,67,21])
    values=[];stages=[]
    result=AIEngine(pdf).find(str(PDF),0,template,'QP14',progress=values.append,status=stages.append)
    assert len(result['matches'])==4 and len(result['discovered_other_label'])==8
    assert values==sorted(values) and values[-1]==100
    assert any('tekstu' in s.lower() for s in stages)
    assert any('geometrii' in s.lower() for s in stages)
    assert any('oznaczeniami' in s.lower() for s in stages)
