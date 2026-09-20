"""Bounded, offline startup measurements. Executed in an independently killable process."""
from datetime import datetime, timezone
from importlib import metadata, util
from pathlib import Path
from statistics import median
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from .hardware_windows import cpu_info, memory_status, process_memory, gpu_info, cuda_info, dll_available


SCHEMA = 1
BENCHMARK_VERSION = 1


def runtime_info():
    backends = [{"name":"OpenCV CPU","available":True,"inference_tested":False}]
    if util.find_spec("onnxruntime"):
        try:
            import onnxruntime as ort
            backends.extend({"name":name,"available":True,"inference_tested":False} for name in ort.get_available_providers())
        except Exception as exc:
            backends.append({"name":"ONNX Runtime","available":False,"reason":str(exc)})
    versions = {}
    for package in ("opencv-python-headless","pypdfium2","numpy","onnxruntime","onnxruntime-gpu","onnxruntime-directml"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            pass
    return backends,versions


def benchmark_pdf():
    # Small anonymous vector workload, generated in memory without a PDF authoring dependency.
    drawing = b"0.8 w\n" + b"\n".join(
        f"{x} {y} 28 12 re S {x} {y} m {x+28} {y+12} l S {x+28} {y} m {x} {y+12} l S".encode()
        for y in range(20,780,25) for x in range(20,560,40))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << >> >>",
        b"<< /Length "+str(len(drawing)).encode()+b" >>\nstream\n"+drawing+b"\nendstream"]
    data = bytearray(b"%PDF-1.4\n"); offsets = [0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(data)); data.extend(f"{index} 0 obj\n".encode()+obj+b"\nendobj\n")
    start = len(data)
    data.extend(b"xref\n0 5\n0000000000 65535 f \n")
    data.extend(b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:]))
    data.extend(f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(data)


def measure(operation, deadline, minimum=3):
    values = []
    # Each stage has bounded repetitions; the parent enforces the hard wall-clock budget.
    while len(values)<minimum and time.monotonic()<deadline:
        start=time.perf_counter(); operation(); values.append((time.perf_counter()-start)*1000)
    if not values:
        return {"status":"skipped","reason":"Startup benchmark time budget exhausted"}
    return {"status":"measured","median_ms":round(median(values),3),"iterations":len(values)}


class HardwareProfiler:
    def collect(self):
        gpus,error = gpu_info()
        backends,versions = runtime_info()
        hardware = {"os":platform.platform(),"cpu":cpu_info(),**memory_status(),"gpus":gpus,
            "gpu_probe_error":error,"directx_available":any(g.get("directx12") for g in gpus),
            "winml_runtime_available":dll_available("Windows.AI.MachineLearning.dll"),
            "winml_adapter_active":False,"cuda":cuda_info(),"backends":backends,"runtime_versions":versions}
        return hardware

    def run(self, cache_path=None, force=False, budget_seconds=8):
        started = time.monotonic()
        hardware = self.collect()
        stable = {k:v for k,v in hardware.items() if k!="available_ram_mb"}
        fingerprint = hashlib.sha256(json.dumps([SCHEMA,BENCHMARK_VERSION,stable],sort_keys=True).encode()).hexdigest()
        if cache_path and not force:
            try:
                cached = json.loads(Path(cache_path).read_text(encoding="utf-8"))
                age = time.time()-cached["created_unix"]
                if cached["fingerprint"]==fingerprint and cached["schema"]==SCHEMA and 0<=age<7*86400 and "benchmarks" in cached:
                    cached.update(hardware=hardware,cached=True,seconds=round(time.monotonic()-started,3))
                    return cached
            except (OSError,ValueError,KeyError,TypeError):
                pass
        metrics = {}
        memory_before = process_memory()
        deadline = started+budget_seconds
        try:
            import cv2
            import numpy as np
            import pypdfium2 as pdfium
            cv2.setNumThreads(1)
            with pdfium.PdfDocument(benchmark_pdf()) as doc:
                page = doc[0]
                def render():
                    bitmap = page.render(scale=1.5)
                    bitmap.close()
                metrics["pdf_render"] = measure(render,deadline)
                page.close()
            image = np.full((640,640),255,dtype=np.uint8)
            for y in range(20,600,40):
                for x in range(20,600,40):
                    cv2.rectangle(image,(x,y),(x+28,y+12),0,1)
                    cv2.line(image,(x,y),(x+28,y+12),0,1)
            orb = cv2.ORB_create(nfeatures=600)
            metrics["feature_extraction"] = measure(lambda:orb.detectAndCompute(image,None),deadline)
        except Exception as exc:
            metrics["benchmark_error"] = str(exc)
        # No stand-in arithmetic is reported as neural or GPU inference.
        metrics["embedding_inference"] = {"status":"skipped","reason":"No local symbol encoder installed"}
        metrics["gpu_inference"] = {"status":"skipped","reason":"No enabled GPU inference adapter/model"}
        metrics["memory"] = {"before":memory_before,"after":process_memory(),"vram_usage_mb":None,
                              "vram_reason":"No GPU inference workload; allocation usage not measured"}
        report = {"schema":SCHEMA,"benchmark_version":BENCHMARK_VERSION,"fingerprint":fingerprint,
            "created_unix":time.time(),"created_at":datetime.now(timezone.utc).isoformat(),
            "hardware":hardware,"benchmarks":metrics,"cached":False,"seconds":round(time.monotonic()-started,3)}
        if cache_path:
            destination = Path(cache_path)
            destination.parent.mkdir(parents=True,exist_ok=True)
            temporary = destination.with_suffix(f".{os.getpid()}.tmp")
            try:
                temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                temporary.replace(destination)
            except OSError:
                temporary.unlink(missing_ok=True)
        return report


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = HardwareProfiler().run(request.get("cache_path"),request.get("force",False))
        print(json.dumps(result),flush=True)
    except Exception as exc:
        print(json.dumps({"error":str(exc)}),flush=True)


if __name__ == "__main__":
    main()
