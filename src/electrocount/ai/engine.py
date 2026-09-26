"""Compatibility facade; the tested deterministic engine remains the decision authority."""
from dataclasses import asdict
from ..detection_engine import DetectionEngine
from .context_engine import ContextEngine
from .training_dataset import TrainingDatasetManager
from .contracts import SignalBreakdown


class AIEngine:
    def __init__(self, pdf_engine, *, detector=None, model_manager=None, context_engine=None, dataset_manager=None,visual_encoder=None):
        self.detector = detector or DetectionEngine(pdf_engine,visual_encoder=visual_encoder)
        self.models = model_manager
        self.context = context_engine or ContextEngine()
        self.dataset = dataset_manager or TrainingDatasetManager()

    def find(self, path, page, template, label="", threshold=.82, progress=lambda p:None, template_path=None, status=None):
        extra = {"status":status} if status is not None else {}
        result = self.detector.find(path,page,template,label,threshold,progress,template_path,**extra)
        result["pipeline"] = {"version":"one-shot-v6", "local_only":True,"decision_engine":"FinalDecisionEngineV2",
            "active":["pdf_structure","candidate_generator","geometry","native_text","local_vector_index","rotated_symbol_layout","color_signature","text_roles"],
            "inactive":["neural_encoder","context_ai","training_collection"],
            "confidence_kind":"heuristic_not_probability"}
        if getattr(self.detector,'encoder',None):
            result['pipeline']['active'] += ['dinov2_embedding','dense_tile_retrieval']
            result['pipeline']['inactive'].remove('neural_encoder')
            result['pipeline']['model']={'name':self.detector.encoder.name,'revision':self.detector.encoder.version}
        result['pipeline']['engine_mode']=('hybrid_base' if self.detector.encoder.model_key=='base' else 'hybrid') if getattr(self.detector,'encoder',None) else 'classic'
        result['pipeline']['application_profile']='electrical-takeoff-v1'
        return result
