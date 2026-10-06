"""Regression checks for CAD clipping, tessellation and initial learning."""
import math
import numpy as np
from reportlab.pdfgen import canvas
from electrocount.native_geometry import NativeVectorPage, intersects_selection, connected_geometry, paint_group
from electrocount.vector_engine import bbox,signature
from electrocount.socket_symbols import definition,match_candidate
from electrocount.ai.learning_store import LearningStore
from electrocount.ai.learning_training import train
from electrocount.ai.tiny_model import TinyPairModel


def path(points,identifier,fill=False):
    segments=[{'kind':'line','points':[list(a),list(b)]} for a,b in zip(points,points[1:])]
    return {'id':identifier,'segments':segments,'bbox':bbox(points),'fill':fill,'stroke':not fill,
            'color':[0,0,0,255],'stroke_width':.3}


def socket(n=14,inner=False,glyph_scale=1):
    arc=[(10-4*math.cos(i*math.pi/n),10+4*math.sin(i*math.pi/n)) for i in range(n+1)]
    paths=[path(arc,1),path([(6,14),(10,14)],2),path([(10,14),(14,14)],3),path([(10,14),(10,17)],4)]
    if inner:paths.append(path([(10-2*math.cos(i*math.pi/10),10+2*math.sin(i*math.pi/10)) for i in range(11)],5))
    # Complete closed glyph; size changes independently of the cup geometry.
    glyph=np.array([[0,0],[2,0],[2,1],[1,2],[2,2],[2,3],[0,3],[0,2],[1,1],[0,1],[0,0]])*glyph_scale+[9,6]
    paths.append(path(glyph,6,True))
    return signature(paths,preserve_selection=True)


def test_enclosing_cad_clip_keeps_paths_and_cutting_clip_rejects(tmp_path):
    filename=tmp_path/'clipped.pdf';c=canvas.Canvas(str(filename),pagesize=(200,200))
    c.saveState();clip=c.beginPath();clip.moveTo(10,10)
    for x in range(20,181,10):clip.lineTo(x,10)
    clip.lineTo(190,190);clip.lineTo(10,190);clip.close();c.clipPath(clip,stroke=0)
    c.circle(60,80,10,stroke=1,fill=0);c.restoreState()
    c.saveState();clip=c.beginPath();clip.rect(110,70,10,20);c.clipPath(clip,stroke=0)
    c.circle(120,80,10,stroke=1,fill=0);c.restoreState();c.save()
    with NativeVectorPage(str(filename),0) as native:
        paths=native.decode(range(len(native.index)),preserve=True)
        assert any(abs(p['bbox'][0]-50)<.01 for p in paths)
        assert not any(abs(p['bbox'][0]-110)<.01 for p in paths)
        assert native.clipped


def test_frame_bounds_are_not_painted_inside_selection():
    frame=path([(0,0),(100,0),(100,100),(0,100),(0,0)],1)
    assert not intersects_selection(frame,[30,30,20,20])
    assert intersects_selection(frame,[0,30,20,20])
    frame['fill']=True
    assert intersects_selection(frame,[30,30,20,20])


def test_retessellated_body_and_independent_glyph_size_keep_features():
    a=definition(socket(14));b=definition(socket(17,glyph_scale=.8))
    assert a and b
    body,glyph=match_candidate(a,b)
    assert body>.98 and glyph>.95
    changed=definition(socket(17,inner=True,glyph_scale=.8))
    assert match_candidate(a,changed)[0]<.93
    missing={**b,'has_designation':False,'designation':np.zeros_like(b['designation'])}
    assert match_candidate(a,missing)[1]==0


def test_background_recovery_cannot_drop_disconnected_inner_arc():
    plain=socket();variant=socket(inner=True)
    anchor=variant['paths'][0];paths=variant['paths'][:-1]
    # Include an unrelated same-style path so each recovery is exercised.
    paths.append(path([(8,16),(9,16)],1000))
    assert any(p['id']==5 for p in connected_geometry(plain,paths,anchor))
    paths[4]['id']=5000
    assert any(p['id']==5000 for p in paint_group(plain,paths,anchor))


def test_preliminary_training_is_portable_and_does_not_consume_test_pdf(tmp_path):
    store=LearningStore(tmp_path)
    white=np.full((48,48,3),255,np.uint8);square=white.copy();square[12:36,12:36]=0
    for i in range(90):
        label='correct' if i%2 else 'wrong'
        store.record({'document':'one-pdf','document_name':'Drawing','page':0,'group_id':'socket',
            'group_name':'Socket','rect':[i*10,20,5,5],'outcome':label,'split':'train'},
            square,square if label=='correct' else white)
    store.record({'document':'held-out','page':0,'group_id':'socket','group_name':'Socket',
                  'rect':[1,2,3,4],'outcome':'correct','split':'test'},square,square)
    assert not store.readiness()[0] and store.preliminary_readiness()[0]
    report=train(tmp_path,epochs=2,preliminary=True)
    assert report['preliminary'] and report['validation_scope']=='same_document_locations'
    assert not report['generalization_verified']
    assert all(d==['one-pdf'] for d in report['documents'].values())
    model=TinyPairModel.load(tmp_path/'models'/report['model_file'])
    assert model.metadata['report']['preliminary']


def test_embedded_legend_excludes_only_its_examples(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from electrocount import socket_symbols
    candidate=definition(socket());candidate['rect']=[6,6,8,11]
    other={**candidate,'rect':[56,6,8,11]}
    native=SimpleNamespace(source_path=str(tmp_path/'drawing.pdf'),page_index=0,
        truncated=False,limited_queries=False,index=[],index_cache_hit=False,decoded=0)
    monkeypatch.setattr(socket_symbols,'scan',lambda *a,**kw:[candidate,other])
    template={'signature':socket(),'rect':[6,6,8,11],'page':0,'source':'LEGEND'}
    entry={'group_id':'socket','template':template,'template_path':native.source_path}
    result=socket_symbols.catalogue_results(native,[entry])[0]['result']
    assert [hit['rect'] for hit in result['matches']]==[other['rect']]
    template['reference_page_only']=True
    result=socket_symbols.catalogue_results(native,[entry])[0]['result']
    assert not result['matches'] and not result['review']


def test_separate_filled_triangles_do_not_fill_frame_interior():
    triangles=[[(0,0),(100,0),(100,1),(0,0)],[(0,0),(100,1),(0,1),(0,0)],
               [(0,99),(100,99),(100,100),(0,99)],[(0,99),(100,100),(0,100),(0,99)]]
    frame=path(triangles[0],1,True)
    frame['segments']=[segment for triangle in triangles for segment in path(triangle,1,True)['segments']]
    frame['bbox']=[0,0,100,100]
    assert not intersects_selection(frame,[30,30,20,20])
    assert intersects_selection(frame,[30,0,20,20])


def test_explicit_shape_color_mode_distinguishes_gray_architecture():
    from electrocount.detection_engine import color_matches
    assert color_matches({'foreground_color':[0,0,0]},{'foreground_color':[20,20,20]})
    assert not color_matches({'foreground_color':[0,0,0]},{'foreground_color':[128,128,128]})
