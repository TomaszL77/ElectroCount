"""Persistent collector/trainer, isolated from the GUI and viewer process."""
import hashlib
import json
import sys
from pathlib import Path
import cv2
from .ai.learning_store import LearningStore
from .ai.learning_training import train
from .pdf_engine import PdfiumEngine
from .render_session import RenderSession
from .pdf_cache import CachedPDFEngine
from .ai.learning_images import symbol_crop

DIGESTS = {}


def emit(message):
    print(json.dumps(message, ensure_ascii=True), flush=True)


def capture(request, pdf):
    template = request['template']
    source, reference_page = request['template_path'], request['template_page']
    reference_box = template.get('raster_rect', template.get('symbol_bbox', template['rect']))
    candidate_box = request['rect']
    reference = symbol_crop(pdf,source,reference_page,reference_box)
    crop = symbol_crop(pdf,request['path'],request['page'],candidate_box)
    stat = Path(request['path']).stat()
    key = (request['path'], stat.st_size, stat.st_mtime_ns)
    if key not in DIGESTS:
        if len(DIGESTS) >= 16: DIGESTS.clear()
        with Path(request['path']).open('rb') as stream:
            DIGESTS[key] = hashlib.file_digest(stream, 'sha256').hexdigest()
    document = DIGESTS[key]
    record = {'document': document, 'document_name': Path(request['path']).name,
              'page': request['page'], 'group_id': request['group_id'],
              'group_name': request['group_name'], 'rect': candidate_box,
              'outcome': request['outcome'], 'metadata': request.get('metadata', {})}
    return LearningStore(request['directory']).record(record, reference, crop)


def main():
    cv2.setNumThreads(1)
    pdf = RenderSession(CachedPDFEngine(PdfiumEngine(), memory_limit=64 * 1024 * 1024))
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                if request['kind'] == 'capture':
                    result = capture(request, pdf)
                elif request['kind'] == 'train':
                    result = train(request['directory'],
                        progress=lambda p: emit({'progress': p}),
                        status=lambda s: emit({'status': s}))
                elif request['kind'] == 'reconcile':
                    LearningStore(request['directory']).reconcile(request['assessments'])
                    result = True
                else:
                    raise ValueError('Nieznane zadanie uczenia.')
                emit({'id': request['id'], 'result': result})
            except Exception as exc:
                emit({'id': request['id'], 'error': str(exc)})
    finally:
        pdf.close()


if __name__ == '__main__':
    main()
