"""Retry memory failures with less cache, never with fewer stages."""
from dataclasses import replace
import gc
from .performance import execution_plan, is_resource_failure

def run_with_fallback(operation, plan=None, notify=lambda plan:None):
    current=plan or execution_plan()
    while True:
        try: return operation(current)
        except Exception as exc:
            if not is_resource_failure(exc) or (current.memory_cache_mb<=8 and current.provider=='CPU'): raise
            current=replace(current,cpu_threads=1,memory_cache_mb=max(8,current.memory_cache_mb//2),
                provider='CPU',reason='Mniejszy cache; ta sama analiza, model i progi.')
            gc.collect()
            notify(current.to_dict())
