"""Local, opt-in evidence. Never upload drawings or environment data."""
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
import hashlib
import json
import locale
import logging
import os
import platform
import subprocess
import sys
from uuid import uuid4


def data_dir():
    override = os.environ.get("ELECTROCOUNT_DATA_DIR")
    if override:
        return Path(override).resolve()
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ElectroCount"


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            value.update(chunk)
    return value.hexdigest()


def code_identity():
    from . import __version__
    root = Path(__file__).resolve().parent
    sources = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest() for p in sorted(root.rglob("*.py"))}
    identity = {"version": __version__, "source_root": str(root), "source_sha256":
                hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
                "files": sources, "frozen": bool(getattr(sys, "frozen", False))}
    for name, args in (("commit", ["rev-parse", "HEAD"]), ("branch", ["branch", "--show-current"]),
                       ("working_tree", ["status", "--porcelain"])):
        try:
            result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                text=True, encoding="utf-8", timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            identity[name] = result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            identity[name] = None
    return identity


def qt_screen_info(app):
    return [{"name": s.name(), "logical_dpi": s.logicalDotsPerInch(),
             "physical_dpi": s.physicalDotsPerInch(), "devicePixelRatio": s.devicePixelRatio(),
             "geometry": [s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height()]}
            for s in app.screens()]


def runtime_info(app=None, probe_hardware=False):
    import cv2
    import pypdfium2 as pdfium
    from PySide6.QtCore import qVersion
    packages = {}
    for name in ("PySide6", "PyMuPDF", "pypdfium2", "opencv-python-headless", "opencv-python",
                 "numpy", "pillow", "onnxruntime", "onnxruntime-gpu", "onnxruntime-directml"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix,
        "os": platform.platform(), "machine": platform.machine(), "cpu": platform.processor(),
        "logical_cores": os.cpu_count(), "locale": locale.getlocale(),
        "filesystem_encoding": sys.getfilesystemencoding(), "packages": packages, "qt": qVersion(),
        "renderer": "PDFium", "pdfium": str(pdfium.PDFIUM_INFO), "render_scale": 2.0, "render_dpi": 144,
        "backend": "CPU / native PDF geometry + OpenCV", "model": None,
        "gpu_used_for_detection": False, "opencv_threads": cv2.getNumThreads(),
        "opencv_opencl": cv2.ocl.useOpenCL(), "code": code_identity(),
        "qt_environment": {k: os.environ.get(k) for k in ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_QPA_PLATFORM")},
        "screens": qt_screen_info(app) if app else [], "hardware": None}
    if probe_hardware:
        from .hardware_profiler import HardwareProfiler
        try:
            result["hardware"] = HardwareProfiler().collect()
        except Exception as exc:
            result["hardware_error"] = str(exc)
    return result


def new_debug_run():
    folder = data_dir()/"debug"/(datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=True)
    write_json(data_dir()/"debug"/"latest.json", {"directory": str(folder)})
    return folder


class RenderRecorder:
    """Transparent decorator records the actual raster inputs of the engine."""
    def __init__(self, engine, directory):
        self.engine, self.directory = engine, Path(directory)
        self.renders = []
        self.bytes = 0

    def __getattr__(self, name):
        return getattr(self.engine, name)

    def render(self, path, page, scale, rect=None):
        import cv2
        image = self.engine.render(path, page, scale, rect)
        entry = {"path": str(path), "page": page, "bbox_pdf": rect, "scale": scale,
                 "dpi": 72*scale, "pixels": [image.shape[1], image.shape[0]]}
        # Avoid exhausting the user's disk on a giant raster drawing. All calls
        # remain in the manifest, including those beyond the PNG byte budget.
        if self.bytes < 256*1024*1024:
            self.directory.mkdir(parents=True, exist_ok=True)
            name = f"render_{len(self.renders)+1:05}.png"
            encoded = cv2.imencode('.png', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))[1]
            encoded.tofile(str(self.directory/name))
            self.bytes += encoded.nbytes
            entry["file"] = name
        else:
            entry["not_saved"] = "debug_png_budget_256MiB"
        self.renders.append(entry)
        return image


def export_images(directory, pdf, path, page_index, template, result=None, template_path=None):
    """Only the two template crops and a small extraction record."""
    import base64
    from .template_representation import build_representation
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    representation=template.get('representation') or build_representation(
        pdf,template_path or path,template['page'],template)
    for filename,key in [('selection_crop.png','original_rgb_crop'),('matching_crop.png','visual_crop')]:
        (directory/filename).write_bytes(base64.b64decode(representation[key]['png_base64']))
    info={k:template.get(k) for k in ('selection_bbox','symbol_bbox','matching_bbox','source',
          'extraction_mode','preserved_paths','removed_paths')}
    info['detected_label']=template.get('label','')
    write_json(directory/'template_log.json',info)
    return info
