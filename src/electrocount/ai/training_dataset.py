"""Versioned dataset contract only. User actions are NOT collected in stage 1."""
from dataclasses import dataclass
from enum import StrEnum


class DatasetAction(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_ADD = "manual_add"
    CHANGE_GROUP = "change_group"


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    BENCHMARK = "benchmark"


@dataclass(frozen=True)
class TrainingExample:
    dataset_version: str
    source_project_id: str
    document_hash: str
    page: int
    bbox: tuple[float, float, float, float]
    symbol_group: str
    detected_label: str
    corrected_label: str
    action: DatasetAction
    rotation: float
    source_format: str
    timestamp: str
    split: DatasetSplit
    schema_version: int = 1


class TrainingDatasetManager:
    enabled = False

    def record(self, example: TrainingExample, crop=None) -> bool:
        # Deliberate no-op: no document, crop or annotation is persisted.
        return False
