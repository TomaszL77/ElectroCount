import shutil
import json
import sqlite3
from pathlib import Path
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint, QPointF
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QInputDialog
from electrocount.main_window import MainWindow
from electrocount.file_import_manager import FileImportManager
from electrocount.domain import Project, Group
from electrocount.project_manager import ProjectManager, digest
from test_ui import wait


def test_import_router_and_errors(document, tmp_path):
    path, _ = document
    dwg, dxf = tmp_path/"sample.dwg", tmp_path/"sample.DXF"
    dwg.write_bytes(b"placeholder")
    dxf.write_bytes(b"placeholder")
    calls=[]
    class CAD:
        def inspect(self,p):
            calls.append(p)
            return [{"name":"CAD","width":100,"height":100}]
    manager=FileImportManager(cad_engine=CAD())
    result=manager.inspect_many([str(path),str(dwg),str(dxf)])
    assert len(result["documents"]) == 3 and len(calls)==2
    unavailable=FileImportManager().inspect_many([str(path),str(dwg)])
    assert len(unavailable["documents"]) == 1
    assert "CAD" in unavailable["errors"][0]
    assert FileImportManager().plan([str(path),str(path)]).errors


def test_multi_pdf_add_save_undo_and_new_project(app,document,tmp_path,monkeypatch):
    path,_=document
    second=tmp_path/"drugi rzut.pdf"
    shutil.copyfile(path,second)
    window=MainWindow()
    window.show()
    try:
        window.import_paths([str(path),str(second)])
        wait(app,lambda:not window.loading)
        assert len(window.project.documents)==2 and len(window.project.pages)==4
        assert window.project.page_location(2)[0] == str(second)
        assert window.project.page_location(2)[1] == 0
        group=Group("Zachowaj")
        window.project.groups.append(group)
        window.project.active=group.id
        third=tmp_path/"trzeci.pdf"
        shutil.copyfile(path,third)
        window.import_paths([str(third)],mode="add")
        wait(app,lambda:not window.loading)
        assert len(window.project.documents)==3 and len(window.project.pages)==6
        assert window.project.groups[0].id == group.id
        window.undo()
        assert len(window.project.documents)==2 and len(window.project.pages)==4
        window.redo()
        assert len(window.project.documents)==3
        window.folder=str(tmp_path/"saved")
        assert window.save_project()
        restored=ProjectManager().load(tmp_path/"saved"/"project.sqlite")
        assert len(restored.documents)==3
        assert all(Path(d.path).is_file() for d in restored.documents)
        assert restored.pages==window.project.pages
        window.import_paths([str(path)],mode="cancel")
        assert len(window.project.documents)==3
        monkeypatch.setattr(window,"maybe_save",lambda:True)
        window.import_paths([str(path)],mode="new")
        wait(app,lambda:not window.loading)
        assert len(window.project.documents)==1 and not window.project.groups
    finally:
        window.jobs.close()
        window.loading=window.busy=window.dirty=False
        window.close()


def test_real_qt_drag_drop_events(app,document,monkeypatch):
    path,_=document
    window=MainWindow()
    window.show()
    mime=QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)), QUrl.fromLocalFile("C:/example.DWG")])
    delivered=[]
    monkeypatch.setattr(window,"import_paths",lambda paths:delivered.extend(paths))
    try:
        enter=QDragEnterEvent(QPoint(120,150),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window,enter)
        assert enter.isAccepted() and window.drop_overlay.isVisible()
        drop=QDropEvent(QPointF(120,150),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window,drop)
        assert drop.isAccepted()
        assert len(delivered)==2
        assert not window.drop_overlay.isVisible()
    finally:
        window.jobs.close()
        window.dirty=False
        window.close()


def test_prepare_template_in_gui_proposes_label_without_existing_group(app,monkeypatch):
    path=Path(__file__).parent/"fixtures"/"rzut-testowy-demo.pdf"
    window=MainWindow()
    window.show()
    prompts=[]
    def answer(*args,**kwargs):
        prompts.append((args,kwargs))
        return kwargs["text"],True
    monkeypatch.setattr(QInputDialog,"getText",answer)
    try:
        window.open_path(str(path))
        wait(app,lambda:not window.loading)
        window.set_mode("template")
        window.rectangle_selected([106,175,67,21])
        wait(app,lambda:not window.loading)
        group=window.project.active_group()
        assert group.name==group.label=="QP14"
        assert not prompts
        assert "Wykryte oznaczenie: QP14" in window.statusBar().currentMessage()
        window.find_matches()
        wait(app,lambda:not window.busy)
        assert len(window.project.detections)==4
        assert len(window.project.discoveries)==8
    finally:
        window.jobs.close()
        window.loading=window.busy=window.dirty=False
        window.close()


def test_v1_project_migrates(document,tmp_path):
    path,_=document
    folder=tmp_path/"legacy"
    folder.mkdir()
    shutil.copyfile(path,folder/"source.pdf")
    from electrocount.pdf_engine import PdfiumEngine
    old=Project(source="source.pdf",source_hash=digest(path),pages=PdfiumEngine().inspect(str(path))).to_dict()
    for key in ("documents","discoveries","text_items"):
        old.pop(key)
    for page in old["pages"]:
        page.pop("document_id")
        page.pop("source_page")
    old["groups"] = [{"name":"QP14", "id":"legacy"}]
    old["detections"] = [{"group":"legacy","page":0,"rect":[10,10,20,20],"decision":"accepted"}]
    with sqlite3.connect(folder/"project.sqlite") as db:
        db.execute("CREATE TABLE snapshot (id INTEGER PRIMARY KEY, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO snapshot VALUES (1,1,?)",(json.dumps(old),))
    loaded=ProjectManager().load(folder/"project.sqlite")
    assert len(loaded.documents)==1
    assert loaded.page_location(1)==(str(folder/"source.pdf"),1)


    assert loaded.detections[0].group == ""
    assert loaded.detections[0].decision == "review"
    assert loaded.detections[0].previous_decision == "accepted"
