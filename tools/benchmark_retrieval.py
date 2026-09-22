"""Paired classic/hybrid benchmark with identical PDF bytes, crop and ground truth."""
import argparse,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'tests')]
from electrocount.pdf_engine import PdfiumEngine
from electrocount.pdf_cache import CachedPDFEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount.diagnostics import digest
from electrocount.benchmark import metrics,promotion_allowed
from test_multimodal import fixture_pdf

p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
p.add_argument('--hall',type=Path)
p.add_argument('--case',action='append',help='Run only named cases')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
cases=[]
for label in ('D1','AW2','EW1','QP14','AS1','1A','2A','10','7N'):
    path=a.output/(label+'.pdf');boxes,selection=fixture_pdf(path,label)
    cases.append(dict(id=label,path=str(path),selection=selection,label=label,expected=boxes,metric_bbox='rect',provenance='generated annotated positions'))
if a.hall:
    pdf=PdfiumEngine()
    # All L3 texts in the lower drawing rows were previously manually audited.
    # Use label boxes from the PDF, not boxes produced by either detector.
    boxes=[i.bbox for i in pdf.extract_text(str(a.hall),0) if i.normalized_text=='L3' and 800<i.bbox[1]<1500]
    if len(boxes)!=72:raise ValueError('Hall ground truth does not match the manually audited source')
    for name,selection in [('hall-legend',[5080,420,57,20]),('hall-drawing',[3130,1360,80,100])]:
        cases.append(dict(id=name,path=str(a.hall),selection=selection,label='L3',expected=boxes,
            metric_bbox='label_bbox',provenance='72 manually audited devices; localization measured at native associated label box'))
report={'cases':[],'promotion_allowed':False}
for case in cases:
    if a.case and case['id'] not in a.case:continue
    pdf=CachedPDFEngine(PdfiumEngine(),a.output/'cache')
    template=prepare_detection(pdf,case['path'],0,case['selection'])
    row={**case,'file_sha256':digest(case['path']),'results':{}}
    for mode in ('classic','hybrid'):
        start=time.monotonic()
        result=run_detection(pdf,case['path'],0,template,case['label'],config={'engine_mode':mode})
        boxes=[h.get(case['metric_bbox']) or h['rect'] for h in result['matches']]
        row['results'][mode]={**metrics(boxes,case['expected']),'seconds':time.monotonic()-start,
            'counts':result['counts'],'review':len(result['review']),'stages':result['stages'],
            'result_sha256':result['result_sha256']}
        print(case['id'],mode,json.dumps(row['results'][mode]),flush=True)
        (a.output/(case['id']+'-'+mode+'.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    report['cases'].append(row)
    report['promotion_allowed']=promotion_allowed([c['results']['classic'] for c in report['cases']],
        [c['results']['hybrid'] for c in report['cases']])
    (a.output/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
