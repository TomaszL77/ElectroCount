"""Vector geometry extraction and scale/rotation-aware signatures in page coordinates."""
import ctypes
import math
import numpy as np
import pypdfium2 as pdfium


def bbox(points):
    points=np.asarray(points,dtype=float)
    lower=points.min(axis=0);upper=points.max(axis=0)
    return [*lower.tolist(),*(upper-lower).tolist()]


def contains(outer,inner,tolerance=0.5):
    x,y,w,h=outer;a,b,c,d=inner
    return a>=x-tolerance and b>=y-tolerance and a+c<=x+w+tolerance and b+d<=y+h+tolerance


def extract_vectors(path,page_index,max_segments=40000):
    paths=[];has_images=False;unsupported=0
    segment_total=0;truncated=False
    with pdfium.PdfDocument(path) as doc:
        page=doc[page_index]
        w,h=page.get_size()
        converter=pdfium.PdfPosConv(page,(0,0,round(w*1000),round(h*1000),0))
        for obj in page.get_objects():
            if obj.type==pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                has_images=True
            if obj.type!=pdfium.raw.FPDF_PAGEOBJ_PATH:
                continue
            clip=pdfium.raw.FPDFPageObj_GetClipPath(obj)
            if clip and pdfium.raw.FPDFClipPath_CountPaths(clip)>0:
                unsupported+=1
                continue
            segment_total += pdfium.raw.FPDFPath_CountSegments(obj)
            if segment_total > max_segments:
                # Never present partial vector extraction as complete evidence.
                # The caller must use its full-page tiled raster route instead.
                paths.clear(); unsupported += 1; truncated = True
                break
            chain=[];current=obj
            while current is not None:
                chain.append(current.get_matrix())
                current=current.container
            def point(raw):
                x,y=raw
                for matrix in chain:
                    x,y=matrix.on_point(x,y)
                px,py=converter.to_bitmap(x,y)
                return [px/1000,py/1000]
            segments=[];previous=None;start=None;controls=[]
            for index in range(pdfium.raw.FPDFPath_CountSegments(obj)):
                segment=pdfium.raw.FPDFPath_GetPathSegment(obj,index)
                x,y=ctypes.c_float(),ctypes.c_float()
                if not pdfium.raw.FPDFPathSegment_GetPoint(segment,x,y):
                    continue
                target=point((x.value,y.value))
                kind=pdfium.raw.FPDFPathSegment_GetType(segment)
                if kind==pdfium.raw.FPDF_SEGMENT_MOVETO:
                    previous=start=target;controls=[]
                elif kind==pdfium.raw.FPDF_SEGMENT_LINETO and previous is not None:
                    segments.append({"kind":"line","points":[previous,target]})
                    previous=target
                elif kind==pdfium.raw.FPDF_SEGMENT_BEZIERTO and previous is not None:
                    controls.append(target)
                    if len(controls)==3:
                        segments.append({"kind":"curve","points":[previous,*controls]})
                        previous=controls[-1];controls=[]
                if pdfium.raw.FPDFPathSegment_GetClose(segment) and previous and start:
                    if np.linalg.norm(np.array(previous)-start)>0.001:
                        segments.append({"kind":"line","points":[previous,start]})
                    previous=start
            if segments:
                bounds=bbox([p for s in segments for p in s["points"]])
                if contains([0,0,w,h],bounds,1):
                    paths.append({"id":len(paths),"bbox":bounds,"segments":segments})
                else:
                    unsupported+=1
        page.close()
    return {"paths":paths,"has_images":has_images,"unsupported":unsupported,
            "truncated":truncated,"limit_reason":"vector_segment_budget" if truncated else ""}


def sample_segment(segment):
    points=np.array(segment["points"],dtype=float)
    t=np.linspace(0,1,9)[:,None]
    if segment["kind"]=="curve":
        return (1-t)**3*points[0]+3*(1-t)**2*t*points[1]+3*(1-t)*t*t*points[2]+t**3*points[3]
    return (1-t)*points[0]+t*points[-1]


def intersections(segments):
    lines=[s["points"] for s in segments if s["kind"]=="line"]
    count=0
    for i,(a,b) in enumerate(lines):
        a,b=np.array(a),np.array(b)
        for c,d in lines[i+1:]:
            c,d=np.array(c),np.array(d)
            matrix=np.column_stack((b-a,c-d))
            if abs(np.linalg.det(matrix))<1e-8:
                continue
            u,v=np.linalg.solve(matrix,c-a)
            if .01<u<.99 and .01<v<.99:
                count+=1
    return count


def signature(paths):
    segments=[s for p in paths for s in p["segments"]]
    if len(segments)<3 or len(segments)>512:
        return None
    bounds=bbox([p for s in segments for p in s["points"]])
    if min(bounds[2:])<.05:
        return None
    diagonal=math.hypot(*bounds[2:])
    origin=np.array(bounds[:2])
    return {"bbox":bounds,"paths":paths,"segment_count":len(segments),
        "relative_positions":[((np.array(s["points"])-origin)/diagonal).tolist() for s in segments],
        "angles":[math.degrees(math.atan2(*(np.array(s["points"][-1])-s["points"][0])[::-1])) for s in segments],
        "relative_lengths":[float(np.linalg.norm(np.diff(sample_segment(s),axis=0),axis=1).sum()/diagonal) for s in segments],
        "aspect":bounds[2]/bounds[3],"intersections":intersections(segments)}


def signature_in_rect(data,rect):
    paths=[p for p in data["paths"] if contains(rect,p["bbox"])]
    return signature(paths)


class VectorCandidateGenerator:
    """Anchor path hypotheses, then independent full-symbol structural verification."""
    def find(self,reference,data,progress=lambda p:None):
        segments=[s for p in reference["paths"] for s in p["segments"]]
        anchor=max(reference["paths"],key=lambda p:len(p["segments"]))
        anchor_line=next((s for s in anchor["segments"] if np.linalg.norm(np.array(s["points"][-1])-s["points"][0])>1),None)
        if anchor_line is None:
            return []
        p0,p1=np.array(anchor_line["points"])[[0,-1]]
        delta=p1-p0;length=np.linalg.norm(delta)
        reference_points=np.concatenate([sample_segment(s) for s in segments])
        candidates=[]
        total=max(1,len(data["paths"]))
        for index,path in enumerate(data["paths"]):
            if len(path["segments"])!=len(anchor["segments"]):
                continue
            for edge in path["segments"]:
                if edge["kind"]!=anchor_line["kind"]:
                    continue
                for reverse in (False,True):
                    q0,q1=np.array(edge["points"])[[0,-1]][::-1 if reverse else 1]
                    target=q1-q0
                    scale=np.linalg.norm(target)/length
                    angle=math.atan2(target[1],target[0])-math.atan2(delta[1],delta[0])
                    angle=(angle+math.pi)%(2*math.pi)-math.pi
                    if not .80<=scale<=1.25 or abs(angle)>math.radians(12):
                        continue
                    rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])*scale
                    translation=q0-rotation@p0
                    expected=reference_points@rotation.T+translation
                    box=bbox(expected)
                    nearby=[p for p in data["paths"] if contains(box,p["bbox"],max(1.0,min(box[2:])*.06))]
                    verified=self.verify(reference,nearby,rotation,translation,box)
                    candidates.append({"rect":box,"score":verified["graphic_score"],"rotation":math.degrees(angle),"scale":scale,
                                       "source":"vector",**verified})
            if index%100==0:
                progress(round(index*100/total))
        # Native hypotheses may share anchors. Keep highest verified evidence at each location.
        from .domain import overlap_metrics
        kept=[]
        for candidate in sorted(candidates,key=lambda c:c["geometry_score"]+c["feature_score"],reverse=True):
            if not any(overlap_metrics(candidate["rect"],other["rect"])[0]>.4 for other in kept):
                kept.append(candidate)
        progress(100)
        return kept

    def verify(self,reference,nearby,rotation,translation,box):
        from collections import Counter
        ref=[s for p in reference["paths"] for s in p["segments"]]
        actual=[s for p in nearby for s in p["segments"]]
        ratio=min(len(ref),len(actual))/max(len(ref),len(actual),1)
        kinds=Counter(s["kind"] for s in ref)==Counter(s["kind"] for s in actual)
        if len(actual)!=len(ref) or not kinds:
            return {"graphic_score":0.0,"feature_score":ratio*.4,"geometry_score":0.0,
                    "verified":False,"verification_method":"vector_signature","verification_reason":"structural_mismatch","template_score":None}
        if not actual:
            return {"graphic_score":0.0,"feature_score":0.0,"geometry_score":0.0,
                    "verified":False,"verification_method":"vector_signature","verification_reason":"missing_geometry","template_score":None}
        expected=[sample_segment(s)@rotation.T+translation for s in ref]
        samples=np.asarray([sample_segment(s) for s in actual])
        diagonal=max(math.hypot(*box[2:]),1)
        costs=[]
        for i,a in enumerate(expected):
            forward=np.linalg.norm(samples-a,axis=2).mean(axis=1)
            reverse=np.linalg.norm(samples[:,::-1]-a,axis=2).mean(axis=1)
            distances=np.minimum(forward,reverse)/diagonal
            costs.extend((float(distances[j]),i,j) for j in range(len(actual)) if ref[i]["kind"]==actual[j]["kind"])
        used_ref=set();used_actual=set();errors=[]
        for error,i,j in sorted(costs):
            if i not in used_ref and j not in used_actual:
                used_ref.add(i);used_actual.add(j);errors.append(error)
        geometry=math.exp(-25*max(errors,default=1))
        consistent=geometry>=.88 and intersections(actual)==reference["intersections"]
        feature=ratio*(1.0 if kinds else .4)*(1.0 if consistent else .4)
        verified=feature>=.95 and geometry>=.88 and len(used_ref)==len(ref)
        return {"graphic_score":(feature+geometry)/2,"feature_score":feature,"geometry_score":geometry,
                "template_score":None,"verified":verified,"verification_method":"vector_signature",
                "verification_reason":"verified_structure" if verified else "structural_mismatch",
                "inliers":len([e for e in errors if e<.02]),"feature_matches":len(errors),
                "transform":[*rotation.tolist()[0],translation[0],*rotation.tolist()[1],translation[1]]}

