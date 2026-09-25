"""Paired synthetic electrical variants; never a claim about private drawings."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from electrocount.benchmark import metrics
from electrocount.detection_service import prepare_detection, run_detection
from electrocount.pdf_engine import PdfiumEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    make_pdf = runpy.run_path(str(ROOT / 'tests/test_electrical_ai.py'))['electrical_pdf']
    pdf = PdfiumEngine()
    rows = []
    for rating in ('IP44', 'EX', '3~'):
        path = args.output / (rating.replace('~', 'phase') + '.pdf')
        selection, truth = make_pdf(path, rating)
        template = prepare_detection(pdf, str(path), 0, selection)
        for mode in ('classic', 'hybrid', 'hybrid_base'):
            start = time.perf_counter()
            result = run_detection(pdf, str(path), 0, copy.deepcopy(template), 'G1',
                                   config={'engine_mode': mode})
            rows.append(dict(rating=rating, engine_mode=mode,
                elapsed_seconds=round(time.perf_counter()-start, 3),
                pdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                selection=selection, expected=truth,
                metrics=metrics([h['rect'] for h in result['matches']], truth, iou=.7),
                review=len(result['review']), other=len(result['discovered_other_label']),
                pipeline=result['pipeline'], result_sha256=result['result_sha256']))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    report = {'scope': 'synthetic; identical inputs; later cases may reuse model/image caches',
              'results': rows}
    (args.output/'benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if all(r['metrics']['tp']==2 and r['metrics']['false_positives']==0 and
                   r['metrics']['false_negatives']==0 and r['review']==1 and r['other']==2 for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
