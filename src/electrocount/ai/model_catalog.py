"""Pinned ONNX releases; no downloads during inference or automatic substitution."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EncoderSpec:
    key: str
    revision: str
    sha256: str
    size_bytes: int
    dimensions: int
    parameters_million: int

    @property
    def relative_path(self):
        return f'dinov2-{self.key}/{self.revision[:7]}/model.onnx'

    @property
    def url(self):
        return f'https://huggingface.co/onnx-community/dinov2-{self.key}/resolve/{self.revision}/onnx/model.onnx'


MODELS = {
    'small': EncoderSpec('small','8b1f705a3a7f6f062f6bdd21986c1583d3ef105d',
        'f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a',88532934,384,21),
    'base': EncoderSpec('base','31ef06cac16d5d301c5930d147002a058c85a5e4',
        '320d1012a6fc65b101fc85ca30ee7a47b2e4f6a2e8bd78fb9d7036def0e30cb0',346627111,768,86),
}
ENGINE_MODES = {'classic':None, 'hybrid':'small', 'hybrid_base':'base'}


def model_for_mode(mode):
    if mode not in ENGINE_MODES:raise ValueError(f'Nieznany tryb analizy: {mode}')
    return ENGINE_MODES[mode]
