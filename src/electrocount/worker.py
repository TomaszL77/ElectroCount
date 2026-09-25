"""Short-lived subprocess. A result is published only after a complete operation."""
import json
import sys
import time
import traceback
from pathlib import Path
import cv2
from .pdf_engine import PdfiumEngine
from .pdf_cache import CachedPDFEngine
from .detection_service import run_detection, prepare_detection, self_test
from .diagnostics import runtime_info, write_json, data_dir
from .performance import ExecutionPlan, execution_plan
from .runtime_runner import run_with_fallback
from .text_engine import prepare_template
from .file_import_manager import FileImportManager


def emit(message):
    print(json.dumps(message,ensure_ascii=True),flush=True)


def execute(request, plan):
    cv2.setNumThreads(plan.cpu_threads)
    engine = CachedPDFEngine(PdfiumEngine(),request.get("cache_dir"),memory_limit=plan.memory_cache_mb*1024*1024)
    kind = request["kind"]
    if kind=="import":
        emit({"status":"Sprawdzanie dokumentów i stron PDF…"})
        return FileImportManager(pdf_engine=engine).inspect_many(request["paths"])
    if kind=="template":
        emit({"status":"Wyodrębnianie symbolu i oznaczenia z zaznaczenia…"})
        return prepare_detection(engine,request["path"],request["page"],request["rect"],
            debug_dir=request.get('debug_dir'),selection_context=request.get('selection_context'),ocr_enabled=request.get('ocr_enabled',False),model_name=request.get('model_name','small'))
    if kind=="inspect":
        return engine.inspect(request["path"])
    if kind=="render":
        array = engine.render(request["path"],request["page"],request["scale"],request.get("rect"))
        cv2.imencode(".png",cv2.cvtColor(array,cv2.COLOR_RGB2BGR))[1].tofile(request["output"])
        return request["output"]
    if kind=="runtime":
        report=runtime_info(probe_hardware=True)
        write_json(data_dir()/"logs"/"worker_runtime.json",report)
        return report
    if kind=="self_test":
        return self_test(engine,request["debug_dir"],config=plan.to_dict(),
            progress=lambda p:emit({"progress":p}),status=lambda s:emit({"status":s}))
    if kind=="batch_match":
        results = []
        pages = request["pages"]
        template = request["template"]
        for index,page in enumerate(pages):
            emit({"status":f"Analizowanie strony {index+1} / {len(pages)}"})
            found = run_detection(engine,page["path"],page["source_page"],template,
                request.get("label",""),request["threshold"],
                lambda value,index=index:emit({"progress":round((index+value/100)*100/len(pages))}),request["template_path"],
                status=lambda stage,index=index:emit({"status":f"Strona {index+1}/{len(pages)} · {stage}"}),
                config={**plan.to_dict(),**request.get('config',{})},
                debug_dir=str(Path(request['debug_dir'])/f"page-{page['page']+1}") if request.get('debug_dir') else None)
            template=found["template"]
            found["pipeline"]["execution"] = {**plan.to_dict(),**request.get('config',{})}
            results.append({"page":page["page"],"result":found})
        return {"pages":results,"cache_hits":engine.hits}
    if kind=="match":
        result = run_detection(engine,request["path"],request["page"],request["template"],
            request.get("label",""),request["threshold"],lambda v:emit({"progress":v}),request.get("template_path"),status=lambda stage:emit({"status":stage}),config=plan.to_dict(),debug_dir=request.get('debug_dir'))
        result["pipeline"]["execution"] = plan.to_dict()
        return result
    raise ValueError("Nieznany rodzaj operacji")


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    started = time.monotonic()
    try:
        from dataclasses import replace
        plan = execution_plan()
        plan=replace(plan,neural_enabled=request.get('config',{}).get('engine_mode') in ('hybrid','hybrid_base') or request.get('ocr_enabled',False))
        result = run_with_fallback(lambda current:execute(request,current),plan,
            lambda current:emit({"performance_fallback":current}))
        emit({"result":result,"seconds":time.monotonic()-started})
    except Exception as exc:
        message = str(exc) or "Brak pamięci dla tej operacji." if isinstance(exc,MemoryError) else str(exc)
        emit({"error":message,"trace":traceback.format_exc()})
        sys.exit(1)


if __name__=="__main__":
    main()
