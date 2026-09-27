"""Foreground HSV distributions, tolerant to antialiasing and monochrome copies."""
import cv2
import numpy as np


def native_color_signature(paths):
    """Measure native PDF foreground paints without rendering the entire page."""
    paints=[];weights=[]
    for path in paths:
        color=path.get('color',[])
        if len(color)<4 or color[3]==0:continue
        w,h=path['bbox'][2:]
        weight=w*h if path.get('fill') else max(w,h)*max(path.get('stroke_width',.5),.1)
        paints.append(color[:3]);weights.append(max(weight,.01))
    if not paints:return None
    counts=np.maximum(1,np.rint(np.array(weights)/sum(weights)*512).astype(int))
    rgb=np.repeat(np.array(paints,np.uint8),counts,axis=0)[None,:,:]
    return color_signature(rgb)


def color_signature(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    foreground = (hsv[:,:,1] > 35) | (hsv[:,:,2] < 205)
    pixels = rgb[foreground]
    if len(pixels) < 3:
        return {'confidence': 0., 'dominant_color': None, 'hsv_distribution': [], 'saturation': 0.}
    values = hsv[foreground]
    hist, _, _ = np.histogram2d(values[:,0], values[:,1], bins=(18,4), range=((0,180),(0,256)))
    hist = hist / hist.sum()
    return {'confidence': float(min(1, len(pixels)/30)),
        'dominant_color': np.median(pixels,axis=0).round().astype(int).tolist(),
        'foreground_color': np.median(pixels,axis=0).round().astype(int).tolist(),
        'mean_saturation': float(values[:,1].mean()/255),
        'foreground_fraction': float(foreground.mean()),
        'foreground_pixel_distribution': cv2.resize(foreground.astype(np.float32),(8,8),interpolation=cv2.INTER_AREA).ravel().tolist(),
        'hsv_distribution': hist.ravel().tolist(), 'saturation': float(np.median(values[:,1])/255),
        'hsv_statistics': {'mean': values.mean(axis=0).tolist(), 'std': values.std(axis=0).tolist()}}


def color_similarity(a, b):
    if not a.get('hsv_distribution') or not b.get('hsv_distribution'):
        return None
    if min(a['saturation'], b['saturation']) < .12:
        # Color is uninformative across a monochrome conversion, not negative.
        return None
    # Compare hue distributions on chromatic foreground. PDF antialiasing blends
    # a colored stroke with white and spreads saturation across several bins;
    # requiring identical saturation bins incorrectly penalizes the same paint.
    ha=np.array(a['hsv_distribution']).reshape(18,4)[:,1:].sum(axis=1)
    hb=np.array(b['hsv_distribution']).reshape(18,4)[:,1:].sum(axis=1)
    if not ha.sum() or not hb.sum():return None
    ha/=ha.sum();hb/=hb.sum()
    ha=(ha*2+np.roll(ha,1)+np.roll(ha,-1))/4
    hb=(hb*2+np.roll(hb,1)+np.roll(hb,-1))/4
    return float(np.clip(np.sqrt(ha*hb).sum(),0,1))



def color_name(signature):
    rgb=signature.get('dominant_color')
    if rgb is None:return 'nieustalony'
    h,s,v=cv2.cvtColor(np.array([[rgb]],dtype=np.uint8),cv2.COLOR_RGB2HSV)[0,0]
    if s<35:return 'czarny / szary' if v<205 else 'biały'
    if h<10 or h>=170:return 'czerwony'
    if h<25:return 'pomarańczowy'
    if h<40:return 'żółty'
    if h<85:return 'zielony'
    if h<100:return 'cyjan'
    if h<135:return 'niebieski'
    return 'magenta'
