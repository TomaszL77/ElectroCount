"""Explicit installation only. Inference never contacts the network."""
import hashlib,json,sys,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from electrocount.ai.visual_encoder import MODEL_REVISION,MODEL_SHA256,DinoV2Encoder


def main():
    folder=root/'models/dinov2-small/8b1f705';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'model.onnx'
    def checksum(p):
        with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    if not path.exists() or checksum(path)!=MODEL_SHA256:
        temporary=folder/'model.download'
        url=f'https://huggingface.co/onnx-community/dinov2-small/resolve/{MODEL_REVISION}/onnx/model.onnx'
        print('Pobieranie DINOv2-small (89 MB)...',flush=True)
        urllib.request.urlretrieve(url,temporary)
        if checksum(temporary)!=MODEL_SHA256:raise ValueError('Model SHA-256 mismatch')
        temporary.replace(path)
    manifest=dict(name='dinov2-small',version='8b1f705',role='symbol_encoder',filename='model.onnx',
        checksum=MODEL_SHA256,required_ram_mb=500,required_vram_mb=0,backends=['CPU'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    import numpy as np
    encoder=DinoV2Encoder(path)
    assert len(encoder.encode(np.full((30,60,3),255,np.uint8)).values)==384
    from electrocount.ocr_engine import OCREngine
    OCREngine()
    print('DINOv2 + OCR: lokalne modele gotowe. Inference nie wymaga internetu.')


if __name__=='__main__':main()
