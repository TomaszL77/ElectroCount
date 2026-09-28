"""Reproduce 7/8 and color decisions on one PDF, with separate score evidence."""
import argparse,base64,copy,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'tests')]
from test_template_074 import scene
from electrocount.pdf_engine import PdfiumEngine
from electrocount.detection_service import prepare_detection,run_detection
from electrocount.diagnostics import digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['classic','hybrid','hybrid_base','all'],default='all')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/'identical-7-8.pdf';selection,boxes=scene(path)
    pdf=PdfiumEngine();template=prepare_detection(pdf,str(path),0,selection)
    original=template['representation']['original_rgb_crop']
    (args.output/'original-rgb.png').write_bytes(base64.b64decode(original['png_base64']))
    rows=[]
    for mode in (('classic','hybrid','hybrid_base') if args.mode=='all' else (args.mode,)):
        start=time.monotonic()
        result=run_detection(pdf,str(path),0,copy.deepcopy(template),config={'engine_mode':mode})
        hits=[]
        for bucket in ('matches','review','discovered_other_label'):
            for h in result[bucket]:
                hits.append({k:h.get(k) for k in ('rect','label','status','reason','shape_score','geometry_score','visual_score','color_score','label_score','text_association_score','confidence','text_source')})
        row={'mode':mode,'detected_label':template['label'],'seconds':round(time.monotonic()-start,3),
             'counts':{bucket:len(result[bucket]) for bucket in ('matches','review','discovered_other_label')},
             'pipeline':result['pipeline'],'hits':hits}
        rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    report={'file_sha256':digest(path),'selection':selection,'truth':boxes,'template':template,'results':rows}
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(r['detected_label']=='7' and r['counts']=={'matches':3,'review':1,'discovered_other_label':1} for r in rows) else 1


if __name__=='__main__':raise SystemExit(main())
