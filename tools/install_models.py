"""Explicit verified model installation; inference stays offline."""
import argparse, hashlib, json, sys, urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from electrocount.ai.model_catalog import MODELS
from electrocount.ai.visual_encoder import DinoV2Encoder


def checksum(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def install(name):
    spec=MODELS[name];path=root/'models'/spec.relative_path
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or checksum(path)!=spec.sha256:
        temporary=path.with_suffix('.download')
        print(f'Pobieranie DINOv2-{name}: {spec.size_bytes/1e6:.0f} MB...',flush=True)
        try:
            with urllib.request.urlopen(spec.url,timeout=60) as response, temporary.open('wb') as stream:
                while chunk:=response.read(1024*1024):stream.write(chunk)
            if temporary.stat().st_size!=spec.size_bytes or checksum(temporary)!=spec.sha256:
                raise ValueError('Nieprawidlowy rozmiar lub SHA-256 modelu; plik nie zostal zainstalowany.')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    manifest=dict(name='dinov2-'+name,version=spec.revision,role='symbol_encoder',filename='model.onnx',
        checksum=spec.sha256,required_ram_mb=1200 if name=='base' else 500,required_vram_mb=0,backends=['CPU'])
    path.with_name('manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    import numpy as np
    encoder=DinoV2Encoder(path,model_name=name)
    assert len(encoder.encode(np.full((30,60,3),255,np.uint8)).values)==spec.dimensions
    print(f'DINOv2-{name}: SHA-256 i inference OK ({spec.dimensions} cech).',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['base','small','all'],default='base')
    args=parser.parse_args()
    for name in (('small','base') if args.model=='all' else (args.model,)):install(name)
    from electrocount.ocr_engine import OCREngine
    OCREngine()
    print('Modele gotowe. Analiza dziala bez internetu.')


if __name__=='__main__':main()
