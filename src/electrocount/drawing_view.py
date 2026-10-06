import math
from collections import OrderedDict
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
        self.last_selection_context = {}
        self.mode = "pan"
        self.start_point = None
        self.rubber = None
        self.overlays = []
        self.preview = None
        self.detail = None
        self.tiles = OrderedDict()
        self.tile_bytes = 0
        self.tile_limit = 64 * 1024 * 1024
        self.needed_tiles = set()
        self.page_rect = QRectF()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.viewport_changed)
        self.horizontalScrollBar().valueChanged.connect(self.schedule_detail)
        self.verticalScrollBar().valueChanged.connect(self.schedule_detail)

    def schedule_detail(self, *_):
        # Throttle to one request per frame, including during continuous drag.
        # Restarting a debounce timer would postpone quality until drag stops.
        if not self.timer.isActive():
            self.timer.start()

    def set_page(self, width, height):
        self.scene().clear()
        self.tiles.clear()
        self.tile_bytes = 0
        self.needed_tiles.clear()
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
        self.preview.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.preview.setScale(self.page_rect.width()/pixmap.width())
        self.preview.setZValue(1)

    def set_detail(self, pixmap, rect, scale):
        if self.detail:
            self.scene().removeItem(self.detail)
        self.detail = self.scene().addPixmap(pixmap)
        self.detail.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.detail.setPos(rect[0], rect[1])
        self.detail.setScale(1/scale)
        self.detail.setZValue(2)

    def set_tile(self, key, pixmap, rect, scale):
        if key in self.tiles:
            self.tiles.move_to_end(key)
            return
        item = self.scene().addPixmap(pixmap)
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        item.setPos(rect[0], rect[1])
        item.setScale(1 / scale)
        # Retain sharper tiles over lower resolution fallbacks after zooming out.
        item.setZValue(2 + (math.log2(scale) + 8) / 100)
        size = pixmap.width() * pixmap.height() * 4
        self.tiles[key] = (item, size)
        self.tile_bytes += size
        self.trim_tiles()

    def trim_tiles(self):
        for key in list(self.tiles):
            if self.tile_bytes <= self.tile_limit:
                break
            if key in self.needed_tiles:
                continue
            item, size = self.tiles.pop(key)
            self.scene().removeItem(item)
            self.tile_bytes -= size

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
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            pixels = event.pixelDelta()
            angles = event.angleDelta()
            delta = (pixels.x() or pixels.y()) if not pixels.isNull() else (angles.x() or angles.y()) / 120 * 80
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - round(delta))
            self.schedule_detail()
            event.accept()
            return
        if not event.angleDelta().y():
            event.accept()
            return
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
                self.start_screen = event.position()
                self.start_point = self.viewportTransform().inverted()[0].map(event.position())
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
            rect = QRectF(self.start_point, self.viewportTransform().inverted()[0].map(event.position())).normalized()
            self.rubber.setRect(rect.intersected(self.page_rect))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start_point is not None and self.rubber:
            # Recompute at release: Windows can coalesce/drop the last move event.
            rect = QRectF(self.start_point,self.viewportTransform().inverted()[0].map(event.position())).normalized().intersected(self.page_rect)
            screen=QRectF(self.start_screen,event.position()).normalized()
            dpr=self.viewport().devicePixelRatioF();zoom=self.transform().m11()
            self.last_selection_context={
                'screen_selection_bbox':[screen.x(),screen.y(),screen.width(),screen.height()],
                'screen_coordinate_space':'viewport logical pixels (Qt events)',
                'physical_selection_bbox':[v*dpr for v in [screen.x(),screen.y(),screen.width(),screen.height()]],
                'pdf_selection_bbox':[rect.x(),rect.y(),rect.width(),rect.height()],
                'rendered_image_bbox':[v*2 for v in [rect.x(),rect.y(),rect.width(),rect.height()]],
                'render_scale':2.0,'dpi':144,'zoom':zoom,'devicePixelRatio':dpr,
                'logical_dpi':self.logicalDpiX(),'transform':[self.viewportTransform().m11(),self.viewportTransform().m22(),self.viewportTransform().dx(),self.viewportTransform().dy()]}

            self.scene().removeItem(self.rubber)
            self.rubber = None
            self.start_point = None
            if rect.width() >= 3 and rect.height() >= 3:
                self.rectangle_selected.emit([rect.x(), rect.y(), rect.width(), rect.height()])
            return
        super().mouseReleaseEvent(event)

    def draw_detections(self, project, conflicts, selected="", only_review=False, only_active=False):
        for item in self.overlays:
            self.scene().removeItem(item)
        self.overlays = []
        groups = {g.id: g for g in project.groups}
        for detection in project.detections:
            group = groups.get(detection.group or detection.requested_group)
            if only_active and (not group or group.id != project.active):
                continue
            if not group or not group.visible or detection.page != project.page:
                continue
            if only_review and detection.decision != "review" and detection.id not in conflicts:
                continue
            if detection.decision == "rejected":continue
            color = QColor("#d526b7" if detection.id in conflicts else
                "#35a867" if detection.decision=="accepted" else
                "#e58a22" if not detection.group or detection.reason in ("ambiguous_label","missing_label","shared_label","not_rediscovered") else "#e84242")
            if detection.decision == "rejected":
                color = QColor("#8b94a2")
            pen = QPen(color, 3.2 if detection.id == selected else 2.0)
            pen.setCosmetic(True)
            color.setAlpha(220)
            fill = QColor(color)
            fill.setAlpha(50 if detection.id == selected else 38)
            marker = QRectF(*detection.rect)
            # Keep thin native bodies visible/clickable without changing their
            # measured geometry, quantities or conflict checks.
            minimum=8/max(.01,self.transform().m11())
            dx=max(0,(minimum-marker.width())/2);dy=max(0,(minimum-marker.height())/2)
            if detection.id==selected:
                dx+=2/max(.01,self.transform().m11());dy+=2/max(.01,self.transform().m11())
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
