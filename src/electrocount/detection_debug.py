"""Developer-only score inspection; no scores are presented as calibrated probabilities."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget,QPlainTextEdit


class DetectionDebug(QDockWidget):
    def __init__(self,parent):
        super().__init__("Detection Debug",parent)
        self.setObjectName("detectionDebug")
        self.text=QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("font-family: Consolas; font-size: 12px; background: #172232;")
        self.setWidget(self.text)
        self.setMinimumHeight(150)

    def inspect(self,detection,project):
        if detection is None:
            self.text.setPlainText("Wybierz wykrycie na rysunku lub liście.\nOceny są heurystyczne, nie są prawdopodobieństwem.")
            return
        d=detection
        score=lambda value: "n/d — nie użyto" if value is None else f"{value:.1%}"
        lines=[f"ID: {d.id}   strona: {d.page+1}   bbox [x,y,w,h]: {d.rect}",
               f"Źródło: {d.candidate_source or d.source}   metoda: {d.verification_method or 'legacy/manual'}",
               f"Template score: {score(d.template_score)}   Grafika: {score(d.graphic_score)}",
               f"Feature score: {score(d.feature_score)}   Geometry score: {score(d.geometry_score)}",
               f"Tekst PDF: {d.label or '(brak)'}   Text score: {score(d.text_score)}",
               f"Spatial text score: {score(d.spatial_association_score)}   Final confidence: {score(d.confidence)}",
               "AI signals (null = nieaktywne): "+json.dumps(d.signals,ensure_ascii=False),
               f"Status: {d.decision}   Powód: {d.reason}",
               json.dumps(d.verification_details,ensure_ascii=False),
               "Etapy analizy: "+json.dumps(project.analysis_reports.get(f"{d.group or d.requested_group}:{d.page}",{}).get("stages",{}),ensure_ascii=False)]
        self.text.setPlainText("\n".join(lines))

