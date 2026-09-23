"""Repeatable real-document regression; counts are detections, not ground truth."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from electrocount.pdf_engine import PdfiumEngine
from electrocount.pdf_cache import CachedPDFEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount.diagnostics import digest
from electrocount.domain import overlap_metrics

p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--case',action='append');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
if digest(a.pdf)!='208e7dc0042923bed70689ec9ac2da0a35fc574f72212976581c14704f486bb7':
    raise ValueError('The annotated selections belong to CPP-TD-CR-EB-203.pdf; source bytes differ.')
cases={'L1':[1493,1526.84,20,7],'L1-1':[1493,1547.6,20,7],
       'L2':[1493,1568.48,20,7],'L2-1':[1493,1589.24,20,7],
       'L3':[1488,1609,30,10],'L3-1':[1488,1629.9,30,10],
       'L6':[1498,1733.24,10,10],'L6-1':[1498,1754,10,10]}
pdf=CachedPDFEngine(PdfiumEngine(),a.output/'cache');report={'file_sha256':digest(a.pdf),'ground_truth_complete':False,'cases':{},'variant_overlap':{}}
results={}
for name,selection in cases.items():
    if a.case and name not in a.case:continue
    start=time.monotonic();template=prepare_detection(pdf,str(a.pdf),0,selection)
    result=run_detection(pdf,str(a.pdf),0,template,status=lambda message:print(name,message,flush=True))
    results[name]=result
    (a.output/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    report['cases'][name]={'selection':selection,'source':template['source'],'counts':result['counts'],
        'review':len(result['review']),'seconds':time.monotonic()-start,'result_sha256':result['result_sha256'],
        'warnings':result['coverage_warnings']}
    for kind in ('L1','L2','L3','L6'):
        if kind in results and kind+'-1' in results:
            report['variant_overlap'][kind]=sum(overlap_metrics(x['rect'],y['rect'])[0]>.5
                for x in results[kind]['matches'] for y in results[kind+'-1']['matches'])
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,json.dumps(report['cases'][name]),flush=True)
