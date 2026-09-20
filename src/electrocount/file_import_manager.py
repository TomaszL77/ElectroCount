"""Format routing belongs here, never in drag/drop event handlers."""
from dataclasses import dataclass, field
from pathlib import Path
from .domain import Document
from .pdf_engine import PdfiumEngine


class UnsupportedCAD:
    def inspect(self, path):
        raise NotImplementedError("Moduł CAD nie jest jeszcze dostępny. Plik nie został zaimportowany. Wyeksportuj rzut do PDF.")

    def read_blocks(self, path):
        raise NotImplementedError("Moduł CAD nie jest jeszcze dostępny.")


@dataclass
class ImportPlan:
    paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class FileImportManager:
    EXTENSIONS = {".pdf", ".dwg", ".dxf"}

    def __init__(self, pdf_engine=None, cad_engine=None):
        self.pdf = pdf_engine or PdfiumEngine()
        self.cad = cad_engine or UnsupportedCAD()

    def accepts(self, paths):
        return bool(paths) and any(Path(p).suffix.lower() in self.EXTENSIONS for p in paths)

    def plan(self, paths, existing=()):
        plan = ImportPlan()
        seen = {str(Path(p).resolve()).casefold() for p in existing}
        for value in paths:
            path = Path(value).resolve()
            key = str(path).casefold()
            if path.suffix.lower() not in self.EXTENSIONS:
                plan.errors.append(f"{path.name}: nieobsługiwany format.")
            elif not path.is_file():
                plan.errors.append(f"{path.name}: plik nie istnieje.")
            elif key in seen:
                plan.errors.append(f"{path.name}: plik jest już w projekcie lub na liście importu.")
            else:
                seen.add(key)
                plan.paths.append(str(path))
        return plan

    def inspect(self, path):
        suffix = Path(path).suffix.lower()
        if suffix == ".pdf":
            return self.pdf.inspect(path)
        if suffix in (".dwg", ".dxf"):
            return self.cad.inspect(path)
        raise ValueError("Nieobsługiwany format pliku.")

    def inspect_many(self, paths):
        successes, errors = [], []
        for path in paths:
            try:
                pages = self.inspect(path)
                if not pages:
                    raise ValueError("Dokument nie zawiera stron.")
                successes.append({"path": path, "name": Path(path).name, "pages": pages})
            except Exception as exc:
                errors.append(f"{Path(path).name}: {exc}")
        return {"documents": successes, "errors": errors}

    def apply(self, project, imported):
        for entry in imported["documents"]:
            project.append_document(Document(entry["path"], entry["name"]), entry["pages"])

