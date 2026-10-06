"""Detection V2: proposals -> feature evidence -> geometry gate -> text -> confidence."""
from collections import Counter
import cv2
from .text_engine import TextEngine, normalize_text, prepare_template, mask_text, transformed_layout, TextSpatialIndex
from .matcher import TemplateMatcher, template_variant
from .feature_matcher import OpenCVFeatureMatcher
from .vector_engine import VectorCandidateGenerator, signature_in_rect
from .domain import overlap_metrics


class DetectionEngine:
    def __init__(self,pdf_engine,matcher=None,text_engine=None,feature_matcher=None,visual_encoder=None,learned_model=None,fast=False):
        self.encoder=visual_encoder
        self.learned_model=learned_model
        self.fast=fast
        self.pdf=pdf_engine
        self.matcher=matcher or TemplateMatcher()
        self.custom_matcher=matcher is not None
        self.text=text_engine or TextEngine()
        self.features=feature_matcher or OpenCVFeatureMatcher()

    def find(self,path,page,template,label="",threshold=.82,progress=lambda p:None,template_path=None,status=lambda text:None):
        status("Odczyt tekstu i przygotowanie wzorca")
        source=template_path or path
        if not template.get("text_aware") or (template.get("definition_version",0)<13 and
                template.get("selection_rect") and hasattr(self.pdf,"open_vector_page") and
                template.get('extraction_mode')!='reviewed_apparatus_parts'):
            previous=template
            from .detection_service import prepare_detection
            template=prepare_detection(self.pdf,source,template['page'],template.get('selection_bbox',template.get('selection_rect',template['rect'])))
            if previous.get('source_override'):
                template['source']=previous['source_override']
            elif previous.get('source')=='LEGEND':
                template['source']='LEGEND'
            if 'match_mode' in previous:template['match_mode']=previous['match_mode']
            if template.get('signature'):
                template['signature']['source_legend']=template.get('source')=='LEGEND'
            template['group_id']=previous.get('group_id',previous.get('representation',{}).get('group_id'))
            template['id']=previous.get('id',previous.get('representation',{}).get('id'))
        shape_color=template.get('match_mode') in ('shape','shape_color')
        strict_color=template.get('match_mode')=='shape_color'
        from .text_roles import TextRoleClassifier
        supplied=normalize_text(label)
        if supplied and TextRoleClassifier().classify(supplied)[0]!='DEVICE_LABEL':supplied=''
        expected='' if shape_color else normalize_text(supplied or template.get("label",""))
        original_template=template
        if template.get('analysis_signature') and not shape_color:
            from .text_engine import as_item
            body=template['analysis_signature']['bbox']
            association=self.text.associate(body,[as_item(template['label_item'])])
            template={**template,'rect':list(body),'signature':template['analysis_signature'],
                'raster_rect':[body[0]-.5,body[1]-.5,body[2]+1,body[3]+1],
                'association':association.get('layout')}
        if template.get('signature') and template.get('source')=='LEGEND':
            template['signature']['source_legend']=True
        if not self.custom_matcher and hasattr(self.pdf,'open_vector_page'):
            from .socket_symbols import definition, catalogue_results
            if definition(template.get('signature')) is not None:
                status('Sprawdzanie pełnych kształtów gniazd i oznaczeń wariantów')
                with self.pdf.open_vector_page(path,page) as native:
                    results=catalogue_results(native,[{'group_id':'active','template':template,'label':expected,'template_path':source}],progress,strict=True)
                if self.learned_model:
                    from .socket_symbols import score_review_pairs
                    score_review_pairs(self.pdf,path,page,results,
                        [{'group_id':'active','template':template,'template_path':source}],self.learned_model)
                result=results[0]['result']
                progress(100)
                return result
        items=self.pdf.extract_text(path,page)
        if not items and not self.custom_matcher and hasattr(self.pdf,'open_vector_page'):
            from .ocr_engine import OCREngine
            status('Odczyt oznaczeń zapisanych w PDF jako kształty')
            items=OCREngine().read_outlined_text(self.pdf,path,page)
        template_items=items if source==path and page==template["page"] else self.pdf.extract_text(source,template["page"])
        progress(5)
        status("Odczyt geometrii PDF")
        proposals=[]
        warnings=[]
        signature=template.get("signature")
        vectors=None
        native_stats={}
        if not self.custom_matcher and signature and signature.get("native_local") and hasattr(self.pdf,"open_vector_page"):
            progress(10)
            status("Indeks geometrii i sprawdzanie otoczenia oznaczeń")
            try:
                with self.pdf.open_vector_page(path,page) as native:
                    found,native_stats=native.find(signature,items,expected,lambda p:progress(10+round(p*.20)))
                    proposals.extend(found)
                vectors={"has_images":native_stats["has_images"],"unsupported":int(native_stats["truncated"] or native_stats["limited_queries"] or native_stats["clipped_anchor_paths"]),
                         "truncated":native_stats["truncated"]}
            except (RuntimeError,AttributeError) as exc:
                warnings.append("Geometria PDF niedostępna; przełączono na matcher obrazu CPU: "+str(exc))
                native_stats={}
                vectors={'has_images':True,'unsupported':1,'truncated':False,'paths':[]}
                signature=None
        elif not self.custom_matcher and hasattr(self.pdf,"extract_vectors"):
            if not signature and template.get('definition_version',0)<11:
                signature=signature_in_rect(self.pdf.extract_vectors(source,template["page"]),template["rect"])
            vectors=self.pdf.extract_vectors(path,page)
        if not native_stats:progress(10)
        status("Wyszukiwanie kandydatów wektorowych")
        if signature and vectors and not native_stats:
            proposals.extend(VectorCandidateGenerator().find(signature,vectors,lambda p:progress(10+round(p*.20))))
        use_raster=self.custom_matcher or not signature or vectors is None or vectors["has_images"] or vectors["unsupported"]>0
        progress(30)
        if use_raster:
            status("Wyszukiwanie podobnych kształtów w kafelkach")
            try:
                raster_options={}
                if not self.custom_matcher and native_stats and vectors['unsupported']==0:
                    raster_options['search_regions']=native_stats.get('image_regions')
                proposals.extend(self.matcher.find(self.pdf,path,page,template,threshold,
                    lambda p:progress(30+round(p*.20)),text_items=items,
                    template_items=template_items,template_path=source,**raster_options))
            except ValueError as exc:
                if not native_stats or not proposals:raise
                warnings.append("Analiza obrazu niepełna: "+str(exc))
        retrieval_stats={}
        if self.fast and not self.custom_matcher:
            from .ai.fast_proposals import propose
            status('Szybki skan obrazu strony i ponowne użycie cech')
            extra,notes=propose(self.pdf,path,page,template,source,items,template_items,threshold)
            warnings.extend(notes)
            certain=[c['rect'] for c in proposals if c.get('verified')]
            proposals.extend(c for c in extra if not any(overlap_metrics(c['rect'],r)[0]>.45 for r in certain))
        if self.encoder:
            from .ai.retrieval import VisualRetrieval
            status('Analiza AI: przeszukiwanie wszystkich kafelków strony')
            reference_image=mask_text(self.pdf.render(source,template['page'],2.,template.get('raster_rect',template['rect'])),
                template_items,template.get('raster_rect',template['rect']),2.)
            recovered,retrieval_stats=VisualRetrieval(self.encoder).find(self.pdf,path,page,template,reference_image,items,
                lambda p:progress(30+round(p*.2)))
            proposals.extend(recovered)
        from .occlusion import label_proposals,verify_partial
        # A native geometry match already explains its label. Do not probe other
        # rotations around that same annotation, preserving the vector fast path.
        seed_items=items
        if not self.custom_matcher:
            seed_index=TextSpatialIndex(items);explained=set()
            for candidate in proposals:
                if not candidate.get('verified'):continue
                association=self.text.associate(candidate['rect'],seed_index,
                    transformed_layout(template.get('association'),candidate.get('rotation',0),candidate.get('scale',1)))
                item=association.get('item')
                if item and item.source=='pdf_native':explained.add(tuple(item.bbox))
            seed_items=[i for i in items if tuple(i.bbox) not in explained]
        seeds=[] if self.custom_matcher or shape_color else label_proposals(template,expected,seed_items,self.pdf.inspect(path)[page])
        proposals.extend(seeds)
        progress(50)
        status("Weryfikacja cech i geometrii kandydatów")
        reference=None
        learned_reference=None
        learned_recovered=0
        shape_recovered=0
        reference_cache={}
        verified=[];rejected=[]
        visible_cache={}
        for index,candidate in enumerate(proposals):
            if candidate.get('verified') and candidate.get('source','').startswith('native_'):
                from .symbol_sampling import verification_images
                from .feature_matcher import contour_evidence
                from .foreground import foreground_crop
                pose={**candidate,'raster_angle':-candidate.get('rotation',0)}
                key=(tuple(round(v,3) for v in candidate['rect']),candidate.get('rotation',0))
                if key not in visible_cache:
                    # Geometry bounds omit half the stroke. Include the observed
                    # stroke margin available inside the authoritative selection.
                    import numpy as np
                    sx,sy,sw,sh=template.get('selection_bbox',template['rect'])
                    rx,ry,rw,rh=template['rect']
                    left,top=max(sx,rx-.75),max(sy,ry-.75)
                    right,bottom=min(sx+sw,rx+rw+.75),min(sy+sh,ry+rh+.75)
                    ref_box=[left,top,right-left,bottom-top]
                    matrix=np.asarray(candidate['transform']).reshape(2,3)
                    corners=np.array([[left,top],[right,top],[left,bottom],[right,bottom]])@matrix[:,:2].T+matrix[:,2]
                    from .vector_engine import bbox
                    pose['verification_rect']=bbox(corners)
                    paint_template={**template,'raster_rect':ref_box}
                    transformed,patch,sampling,_=verification_images(
                        self.pdf,source,path,page,paint_template,pose,template_items,items,reference_cache)
                    from .feature_matcher import gray
                    visible_cache[key]=contour_evidence(foreground_crop(gray(transformed)),foreground_crop(gray(patch)))
                paint=visible_cache[key]
                candidate['visible_paint']={k:paint.get(k) for k in
                    ('contours_reference','contours_candidate','fill_consistent','reference_coverage')}
                if not paint.get('fill_consistent',True):
                    candidate.update(verified=False,verification_reason='visible_fill_variant_mismatch')
                elif paint.get('contours_reference')!=paint.get('contours_candidate'):
                    # A line crossing a device must continue through both
                    # outside margins; an internal variant cannot use this.
                    cx,cy,cw,ch=pose['verification_rect']
                    margin=4.;meta=self.pdf.inspect(path)[page]
                    confirmed=False
                    if cx>=margin and cy>=margin and cx+cw+margin<=meta['width'] and cy+ch+margin<=meta['height']:
                        context_box=[cx-margin,cy-margin,cw+2*margin,ch+2*margin]
                        outer=mask_text(self.pdf.render(path,page,sampling,context_box),items,context_box,sampling)
                        aligned=cv2.resize(transformed,(patch.shape[1],patch.shape[0]))
                        from .feature_matcher import NativePaintMatcher
                        evidence=NativePaintMatcher().verify_with_context(aligned,patch,outer,round(margin*sampling),width_fraction=.25)
                        confirmed=evidence.get('verification_reason')=='complete_symbol_with_external_crossing' and evidence.get('verified')
                    candidate['visible_paint_review']=not confirmed
            if "verified" not in candidate:
                from .symbol_sampling import verification_images
                transformed,patch,sampling,reference = verification_images(
                    self.pdf,source,path,page,template,candidate,template_items,items,reference_cache)
                candidate['verification_scale']=sampling
                evidence={'verified':False,'geometry_score':0.,'feature_score':0.} if candidate.get('recovery_only') else self.features.verify(transformed,patch)
                if (candidate.get('source')=='outline_geometry_probe' and template.get('analysis_signature')
                        and not evidence['verified']):
                    from .feature_matcher import contour_evidence
                    import numpy as np
                    colors={tuple(p.get('color',[])[:3]) for p in signature['paths']}
                    if len(colors)==1:
                        color=next(iter(colors))
                        if len(color)==3 and max(color)-min(color)>=45:
                            # Grey architecture may cross a coloured inscription.
                            # Compare observed coloured paint, retaining every
                            # interior mark and hole, without reconstructing ink.
                            rgb=patch.astype(np.int16)
                            keep=(rgb.max(axis=2)-rgb.min(axis=2)>=30)&(rgb.argmax(axis=2)==int(np.argmax(color)))
                            clean=patch.copy();clean[~keep]=255
                            paint=contour_evidence(transformed,clean)
                            if paint['verified']:
                                evidence={**paint,'verification_method':'outline_label_complete_paint',
                                    'verification_reason':'complete_coloured_symbol_and_independent_label'}
                            elif (paint.get('geometry_score',0)>=.70 and
                                    paint.get('reference_coverage',0)>=.70 and
                                    paint.get('foreground_ratio',0)>=.60 and
                                    paint.get('fill_consistent',False)):
                                # A legible code with substantial observed body
                                # support is useful to review, never an automatic quantity.
                                evidence={**paint,'verified':True,'verification_method':'outline_label_paint_review'}
                                candidate['outline_paint_review']=True
                if not evidence['verified'] and hasattr(self.features,'verify_with_context') and evidence.get('reference_coverage',0)>=.99 and evidence.get('fill_consistent',True):
                    x,y,w,h=candidate.get('verification_rect',candidate['rect'])
                    meta=self.pdf.inspect(path)[page]
                    if x>=4 and y>=4 and x+w+4<=meta['width'] and y+h+4<=meta['height']:
                        context_box=[x-4,y-4,w+8,h+8]
                        context=mask_text(self.pdf.render(path,page,sampling,context_box),items,context_box,sampling)
                        evidence=self.features.verify_with_context(transformed,patch,context,round(4*sampling))
                if self.fast and not evidence['verified'] and not candidate.get('recovery_only'):
                    from .foreground import shape_evidence
                    shape=shape_evidence(transformed,patch)
                    if shape:
                        # Foreground agreement can rescue a failed ORB gate,
                        # but only as a proposal for human review.
                        evidence={**evidence,'verified':True}
                        candidate.update(shape_recovery=True,foreground_shape_score=shape['geometry_score'],
                                         foreground_shape_details=shape)
                        shape_recovered+=1
                candidate.update(evidence)
                candidate["graphic_score"]=(candidate["score"]+evidence["feature_score"])/2
                if candidate.get('source') in ('label_geometry_probe','outline_geometry_probe') and evidence['verified']:
                    candidate['graphic_score']=(evidence['geometry_score']+evidence['feature_score'])/2
            if not candidate['verified'] and not self.custom_matcher and candidate.get('verification_reason')!='visible_fill_variant_mismatch':
                if reference is None:
                    reference=mask_text(self.pdf.render(source,template['page'],2.,template.get('raster_rect',template['rect'])),template_items,template.get('raster_rect',template['rect']),2.)
                partial=verify_partial(self.pdf,path,page,template,reference,candidate,items)
                if partial:candidate.update(partial)
            if self.learned_model and candidate.get('verification_reason')!='visible_fill_variant_mismatch' and (not candidate['verified'] or candidate.get('source') in ('raster','coarse_page')):
                # Small model can recover proposals rejected by image geometry,
                # but these are always review items, never automatic quantities.
                from .ai.learning_images import symbol_crop
                from .symbol_sampling import verification_images
                compatible=True
                if not candidate['verified']:
                    from .foreground import learned_pair_compatible
                    transformed,comparison_patch,_,_ = verification_images(
                        self.pdf,source,path,page,template,candidate,template_items,items,reference_cache)
                    compatible=learned_pair_compatible(transformed,comparison_patch)
                if compatible:
                    if learned_reference is None:
                        ref_box=template.get('raster_rect',template['rect'])
                        learned_reference=symbol_crop(self.pdf,source,template['page'],ref_box,template_items)
                    patch=symbol_crop(self.pdf,path,page,candidate['rect'],items)
                    probability=self.learned_model.score(learned_reference,patch)
                    candidate['learned_score']=probability
                    if not candidate['verified'] and probability>=self.learned_model.metadata.get('threshold',.9):
                        candidate.update(verified=True,learned_recovery=True,
                                         verification_method='learned_pair_review')
                        learned_recovered+=1
                else:
                    candidate['learned_skip_reason']='different_visual_structure'
            if candidate["verified"]:
                verified.append(candidate)
            else:
                rejected.append({k:candidate.get(k) for k in
                    ("rect","template_score","feature_score","geometry_score","verification_method","verification_reason")}|{'status':'REJECTED',
                        'reason':candidate.get('verification_reason','geometry_not_verified'),
                        'signals':{'visual_ai_score':None,'color_score':None,'text_score':None,
                            'geometry_score':candidate.get('geometry_score'),'feature_score':candidate.get('feature_score')},
                        'unevaluated_reason':'failed_geometry_gate'})
            progress(50+round(35*(index+1)/max(1,len(proposals))))
        # Symmetric shapes permit several rotations. Resolve the orientation
        # with spatial text evidence, without favoring the requested code.
        text_index=TextSpatialIndex(items)
        ocr=None

        for candidate in verified:
            if shape_color:
                candidate['association_result']={'item':None,'score':0.,'reason':'shape_color_mode','associated_texts':[]}
                continue
            layout=None if template.get('source')=='LEGEND' else template.get('association')
            options=[self.text.associate(candidate['rect'],text_index,
                transformed_layout(layout,candidate.get('rotation',0),candidate.get('scale',1)))]
            if layout and candidate.get('rotation',0)%360:
                # Text may stay horizontal while the device rotates. Neither option
                # gets any knowledge of the requested label.
                options.append(self.text.associate(candidate['rect'],text_index,transformed_layout(layout,0,candidate.get('scale',1))))
            options.sort(key=lambda a:(a['item'] is not None,a['score']),reverse=True)
            chosen=options[0]
            if len(options)>1 and all(a['item'] for a in options) and options[0]['item'].normalized_text!=options[1]['item'].normalized_text and abs(options[0]['score']-options[1]['score'])<.10:
                chosen={**chosen,'item':None,'reason':'ambiguous_label'}
            candidate['association_result']=chosen
        # Learn repeated layout from unambiguous neighbors on this page, never
        # from the requested label. Legend typography/rotation is often different.
        if template.get('source')=='LEGEND' and not shape_color:
            from .text_layout import resolve_repeated_layout
            resolve_repeated_layout(verified,self.text,text_index)
        candidates=[]
        for candidate in sorted(verified,key=lambda c:(not c.get("partial_occlusion",False),c["geometry_score"]+c["feature_score"]+
                .2*c["association_result"]["score"]),reverse=True):
            if not any(overlap_metrics(candidate["rect"],other["rect"])[0]>.4 for other in candidates):
                candidates.append(candidate)
        # Resolve geometric duplicates before expensive OCR. OCR is independent
        # of DINOv2; exact native associations never get overwritten.
        if not shape_color and not self.custom_matcher and any(not c['association_result']['item'] for c in candidates):
            from .ocr_engine import OCREngine
            ocr=OCREngine()
            status('OCR: sprawdzanie kandydatów bez tekstu PDF')
            for candidate in candidates:
                if candidate['association_result']['item']:continue
                recognized=ocr.read_region(self.pdf,path,page,candidate['rect'],text_index.near(candidate['rect'],80))
                if recognized:
                    layout=None if template.get('source')=='LEGEND' else transformed_layout(template.get('association'),candidate.get('rotation',0),candidate.get('scale',1))
                    candidate['association_result']=self.text.associate(candidate['rect'],recognized,layout)
        result={"matches":[],"review":[],"discovered_other_label":[],"label":expected,
                "template":template,"coverage_warnings":warnings,"text_items":[i.to_dict() for i in items],
                "rejected_candidates":rejected,
                "stages":{"occlusion_label_probes":len(seeds),"partial_occlusion_candidates":sum(bool(c.get("partial_occlusion")) for c in candidates),"generated":len(proposals),"verified":len(candidates),"rejected":len(rejected),
                          "ai_retrieval":retrieval_stats,"learned_recovered":learned_recovered,"shape_recovered":shape_recovered,"vector_first":bool(signature and vectors),"raster_used":use_raster,
                          "vector_limit_reached":bool(vectors and vectors.get("truncated")),"native_local":native_stats}}
        progress(85)
        status("Łączenie symboli z oznaczeniami tekstowymi")
        associations=[c["association_result"] for c in candidates]
        owners=Counter(tuple(a["item"].bbox) for a in associations if a["item"])
        from .color_features import color_signature, color_similarity
        from .final_decision import FinalDecisionEngine
        from .template_representation import build_representation
        if not template.get('representation',{}).get('original_rgb_crop'):
            template['representation']=build_representation(self.pdf,source,template['page'],template)
        reference_color=template['representation']['color_signature']
        if shape_color and signature:
            colors=[tuple(p.get('color',[])[:3]) for p in signature['paths']
                    if len(p.get('color',[]))>=3 and min(p['color'][:3])<245]
            if colors:
                reference_color={**reference_color,'foreground_color':list(Counter(colors).most_common(1)[0][0])}
        reference_embedding=None
        if self.encoder:
            from dataclasses import asdict
            reference_embedding=self.encoder.encode(reference_image)
            template['representation']['visual_embedding']=asdict(reference_embedding)
            template['representation']['visual_features'].update(embedding=template['representation']['visual_embedding'])
        if self.encoder:status('Analiza AI i koloru: ocena podobieństwa kandydatów')
        from .electrical_profile import build_profile,compare_profiles,display_label
        peer_rects=[c['rect'] for c in candidates]
        expected_profile=template.get('electrical_profile',{})
        for hit_index,(candidate,association) in enumerate(zip(candidates,associations)):
            progress(85+round(14*(hit_index+1)/max(1,len(candidates))))
            item=association["item"]
            if item and owners[tuple(item.bbox)]>1:
                item=None
                association={**association,"reason":"shared_label"}
            actual=item.normalized_text if item else ""
            exact=bool(expected and actual==expected)
            spatial=association["score"]
            graphic=candidate["graphic_score"]
            feature=candidate["feature_score"];geometry=candidate["geometry_score"]
            confidence=(.20*graphic+.20*feature+.25*geometry+.25*int(exact)+.10*spatial) if expected else .30*graphic+.30*feature+.40*geometry
            hit={"rect":candidate["rect"],"graphic_score":graphic,
                 "template_score":candidate.get("template_score"),"feature_score":feature,"geometry_score":geometry,
                 "text_score":1.0 if exact else 0.0,"spatial_association_score":spatial,"confidence":confidence,
                 "label":actual,"label_bbox":item.bbox if item else None,"reason":association["reason"],
                 "verification_method":candidate.get("verification_method","custom"),
                 "verification_details":{k:candidate.get(k) for k in ("inliers","feature_matches","inlier_coverage",
                    "transform","scale","rotation","verification_reason","chamfer_error")},
                 "candidate_source":candidate.get("source","custom")}
            crop_box=candidate.get('verification_rect',candidate['rect'])
            cx,cy,cw,ch=crop_box
            if min(cw,ch)<3:
                meta=self.pdf.inspect(path)[page];left,top=max(0,cx-3),max(0,cy-3)
                crop_box=[left,top,min(meta['width'],cx+cw+3)-left,min(meta['height'],cy+ch+3)-top]
            candidate_color=candidate.get('color_signature')
            if candidate_color is None or self.encoder:
                patch=mask_text(self.pdf.render(path,page,2.,crop_box),items,crop_box,2.)
                if candidate_color is None:candidate_color=color_signature(patch)
            if strict_color and not color_matches(reference_color,candidate_color):
                result['rejected_candidates'].append({'rect':candidate['rect'],'status':'REJECTED','reason':'different_foreground_color'})
                continue
            visual=None
            if self.encoder:
                from .ai.visual_encoder import cosine
                import numpy as np
                angle=candidate.get('rotation',0)
                aligned=np.rot90(patch,int(round(angle/90))%4).copy() if abs(angle/90-round(angle/90))<.03 else patch
                visual=cosine(reference_embedding,self.encoder.encode(aligned))
            signals={'visual_ai_score':visual,'embedding_score':visual,'geometry_score':geometry,
                'feature_score':feature,'color_score':color_similarity(reference_color,candidate_color),
                'device_label_score':(float(exact) if expected else None),
                'text_score':(float(exact) if expected else None),
                'text_role_confidence':association.get('text_role_confidence',0),
                'spatial_text_score':spatial,'spatial_association_score':spatial}
            if item and item.source in ('ocr','pdf_outline'):
                signals['text_score']=signals['device_label_score']=item.confidence if exact else 0.
            signals.update(shape_score=graphic,visual_score=visual,label_score=signals['device_label_score'],text_association_score=spatial)
            state,confidence,decision_reason=FinalDecisionEngine().decide(expected,actual,signals)
            candidate_profile=build_profile(candidate['rect'],
                text_index.near(candidate['rect'],max(12.,max(candidate['rect'][2:])*.75))+
                association.get('associated_texts',[]),peer_rects)
            profile_state,profile_reason=compare_profiles(expected_profile,candidate_profile)
            if state=='MATCH' and profile_state!='MATCH':
                state,decision_reason=profile_state,profile_reason
            hit['verification_details']['electrical_profile']=candidate_profile
            if candidate.get('learned_score') is not None:
                hit['verification_details']['learned_pair_score']=candidate['learned_score']
            hit['verification_details']['expected_electrical_profile']=expected_profile
            if profile_state=='OTHER_VARIANT':
                hit['label']=display_label(actual,candidate_profile) or actual
            if item and item.source in ('ocr','pdf_outline') and item.confidence<.95 and state=='MATCH':
                state,decision_reason='REVIEW','uncertain_ocr_label'
            if candidate.get('partial_occlusion') and state!='OTHER_VARIANT':
                state,decision_reason='REVIEW','partial_occlusion_review'
            if candidate.get('visible_paint_review') and state!='OTHER_VARIANT':
                state,decision_reason='REVIEW','visible_paint_needs_review'
            if candidate.get('outline_paint_review') and state!='OTHER_VARIANT':
                state,decision_reason='REVIEW','outlined_code_graphic_needs_review'
            if candidate.get('visible_paint'):
                hit['verification_details']['visible_paint']=candidate['visible_paint']
            if candidate.get('learned_recovery') and state!='OTHER_VARIANT':
                state,decision_reason='REVIEW','learned_pair_review'
            if candidate.get('shape_recovery'):
                hit['verification_details']['foreground_shape']=candidate['foreground_shape_details']
                signals['foreground_shape_score']=candidate['foreground_shape_score']
                if state!='OTHER_VARIANT':state,decision_reason='REVIEW','shape_similarity_review'
            if candidate.get('occlusion'):hit['verification_details']['occlusion']=candidate['occlusion']
            hit['text_source']=item.source if item else None
            hit.update(shape_score=graphic,visual_score=visual,label_score=signals['device_label_score'],text_association_score=spatial)
            hit['verification_details'].update(text_source=hit['text_source'],label_rotation=item.rotation if item else None,decision=state)
            hit.update(signals=signals,confidence=confidence,color_score=signals['color_score'],
                visual_ai_score=visual,status=state,text_role='DEVICE_LABEL' if actual else 'UNKNOWN',
                text_role_confidence=signals['text_role_confidence'])
            if candidate.get('learned_score') is not None:
                hit['signals']['learned_pair_score']=candidate['learned_score']
            hit['verification_details'].update(associated_texts=association.get('associated_texts',[]),
                color_signature=candidate_color,final_decision_reason=decision_reason)
            if state=='MATCH':
                if not expected:hit['reason']='unlabelled_symbol_geometry_verified'
                result['matches'].append(hit)
            elif state=='OTHER_VARIANT':
                hit['reason']='different_label' if decision_reason=='different_device_label' else decision_reason
                result['discovered_other_label'].append(hit)
            else:
                hit['reason']=association['reason'] if association['reason']=='shared_label' else decision_reason
                result['review'].append(hit)
        from .document_regions import region_for
        regions=list(native_stats.get('regions',[]))
        if native_stats.get('annotation_frames'):
            from .document_regions import confirmed_reference_panels
            status('Sprawdzanie legend i przykładów w uwagach')
            try:
                regions.extend(confirmed_reference_panels(self.pdf,path,page,items,native_stats['annotation_frames'],result['matches']))
            except (RuntimeError,ImportError,OSError) as exc:
                warnings.append('Nie udało się sprawdzić opisów ramek z uwagami: '+str(exc))
        result['legend_matches']=[]
        countable=[]
        for hit in result['matches']:
            region=region_for(hit['rect'],regions)
            is_source=template.get('source')=='LEGEND' and source==path and page==template['page'] and overlap_metrics(hit['rect'],template['rect'])[0]>.5
            if region or is_source:
                result['legend_matches'].append({**hit,'status':'SOURCE_TEMPLATE' if is_source else 'LEGEND_REFERENCE','reason':'annotation_reference' if region and region.get('kind')=='reference_panel' else 'legend_reference','region':region['rect'] if region else template['rect']})
            else:countable.append(hit)
        result['occlusion_excluded_references']=[]
        for hit in list(result['review']):
            if not hit['verification_details'].get('occlusion'):continue
            region=region_for(hit['rect'],regions)
            is_source=template.get('source')=='LEGEND' and source==path and page==template['page'] and overlap_metrics(hit['rect'],template['rect'])[0]>.5
            if region or is_source:
                result['review'].remove(hit)
                result['occlusion_excluded_references'].append(hit)
        result['matches']=countable
        result['counts']={'raw_matches':len(countable)+len(result['legend_matches']),
            'legend_matches':len(result['legend_matches']),'countable_devices':len(countable)}
        result['regions']=regions
        result['template']=original_template
        if len(countable)<=1:
            warnings.append("Znaleziono co najwyżej jeden element. Sprawdź wycinek wzorca, oznaczenie i zakres stron; wynik nie potwierdza kompletności zliczania.")
        status("Kończenie analizy strony")
        progress(100)
        return result


def color_matches(reference,candidate,tolerance=40):
    """Explicit shape/color mode keeps gray architecture out of black symbols."""
    import numpy as np
    a=reference.get('foreground_color');b=candidate.get('foreground_color')
    return a is not None and b is not None and float(np.max(np.abs(np.asarray(a,float)-np.asarray(b,float))))<=tolerance
