"""Detection V2: proposals -> feature evidence -> geometry gate -> text -> confidence."""
from collections import Counter
import cv2
from .text_engine import TextEngine, normalize_text, prepare_template, mask_text, transformed_layout, TextSpatialIndex
from .matcher import TemplateMatcher, template_variant
from .feature_matcher import OpenCVFeatureMatcher
from .vector_engine import VectorCandidateGenerator, signature_in_rect
from .domain import overlap_metrics


class DetectionEngine:
    def __init__(self,pdf_engine,matcher=None,text_engine=None,feature_matcher=None):
        self.pdf=pdf_engine
        self.matcher=matcher or TemplateMatcher()
        self.custom_matcher=matcher is not None
        self.text=text_engine or TextEngine()
        self.features=feature_matcher or OpenCVFeatureMatcher()

    def find(self,path,page,template,label="",threshold=.82,progress=lambda p:None,template_path=None,status=lambda text:None):
        status("Odczyt tekstu i przygotowanie wzorca")
        source=template_path or path
        if not template.get("text_aware") or (template.get("definition_version",0)<3 and
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
            with self.pdf.open_vector_page(path,page) as native:
                found,native_stats=native.find(signature,items,expected,lambda p:progress(10+round(p*.20)))
                proposals.extend(found)
            vectors={"has_images":native_stats["has_images"],"unsupported":int(native_stats["truncated"] or native_stats["limited_queries"] or native_stats["clipped_anchor_paths"]),
                     "truncated":native_stats["truncated"]}
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
                proposals.extend(self.matcher.find(self.pdf,path,page,template,threshold,
                    lambda p:progress(30+round(p*.20)),text_items=items,
                    template_items=template_items,template_path=source))
            except ValueError as exc:
                if not native_stats or not proposals:raise
                warnings.append("Analiza obrazu niepełna: "+str(exc))
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
                candidate.update(evidence)
                candidate["graphic_score"]=(candidate["score"]+evidence["feature_score"])/2
            if candidate["verified"]:
                verified.append(candidate)
            else:
                rejected.append({k:candidate.get(k) for k in
                    ("rect","template_score","feature_score","geometry_score","verification_method","verification_reason")})
            progress(50+round(35*(index+1)/max(1,len(proposals))))
        # Symmetric shapes permit several rotations. Resolve the orientation
        # with spatial text evidence, without favoring the requested code.
        text_index=TextSpatialIndex(items)
        for candidate in verified:
            candidate["association_result"]=self.text.associate(candidate["rect"],text_index,
                transformed_layout(template.get("association"),candidate.get("rotation",0),candidate.get("scale",1)))
        candidates=[]
        for candidate in sorted(verified,key=lambda c:(c["geometry_score"]+c["feature_score"]+
                .2*c["association_result"]["score"]),reverse=True):
            if not any(overlap_metrics(candidate["rect"],other["rect"])[0]>.4 for other in candidates):
                candidates.append(candidate)
        result={"matches":[],"review":[],"discovered_other_label":[],"label":expected,
                "template":template,"coverage_warnings":warnings,"text_items":[i.to_dict() for i in items],
                "rejected_candidates":rejected[:500],
                "stages":{"generated":len(proposals),"verified":len(candidates),"rejected":len(rejected),
                          "vector_first":bool(signature and vectors),"raster_used":use_raster,
                          "vector_limit_reached":bool(vectors and vectors.get("truncated")),"native_local":native_stats}}
        progress(85)
        status("Łączenie symboli z oznaczeniami tekstowymi")
        associations=[c["association_result"] for c in candidates]
        owners=Counter(tuple(a["item"].bbox) for a in associations if a["item"])
        for candidate,association in zip(candidates,associations):
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
            if not expected:
                hit["reason"]="unlabelled_symbol_geometry_verified"
                result["matches"].append(hit)
            elif not actual:
                result["review"].append(hit)
            elif exact:
                result["matches"].append(hit)
            else:
                hit["reason"]="different_label"
                result["discovered_other_label"].append(hit)
        status("Kończenie analizy strony")
        progress(100)
        return result

