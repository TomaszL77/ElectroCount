from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem


class DrawingView(QGraphicsView):
    rectangle_selected = Signal(object)
    detection_selected = Signal(str)
    viewport_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#151e2b"))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(self.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(self.DragMode.ScrollHandDrag)
        self.mode = "pan"
        self.start_point = None
        self.rubber = None
        self.overlays = []
        self.preview = None
        self.detail = None
        self.page_rect = QRectF()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self.viewport_changed)
        self.horizontalScrollBar().valueChanged.connect(self.schedule_detail)
        self.verticalScrollBar().valueChanged.connect(self.schedule_detail)

    def schedule_detail(self, *_):
        self.timer.start()

    def set_page(self, width, height):
        self.scene().clear()
        self.preview = self.detail = self.rubber = None
        self.overlays = []
        self.page_rect = QRectF(0, 0, width, height)
        self.scene().setSceneRect(self.page_rect)
        self.scene().addRect(self.page_rect, QPen(Qt.PenStyle.NoPen), QBrush(Qt.GlobalColor.white))
        self.fit()

    def set_preview(self, pixmap):
        if self.preview:
            self.scene().removeItem(self.preview)
        self.preview = self.scene().addPixmap(pixmap)
        self.preview.setScale(self.page_rect.width()/pixmap.width())
        self.preview.setZValue(1)

    def set_detail(self, pixmap, rect, scale):
        if self.detail:
            self.scene().removeItem(self.detail)
        self.detail = self.scene().addPixmap(pixmap)
        self.detail.setPos(rect[0], rect[1])
        self.detail.setScale(1/scale)
        self.detail.setZValue(2)

    def set_mode(self, mode):
        self.mode = mode
        if self.rubber:
            self.scene().removeItem(self.rubber)
            self.rubber = None
        self.start_point = None
        self.setDragMode(self.DragMode.ScrollHandDrag if mode == "pan" else self.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor if mode == "pan" else Qt.CursorShape.CrossCursor)

    def fit(self):
        if not self.page_rect.isEmpty():
            self.fitInView(self.page_rect.adjusted(-12, -12, 12, 12), Qt.AspectRatioMode.KeepAspectRatio)
            self.schedule_detail()

    def focus_rect(self, rect):
        target = QRectF(*rect)
        self.fitInView(target.adjusted(-70, -70, 70, 70), Qt.AspectRatioMode.KeepAspectRatio)
        self.centerOn(target.center())
        self.schedule_detail()

    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 1/1.18
        if 0.03 <= self.transform().m11()*factor <= 12:
            self.scale(factor, factor)
        self.schedule_detail()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_detail()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode != "pan":
                self.start_point = self.mapToScene(event.position().toPoint())
                self.rubber = self.scene().addRect(QRectF(self.start_point, self.start_point),
                    QPen(QColor("#29d8c1"), 0), QBrush(QColor(41, 216, 193, 30)))
                self.rubber.setZValue(20)
                return
            for item in self.items(event.position().toPoint()):
                if item.data(0):
                    self.detection_selected.emit(item.data(0))
                    break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_point is not None and self.rubber:
            rect = QRectF(self.start_point, self.mapToScene(event.position().toPoint())).normalized()
            self.rubber.setRect(rect.intersected(self.page_rect))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start_point is not None and self.rubber:
            rect = self.rubber.rect()
            self.scene().removeItem(self.rubber)
            self.rubber = None
            self.start_point = None
            if rect.width() >= 3 and rect.height() >= 3:
                self.rectangle_selected.emit([rect.x(), rect.y(), rect.width(), rect.height()])
            return
        super().mouseReleaseEvent(event)

    def draw_detections(self, project, conflicts, selected="", only_review=False):
        for item in self.overlays:
            self.scene().removeItem(item)
        self.overlays = []
        groups = {g.id: g for g in project.groups}
        for detection in project.detections:
            group = groups.get(detection.group or detection.requested_group)
            if not group or not group.visible or detection.page != project.page:
                continue
            if only_review and detection.decision != "review" and detection.id not in conflicts:
                continue
            color = QColor("#fa6076") if detection.id in conflicts else QColor(group.color)
            if detection.decision == "rejected":
                color = QColor("#8b94a2")
            pen = QPen(color, 2.8 if detection.id == selected else 1.5)
            pen.setCosmetic(True)
            if detection.decision == "review":
                pen.setStyle(Qt.PenStyle.DashLine)
            fill = QColor(color)
            fill.setAlpha(24 if detection.decision != "rejected" else 7)
            marker = QRectF(*detection.rect)
            # Keep thin native bodies visible/clickable without changing their
            # measured geometry, quantities or conflict checks.
            dx=max(0,(3-marker.width())/2);dy=max(0,(3-marker.height())/2)
            marker.adjust(-dx,-dy,dx,dy)
            item = self.scene().addRect(marker, pen, QBrush(fill))
            item.setZValue(8 if detection.id == selected else 5)
            item.setData(0, detection.id)
            item.setToolTip(f"{group.name if detection.group else 'Bez przypisania'} · {detection.label or '?'} · {detection.decision}\nKształt {detection.graphic_score or detection.score:.0%} · tekst {detection.text_score:.0%} · położenie {detection.spatial_association_score:.0%}")
            self.overlays.append(item)
            if detection.decision == "rejected":
                x, y, w, h = detection.rect
                cross = self.scene().addLine(x, y, x+w, y+h, pen)
                cross.setZValue(6)
                self.overlays.append(cross)

