"""Integration harness: actual Qt mouse drag -> GUI command -> worker -> result table."""
import argparse,json,os,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
p=argparse.ArgumentParser();p.add_argument('--pdf',required=True);p.add_argument('--output',required=True);p.add_argument('--zoom',type=float,default=3);p.add_argument('--selection',type=float,nargs=4,default=[3145,1380,40,55]);p.add_argument('--label',default='L3');p.add_argument('--expected',type=int,default=72);p.add_argument('--legend-count',type=int,default=1);a=p.parse_args()
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['ELECTROCOUNT_SKIP_PROFILE']='1'
os.environ['ELECTROCOUNT_DATA_DIR']=str(out);os.environ['ELECTROCOUNT_SETTINGS_PATH']=str(out/'settings.ini')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QPointF,Qt
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtTest import QTest
from electrocount.main_window import MainWindow
from electrocount.detection_service import run_detection,result_signature
from electrocount.pdf_engine import PdfiumEngine
from electrocount.pdf_cache import CachedPDFEngine
from electrocount.project_manager import ProjectManager
app=QApplication([])
for f in ('segoeui.ttf','segoeuib.ttf'):
 font=Path('C:/Windows/Fonts')/f
 if font.exists():QFontDatabase.addApplicationFont(str(font))
app.setFont(QFont('Segoe UI',10));w=MainWindow();w.resize(1560,940);w.show()
w.settings_store.set('debug/artifacts',True);w.performance.set_mode('ECO')
errors=[];w.jobs.failed.disconnect();w.jobs.failed.connect(errors.append)
w.open_path(a.pdf);start=time.monotonic();phase='open';exitcode=1

def stop():
 w.jobs.close();w.loading=w.busy=w.dirty=False;w.close();app.quit()

def step():
 global phase,exitcode
 try:
  if errors:raise RuntimeError(str(errors))
  if time.monotonic()-start>900:raise RuntimeError('GUI diagnostic timeout: '+phase)
  if phase=='open' and w.view.preview is not None and not w.loading:
   w.view.resetTransform();w.view.scale(a.zoom,a.zoom);w.view.centerOn(a.selection[0]+a.selection[2]/2,a.selection[1]+a.selection[3]/2);app.processEvents()
   w.registry.invoke('template')
   x,y,sw,sh=a.selection
   left=w.view.mapFromScene(QPointF(x,y));right=w.view.mapFromScene(QPointF(x+sw,y+sh))
   QTest.mousePress(w.view.viewport(),Qt.MouseButton.LeftButton,pos=left)
   QTest.mouseMove(w.view.viewport(),right)
   QTest.mouseRelease(w.view.viewport(),Qt.MouseButton.LeftButton,pos=right)
   phase='template'
  elif phase=='template' and w.project.active_group() and not w.loading:
   assert w.project.active_group().label==a.label
   phase='find';w.registry.invoke('find')
  elif phase=='find' and w.project.analysis_reports and not w.busy:
   group=w.project.active_group();gui=w.project.analysis_reports[f'{group.id}:0']
   direct=run_detection(CachedPDFEngine(PdfiumEngine(),out/'direct-cache'),a.pdf,0,group.template,a.label,w.project.threshold,
                        config=w.performance.plan.to_dict())
   assigned=[d for d in w.project.detections if d.group==group.id]
   w.folder=str(out/'saved-project');assert w.save_project()
   restored=ProjectManager().load(out/'saved-project/project.sqlite')
   report={'counts':gui['counts'],'dpr':w.view.devicePixelRatioF(),'zoom':a.zoom,
      'selection':w.view.last_selection_context,'gui_result_sha256':gui['result_sha256'],
      'service_result_sha256':direct['result_sha256'],'same_result':gui['result_sha256']==direct['result_sha256'],
      'assigned':len(assigned),'ui_row':[w.groups.topLevelItem(0).text(i) for i in range(4)],
      'summary':w.summary.text(),'save_restore_equal':restored.detections==w.project.detections,
      'unique_labels':len({tuple(d.label_bbox) for d in assigned if d.label_bbox}), 'unique_positions':len({tuple(round(v,2) for v in d.rect) for d in assigned}),'seconds':time.monotonic()-start,'errors':errors}
   assert report['counts']=={'raw_matches':a.expected+a.legend_count,'legend_matches':a.legend_count,'countable_devices':a.expected}
   assert report['same_result'] and report['unique_positions']==a.expected and report['save_restore_equal']
   w.grab().save(str(out/'gui-detail.png'));w.view.fit();w.refresh_results();w.grab().save(str(out/'gui-fit.png'))
   (out/'gui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps(report,ensure_ascii=True),flush=True);exitcode=0;stop();return
 except Exception as exc:
  import traceback
  print(traceback.format_exc(),flush=True);(out/'gui-error.txt').write_text(traceback.format_exc(),encoding='utf-8');stop();return
 QTimer.singleShot(100,step)
QTimer.singleShot(100,step);app.exec();raise SystemExit(exitcode)
