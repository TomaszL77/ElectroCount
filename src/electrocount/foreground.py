"""Keep every selected stroke; exclude exterior paper from image comparisons."""
import cv2
import numpy as np
import math


def ink_mask(image):
    return (np.min(image[:, :, :3], axis=2) if image.ndim == 3 else image) < 245


def foreground_crop(image):
    """Trim only empty exterior margins, without stretching or selecting parts."""
    if not image.size:return image.copy()
    ys, xs = np.where(ink_mask(image))
    if not len(xs):return image.copy()
    return image[ys.min():ys.max()+1, xs.min():xs.max()+1].copy()


def matching_mask(image):
    # Enclosed white areas belong to a shape (e.g. hollow vs filled symbols).
    # Only white connected to the exterior is background to be ignored.
    white=(~ink_mask(image)).astype(np.uint8)
    _, labels=cv2.connectedComponents(white, connectivity=4)
    border=np.unique(np.r_[labels[0], labels[-1], labels[:,0], labels[:,-1]])
    exterior=np.isin(labels,border[border!=0])
    return (~exterior).astype(np.uint8)


def matching_scores(image, pattern):
    page=(255-image.astype(np.float32))/255
    template=(255-pattern.astype(np.float32))/255
    scores=cv2.matchTemplate(page,template,cv2.TM_CCORR_NORMED,mask=matching_mask(pattern))
    return np.clip(np.nan_to_num(scores,nan=0.,posinf=0.,neginf=0.),0.,1.)


def graphic_box(image, sample, render_scale):
    ys,xs=np.where(ink_mask(image))
    if not len(xs):return list(sample)
    return [sample[0]+float(xs.min())/render_scale,sample[1]+float(ys.min())/render_scale,
            float(xs.max()+1-xs.min())/render_scale,float(ys.max()+1-ys.min())/render_scale]


def placed_symbol_rect(symbol, sample, patch, size, angle):
    """Preserve off-centre symbol placement through scale and rotation."""
    sx,sy,sw,sh=symbol; bx,by,bw,bh=sample
    radians=math.radians(angle);co,si=math.cos(radians),math.sin(radians)
    corners=np.array([[sx-bx,sy-by],[sx-bx+sw,sy-by],
                      [sx-bx,sy-by+sh],[sx-bx+sw,sy-by+sh]])*size
    rotated=corners@np.array([[co,-si],[si,co]])
    canvas=np.array([[0,0],[bw,0],[0,bh],[bw,bh]])*size@np.array([[co,-si],[si,co]])
    offset=rotated.min(axis=0)-canvas.min(axis=0)
    offset+=(np.array(patch[2:])-np.ptp(canvas,axis=0))/2
    dims=np.ptp(rotated,axis=0)
    return [patch[0]+float(offset[0]),patch[1]+float(offset[1]),float(dims[0]),float(dims[1])]


def transparent_selection(image):
    rgba=np.dstack((image[:,:,:3],np.where(ink_mask(image),255,0).astype(np.uint8)))
    return rgba


def shape_evidence(reference, candidate):
    from .feature_matcher import contour_evidence
    ys,xs=np.where(ink_mask(reference))
    if not len(xs):return None
    # Ignore candidate ink in the reference's exterior paper too. Preserve
    # everything inside the selected graphic's bounds, including extra strokes.
    left,top,right,bottom=xs.min(),ys.min(),xs.max()+1,ys.max()+1
    sy,sx=candidate.shape[0]/reference.shape[0],candidate.shape[1]/reference.shape[1]
    a=foreground_crop(reference[top:bottom,left:right])
    aligned=foreground_crop(candidate[int(top*sy):max(int(top*sy)+1,round(bottom*sy)),
                                      int(left*sx):max(int(left*sx)+1,round(right*sx))])
    # Native proposals may already be tight symbol boxes, whereas raster
    # proposals carry the full selection. Check each without changing its pose.
    accepted=[]
    for b in (aligned,foreground_crop(candidate)):
        if min(a.shape[:2]+b.shape[:2])<2 or not ink_mask(a).any() or not ink_mask(b).any():continue
        ar,br=a.shape[1]/a.shape[0],b.shape[1]/b.shape[0]
        if max(ar,br)/min(ar,br)>1.2:continue
        evidence=contour_evidence(a,b)
        if (evidence.get('geometry_score',0)>=.90 and evidence.get('feature_score',0)>=.78
                and evidence.get('reference_coverage',0)>=.85 and evidence.get('fill_consistent',False)):
            accepted.append(evidence)
    return max(accepted,key=lambda e:e['geometry_score']) if accepted else None


def learned_pair_compatible(reference, candidate):
    """A pair score may recover an ORB failure, never a visibly different body."""
    from .feature_matcher import contour_evidence
    a,b=foreground_crop(reference),foreground_crop(candidate)
    if min(a.shape[:2]+b.shape[:2])<2:return False
    if not ink_mask(a).any() or not ink_mask(b).any():return False
    ar,br=a.shape[1]/a.shape[0],b.shape[1]/b.shape[0]
    if max(ar,br)/min(ar,br)>1.2:return False
    evidence=contour_evidence(a,b)
    return (evidence.get('geometry_score',0)>=.70
        and evidence.get('feature_score',0)>=.60
        and evidence.get('foreground_ratio',0)>=.60
        and evidence.get('reference_coverage',0)>=.70
        and evidence.get('fill_consistent',False))
