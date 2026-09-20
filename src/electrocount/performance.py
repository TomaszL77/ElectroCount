"""Quality-invariant resource profiles. Only measured, available capabilities affect AUTO."""
from dataclasses import asdict, dataclass
from enum import StrEnum


class PerformanceMode(StrEnum):
    AUTO = "AUTO"
    ECO = "ECO"
    STANDARD = "STANDARD"
    ENHANCED = "ENHANCED"
    MAXIMUM = "MAXIMUM"


LEVELS = [PerformanceMode.ECO,PerformanceMode.STANDARD,PerformanceMode.ENHANCED,PerformanceMode.MAXIMUM]


@dataclass(frozen=True)
class ExecutionPlan:
    mode: str
    effective: str
    cpu_threads: int
    memory_cache_mb: int
    provider: str = "CPU"
    # Stage 1 keeps every geometric/text quality gate and the existing search scales.
    neural_enabled: bool = False
    context_enabled: bool = False
    reason: str = ""

    def to_dict(self):
        return asdict(self)


def auto_profile(report):
    hardware = report.get("hardware",{})
    metrics = report.get("benchmarks",{})
    available = hardware.get("available_ram_mb") or 0
    cores = hardware.get("cpu",{}).get("physical_cores") or hardware.get("cpu",{}).get("logical_cores",1)
    def measured(name, limit):
        metric = metrics.get(name,{})
        value = metric.get("median_ms")
        return metric.get("status")=="measured" and isinstance(value,(int,float)) and 0 < value <= limit
    if available < 2500 or cores < 2:
        return PerformanceMode.ECO, "Ograniczona dostępna pamięć RAM lub liczba rdzeni."
    if not measured("pdf_render",150) or not measured("feature_extraction",200):
        return PerformanceMode.ECO, "Benchmark nie potwierdził wydajności profilu Standard."
    # Enhanced/Maximum require a future real encoder/provider benchmark; no GPU-name guesses.
    return PerformanceMode.STANDARD, "Benchmark PDF/OpenCV i dostępna pamięć pozwalają na Standard."


def execution_plan(mode, report=None, ceiling=None):
    try:
        mode = PerformanceMode(mode)
    except ValueError:
        mode = PerformanceMode.AUTO
    report = report or {}
    chosen,reason = auto_profile(report) if mode==PerformanceMode.AUTO else (mode,"Profil wybrany ręcznie; moduły AI pozostają nieaktywne.")
    if ceiling is not None and LEVELS.index(chosen) > LEVELS.index(PerformanceMode(ceiling)):
        chosen = PerformanceMode(ceiling)
        reason = "Profil obniżony po problemie z zasobami."
    cpu = report.get("hardware",{}).get("cpu",{}).get("logical_cores",1)
    threads,cache = {PerformanceMode.ECO:(1,24),PerformanceMode.STANDARD:(4,48),
                     PerformanceMode.ENHANCED:(6,72),PerformanceMode.MAXIMUM:(8,96)}[chosen]
    available = report.get("hardware",{}).get("available_ram_mb") or 0
    if available < 1500:
        cache = min(cache,24)
    return ExecutionPlan(mode.value,chosen.value,max(1,min(threads,max(1,cpu-1))),cache,reason=reason)


def lower_profile(profile):
    return LEVELS[max(0,LEVELS.index(PerformanceMode(profile))-1)].value


class BackendResourceError(RuntimeError):
    """Future provider adapters translate OOM/backend failures/latency limits to this type."""


def is_resource_failure(error):
    if isinstance(error,(MemoryError,BackendResourceError)):
        return True
    # OpenCV allocation errors are structured; do not retry arbitrary invalid-document errors.
    return getattr(error,"code",None)==-4 and type(error).__module__=="cv2"
