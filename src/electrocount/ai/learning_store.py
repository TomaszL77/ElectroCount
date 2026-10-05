"""Portable human feedback. Only explicit assessments become training labels."""
import base64
import hashlib
import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from PIL import Image

OUTCOMES = ('correct', 'wrong', 'variant', 'uncertain', 'pending')
SPLITS = ('train', 'validation', 'test')


def png_bytes(array):
    image = Image.fromarray(np.asarray(array, dtype=np.uint8)).convert('RGB')
    # Keep whole crop and aspect ratio, with a bounded storage/rendering cost.
    image.thumbnail((256, 256), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()


def decode(blob):
    with Image.open(io.BytesIO(blob)) as image:
        if max(image.size) > 2048:
            raise ValueError('Za duży obraz przykładu.')
        return np.asarray(image.convert('RGB')).copy()


class LearningStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'examples.sqlite'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents(hash TEXT PRIMARY KEY, name TEXT, split TEXT);
                CREATE TABLE IF NOT EXISTS examples(
                    id TEXT PRIMARY KEY, document TEXT, page INTEGER, group_id TEXT,
                    group_name TEXT, rect TEXT, outcome TEXT, reference BLOB, crop BLOB,
                    metadata TEXT, updated REAL);
                CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, body TEXT, created REAL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, record, reference, crop):
        if record['outcome'] not in OUTCOMES:
            raise ValueError('Nieznana ocena.')
        blob_ref = png_bytes(reference) if not isinstance(reference, bytes) else reference
        blob_crop = png_bytes(crop) if not isinstance(crop, bytes) else crop
        decode(blob_ref); decode(blob_crop)
        doc = record['document']
        identifier = hashlib.sha256(json.dumps([doc, record['page'], record['group_id'],
            [round(float(v), 3) for v in record['rect']]], sort_keys=True).encode()).hexdigest()
        with self.connect() as db:
            # Search can assign fresh detection UUIDs at the same location.
            # A review-queue import must never erase an existing human rating.
            if record['outcome']=='pending' and db.execute('SELECT 1 FROM examples WHERE id=?',(identifier,)).fetchone():
                return identifier
            count = db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
            # All pages of one PDF stay together. First two documents teach,
            # third validates, fourth tests; later documents default to train.
            split = 'validation' if count == 2 else 'test' if count == 3 else 'train'
            db.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?)',
                       (doc, record.get('document_name', 'Dokument'), record.get('split', split)))
            db.execute('INSERT OR REPLACE INTO examples VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (identifier, doc, record['page'], record['group_id'], record['group_name'],
                 json.dumps(record['rect']), record['outcome'], blob_ref, blob_crop,
                 json.dumps(record.get('metadata', {})), time.time()))
        return identifier

    def examples(self, with_images=True):
        with self.connect() as db:
            images = 'e.reference,e.crop' if with_images else 'NULL,NULL'
            rows = db.execute(f'''SELECT e.id,e.document,e.page,e.group_id,e.group_name,
                e.rect,e.outcome,{images},e.metadata,e.updated,d.name,d.split FROM examples e
                JOIN documents d ON d.hash=e.document ORDER BY e.updated DESC''').fetchall()
        return [dict(id=r[0], document=r[1], page=r[2], group_id=r[3], group_name=r[4],
                     rect=json.loads(r[5]), outcome=r[6], reference=r[7] if with_images else None,
                     crop=r[8] if with_images else None, metadata=json.loads(r[9]),
                     updated=r[10], document_name=r[11], split=r[12]) for r in rows]

    def images(self, identifier):
        with self.connect() as db:
            return db.execute('SELECT reference,crop FROM examples WHERE id=?', (identifier,)).fetchone()

    def reconcile(self, assessments):
        for row in self.examples(False):
            identifier = row['metadata'].get('detection_id')
            if identifier in assessments:
                state = assessments[identifier]
                if isinstance(state, str):
                    outcome = state
                else:
                    outcome = state['outcome'] if row['group_id'] == state['group_id'] else (
                        'variant' if state['outcome'] == 'correct' else 'uncertain')
                    actual, expected = row['metadata'].get('label'), row['metadata'].get('expected_label')
                    if outcome == 'wrong' and actual and expected and actual != expected:
                        outcome = 'variant'
                self.assess(row['id'], outcome)

    def assess(self, identifier, outcome):
        if outcome not in OUTCOMES:
            raise ValueError('Nieznana ocena.')
        with self.connect() as db:
            db.execute('UPDATE examples SET outcome=?,updated=? WHERE id=?', (outcome, time.time(), identifier))

    def split_document(self, document, split):
        if split not in SPLITS:
            raise ValueError('Nieznany podział.')
        with self.connect() as db:
            db.execute('UPDATE documents SET split=? WHERE hash=?', (split, document))

    def counts(self):
        rows = self.examples(False)
        return {split: {label: sum(r['split'] == split and r['outcome'] == label for r in rows)
                        for label in OUTCOMES} for split in SPLITS}

    def readiness(self):
        rows = self.examples(False)
        split_names={'train':'Uczenie','validation':'Walidacja','test':'Test'}
        outcome_names={'correct':'poprawnych','wrong':'błędnych kształtów'}
        for split, minimum in [('train', 20), ('validation', 5), ('test', 5)]:
            for outcome in ('correct', 'wrong'):
                count = sum(r['split'] == split and r['outcome'] == outcome for r in rows)
                if count < minimum:
                    return False, f'{split_names[split]}: potrzeba {minimum} przykładów {outcome_names[outcome]}, jest {count}.'
        train_docs = {r['document'] for r in rows if r['split'] == 'train' and r['outcome'] in ('correct', 'wrong')}
        if len(train_docs) < 2:
            return False, 'Uczenie wymaga przykładów z co najmniej dwóch różnych PDF-ów.'
        return True, 'Dane gotowe do pierwszego treningu.'

    def export_data(self, path):
        rows = self.examples()
        for row in rows:
            row['reference'] = base64.b64encode(row['reference']).decode()
            row['crop'] = base64.b64encode(row['crop']).decode()
        payload = json.dumps({'format': 'electrocount-examples-v1', 'examples': rows}, ensure_ascii=False)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('examples.json', payload)

    def import_data(self, path):
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('examples.json')
            if info.file_size > 256 * 1024 * 1024:
                raise ValueError('Pakiet przekracza 256 MiB. Podziel bazę przed importem.')
            payload = json.loads(archive.read(info))
        if payload.get('format') != 'electrocount-examples-v1':
            raise ValueError('Nieprawidłowy format danych.')
        prepared = []
        for row in payload['examples']:
            if row.get('split') not in SPLITS or row.get('outcome') not in OUTCOMES:
                raise ValueError('Nieprawidłowa ocena lub podział w pakiecie.')
            if len(row['rect']) != 4 or not all(np.isfinite(float(v)) for v in row['rect']):
                raise ValueError('Nieprawidłowe współrzędne.')
            ref, crop = base64.b64decode(row['reference'], validate=True), base64.b64decode(row['crop'], validate=True)
            decode(ref); decode(crop)
            prepared.append((row, ref, crop))
        # Validate the entire archive before committing any import.
        backup = self.directory / 'before-import.sqlite'
        with self.connect() as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        try:
            for row, ref, crop in prepared:
                self.record(row, ref, crop)
        except Exception:
            with sqlite3.connect(backup) as source, self.connect() as destination:
                source.backup(destination)
            raise
        finally:
            backup.unlink(missing_ok=True)
        return len(prepared)

    def save_report(self, report):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO reports VALUES(?,?,?)',
                       (report['id'], json.dumps(report), time.time()))

    def reports(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM reports ORDER BY created DESC')]
