"""One detection policy; legacy profile names are migration inputs only."""
from dataclasses import asdict, dataclass
from enum import StrEnum

class PerformanceMode(StrEnum):
    AUTO = 'AUTO'

@dataclass(frozen=True)
class ExecutionPlan:
    mode: str = 'DETERMINISTIC'
    effective: str = 'DETERMINISTIC'
    cpu_threads: int = 1
    memory_cache_mb: int = 48
    provider: str = 'CPU'
    neural_enabled: bool = False
    context_enabled: bool = False
    reason: str = 'Jedna jakość analizy na każdym komputerze.'
    def to_dict(self): return asdict(self)

def execution_plan(mode=None, report=None, ceiling=None):
    # Hardware/legacy settings never select models, DPI, thresholds or stages.
    return ExecutionPlan()

def auto_profile(report): return 'DETERMINISTIC', execution_plan().reason

class BackendResourceError(RuntimeError): pass

def is_resource_failure(error):
    return isinstance(error,(MemoryError,BackendResourceError)) or (
        getattr(error,'code',None)==-4 and type(error).__module__=='cv2')
