"""Separate template and candidate evidence; heuristic scores are not probabilities."""
import json
from PySide6.QtWidgets import QDockWidget,QPlainTextEdit
from .color_features import color_name


def score(value):
    return 'n/d — nie użyto' if value is None else f'{value:.1%}'


class DetectionDebug(QDockWidget):
    def __init__(self,parent):
        super().__init__('Detection Debug',parent)
        self.setObjectName('detectionDebug')
        self.text=QPlainTextEdit();self.text.setReadOnly(True)
        self.text.setStyleSheet('font-family: Consolas; font-size: 12px; background: #172232;')
        self.setWidget(self.text);self.setMinimumHeight(150)

    def inspect(self,detection,project):
        group=project.active_group()
        template=(group.template or {}) if group else {}
        representation=template.get('representation',{})
        lines=[f"WZORZEC · Detected label: {representation.get('detected_label',template.get('label')) or '(brak)'}",
            f"Detected color: {color_name(representation.get('color_signature',{}))}",
            f"Text source: {representation.get('text_source') or '(brak)'}",
            f"Label bbox: {representation.get('label_bbox')} · rotation: {representation.get('label_rotation')} · position: {representation.get('label_position')}",
            'Associated texts: '+json.dumps(representation.get('associated_texts',[]),ensure_ascii=False)]
        if detection is not None:
            d=detection
            lines += [f'KANDYDAT · ID: {d.id} · strona: {d.page+1}',
                f'Shape: {score(d.graphic_score)} · Geometry: {score(d.geometry_score)} · Features: {score(d.feature_score)}',
                f"Visual AI: {score(d.signals.get('visual_score',d.signals.get('visual_ai_score')))} · Color: {score(d.signals.get('color_score'))}",
                f"Label: {d.label or '(brak)'} · Label score: {score(d.text_score)} · Text source: {d.verification_details.get('text_source')}",
                f'Text association: {score(d.spatial_association_score)} · Final: {score(d.confidence)}',
                f"Decision: {d.verification_details.get('decision',d.decision)} · Powód: {d.reason}",
                json.dumps(d.verification_details,ensure_ascii=False)]
        else:lines.append('Wybierz wykrycie na rysunku lub liście, aby zobaczyć szczegóły kandydata.')
        if group:
            variants=[d for d in project.discoveries if d['requested_group']==group.id and d['page']==project.page]
            lines.append(f'INNE WARIANTY na stronie: {len(variants)}')
            for d in variants[:20]:
                signals=d.get('signals',{})
                lines.append(f"Label: {d.get('label')} · Shape: {score(d.get('graphic_score'))} · Color: {score(signals.get('color_score'))} · Label score: {score(d.get('text_score'))} · Final: {score(d.get('confidence'))} · Decision: OTHER_VARIANT")
        lines.append('Oceny są heurystyczne, nie są prawdopodobieństwem.')
        self.text.setPlainText('\n'.join(lines))
