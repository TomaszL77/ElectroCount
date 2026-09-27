"""Compare full matches and review recovery on a reproducible six-device PDF."""
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--source-root',type=Path,default=root)
p.add_argument('--mode',choices=['classic','hybrid','hybrid_base','all'],default='all')
a=p.parse_args();sys.path[:0]=[str(a.source_root/'src'),str(root/'tests')]
from occlusion_fixture import scene
from electrocount import __version__
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount.domain import overlap_metrics

a.output.mkdir(parents=True,exist_ok=True)
path=a.output/'occluded.pdf';selection,boxes=scene(path)
pdf=PdfiumEngine();template=prepare_detection(pdf,str(path),0,selection);rows=[]
for mode in (('classic','hybrid','hybrid_base') if a.mode=='all' else (a.mode,)):
    start=time.monotonic()
    result=run_detection(pdf,str(path),0,copy.deepcopy(template),config={'engine_mode':mode})
    cases=[]
    for kind,box in zip(('clean7','text7','diagonal7','other8','wrong7','opaque7'),boxes):
        hits=[{'bucket':bucket,**{k:h.get(k) for k in ('label','reason','confidence','shape_score','color_score','label_score','verification_details')}}
              for bucket in ('matches','review','discovered_other_label') for h in result[bucket]
              if overlap_metrics(box,h['rect'])[0]>.5]
        cases.append({'case':kind,'hits':hits})
    rows.append({'mode':mode,'seconds':round(time.monotonic()-start,3),
                 'counts':{k:len(result[k]) for k in ('matches','review','discovered_other_label')},
                 'cases':cases,'pipeline':result['pipeline']})
    print(json.dumps({k:v for k,v in rows[-1].items() if k not in ('cases','pipeline')}),flush=True)
report={'version':__version__,'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'selection':selection,'results':rows}
(a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
