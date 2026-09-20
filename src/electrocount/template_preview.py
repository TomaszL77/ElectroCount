"""Compact preview of the isolated query, not the surrounding drawing."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class TemplatePreview(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.template=None;self.label=''
        self.setFixedHeight(82);self.hide()

    def set_template(self,template,label=''):
        self.template=template;self.label=label
        self.setVisible(bool(template and template.get('signature')))
        self.setToolTip('Wyodrębniony symbol używany do wyszukiwania. Oznaczenie jest sprawdzane osobno.')
        self.update()

    def paintEvent(self,event):
        if not self.template:return
        signature=self.template.get('signature')
        if not signature:return
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(QRectF(0,2,88,76),QColor('#f7fafc'))
        x,y,w,h=signature['bbox'];scale=min(70/max(w,.1),62/max(h,.1))
        ox,oy=(88-w*scale)/2,(80-h*scale)/2
        painter.save();painter.translate(ox,oy);painter.scale(scale,scale);painter.translate(-x,-y)
        pen=QPen(QColor('#13283b'));pen.setWidthF(1);pen.setCosmetic(True);painter.setPen(pen)
        for item in signature['paths']:
            painter.setBrush(QColor('#13283b') if item.get('fill') else Qt.NoBrush)
            path=QPainterPath()
            for segment in item['segments']:
                points=segment['points']
                if path.isEmpty() or abs(path.currentPosition().x()-points[0][0])>.001 or abs(path.currentPosition().y()-points[0][1])>.001:
                    path.moveTo(*points[0])
                if segment['kind']=='curve':path.cubicTo(*points[1],*points[2],*points[3])
                else:path.lineTo(*points[-1])
            painter.drawPath(path)
        painter.restore();painter.setPen(QColor('#b9cede'))
        painter.drawText(QRectF(100,8,max(0,self.width()-102),25),Qt.AlignLeft,'Szukany symbol')
        painter.setPen(QColor('#5ecbc0'))
        painter.drawText(QRectF(100,32,max(0,self.width()-102),38),Qt.AlignLeft|Qt.TextWordWrap,
                         'Oznaczenie: '+(self.label or 'brak'))
