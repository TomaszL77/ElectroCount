import json
from pathlib import Path
from PySide6.QtWidgets import QInputDialog
from electrocount.main_window import MainWindow
from electrocount.profiling_service import PerformanceController
from electrocount.performance_dialog import PerformanceDialog
from electrocount.settings import Settings
from electrocount.domain import Group,counts
from electrocount.project_manager import ProjectManager
from test_ui import wait
from test_ai_foundation import measured_report

PDF=Path(__file__).parent/'fixtures'/'rzut-testowy-demo.pdf'


def test_legacy_mode_is_ignored_without_hardware_process(app):
    settings=Settings();settings.set('performance/mode','MAXIMUM')
    service=PerformanceController(settings);service.start()
    assert service.plan.effective=='DETERMINISTIC' and service.process is None
    dialog=PerformanceDialog(service);dialog.show();dialog.close()
    service.set_mode('ECO');assert service.plan.effective=='DETERMINISTIC'


def test_gui_native_templates_groups_save_reopen_under_auto(app,tmp_path,monkeypatch):
    errors=[];window=MainWindow();window.jobs.failed.disconnect();window.jobs.failed.connect(errors.append)
    window.show()
    monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Unexpected naming dialog')))
    try:
        window.open_path(str(PDF))
        wait(app,lambda:bool(window.project.pages) and window.view.preview is not None)
        assert not window.pages_sidebar.collapsed
        assert not window.current_page_only.isChecked()
        window.set_mode('template');window.rectangle_selected([106,175,67,21])
        wait(app,lambda:len(window.project.groups)==1 and not window.loading)
        assert window.project.active_group().label=='QP14'
        window.find_matches();wait(app,lambda:not window.busy,timeout=180)
        assert len(window.project.detections)==4
        window.selected=window.project.detections[0].id
        window.decide('accepted')
        window.set_mode('template');window.rectangle_selected([106,455,55,21])
        wait(app,lambda:len(window.project.groups)==2 and not window.loading)
        assert window.project.active_group().label=='A1'
        window.find_matches();wait(app,lambda:not window.busy,timeout=180)
        assert len(window.project.detections)==12 and not window.conflicts
        assert sorted((g.label,sum(d.group==g.id for d in window.project.detections)) for g in window.project.groups)==[('A1',8),('QP14',4)]
        window.performance.set_mode('STANDARD')
        assert window.jobs.performance_plan['effective']=='DETERMINISTIC'
        window.find_matches();wait(app,lambda:not window.busy,timeout=180)
        assert len(window.project.detections)==12
        assert sum(d.decision=='accepted' for d in window.project.detections)==1
        window.folder=str(tmp_path/'gui-saved');assert window.save_project()
        restored=ProjectManager().load(tmp_path/'gui-saved'/'project.sqlite')
        assert restored.detections==window.project.detections
        assert restored.groups==window.project.groups
        window.replace_project(restored,window.folder)
        wait(app,lambda:window.view.preview is not None)
        assert not errors
    finally:
        window.jobs.close();window.dirty=False;window.close()


def test_single_page_sidebar_and_advanced_pdf_open(app,tmp_path):
    from electrocount.hardware_profiler import benchmark_pdf
    single=tmp_path/'one.pdf';single.write_bytes(benchmark_pdf())
    window=MainWindow();errors=[];window.jobs.failed.disconnect();window.jobs.failed.connect(errors.append)
    window.show()
    try:
        window.open_path(str(single))
        wait(app,lambda:len(window.project.pages)==1 and window.view.preview is not None)
        assert window.pages_sidebar.collapsed
        window.dirty=False
        advanced=Path(__file__).parent/'fixtures'/'electrocount_test_advanced.pdf'
        window.import_paths([str(advanced)],mode="new")
        wait(app,lambda:len(window.project.pages)==3 and window.view.preview is not None)
        assert not window.pages_sidebar.collapsed
        for index in range(3):
            window.pages.setCurrentRow(index)
            wait(app,lambda:window.view.preview is not None)
        assert not errors
    finally:
        window.jobs.close();window.dirty=False;window.close()
