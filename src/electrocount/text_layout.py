"""Page-local layout consensus learned without looking at target device codes."""
from collections import defaultdict, Counter
import math
import statistics


def resolve_repeated_layout(candidates, engine, items):
    groups=defaultdict(dict)
    def key(c):
        w,h=c['rect'][2:]
        return w>=h,round(math.log2(max(w,h,1)))
    for c in candidates:
        a=c['association_result']
        if a['item'] and a['score']>=.8 and a.get('layout'):
            groups[key(c)][tuple(round(v,1) for v in c['rect'])]=a['layout']
    layouts={}
    for group,records in groups.items():
        rows=list(records.values())
        if len(rows)<5:continue
        bins=Counter(tuple(round(v*4) for v in row['offset']) for row in rows)
        dominant,count=bins.most_common(1)[0]
        if count/len(rows)<.5:continue
        consistent=[row for row in rows if tuple(round(v*4) for v in row['offset'])==dominant]
        layouts[group]={k:statistics.median(row[k] for row in consistent) for k in ('dx','dy','glyph_size')}
        layouts[group]['offset']=[statistics.median(row['offset'][i] for row in consistent) for i in (0,1)]
    for c in candidates:
        if not c['association_result']['item'] and key(c) in layouts:
            a=engine.associate(c['rect'],items,layouts[key(c)])
            if a['item']:
                a['layout_source']='page_consensus'
                c['association_result']=a
