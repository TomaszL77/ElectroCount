"""Real-PDF audit. Private PDFs stay external; checked ROI annotations below."""
import argparse,json,time,sys,math,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--pdf',required=True);p.add_argument('--suite',choices=['floor','cpp204','cpp203'],required=True);p.add_argument('--output',required=True);p.add_argument('--source-root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--mode',choices=['classic','hybrid','hybrid_base'],default='classic');p.add_argument('--label');a=p.parse_args()
sys.path.insert(0,str(Path(a.source_root)/'src'))
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount import __version__
pdf=PdfiumEngine();items=pdf.extract_text(a.pdf,0);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
rows=[]
if a.suite=='floor':
 cases=[]
 for label,index in [('7',4),('8',2),('9',0),('10',4)]:
  i=[i for i in items if i.normalized_text==label][index];x,y,w,h=i.bbox
  cases.append((label,[x-3,y-1,w+6,14]))
 roi=None;truth=None
elif a.suite=='cpp204':
 cases=[('AW3',[697,609,6,6]),('EW3',[772.8,609.5,13,6.3])];roi=[680,595,480,220]
 truth={'AW3':[[700.4,611.1],[848.9,611.1],[996.7,611.1],[1127.4,611.1],[700.4,791.6],[848.9,791.6],[996.7,791.6],[1127.4,775.]],'EW3':[[779.3,612.6],[1063.6,713.8]]}
else:
 cases=[('AW4',[143.7,349.8,5.5,5.5])];roi=[50,270,600,310]
 truth={'AW4':[[146.4,352.1],[322.,352.1],[519.6,352.1],[146.4,529.2],[322.,529.2],[519.6,529.2]]}
for label,selection in cases:
 if a.label and label!=a.label:continue
 start=time.monotonic();t=prepare_detection(pdf,a.pdf,0,selection)
 print('START',label,'recognized',t['label'],flush=True)
 r=run_detection(pdf,a.pdf,0,t,config={'engine_mode':a.mode})
 (out/(label+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2))
 correct=set();reviews=set();wrong=[];outside=0;duplicates=0
 if a.suite=='floor':
  expected=[i for i in items if i.normalized_text==label and i.center[0]<1800]
 else:expected=truth[label]
 for bucket,seen in [('matches',correct),('review',reviews)]:
  for h in r[bucket]:
   x,y,w,hg=h['rect'];center=[x+w/2,y+hg/2]
   if roi and not (roi[0]<=center[0]<=roi[0]+roi[2] and roi[1]<=center[1]<=roi[1]+roi[3]):
    if bucket=='matches':outside+=1
    continue
   if a.suite=='floor':
    found=[i for i,e in enumerate(expected) if h.get('label_bbox') and sum(abs(v-u) for v,u in zip(h['label_bbox'],e.bbox))<.1]
   else:found=[i for i,e in enumerate(expected) if math.dist(center,e)<(6 if label=='EW3' else 4)]
   if found:
    if found[0] in seen and bucket=='matches':duplicates+=1
    seen.add(found[0])
   elif bucket=='matches':wrong.append({'rect':h['rect'],'label':h['label']})
 row={'label':label,'recognized_template_label':t['label'],'selection':selection,'seconds':round(time.monotonic()-start,3),'expected_in_audited_scope':len(expected),'correct':len(correct),'review_correct':len(reviews-correct),'missed':len(set(range(len(expected)))-correct-reviews),'false_in_scope':len(wrong),'duplicates':duplicates,'false_details':wrong,'total_full_page_matches':len(r['matches']),'total_full_page_review':len(r['review']),'full_page_matches_outside_audited_roi':outside}
 rows.append(row);print(json.dumps(row),flush=True)
 report={'version':__version__,'pdf_sha256':hashlib.sha256(Path(a.pdf).read_bytes()).hexdigest(),'suite':a.suite,'roi':roi,'reference_centers':truth,'threshold':.82,'mode':a.mode,'results':rows}
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
