"""Shared contracts for future local AI. Missing evidence is None, never a fabricated score."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class AIExecutionProvider(StrEnum):
    CPU = "CPU"
    WINML = "WinML"
    CUDA = "CUDA"


@dataclass(frozen=True)
class SignalBreakdown:
    visual_ai_score: float | None = None
    color_score: float | None = None
    device_label_score: float | None = None
    text_role_confidence: float | None = None
    vector_score: float | None = None
    embedding_score: float | None = None
    feature_score: float | None = None
    geometry_score: float | None = None
    text_score: float | None = None
    spatial_association_score: float | None = None
    legend_score: float | None = None
    context_score: float | None = None


@dataclass(frozen=True)
class VisualEmbedding:
    values: tuple[float, ...]
    model_name: str
    model_version: str
    provider: AIExecutionProvider


@dataclass(frozen=True)
class DocumentEntity:
    id: str
    document_id: str
    page: int
    type: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    rotation: float = 0.0
    source: str = "pdf_native"
    text: str = ""
    graphic_features: dict = field(default_factory=dict)
    neighbors: tuple[str, ...] = ()
    possible_legend_entry: str | None = None


class RelationType(StrEnum):
    NEAR = "NEAR"
    LEFT_OF = "LEFT_OF"
    RIGHT_OF = "RIGHT_OF"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    OVERLAPS = "OVERLAPS"
    INSIDE = "INSIDE"
    CONNECTED_TO = "CONNECTED_TO"
    SAME_VISUAL_PATTERN = "SAME_VISUAL_PATTERN"


@dataclass(frozen=True)
class ContextEvidence:
    score: float | None = None
    legend_id: str | None = None
    ambiguous: bool = True
    reason: str = "context_not_enabled"


@dataclass(frozen=True)
class ReasoningResult:
    candidate_type: str | None = None
    candidate_label: str | None = None
    confidence: float | None = None
    ambiguous: bool = True


class IVisualSymbolEncoder(Protocol):
    def encode(self, crop) -> VisualEmbedding: ...


class IFeatureMatcher(Protocol):
    def verify(self, reference, candidate) -> dict: ...


class IVisionReasoner(Protocol):
    # Only class suggestions for an existing candidate; no quantities or new boxes.
    def resolve(self, candidate: DocumentEntity, context_crop, legend_crop,
                possible_classes: tuple[str, ...]) -> ReasoningResult: ...


class IContextEngine(Protocol):
    def evaluate(self, candidate: DocumentEntity, entities: tuple[DocumentEntity, ...]) -> ContextEvidence: ...


class IAIEngine(Protocol):
    def find(self, path, page, template, label="", threshold=.82,
             progress=lambda p: None, template_path=None, status=None) -> dict: ...


class IModelManager(Protocol):
    def list_models(self) -> list[dict]: ...
    def inspect(self, name: str, version: str) -> dict: ...


class ITrainingDatasetManager(Protocol):
    def record(self, example, crop=None) -> bool: ...
