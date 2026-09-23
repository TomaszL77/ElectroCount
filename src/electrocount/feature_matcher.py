"""Offline feature verification and a learned-matcher extension point."""
from typing import Protocol
from .ai.contracts import IFeatureMatcher
import math
import cv2
import numpy as np


class ISymbolMatcher(Protocol):
    def find(self, engine, path, page, template, threshold, progress, **kwargs): ...


FeatureMatcher = IFeatureMatcher  # Backwards-compatible public name.


def gray(image):
    return cv2.cvtColor(image,cv2.COLOR_RGB2GRAY) if image.ndim==3 else image


def fit_image(image):
    image=gray(image)
    scale=220/max(image.shape)
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(image,18,18,18,18,cv2.BORDER_CONSTANT,value=255)


def contour_evidence(reference,candidate):
    a=fit_image(reference);b=fit_image(candidate)
    if a.shape!=b.shape:
        b=cv2.resize(b,(a.shape[1],a.shape[0]))
    masks=[(cv2.GaussianBlur(image,(3,3),0)<190).astype(np.uint8) for image in (a,b)]
    if any(m.sum()<12 for m in masks):
        return {"feature_score":0.0,"geometry_score":0.0,"verified":False,"verification_reason":"empty_graphic"}
    distances=[cv2.distanceTransform(1-m,cv2.DIST_L2,3) for m in masks]
    error=(float(distances[1][masks[0]>0].mean())+float(distances[0][masks[1]>0].mean()))/2
    reference_coverage=float(np.mean(distances[1][masks[0]>0]<=1.0))
    structures=[];void_masks=[]
    for m in masks:
        contours,hierarchy=cv2.findContours(m,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        significant=[i for i,c in enumerate(contours) if cv2.contourArea(c)>20]
        roots=sum(hierarchy[0][i][3]<0 for i in significant) if hierarchy is not None else 0
        holes=sum(hierarchy[0][i][3]>=0 for i in significant) if hierarchy is not None else 0
        structures.append((roots,holes))
        voids=[]
        for i in significant:
            if hierarchy[0][i][3]<0:continue
            hole=np.zeros_like(m);cv2.drawContours(hole,contours,i,1,-1)
            hole=cv2.erode(hole,np.ones((5,5),np.uint8))
            if hole.sum()>=20:voids.append(hole.astype(bool))
        void_masks.append(voids)
    density=min(float(masks[0].sum()),float(masks[1].sum()))/max(float(masks[0].sum()),float(masks[1].sum()))
    fill_consistent=not any(float(masks[1-side][hole].mean())>.85
        for side in (0,1) for hole in void_masks[side])
    feature=density if structures[0]==structures[1] else density*.35
    geometry=math.exp(-error/2.0)
    return {"feature_score":feature,"geometry_score":geometry,
            "verified":feature>=.78 and geometry>=.82 and fill_consistent,
            "verification_reason":"fill_variant_mismatch" if not fill_consistent else "contour_consistent" if feature>=.78 and geometry>=.82 else "contour_mismatch",
            "reference_coverage":reference_coverage,"foreground_ratio":density,"fill_consistent":fill_consistent,
            "contours_reference":structures[0],"contours_candidate":structures[1],"chamfer_error":error}


def geometric_verification(points0,points1,shape):
    if len(points0)<6:
        return {"verified":False,"geometry_score":0.0,"inliers":0,"feature_matches":len(points0),
                "verification_reason":"insufficient_features"}
    p0=np.asarray(points0,np.float32);p1=np.asarray(points1,np.float32)
    affine,inliers=cv2.estimateAffinePartial2D(p0,p1,method=cv2.RANSAC,ransacReprojThreshold=3,
                                             maxIters=2000,confidence=.995)
    if affine is None or inliers is None:
        return {"verified":False,"geometry_score":0.0,"inliers":0,"feature_matches":len(p0),
                "verification_reason":"ransac_failed"}
    selected=inliers.ravel()>0
    count=int(selected.sum())
    coverage=float(cv2.contourArea(cv2.convexHull(p0[selected])))/(shape[0]*shape[1]) if count>=3 else 0
    scale=math.hypot(affine[0,0],affine[1,0])
    angle=abs(math.degrees(math.atan2(affine[1,0],affine[0,0])))
    predicted=p0@affine[:,:2].T+affine[:,2]
    residual=float(np.linalg.norm(predicted[selected]-p1[selected],axis=1).mean()) if count else 100
    ratio=count/len(p0)
    consistent=count>=6 and ratio>=.65 and coverage>=.08 and .8<=scale<=1.25 and angle<=15
    return {"verified":consistent,"geometry_score":ratio*math.exp(-residual/5),
            "inliers":count,"feature_matches":len(p0),"inlier_coverage":coverage,
            "transform":affine.tolist(),"verification_reason":"ransac_consistent" if consistent else "inconsistent_geometry"}


class OpenCVFeatureMatcher:
    def verify(self,reference,candidate):
        a,b=fit_image(reference),fit_image(candidate)
        if a.shape!=b.shape:
            b=cv2.resize(b,(a.shape[1],a.shape[0]))
        orb=cv2.ORB_create(nfeatures=600,edgeThreshold=8,patchSize=15,fastThreshold=7)
        k0,d0=orb.detectAndCompute(a,None);k1,d1=orb.detectAndCompute(b,None)
        matches=[]
        if d0 is not None and d1 is not None and len(d1)>=2:
            pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d0,d1,k=2)
            used=set()
            for pair in sorted(pairs,key=lambda p:p[0].distance):
                if len(pair)==2 and pair[0].distance<.78*pair[1].distance and pair[0].trainIdx not in used:
                    matches.append(pair[0]);used.add(pair[0].trainIdx)
        contour=contour_evidence(reference,candidate)
        if len(matches)<6:
            # Sparse line symbols do not provide enough distinctive ORB points.
            # Explicit structural contour verification, never a template-score bypass.
            return {**contour,"verification_method":"contour_sparse_features","inliers":0,
                    "feature_matches":len(matches)}
        geometric=geometric_verification([k0[m.queryIdx].pt for m in matches],
                                          [k1[m.trainIdx].pt for m in matches],a.shape)
        # A plan's wall/cable can cross an otherwise complete symbol. Permit extra
        # strokes only when the entire reference survives AND spatially distributed
        # RANSAC correspondences prove the same geometry. Missing strokes still fail.
        extra_strokes=(contour.get("fill_consistent",True) and contour.get("reference_coverage",0)>=.98 and contour.get("foreground_ratio",0)>=.88
                       and contour["geometry_score"]>=.88 and geometric.get("inliers",0)>=20
                       and geometric.get("inlier_coverage",0)>=.35 and geometric["geometry_score"]>=.90)
        structure_ok=contour["verified"] or extra_strokes
        reason=("reference_geometry_with_extra_strokes" if extra_strokes and not contour["verified"]
                else contour["verification_reason"])
        return {**contour,**geometric,"feature_score":min(1,len(matches)/max(12,min(len(k0),len(k1))*.35)),
                "verified":geometric["verified"] and structure_ok,
                "verification_reason":geometric["verification_reason"] if not geometric["verified"] else reason,
                "verification_method":"orb_ransac","contour_geometry_score":contour["geometry_score"]}


class LearnedFeatureMatcher:
    """Inject a local backend returning corresponding points; geometry gates remain shared."""
    def __init__(self,backend):
        self.backend=backend

    def verify(self,reference,candidate):
        points0,points1=self.backend.correspondences(reference,candidate)
        verified=geometric_verification(points0,points1,reference.shape[:2])
        return {**verified,"feature_score":min(1,len(points0)/24),
                "verification_method":"learned_features_ransac"}


class LightGlueFeatureMatcher(LearnedFeatureMatcher):
    """Adapter for preloaded offline SuperPoint/LightGlue. Never downloads weights."""
    def __init__(self,extractor,matcher,device="cpu"):
        class Backend:
            def correspondences(self,reference,candidate):
                import torch
                def tensor(image):
                    if image.ndim==2:
                        image=np.repeat(image[:,:,None],3,axis=2)
                    return torch.from_numpy(image.copy()).permute(2,0,1).float().to(device)/255
                with torch.inference_mode():
                    f0=extractor.extract(tensor(reference),resize=None)
                    f1=extractor.extract(tensor(candidate),resize=None)
                    result=matcher({"image0":f0,"image1":f1})
                    matches=result["matches"][0]
                    return (f0["keypoints"][0][matches[:,0]].cpu().numpy(),
                            f1["keypoints"][0][matches[:,1]].cpu().numpy())
        super().__init__(Backend())

