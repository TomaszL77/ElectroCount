"""Small adapter contracts; OCR, CAD and export are intentionally future modules."""
from typing import Protocol


class PDFEngine(Protocol):
    def inspect(self, path: str) -> list[dict]: ...
    def render(self, path: str, page: int, scale: float, rect=None): ...
    def extract_text(self, path: str, page: int) -> list: ...
    def extract_vectors(self, path: str, page: int) -> dict: ...


class SymbolMatcher(Protocol):
    def find(self, engine: PDFEngine, path: str, page: int, template: dict,
             threshold: float, progress) -> list[dict]: ...


class TextEngine(Protocol):
    def associate(self, symbols, words): ...


class OCREngine(Protocol):
    def read(self, image): ...


class CADEngine(Protocol):
    def inspect(self, path: str) -> list[dict]: ...
    def read_blocks(self, path: str): ...


class ExportEngine(Protocol):
    def export(self, project, destination: str): ...


# These adapters are independent of UI and project persistence.
from .feature_matcher import ISymbolMatcher, FeatureMatcher
