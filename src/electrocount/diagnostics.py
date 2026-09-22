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
    """Context renders are explicitly distinct from vector/raster matcher inputs."""
    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    from .text_engine import mask_text
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source = template_path or path
    box = template.get("raster_rect", template["rect"])
    raw = pdf.render(source, template["page"], 2.0, box)
    def save(name, array):
        cv2.imencode('.png', cv2.cvtColor(array, cv2.COLOR_RGB2BGR))[1].tofile(str(directory/name))
    save('template_crop.png', raw)
    save('template_masked.png', mask_text(raw, pdf.extract_text(source, template['page']), box, 2.0))
    if template.get('selection_rect'):
        save('selection_crop.png', pdf.render(source, template['page'], 2.0, template['selection_rect']))
    meta = pdf.inspect(path)[page_index]
    overview_scale = min(2.0, 2500/max(meta['width'], meta['height']))
    save('page_render.png', pdf.render(path, page_index, overview_scale))
    info = {'template_size': [raw.shape[1], raw.shape[0]], 'template_render_bbox': box,
        'render_scale': 2.0, 'render_dpi': 144, 'page_render_scale': overview_scale,
        'page_render_role': 'context_preview; native geometry has no bitmap input; actual raster calls are in renders/',
        'candidates': []}
    if result:
        with pdfium.PdfDocument(path) as doc:
            page = doc[page_index]
            width,height = page.get_size()
            count = 0
            for bucket in ('matches', 'legend_matches', 'review', 'discovered_other_label', 'rejected_candidates'):
                for hit in result.get(bucket, []):
                    if not hit.get('rect'):continue
                    count += 1
                    x,y,w,h = hit['rect']
                    x0,y0 = max(0,x-8),max(0,y-8)
                    right,bottom = min(width,x+w+8),min(height,y+h+8)
                    entry = {'index': count, 'bucket': bucket, **hit}
                    if count <= 2000 and right>x0 and bottom>y0:
                        scale = min(2.0, 800/max(right-x0,bottom-y0))
                        bitmap = page.render(scale=scale,crop=(x0,height-bottom,width-right,y0),rev_byteorder=True)
                        array = np.array(bitmap.to_numpy(),copy=True)[:,:,:3];bitmap.close()
                        name = f'candidate_{count:03}.png';save(name,array)
                        entry.update(file=name, crop_pdf=[x0,y0,right-x0,bottom-y0], render_scale=scale)
                    else:entry['not_saved']='candidate_png_limit_2000'
                    info['candidates'].append(entry)
            page.close()
    return info
