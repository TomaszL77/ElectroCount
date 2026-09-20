"""Inactive context extension. No graph construction, legend parsing or VLM in stage 1."""
from .contracts import ContextEvidence


class ContextEngine:
    enabled = False

    def evaluate(self, candidate, entities=()):
        return ContextEvidence()
