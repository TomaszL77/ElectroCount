"""Portable evidence of the actual GUI search configuration."""
import base64
from pathlib import Path
import zipfile
from .json_values import dumps


def export_comparison(filename, project, startup_runtime):
    destination=Path(filename)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('runtime.json',dumps(startup_runtime,ensure_ascii=False,indent=2))
        archive.writestr('searches.json',dumps(project.analysis_reports,ensure_ascii=False,indent=2))
        for index,group in enumerate(project.groups):
            template=group.template or {}
            archive.writestr(f'templates/{index+1}.json',dumps(
                {'group':group.name,'label':group.label,'template':template},ensure_ascii=False,indent=2))
            original=template.get('representation',{}).get('original_rgb_crop',{})
            if original.get('png_base64'):
                archive.writestr(f'templates/{index+1}.png',base64.b64decode(original['png_base64']))
    return destination
