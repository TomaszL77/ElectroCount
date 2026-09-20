"""Bounded resource fallback around an atomic operation; quality gates never change."""
from dataclasses import replace
import gc
from .performance import ExecutionPlan, execution_plan, lower_profile, is_resource_failure


def run_with_fallback(operation, plan=None, notify=lambda plan:None):
    current = plan or execution_plan("AUTO")
    while True:
        try:
            return operation(current)
        except Exception as exc:
            if not is_resource_failure(exc) or current.effective=="ECO":
                raise
            current = replace(current,effective=lower_profile(current.effective),
                cpu_threads=max(1,current.cpu_threads//2),memory_cache_mb=max(8,current.memory_cache_mb//2),
                provider="CPU",neural_enabled=False,context_enabled=False,reason="Resource fallback")
            gc.collect()
            notify(current.to_dict())
