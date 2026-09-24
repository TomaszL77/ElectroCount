import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QInputDialog
from electrocount.main_window import MainWindow
from electrocount.domain import Group, Detection
from electrocount.project_manager import ProjectManager


def wait(app, predicate, timeout=35):
    start = time.monotonic()
    while not predicate():
        app.processEvents()
        if time.monotonic()-start > timeout:
            raise AssertionError("Timed out waiting for worker")
        time.sleep(0.02)
    app.processEvents()


def test_pdf_group_match_conflict_save_reopen(app, document, tmp_path, monkeypatch):
    path, template = document
    errors = []
    window = MainWindow()
    window.jobs.failed.disconnect()
    window.jobs.failed.connect(errors.append)
    window.show()
    try:
        assert not window.registry.actions["find"].isEnabled()
        window.open_path(str(path))
        wait(app, lambda: len(window.project.pages) == 2)
        a = Group("A1", template=template)
        window.project.groups.append(a)
        window.project.active = a.id
        window.refresh()
        assert window.registry.actions["find"].isEnabled()
        window.find_matches()
        wait(app, lambda: not window.busy)
        assert not errors
        assert len(window.project.detections) == 8
        first = window.project.detections[0]
        window.selected = first.id
        window.decide("rejected")
        window.find_matches()
        wait(app, lambda: not window.busy)
        assert len(window.project.detections) == 8
        assert first.decision == "rejected"
        window.undo()
        window.undo()
        assert window.project.detections[0].decision == "review"
        window.redo()
        assert window.project.detections[0].decision == "rejected"
        b = Group("QP14", visible=False)
        window.project.groups.append(b)
        second = window.project.detections[1]
        window.project.detections.append(Detection(b.id, 0, second.rect.copy(), decision="accepted"))
        window.refresh()
        assert len(window.conflicts) == 1
        window.show_conflicts()
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args, **kwargs: (args[3][0], True))
        window.resolve_conflict()
        assert not window.conflicts
        window.undo()
        assert len(window.conflicts) == 1
        folder = tmp_path/"saved"
        window.folder = str(folder)
        assert window.save_project()
        restored = ProjectManager().load(folder/"project.sqlite")
        assert len(restored.groups) == 2
        assert restored.groups[1].visible is False
        assert restored.detections == window.project.detections
        window.replace_project(restored, str(folder))
        assert len(window.conflicts) == 1
        wait(app, lambda: window.view.preview is not None)
    finally:
        window.jobs.close()
        window.dirty = False
        window.close()


def test_cancel_has_no_partial_results(app, document):
    path, template = document
    window = MainWindow()
    window.show()
    try:
        window.open_path(str(path))
        wait(app, lambda: bool(window.project.pages))
        group = Group("Test", template=template)
        window.project.groups.append(group)
        window.project.active = group.id
        window.refresh()
        window.find_matches()
        assert window.operation_progress.active
        assert window.operation_progress.isVisible()
        window.cancel_button.click()
        wait(app, lambda: not window.busy)
        assert not window.project.detections
        assert not window.operation_progress.active
        assert not window.operation_progress.isVisible()
    finally:
        window.jobs.close()
        window.dirty = False
        window.close()


def test_found_count_active_group_and_page_overlays(app):
    window=MainWindow()
    try:
        a,b=Group('Oprawy'),Group('Gniazda')
        window.project.groups=[a,b];window.project.active=a.id
        window.project.pages=[{'name':'Parter'},{'name':'Piętro'}]
        window.project.detections=[Detection(a.id,0,[20,20,24,8]),
            Detection(a.id,1,[40,40,24,8]),Detection(b.id,0,[80,80,10,10]),
            Detection(a.id,0,[120,120,24,8],decision='rejected')]
        window.view.set_page(300,300);window.refresh()
        assert window.groups.topLevelItem(0).text(1)=='2'
        assert window.groups.topLevelItem(0).text(2)=='0'
        assert window.found_count.text()=='Znaleziono: 2 · na stronie: 1'
        assert len(window.view.overlays)==2
        window.active_group_only.setChecked(True)
        assert len(window.view.overlays)==1
        assert len(window.project.detections)==4
        window.project.active=b.id;window.refresh()
        assert len(window.view.overlays)==1
        window.active_group_only.setChecked(False)
        assert len(window.view.overlays)==2
    finally:
        window.jobs.close();window.dirty=False;window.close()
