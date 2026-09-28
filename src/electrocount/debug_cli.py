"""Replay a GUI detection log through the exact same application service."""
import argparse
import json
from pathlib import Path
import cv2
from .detection_service import run_detection, self_test
from .diagnostics import new_debug_run, runtime_info, write_json, digest
from .pdf_engine import PdfiumEngine
from .pdf_cache import CachedPDFEngine
from .performance import execution_plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--engine-mode', choices=['classic','hybrid','hybrid_base'], default='classic')
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--pdf', help='New local path to the same document')
    parser.add_argument('--template-pdf', help='New local path if reference is from another document')
    parser.add_argument('--output', type=Path)
    args=parser.parse_args()
    out=args.output or new_debug_run()
    out.mkdir(parents=True,exist_ok=True)
    pdf=CachedPDFEngine(PdfiumEngine(),out/'cache')
    plan=execution_plan('AUTO');cv2.setNumThreads(plan.cpu_threads)
    write_json(out/'runtime_info.json',runtime_info(probe_hardware=True))
    if args.self_test:
        report=self_test(pdf,out,config={**plan.to_dict(),'engine_mode':args.engine_mode,'neural_enabled':args.engine_mode!='classic'})
        print(json.dumps(report,ensure_ascii=True))
        return 0 if report['status']=='PASS' else 1
    if not args.replay:parser.error('Specify --self-test or --replay detection_log.json')
    log=json.loads(args.replay.read_text(encoding='utf-8'))
    path=args.pdf or log['path']
    if digest(path)!=log['file_sha256']:
        raise ValueError('Replay requires the same PDF bytes (SHA-256 differs).')
    source=args.template_pdf or (path if log['template_file_sha256']==log['file_sha256'] else log.get('template_path'))
    if digest(source)!=log['template_file_sha256']:
        raise ValueError('Template PDF SHA-256 differs.')
    config={k:v for k,v in log['config'].items() if k!='gui_runtime'}
    if config.get('cpu_threads'):cv2.setNumThreads(config['cpu_threads'])
    result=run_detection(pdf,path,log['page'],log['template'],log['label'],log['threshold'],
        template_path=source,
        config=config,debug_dir=out)
    equal=log.get('result_sha256')==result['result_sha256']
    report={'counts':result['counts'],'same_result':equal,'output':str(out)}
    write_json(out/'replay_comparison.json',report);print(json.dumps(report))
    return 0 if equal else 1


if __name__=='__main__':
    raise SystemExit(main())
