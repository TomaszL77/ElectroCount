"""Short-lived subprocess. A result is published only after a complete operation."""
import json
import sys
import time
import traceback
from pathlib import Path
import cv2
from .pdf_engine import PdfiumEngine
from .pdf_cache import CachedPDFEngine
from .ai.engine import AIEngine
from .ai.model_manager import ModelManager
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
        return prepare_template(engine,request["path"],request["page"],request["rect"])
    if kind=="inspect":
        return engine.inspect(request["path"])
    if kind=="render":
        array = engine.render(request["path"],request["page"],request["scale"],request.get("rect"))
        cv2.imencode(".png",cv2.cvtColor(array,cv2.COLOR_RGB2BGR))[1].tofile(request["output"])
        return request["output"]
    detector = AIEngine(engine,model_manager=ModelManager(Path(__file__).resolve().parents[2]/"models"))
    if kind=="batch_match":
        results = []
        pages = request["pages"]
        template = request["template"]
        for index,page in enumerate(pages):
            emit({"status":f"Analizowanie strony {index+1} / {len(pages)}"})
            found = detector.find(page["path"],page["source_page"],template,
                request.get("label",""),request["threshold"],
                lambda value,index=index:emit({"progress":round((index+value/100)*100/len(pages))}),request["template_path"],
                status=lambda stage,index=index:emit({"status":f"Strona {index+1}/{len(pages)} · {stage}"}))
            template=found["template"]
            found["pipeline"]["execution"] = plan.to_dict()
            results.append({"page":page["page"],"result":found})
        return {"pages":results,"cache_hits":engine.hits}
    if kind=="match":
        result = detector.find(request["path"],request["page"],request["template"],
            request.get("label",""),request["threshold"],lambda v:emit({"progress":v}),request.get("template_path"),status=lambda stage:emit({"status":stage}))
        result["pipeline"]["execution"] = plan.to_dict()
        return result
    raise ValueError("Nieznany rodzaj operacji")


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    started = time.monotonic()
    try:
        plan = ExecutionPlan(**request["performance"]) if request.get("performance") else execution_plan("AUTO")
        result = run_with_fallback(lambda current:execute(request,current),plan,
            lambda current:emit({"performance_fallback":current}))
        emit({"result":result,"seconds":time.monotonic()-started})
    except Exception as exc:
        message = str(exc) or "Brak pamięci dla tej operacji." if isinstance(exc,MemoryError) else str(exc)
        emit({"error":message,"trace":traceback.format_exc()})
        sys.exit(1)


if __name__=="__main__":
    main()
