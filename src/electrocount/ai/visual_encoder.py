"""Pinned DINOv2 Small/Base FP32 encoders; identical CPU policy on every PC."""
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image
from .contracts import VisualEmbedding, AIExecutionProvider
from .model_catalog import MODELS

MODEL_REVISION = '8b1f705a3a7f6f062f6bdd21986c1583d3ef105d'
MODEL_SHA256 = 'f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a'


class DinoV2Encoder:
    name = 'dinov2-small-onnx-fp32'
    version = MODEL_REVISION

    def __init__(self, path=None, model_name='small'):
        spec=MODELS[model_name]
        self.name=f'dinov2-{model_name}-onnx-fp32'
        self.version=spec.revision
        self.dimensions=spec.dimensions
        self.model_key=model_name
        path = Path(path) if path else Path(__file__).resolve().parents[3]/'models'/spec.relative_path
        if not path.is_file():
            raise RuntimeError(f'Brak modelu DINOv2 {model_name}. Uruchom Instaluj_AI.cmd. Wybrany model nie został zastąpiony.')
        with path.open('rb') as stream:
            checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        if checksum != spec.sha256:
            raise RuntimeError('Nieprawidłowa suma kontrolna DINOv2. Uruchom Instaluj_AI.cmd.')
        from collections import OrderedDict
        self.cache=OrderedDict()
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.add_session_config_entry('session.use_deterministic_compute','1')
        self.session = ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        self.output_name=self.session.get_outputs()[0].name

    @staticmethod
    def preprocess(crop):
        # Preserve the entire symbol, including thin long luminaires. Pad to a
        # square before the fixed 224 resize; no distortion or center cropping.
        image = Image.fromarray(crop.astype(np.uint8)).convert('RGB')
        side = max(image.size)
        canvas = Image.new('RGB',(side,side),'white')
        canvas.paste(image,((side-image.width)//2,(side-image.height)//2))
        # Explicit retrieval preprocessing v1: resize the padded square to 224,
        # without the natural-photo center crop that would cut long symbols.
        canvas = canvas.resize((224,224),Image.Resampling.BICUBIC)
        x = np.asarray(canvas,dtype=np.float32)/255
        x = (x-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
        return np.ascontiguousarray(x.transpose(2,0,1)[None])

    def tokens(self, crop):
        pixels=self.preprocess(crop)
        key=hashlib.sha256(pixels.tobytes()).digest()
        if key not in self.cache:
            result=self.session.run([self.output_name],{'pixel_values':pixels})[0][0]
            if result.shape!=(257,self.dimensions) or not np.isfinite(result).all():
                raise RuntimeError('Nieprawidłowy kształt lub wartości wyjścia modelu DINOv2.')
            self.cache[key]=result
            while len(self.cache)>32:self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]

    def encode(self, crop):
        vector = self.tokens(crop)[0].astype(np.float64)
        vector /= max(1e-12,np.linalg.norm(vector))
        return VisualEmbedding(tuple(vector.tolist()),self.name,self.version,AIExecutionProvider.CPU)


def cosine(a,b):
    if (a.model_name,a.model_version)!=(b.model_name,b.model_version):
        raise ValueError('Nie można porównywać wektorów pochodzących z różnych modeli.')
    return float(np.clip(np.dot(a.values,b.values),0,1))

