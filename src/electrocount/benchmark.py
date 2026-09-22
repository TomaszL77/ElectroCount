"""One-to-one localization metrics; quantities alone never prove correctness."""
from .domain import overlap_metrics


def metrics(predictions, expected, iou=.3):
    edges={i:[j for j,b in enumerate(expected) if overlap_metrics(a,b)[0]>=iou]
        for i,a in enumerate(predictions)}
    assigned={}
    def augment(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or augment(assigned[j],seen):
                assigned[j]=i;return True
        return False
    for i in edges:augment(i,set())
    tp=len(assigned);fp=len(predictions)-tp;fn=len(expected)-tp
    precision=tp/(tp+fp) if tp+fp else float(not expected)
    recall=tp/(tp+fn) if tp+fn else 1.
    return {'tp':tp,'false_positives':fp,'false_negatives':fn,'precision':precision,
        'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.}


def promotion_allowed(classic,hybrid):
    # User requirement: both recall and precision must improve, no regression
    # on any case. Saturated tiny fixtures cannot justify promoting a model.
    no_regression=all(b['precision']>=a['precision'] and b['recall']>=a['recall']
        for a,b in zip(classic,hybrid))
    return bool(classic) and len(classic)==len(hybrid) and no_regression and (
        sum(x['precision'] for x in hybrid)>sum(x['precision'] for x in classic) and
        sum(x['recall'] for x in hybrid)>sum(x['recall'] for x in classic))
