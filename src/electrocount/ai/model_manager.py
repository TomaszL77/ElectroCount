"""Local manifest registry and verified encoder loading; downloads belong to the installer."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
from functools import lru_cache
from .contracts import AIExecutionProvider


@lru_cache(maxsize=2)
def _encoder(path, size, modified, model_name):
    from .visual_encoder import DinoV2Encoder
    return DinoV2Encoder(path,model_name=model_name)


@dataclass(frozen=True)
class ModelManifest:
    name: str
    version: str
    role: str
    filename: str
    checksum: str
    required_ram_mb: int
    required_vram_mb: int
    backends: tuple[AIExecutionProvider, ...]

    @classmethod
    def parse(cls, data):
        data = dict(data)
        data["backends"] = tuple(AIExecutionProvider(b) for b in data["backends"])
        result = cls(**data)
        if not result.name or not result.version or not result.backends:
            raise ValueError("Model name, version and backends are required")
        if result.role not in ("symbol_encoder","feature_matcher","ocr","context"):
            raise ValueError("Unknown model role")
        if not re.fullmatch(r"[a-fA-F0-9]{64}",result.checksum):
            raise ValueError("A SHA-256 checksum is required")
        for size in (result.required_ram_mb,result.required_vram_mb):
            if type(size) is not int or size < 0:
                raise ValueError("Memory requirements must be non-negative MB")
        return result


class ModelManager:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()

    def load_visual_encoder(self, model_name='small'):
        from .model_catalog import MODELS
        from .visual_encoder import DinoV2Encoder
        path=self.directory/MODELS[model_name].relative_path
        if not path.is_file():return DinoV2Encoder(path,model_name=model_name)
        stat=path.stat()
        return _encoder(str(path),stat.st_size,stat.st_mtime_ns,model_name)

    def _manifests(self):
        records = []
        if not self.directory.exists():
            return records
        for file in sorted(self.directory.glob("*/*/manifest.json")):
            try:
                manifest = ModelManifest.parse(json.loads(file.read_text(encoding="utf-8")))
                relative = Path(manifest.filename)
                artifact = (file.parent/relative).resolve()
                if relative.is_absolute() or not artifact.is_relative_to(file.parent.resolve()) or not file.resolve().is_relative_to(self.directory):
                    raise ValueError("Model artifact must stay inside its version directory")
                records.append((manifest,artifact,None))
            except (OSError,ValueError,TypeError,KeyError) as exc:
                records.append((None,file,str(exc)))
        return records

    def list_models(self):
        return [{"name":m.name if m else path.parent.parent.name,
                 "version":m.version if m else path.parent.name,
                 "role":m.role if m else None,
                 "status":"unverified" if m and path.is_file() else "missing" if m else "invalid",
                 "active":False,"reason":error or "No inference adapter enabled"}
                for m,path,error in self._manifests()]

    def inspect(self, name, version):
        matches = [(m,p) for m,p,error in self._manifests() if m and m.name==name and m.version==version]
        if len(matches) != 1:
            return {"status":"missing" if not matches else "ambiguous","active":False}
        manifest,path = matches[0]
        if not path.is_file():
            return {"status":"missing","active":False}
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""):
                    digest.update(chunk)
        except OSError as exc:
            return {"status":"unreadable","active":False,"reason":str(exc)}
        valid = digest.hexdigest() == manifest.checksum.lower()
        return {"status":"verified" if valid else "checksum_mismatch","active":False,
                "manifest":manifest,"path":str(path)}
