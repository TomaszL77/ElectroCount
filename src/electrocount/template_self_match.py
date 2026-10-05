"""Bounded source-location check; never insert a synthetic detection."""
import cv2
from .domain import overlap_metrics
from .feature_matcher import OpenCVFeatureMatcher
from .matcher import TemplateMatcher, template_variant
from .text_engine import mask_text
from .vector_engine import VectorCandidateGenerator


def validate_self_match(pdf,path,page,template):
    """Diagnostic only: matcher limitations must not discard a valid RGB selection."""
    try:
        _validate_self_match(pdf,path,page,template)
    except (ValueError, RuntimeError, AttributeError, cv2.error) as exc:
        template['self_check']=False
        template['self_match']={'passed':False,'method':'local_search','error':str(exc)}
    if not template['self_check']:
        template['preparation_warnings']=list(template.get('preparation_warnings',[]))
        warning='Zapisano dokładne zaznaczenie. Test rozpoznawania źródła nie powiódł się — sprawdź wyniki wyszukiwania.'
        if warning not in template['preparation_warnings']:
            template['preparation_warnings'].append(warning)
    return template['self_match']


def _validate_self_match(pdf,path,page,template):
    signature=template.get('signature')
    items=pdf.extract_text(path,page)
    if signature and hasattr(pdf,'open_vector_page'):
        with pdf.open_vector_page(path,page) as native:
            actual=native.template_signature(template['selection_bbox'],items)
        candidates=VectorCandidateGenerator().find(signature,{'paths':actual['paths']}) if actual else []
        matched=any(c.get('verified') and overlap_metrics(c['rect'],signature['bbox'])[0]>.95
                    for c in candidates)
        method='local_vector_search'
    else:
        box=template['matching_bbox']
        reference=mask_text(pdf.render(path,page,2.,box),items,box,2.)
        candidates=TemplateMatcher().find(pdf,path,page,template,.82,
            text_items=items,template_items=items,search_regions=[box])
        matched=False
        for candidate in candidates:
            if overlap_metrics(candidate['rect'],template['rect'])[0]<.90:continue
            patch_box=candidate.get('verification_rect',candidate['rect'])
            patch=mask_text(pdf.render(path,page,2.,patch_box),items,patch_box,2.)
            transformed=template_variant(cv2.cvtColor(reference,cv2.COLOR_RGB2GRAY),
                candidate.get('scale',1),candidate.get('raster_angle',0))
            if OpenCVFeatureMatcher().verify(transformed,patch)['verified']:
                matched=True;break
        method='local_raster_search'
    template['self_check']=matched
    template['self_match']={'passed':matched,'method':method}
