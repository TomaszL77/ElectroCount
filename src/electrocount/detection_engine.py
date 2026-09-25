"""Detection V2: proposals -> feature evidence -> geometry gate -> text -> confidence."""
from collections import Counter
import cv2
from .text_engine import TextEngine, normalize_text, prepare_template, mask_text, transformed_layout, TextSpatialIndex
from .matcher import TemplateMatcher, template_variant
from .feature_matcher import OpenCVFeatureMatcher
from .vector_engine import VectorCandidateGenerator, signature_in_rect
from .domain import overlap_metrics


class DetectionEngine:
    def __init__(self,pdf_engine,matcher=None,text_engine=None,feature_matcher=None,visual_encoder=None):
        self.encoder=visual_encoder
        self.pdf=pdf_engine
        self.matcher=matcher or TemplateMatcher()
        self.custom_matcher=matcher is not None
        self.text=text_engine or TextEngine()
        self.features=feature_matcher or OpenCVFeatureMatcher()

    def find(self,path,page,template,label="",threshold=.82,progress=lambda p:None,template_path=None,status=lambda text:None):
        status("Odczyt tekstu i przygotowanie wzorca")
        source=template_path or path
        if not template.get("text_aware") or (template.get("definition_version",0)<8 and
                template.get("selection_rect") and hasattr(self.pdf,"open_vector_page")):
            template=prepare_template(self.pdf,source,template["page"],template.get("selection_rect",template["rect"]))
        expected=normalize_text(label or template.get("label",""))
        items=self.pdf.extract_text(path,page)
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
            if not signature:
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
        if self.encoder:
            from .ai.retrieval import VisualRetrieval
            status('Analiza AI: przeszukiwanie wszystkich kafelków strony')
            reference_image=mask_text(self.pdf.render(source,template['page'],2.,template.get('raster_rect',template['rect'])),
                template_items,template.get('raster_rect',template['rect']),2.)
            recovered,retrieval_stats=VisualRetrieval(self.encoder).find(self.pdf,path,page,template,reference_image,items,
                lambda p:progress(30+round(p*.2)))
            proposals.extend(recovered)
        progress(50)
        status("Weryfikacja cech i geometrii kandydatów")
        reference=None
        verified=[];rejected=[]
        for index,candidate in enumerate(proposals):
            if "verified" not in candidate:
                if reference is None:
                    reference=mask_text(self.pdf.render(source,template["page"],2.0,template.get("raster_rect",template["rect"])),
                                        template_items,template.get("raster_rect",template["rect"]),2.0)
                transformed=template_variant(cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY),
                    candidate.get("scale",1),candidate.get("raster_angle",candidate.get("rotation",0)))
                patch=mask_text(self.pdf.render(path,page,2.0,candidate.get("verification_rect",candidate["rect"])),items,candidate.get("verification_rect",candidate["rect"]),2.0)
                evidence=self.features.verify(transformed,patch)
                if not evidence['verified'] and hasattr(self.features,'verify_with_context') and evidence.get('reference_coverage',0)>=.99 and evidence.get('fill_consistent',True):
                    x,y,w,h=candidate.get('verification_rect',candidate['rect'])
                    meta=self.pdf.inspect(path)[page]
                    if x>=4 and y>=4 and x+w+4<=meta['width'] and y+h+4<=meta['height']:
                        context_box=[x-4,y-4,w+8,h+8]
                        context=mask_text(self.pdf.render(path,page,2.,context_box),items,context_box,2.)
                        evidence=self.features.verify_with_context(transformed,patch,context,8)
                candidate.update(evidence)
                candidate["graphic_score"]=(candidate["score"]+evidence["feature_score"])/2
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
        if self.encoder:
            from .ocr_engine import OCREngine
            ocr=OCREngine()
        for candidate in verified:
            candidate["association_result"]=self.text.associate(candidate["rect"],text_index,
                None if template.get("source")=="LEGEND" else transformed_layout(template.get("association"),candidate.get("rotation",0),candidate.get("scale",1)))
        # Learn repeated layout from unambiguous neighbors on this page, never
        # from the requested label. Legend typography/rotation is often different.
        if template.get('source')=='LEGEND':
            from .text_layout import resolve_repeated_layout
            resolve_repeated_layout(verified,self.text,text_index)
        if ocr:
            status('OCR: sprawdzanie kandydatów bez tekstu PDF')
            for candidate in verified:
                if not candidate['association_result']['item']:
                    recognized=ocr.read_region(self.pdf,path,page,candidate['rect'],text_index.near(candidate['rect'],80))
                    if recognized:
                        candidate['association_result']=self.text.associate(candidate['rect'],recognized)
        candidates=[]
        for candidate in sorted(verified,key=lambda c:(c["geometry_score"]+c["feature_score"]+
                .2*c["association_result"]["score"]),reverse=True):
            if not any(overlap_metrics(candidate["rect"],other["rect"])[0]>.4 for other in candidates):
                candidates.append(candidate)
        result={"matches":[],"review":[],"discovered_other_label":[],"label":expected,
                "template":template,"coverage_warnings":warnings,"text_items":[i.to_dict() for i in items],
                "rejected_candidates":rejected,
                "stages":{"generated":len(proposals),"verified":len(candidates),"rejected":len(rejected),
                          "ai_retrieval":retrieval_stats,"vector_first":bool(signature and vectors),"raster_used":use_raster,
                          "vector_limit_reached":bool(vectors and vectors.get("truncated")),"native_local":native_stats}}
        progress(85)
        status("Łączenie symboli z oznaczeniami tekstowymi")
        associations=[c["association_result"] for c in candidates]
        owners=Counter(tuple(a["item"].bbox) for a in associations if a["item"])
        from .color_features import color_signature, color_similarity
        from .final_decision import FinalDecisionEngine
        from .template_representation import build_representation
        if not template.get('representation'):
            template['representation']=build_representation(self.pdf,source,template['page'],template)
        reference_color=template['representation']['color_signature']
        reference_embedding=None
        if self.encoder:
            from dataclasses import asdict
            reference_embedding=self.encoder.encode(reference_image)
            template['representation']['visual_embedding']=asdict(reference_embedding)
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
            if item and item.source=='ocr':
                signals['text_score']=signals['device_label_score']=item.confidence if exact else 0.
            state,confidence,decision_reason=FinalDecisionEngine().decide(expected,actual,signals)
            candidate_profile=build_profile(candidate['rect'],
                text_index.near(candidate['rect'],max(12.,max(candidate['rect'][2:])*.75))+
                association.get('associated_texts',[]),peer_rects)
            profile_state,profile_reason=compare_profiles(expected_profile,candidate_profile)
            if state=='MATCH' and profile_state!='MATCH':
                state,decision_reason=profile_state,profile_reason
            hit['verification_details']['electrical_profile']=candidate_profile
            hit['verification_details']['expected_electrical_profile']=expected_profile
            if profile_state=='OTHER_VARIANT':
                hit['label']=display_label(actual,candidate_profile) or actual
            if item and item.source=='ocr' and item.confidence<.95 and state=='MATCH':
                state,decision_reason='REVIEW','uncertain_ocr_label'
            hit['text_source']=item.source if item else None
            hit.update(signals=signals,confidence=confidence,color_score=signals['color_score'],
                visual_ai_score=visual,status=state,text_role='DEVICE_LABEL' if actual else 'UNKNOWN',
                text_role_confidence=signals['text_role_confidence'])
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
        result['matches']=countable
        result['counts']={'raw_matches':len(countable)+len(result['legend_matches']),
            'legend_matches':len(result['legend_matches']),'countable_devices':len(countable)}
        result['regions']=regions
        if len(countable)<=1:
            warnings.append("Znaleziono co najwyżej jeden element. Sprawdź wycinek wzorca, oznaczenie i zakres stron; wynik nie potwierdza kompletności zliczania.")
        status("Kończenie analizy strony")
        progress(100)
        return result

