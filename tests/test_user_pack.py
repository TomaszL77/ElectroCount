"""Optional local real-document integration suite; never used as training data."""
import os
from pathlib import Path
import pytest
from electrocount.main_window import MainWindow
from electrocount.domain import Group,Detection
from electrocount.project_manager import ProjectManager
from test_ui import wait


def test_user_pdf_pack_import_navigation_groups_and_portable_save(app,tmp_path):
    root=os.environ.get('ELECTROCOUNT_TEST_PACK')
    if not root:
        pytest.skip('Set ELECTROCOUNT_TEST_PACK to the local supplied PDF folder')
    files=sorted(Path(root).glob('*.pdf'))
    assert len(files)==4
    window=MainWindow();errors=[]
    window.jobs.failed.disconnect();window.jobs.failed.connect(errors.append)
    window.show()
    try:
        window.import_paths([str(p) for p in files],mode='new')
        wait(app,lambda:len(window.project.documents)==4 and not window.loading,timeout=60)
        assert len(window.project.pages)==4
        for index in range(4):
            window.pages.setCurrentRow(index)
            wait(app,lambda:window.view.preview is not None,timeout=60)
            assert window.view.preview.pixmap().width()>0
        group=Group('Test ręcznej weryfikacji');window.project.groups.append(group)
        window.project.active=group.id;window.refresh()
        window.set_mode('manual');window.rectangle_selected([100,100,25,15])
        assert len(window.project.detections)==1 and window.project.detections[0].decision=='accepted'
        window.undo();assert not window.project.detections
        window.redo();assert len(window.project.detections)==1
        window.folder=str(tmp_path/'pack-project');assert window.save_project()
        reopened=ProjectManager().load(tmp_path/'pack-project'/'project.sqlite')
        assert len(reopened.documents)==4
        assert reopened.groups==window.project.groups and reopened.detections==window.project.detections
        window.replace_project(reopened,window.folder)
        wait(app,lambda:window.view.preview is not None,timeout=60)
        assert not errors
    finally:
        window.jobs.close();window.dirty=False;window.close()
