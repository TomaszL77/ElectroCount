"""Document-disjoint training, validation threshold, frozen test comparisons."""
import hashlib
import time
from pathlib import Path
import numpy as np
from .learning_store import LearningStore, decode
from .tiny_model import TinyPairModel, pair_features


def metrics(y, scores, threshold=.5):
    predicted = np.asarray(scores) >= threshold
    truth = np.asarray(y) == 1
    tp = int((predicted & truth).sum()); fp = int((predicted & ~truth).sum())
    fn = int((~predicted & truth).sum()); tn = int((~predicted & ~truth).sum())
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=tp / max(1, tp + fp),
                recall=tp / max(1, tp + fn), accuracy=(tp + tn) / max(1, len(truth)),
                count=len(truth))


def train(directory, progress=lambda p: None, status=lambda s: None, epochs=80, preliminary=False):
    store = LearningStore(directory)
    ready, reason = store.preliminary_readiness() if preliminary else store.readiness()
    if not ready:
        raise ValueError(reason)
    rows = [r for r in store.examples() if r['outcome'] in ('correct', 'wrong')]
    splits = {split: [r for r in rows if r['split'] == split] for split in ('train', 'validation', 'test')}
    if preliminary:
        # Only use the user-designated learning PDFs. Never consume existing
        # held-out documents to bootstrap a model. All pairs at one physical
        # location stay together; multiple references cannot leak a crop.
        rows=[r for r in rows if r['split']=='train']
        locations={hashlib.sha256(repr((r['document'],r['page'],tuple(round(v,3) for v in r['rect']))).encode()).hexdigest()
                   for r in rows}
        ordered=sorted(locations)
        assignments={key:('train' if i<len(ordered)*.7 else 'validation' if i<len(ordered)*.85 else 'test')
                     for i,key in enumerate(ordered)}
        splits={s:[] for s in ('train','validation','test')}
        for row in rows:
            key=hashlib.sha256(repr((row['document'],row['page'],tuple(round(v,3) for v in row['rect']))).encode()).hexdigest()
            splits[assignments[key]].append(row)
        for records in splits.values():
            if not records or len({r['outcome'] for r in records})<2:
                raise ValueError('Za mało zróżnicowanych lokalizacji do kontroli nauki wstępnej. Dodaj kolejne ocenione przykłady.')
    status('Przygotowanie ocenionych przykładów…')
    datasets = {}
    for split, records in splits.items():
        x, y = [], []
        for row in records:
            reference, crop = decode(row['reference']), decode(row['crop'])
            x.append(pair_features(reference, crop)); y.append(float(row['outcome'] == 'correct'))
            if split == 'train':
                # Perturb only training crops. Source PDF and all its variants
                # remain in one split; held-out documents are never augmented.
                import cv2
                for offset in (-1, 1):
                    matrix = np.float32([[1, 0, offset], [0, 1, -offset]])
                    perturbed = cv2.warpAffine(crop, matrix, (crop.shape[1], crop.shape[0]),
                                              borderValue=(255, 255, 255))
                    x.append(pair_features(reference, perturbed)); y.append(float(row['outcome'] == 'correct'))
        datasets[split] = (np.asarray(x, np.float32), np.asarray(y, np.float32))
    progress(10); status('Uczenie małej sieci na CPU…')
    started = time.monotonic()
    model = TinyPairModel()
    loss = model.fit(*datasets['train'], datasets['validation'], epochs=epochs, progress=progress)
    vx, vy = datasets['validation']; vs = model.predict(vx)
    # Threshold selection uses validation only, never test examples.
    thresholds = [.5, .6, .7, .8, .9, .95, .99]
    candidates = [(t, metrics(vy, vs, t)) for t in thresholds]
    suitable = [(t, m) for t, m in candidates if m['precision'] >= .98 and m['tp'] > 0]
    threshold = max(suitable, key=lambda item: (item[1]['recall'], -item[0]))[0] if suitable else .9
    status('Kontrola na odłożonych lokalizacjach tych samych PDF-ów…' if preliminary else 'Porównanie na odłożonych dokumentach testowych…')
    tx, ty = datasets['test']
    inference_start = time.monotonic(); scores = model.predict(tx)
    model_ms = (time.monotonic() - inference_start) * 1000
    from ..feature_matcher import OpenCVFeatureMatcher
    classic = []
    matcher = OpenCVFeatureMatcher()
    classic_start = time.monotonic()
    for row in splits['test']:
        result = matcher.verify(decode(row['reference']), decode(row['crop']))
        classic.append(float(result['verified']))
    classic_ms = (time.monotonic() - classic_start) * 1000
    combined = np.maximum(np.asarray(classic), (scores >= threshold).astype(np.float32))
    identity = hashlib.sha256('|'.join(sorted(r['id'] + ':' + r['outcome'] + ':' + r['split']
                                                   for r in rows)).encode()).hexdigest()
    model_id = time.strftime('%Y%m%d-%H%M%S') + '-' + identity[:8]
    by_group = {}
    for row in splits['test']:
        key = row['document_name'] + ' / ' + row['group_name']
        ids = [i for i, r in enumerate(splits['test']) if r['document'] == row['document'] and r['group_id'] == row['group_id']]
        by_group[key] = metrics(ty[ids], scores[ids], threshold)
    report = dict(id=model_id, dataset_digest=identity, threshold=threshold,
        counts={split: len(records) for split, records in splits.items()},
        documents={split: sorted({r['document'] for r in records}) for split, records in splits.items()},
        validation=metrics(vy, vs, threshold), validation_loss=loss,
        comparisons={'classic': metrics(ty, classic), 'model': metrics(ty, scores, threshold),
                     'combined': metrics(ty, combined)}, by_group=by_group,
        timings={'training_seconds': time.monotonic() - started,
                 'model_batch_ms': model_ms, 'classic_crop_ms': classic_ms},
        measurement='human-labelled visual pairs; not whole-page detection recall',
        auto_activated=False)
    report.update(preliminary=preliminary,
        example_ids={s:[r['id'] for r in records] for s,records in splits.items()},
        assessment_origins=sorted({r.get('metadata',{}).get('assessment_origin','user') for r in rows}),
        validation_scope='same_document_locations' if preliminary else 'independent_documents',
        generalization_verified=not preliminary,
        limitation='Nauka wstępna: wycinki pochodzą z tych samych PDF-ów. Wynik nie potwierdza działania na nowym dokumencie.' if preliminary else '')
    if preliminary:report['measurement']='visually assessed pairs at held-out locations in the same documents; not whole-page completeness or new-document generalization'
    model.metadata.update(id=model_id, threshold=threshold, report=report)
    output = Path(directory) / 'models' / (model_id + '.ecmodel')
    model.save(output)
    report['model_file'] = output.name
    store.save_report(report)
    progress(100)
    return report
