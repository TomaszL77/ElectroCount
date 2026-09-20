from dataclasses import asdict
import json
import sqlite3
import pytest
from electrocount.domain import Project, Group, Detection, ConflictEngine, counts
from electrocount.history import History
from electrocount.project_manager import ProjectManager
from electrocount.pdf_engine import PdfiumEngine
from electrocount.matcher import SimpleSymbolMatcher


def test_hidden_group_still_conflicts_and_never_double_counts():
    a, b = Group("A1"), Group("QP14", visible=False)
    x = Detection(a.id, 0, [10, 10, 20, 20], decision="accepted")
    y = Detection(b.id, 0, [11, 11, 20, 20], decision="accepted", source="manual")
    p = Project(groups=[a, b], detections=[x, y])
    ids = set().union(*ConflictEngine().components(p))
    assert ids == {x.id, y.id}
    assert counts(p, a.id, ids) == (0, 0, 1)
    assert counts(p, b.id, ids) == (0, 0, 1)
    p.allowed = [sorted([x.id, y.id])]
    assert not ConflictEngine().pairs(p)
    assert counts(p, a.id, set()) == (1, 0, 0)


def test_three_way_conflict_and_distinct_pages():
    gs = [Group(str(i)) for i in range(3)]
    ds = [Detection(g.id, 0, [0, 0, 20, 20]) for g in gs]
    p = Project(groups=gs, detections=ds)
    assert len(ConflictEngine().components(p)) == 1
    assert len(ConflictEngine().components(p)[0]) == 3
    ds[2].page = 1
    assert len(ConflictEngine().components(p)[0]) == 2
    ds[1].decision = "rejected"
    assert not ConflictEngine().pairs(p)


def test_atomic_conflict_undo_redo():
    p = Project(groups=[Group("A"), Group("B")])
    p.detections = [Detection(g.id, 0, [10, 10, 10, 10]) for g in p.groups]
    history = History()
    history.record(p)
    p.detections[0].decision = "accepted"
    p.detections[1].decision = "rejected"
    assert not ConflictEngine().pairs(p)
    p = history.undo(p)
    assert ConflictEngine().pairs(p)
    p = history.redo(p)
    assert p.detections[0].decision == "accepted"
    assert not ConflictEngine().pairs(p)


def test_portable_save_and_integrity(document, tmp_path):
    path, template = document
    group = Group("A1", visible=False, template=template)
    p = Project(source=str(path), groups=[group], active=group.id,
                pages=PdfiumEngine().inspect(str(path)), view={"scale": 2.3, "x": 20, "y": 30})
    p.detections = [Detection(group.id, 0, [10, 10, 20, 20], decision="accepted")]
    p.resolutions = [{"decision": "test"}]
    folder = tmp_path/"project"
    ProjectManager().save(p, folder)
    path.unlink()
    restored = ProjectManager().load(folder/"project.sqlite")
    assert restored.groups == p.groups
    assert restored.detections == p.detections
    assert restored.view == p.view
    assert restored.resolutions == p.resolutions
    assert not restored.groups[0].visible
    with open(restored.source, "ab") as f:
        f.write(b"tamper")
    with pytest.raises(ValueError, match="zmieniona"):
        ProjectManager().load(folder/"project.sqlite")


def test_future_schema_rejected(tmp_path):
    dbpath = tmp_path/"project.sqlite"
    with sqlite3.connect(dbpath) as db:
        db.execute("CREATE TABLE snapshot (id INTEGER, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO snapshot VALUES (1, 999, '{}')")
    with pytest.raises(ValueError, match="wersja"):
        ProjectManager().load(dbpath)


def test_pdf_render_crop_and_rotation(document):
    path, template = document
    engine = PdfiumEngine()
    pages = engine.inspect(str(path))
    assert len(pages) == 2
    assert pages[0]["width"] == 900
    full = engine.render(str(path), 0, 2)
    crop = engine.render(str(path), 0, 2, template["rect"])
    assert crop.shape[:2] == (40, 72)
    x, y, w, h = [int(v*2) for v in template["rect"]]
    import numpy as np
    assert np.array_equal(crop, full[y:y+h, x:x+w])
    rotated = engine.render(str(path), 1, 1)
    assert rotated.shape[1] == round(pages[1]["width"])
    assert rotated.shape[0] == round(pages[1]["height"])


def test_matcher_counts_shapes_not_codes(document):
    path, template = document
    progress = []
    matches = SimpleSymbolMatcher().find(PdfiumEngine(), str(path), 0, template, 0.88, progress.append)
    assert len(matches) == 12
    assert progress[-1] == 100
    # A1 and QP14 deliberately share shape. No inferred code is returned.
    assert all(set(match) == {"rect", "score"} for match in matches)


def test_blank_template_rejected(document):
    path, _ = document
    with pytest.raises(ValueError, match="puste"):
        SimpleSymbolMatcher().find(PdfiumEngine(), str(path), 0, {"page": 0, "rect": [5, 5, 20, 20]}, 0.8)




def test_same_group_manual_duplicate_is_blocked():
    group = Group("A1")
    a = Detection(group.id, 0, [0, 0, 20, 20], decision="accepted")
    b = Detection(group.id, 0, [1, 0, 20, 20], decision="accepted", source="manual")
    p = Project(groups=[group], detections=[a, b])
    ids = set().union(*ConflictEngine().components(p))
    assert counts(p, group.id, ids) == (0, 0, 2)


def test_proximity_can_flag_adjacent_boxes():
    a, b = Group("A"), Group("B")
    p = Project(groups=[a, b], proximity=.95, detections=[
        Detection(a.id, 0, [0, 0, 20, 20]),
        Detection(b.id, 0, [18, 0, 20, 20])])
    assert ConflictEngine().pairs(p)
