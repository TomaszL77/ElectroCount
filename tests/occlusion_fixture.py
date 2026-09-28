"""Deterministic six-device PDF for occlusion regressions and benchmarks."""
import cv2
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image


def symbol(wrong=False):
    a=np.full((60,120,3),255,np.uint8)
    cv2.rectangle(a,(3,3),(116,56),(0,0,0),2)
    cv2.line(a,(3,3),(116,56),(0,0,0),2)
    if not wrong:cv2.line(a,(3,56),(116,3),(0,0,0),2)
    return a


def scene(path):
    c=canvas.Canvas(str(path),pagesize=(420,350),invariant=1);boxes=[]
    kinds=['clean','text','diagonal','other','wrong','opaque']
    for i,kind in enumerate(kinds):
        x,y=35+(i%2)*210,275-(i//2)*105
        a=symbol(kind=='wrong')
        if kind=='opaque':a[16:44,35:80]=255
        c.drawImage(ImageReader(Image.fromarray(a)),x,y,width=60,height=30)
        c.setFillColorRGB(0,0,0);c.setFont('Helvetica',9)
        c.drawString(x+65,y+11,'8' if kind=='other' else '7')
        if kind in ('text','other','wrong'):
            c.setFont('Helvetica',6);c.drawString(x+23,y+12,'20W')
        if kind=='diagonal':
            c.setLineWidth(.6);c.line(x-9,y+3,x+68,y+23)
        boxes.append([x,350-y-30,60,30])
    c.save()
    return [34,43,62,33],boxes
