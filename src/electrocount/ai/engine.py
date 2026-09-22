"""Compatibility facade; the tested deterministic engine remains the decision authority."""
from dataclasses import asdict
from ..detection_engine import DetectionEngine
from .context_engine import ContextEngine
from .training_dataset import TrainingDatasetManager
from .contracts import SignalBreakdown


class AIEngine:
    def __init__(self, pdf_engine, *, detector=None, model_manager=None, context_engine=None, dataset_manager=None):
        self.detector = detector or DetectionEngine(pdf_engine)
        self.models = model_manager
        self.context = context_engine or ContextEngine()
        self.dataset = dataset_manager or TrainingDatasetManager()

    def find(self, path, page, template, label="", threshold=.82, progress=lambda p:None, template_path=None, status=None):
        extra = {"status":status} if status is not None else {}
        result = self.detector.find(path,page,template,label,threshold,progress,template_path,**extra)
        for bucket in ("matches","review","discovered_other_label"):
            for hit in result[bucket]:
                hit["signals"] = asdict(SignalBreakdown(
                    vector_score=hit["graphic_score"] if hit.get("candidate_source")in ("vector","native_shape","native_text_anchor") else None,
                    feature_score=hit.get("feature_score"), geometry_score=hit.get("geometry_score"),
                    text_score=hit.get("text_score") if hit.get("label") else None, spatial_association_score=hit.get("spatial_association_score")))
        result["pipeline"] = {"version":"stage2-diagnostics-v4", "local_only":True,"decision_engine":"DetectionEngineV4",
            "active":["pdf_structure","candidate_generator","geometry","native_text","local_vector_index","rotated_symbol_layout"],
            "inactive":["neural_encoder","context_ai","training_collection"],
            "confidence_kind":"heuristic_not_probability"}
        return result
