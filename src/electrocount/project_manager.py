"""Version 2: portable, transactional multi-document projects. Version 1 remains readable."""
from .json_values import dumps as json_dumps
import hashlib
import json
import logging
import shutil
import sqlite3
from pathlib import Path
from .domain import Project


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


class ProjectManager:
    VERSION = 2

    def save(self, project, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        data = project.to_dict()
        for document in data["documents"]:
            source = Path(document["path"])
            source_hash = digest(source)
            target = folder / "sources" / (source_hash + source.suffix.lower())
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                temporary = target.with_suffix(".tmp")
                shutil.copyfile(source, temporary)
                if digest(temporary) != source_hash:
                    raise ValueError("Plik źródłowy zmienił się podczas kopiowania.")
                temporary.replace(target)
            elif digest(target) != source_hash:
                raise ValueError("Uszkodzona kopia dokumentu w projekcie.")
            document["path"] = target.relative_to(folder).as_posix()
            document["source_hash"] = source_hash
        data["source"] = data["documents"][0]["path"] if data["documents"] else ""
        data["source_hash"] = data["documents"][0]["source_hash"] if data["documents"] else ""
        with sqlite3.connect(folder / "project.sqlite") as db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("INSERT OR REPLACE INTO snapshot VALUES (1, ?, ?)",
                       (self.VERSION, json_dumps(data, ensure_ascii=False)))
        logging.info("Project saved: %s; documents=%d", folder.name, len(data["documents"]))

    def load(self, filename):
        filename = Path(filename).resolve()
        if not filename.is_file():
            raise ValueError("Nie znaleziono pliku projektu.")
        with sqlite3.connect(filename.as_uri()+"?mode=ro", uri=True) as db:
            row = db.execute("SELECT version, payload FROM snapshot WHERE id=1").fetchone()
        if not row or row[0] not in (1, self.VERSION):
            raise ValueError("Nieobsługiwana wersja projektu.")
        project = Project.from_dict(json.loads(row[1]))
        if row[0] == 1:
            for detection in project.detections:
                if detection.source == "automatic" and detection.decision != "rejected":
                    detection.previous_decision = detection.decision
                    detection.requested_group = detection.group
                    detection.group, detection.decision = "", "review"
                    detection.reason = "legacy_graphic_only"
        for document in project.documents:
            source = (filename.parent / document.path).resolve()
            if not source.is_relative_to(filename.parent):
                raise ValueError("Nieprawidłowa ścieżka źródła w projekcie.")
            if not source.is_file() or digest(source) != document.source_hash:
                raise ValueError("Brakuje dokumentu lub jego zawartość została zmieniona.")
            document.path = str(source)
        if project.documents:
            project.source = project.documents[0].path
            project.source_hash = project.documents[0].source_hash
        return project

