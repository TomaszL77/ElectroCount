"""Single application entry point for GUI workers, diagnostics and regression tests."""
from pathlib import Path
import hashlib
import json
import logging
import time
import cv2
from .ai.engine import AIEngine
from .diagnostics import (RenderRecorder, data_dir, digest, export_images, runtime_info, write_json)
from .text_engine import prepare_template


def prepare_detection(pdf, path, page, selection, *, debug_dir=None, selection_context=None, ocr_enabled=False, model_name='small'):
    try:
        template = prepare_template(pdf, path, page, selection)
        if not template.get('label') and (ocr_enabled or not pdf.extract_text(path,page)):
            from .ocr_engine import OCREngine,TextOverridePDF
            native=pdf.extract_text(path,page)
            recognized=OCREngine().read_region(pdf,path,page,template['rect'],native)
            if recognized:
                pdf=TextOverridePDF(pdf,path,page,native+recognized)
                template=prepare_template(pdf,path,page,selection)
    except Exception as exc:
        if debug_dir:
            try:
                directory=Path(debug_dir);directory.mkdir(parents=True,exist_ok=True)
                image=pdf.render(path,page,2.0,selection)
                cv2.imencode('.png',cv2.cvtColor(image,cv2.COLOR_RGB2BGR))[1].tofile(str(directory/'selection_crop.png'))
                write_json(directory/'template_log.json',{'status':'error','error':str(exc),
                    'selection':selection,'coordinates':selection_context or {},'file_sha256':digest(path)})
            except Exception:logging.exception('Failed template debug export')
        raise
    from .template_representation import build_representation
    template['representation'] = build_representation(pdf,path,page,template)
    if ocr_enabled:
        from .ai.model_manager import ModelManager
        from .text_engine import mask_text
        from dataclasses import asdict
        encoder=ModelManager(Path(__file__).resolve().parents[2]/'models').load_visual_encoder(model_name)
        box=template.get('raster_rect',template['rect'])
        crop=mask_text(pdf.render(path,page,2.,box),pdf.extract_text(path,page),box,2.)
        template['representation']['visual_embedding']=asdict(encoder.encode(crop))
        template['representation']['visual_features'].update(embedding=template['representation']['visual_embedding'])
    template['selection_context'] = selection_context or {}
    if debug_dir:
        try:
            evidence = export_images(debug_dir, pdf, path, page, template)
            write_json(Path(debug_dir)/'template_log.json', {'file_sha256': digest(path),
                'template': template, 'coordinates': selection_context or {}, **evidence})
        except Exception as exc:
            template['debug_error'] = str(exc)
            logging.exception('Template debug export failed')
    return template


def result_signature(result):
    # Coordinates + semantic decisions, not timing, cache statistics or UUIDs.
    data = {bucket: sorted(([round(x, 3) for x in h['rect']], h['label'])
                          for h in result.get(bucket, []))
            for bucket in ('matches', 'legend_matches', 'review', 'discovered_other_label')}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def run_detection(pdf, path, page, template, label='', threshold=.82, progress=lambda p:None,
                  template_path=None, status=lambda s:None, *, config=None, debug_dir=None):
    start = time.monotonic()
    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    cv2.ocl.setUseOpenCL(False)
    config = config or {}
    from .render_session import RenderSession
    render_session=RenderSession(pdf)
    recorder = RenderRecorder(render_session, Path(debug_dir)/'renders') if debug_dir else None
    encoder=None
    from .ai.model_catalog import model_for_mode
    model_name=model_for_mode(config.get('engine_mode','classic'))
    if model_name:
        from .ai.model_manager import ModelManager
        encoder=ModelManager(Path(__file__).resolve().parents[2]/'models').load_visual_encoder(model_name)
    engine = AIEngine(recorder or render_session,visual_encoder=encoder)
    report = {'runtime': runtime_info(), 'path': str(path), 'file_sha256': digest(path),
        'page': page, 'template': template, 'template_bbox': template['rect'],
        'template_path':str(template_path or path), 'template_file_sha256': digest(template_path or path), 'threshold': threshold,
        'label': label, 'config': config, 'render_dpi': 144, 'scale': 2.0,
        'selection_context': template.get('selection_context', {}),
        'engine_entry': 'electrocount.detection_service.run_detection -> AIEngine -> DetectionEngine'}
    try:
        gui_code=config.get('gui_runtime',{}).get('code',{}).get('source_sha256')
        if gui_code and gui_code!=report['runtime']['code']['source_sha256']:
            raise RuntimeError("Kod aplikacji zmienił się od jej uruchomienia. Zapisz projekt i uruchom ElectroCount ponownie.")
        result = engine.find(path,page,template,label,threshold,progress,template_path,status)
        report['runtime']['model']=result['pipeline'].get('model')
        result['result_sha256'] = result_signature(result)
        result['pipeline']['execution'] = config
        report.update(status='complete', result_sha256=result['result_sha256'],
            template=result['template'], template_bbox=result['template']['rect'],
            candidate_count=result['stages']['generated'],
            accepted_count=len(result['matches']), accepted_count_meaning='engine countable matches; not user approval',
            rejected_count=result['stages']['rejected'], counts=result['counts'],
            pipeline=result['pipeline'], stages=result['stages'], coverage_warnings=result['coverage_warnings'],
            similarity_scores={key:result.get(key,[]) for key in ('matches','legend_matches','review','discovered_other_label','rejected_candidates')})
        if debug_dir:
            try:
                report.update(export_images(debug_dir,pdf,path,page,result['template'],result,template_path))
            except Exception as exc:
                result['coverage_warnings'].append('Nie udało się zapisać wszystkich obrazów diagnostycznych: '+str(exc))
                report['debug_export_error'] = str(exc)
        return result
    except Exception as exc:
        report.update(status='error',error=str(exc))
        raise
    finally:
        render_session.close()
        report['seconds'] = time.monotonic()-start
        if recorder:report['actual_matcher_renders'] = recorder.renders
        destination = Path(debug_dir)/'detection_log.json' if debug_dir else data_dir()/'logs'/'last_detection.json'
        try:
            write_json(destination,report)
        except OSError:
            logging.exception('Detection log could not be saved')


def self_test(pdf, directory, *, config=None, progress=lambda p:None, status=lambda s:None):
    from .self_test_pdf import create_pdf
    directory = Path(directory);directory.mkdir(parents=True, exist_ok=True)
    path = directory/'diagnostic.pdf'
    create_pdf(path)
    template = prepare_detection(pdf,str(path),0,[36,36,55,25])
    result = run_detection(pdf,str(path),0,template,'EC12',.82,progress,status=status,
        config=config,debug_dir=directory)
    report = {'status':'PASS' if len(result['matches'])==12 else 'FAIL', 'expected':12,
        'actual':len(result['matches']), 'result_sha256':result['result_sha256'], 'directory':str(directory)}
    write_json(directory/'self_test.json',report)
    return report
