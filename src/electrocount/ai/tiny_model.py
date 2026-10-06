"""Trainable pair classifier (~310 KB). NumPy inference/training, no downloads.

No project-global classes: predicts visual equivalence of two symbol crops.
Exact device text remains an independent rule in the detector.
"""
from ..json_values import dumps as json_dumps
import json
from pathlib import Path
import cv2
import numpy as np
from ..foreground import foreground_crop

SIDE = 20
DIM = SIDE * SIDE * 2 + 6
SCHEMA = 'electrocount-pair-mlp-v2'
LEGACY_SCHEMA = 'electrocount-pair-mlp-v1'


def descriptor(image, foreground=True):
    image = np.asarray(image, dtype=np.uint8)
    if foreground:image=foreground_crop(image)
    h, w = image.shape[:2]
    scale = (SIDE - 2) / max(h, w)
    small = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    canvas = np.full((SIDE, SIDE, 3), 255, np.uint8)
    y, x = (SIDE - small.shape[0]) // 2, (SIDE - small.shape[1]) // 2
    canvas[y:y + small.shape[0], x:x + small.shape[1]] = small
    gray = 1 - cv2.cvtColor(canvas, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    edge = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    pixels = image[np.min(image, axis=2) < 220].astype(np.float32) / 255
    colors = np.r_[pixels.mean(axis=0), pixels.std(axis=0)] if len(pixels) else np.zeros(6)
    return np.r_[gray.ravel(), edge.ravel(), colors].astype(np.float32)


def pair_features(reference, candidate, foreground=True):
    a = descriptor(reference, foreground)
    # Align quarter-turn variants using image evidence, never device names.
    variants = [descriptor(np.rot90(candidate, k).copy(), foreground) for k in range(4)]
    b = min(variants, key=lambda v: float(np.mean(np.abs(a - v))))
    return np.r_[np.abs(a - b), a * b].astype(np.float32)


class TinyPairModel:
    def __init__(self, seed=17):
        rng = np.random.default_rng(seed)
        self.w1 = rng.normal(0, np.sqrt(2 / (2 * DIM)), (2 * DIM, 48)).astype(np.float32)
        self.b1 = np.zeros(48, np.float32)
        self.w2 = rng.normal(0, .1, (48,)).astype(np.float32)
        self.b2 = np.zeros(1, np.float32)
        self.metadata = {'schema': SCHEMA}

    def predict(self, x):
        x = np.asarray(x, np.float32)
        hidden = np.maximum(0, x @ self.w1 + self.b1)
        logit = np.clip(hidden @ self.w2 + self.b2[0], -30, 30)
        return 1 / (1 + np.exp(-logit))

    def score(self, reference, candidate):
        return float(self.predict(pair_features(reference, candidate, self.metadata['schema']!=LEGACY_SCHEMA)))

    def fit(self, x, y, validation, epochs=80, progress=lambda p: None):
        rng = np.random.default_rng(17)
        weights = (self.w1, self.b1, self.w2, self.b2)
        moments = [np.zeros_like(w) for w in weights]
        variances = [np.zeros_like(w) for w in weights]
        best, best_loss, step = None, float('inf'), 0
        vx, vy = validation
        # Class balance applies only to human training labels, no test examples.
        sample_weight = np.where(y == 1, len(y) / (2 * max(1, (y == 1).sum())),
                                 len(y) / (2 * max(1, (y == 0).sum()))).astype(np.float32)
        for epoch in range(epochs):
            order = rng.permutation(len(y))
            for start in range(0, len(y), 32):
                ids = order[start:start + 32]; batch, truth = x[ids], y[ids]
                pre = batch @ self.w1 + self.b1
                hidden = np.maximum(0, pre)
                probability = 1 / (1 + np.exp(-np.clip(hidden @ self.w2 + self.b2[0], -30, 30)))
                delta = (probability - truth) * sample_weight[ids] / len(ids)
                grad2 = hidden.T @ delta + .0001 * self.w2
                grad_hidden = delta[:, None] * self.w2[None, :] * (pre > 0)
                gradients = (batch.T @ grad_hidden + .0001 * self.w1,
                             grad_hidden.sum(axis=0), grad2, np.array([delta.sum()], np.float32))
                step += 1
                for i, (weight, gradient) in enumerate(zip(weights, gradients)):
                    moments[i] *= .9; moments[i] += .1 * gradient
                    variances[i] *= .999; variances[i] += .001 * gradient * gradient
                    weight -= .001 * (moments[i] / (1 - .9 ** step)) / (np.sqrt(variances[i] / (1 - .999 ** step)) + 1e-8)
            p = np.clip(self.predict(vx), 1e-6, 1 - 1e-6)
            loss = float(-(vy * np.log(p) + (1 - vy) * np.log(1 - p)).mean())
            if loss < best_loss:
                best_loss, best = loss, [w.copy() for w in weights]
            progress(round(10 + 80 * (epoch + 1) / epochs))
        for target, value in zip(weights, best):
            target[:] = value
        return best_loss

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            np.savez_compressed(stream, w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2,
                                metadata=np.frombuffer(json_dumps(self.metadata).encode(), dtype=np.uint8))
        temporary.replace(path)

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Nieprawidłowy rozmiar małego modelu.')
        result = cls()
        with np.load(path, allow_pickle=False) as data:
            result.metadata = json.loads(data['metadata'].tobytes())
            if result.metadata.get('schema') not in (SCHEMA, LEGACY_SCHEMA):
                raise ValueError('Nieobsługiwana wersja modelu.')
            for name in ('w1', 'b1', 'w2', 'b2'):
                value = data[name]
                if value.shape != getattr(result, name).shape or not np.isfinite(value).all():
                    raise ValueError('Uszkodzone wagi modelu.')
                setattr(result, name, value.astype(np.float32))
        return result
