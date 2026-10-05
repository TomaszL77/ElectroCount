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


def train(directory, progress=lambda p: None, status=lambda s: None, epochs=80):
    store = LearningStore(directory)
    ready, reason = store.readiness()
    if not ready:
        raise ValueError(reason)
    rows = [r for r in store.examples() if r['outcome'] in ('correct', 'wrong')]
    splits = {split: [r for r in rows if r['split'] == split] for split in ('train', 'validation', 'test')}
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
    status('Porównanie na odłożonych dokumentach testowych…')
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
    model.metadata.update(id=model_id, threshold=threshold, report=report)
    output = Path(directory) / 'models' / (model_id + '.ecmodel')
    model.save(output)
    report['model_file'] = output.name
    store.save_report(report)
    progress(100)
    return report
