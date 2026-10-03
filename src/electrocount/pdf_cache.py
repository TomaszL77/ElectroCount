"""Bounded, local cache shared by workers. Source stat and adapter version invalidate entries."""
import hashlib
import json
import os
import time
from collections import OrderedDict
from pathlib import Path
import numpy as np
from .text_engine import PdfTextItem


class CachedPDFEngine:
    def __init__(self, engine, directory=None, memory_limit=48*1024*1024):
        self.engine = engine
        self.directory = Path(directory) if directory else None
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
        self.memory = OrderedDict()
        self.bytes = 0
        self.limit = memory_limit
        self.writes = 0
        self.hits = 0

    def _call(self, method, path, *args):
        source = Path(path)
        stat = source.stat()
        raw = json.dumps(["v077-selection", getattr(self.engine,"cache_namespace","default"), str(source.resolve()),stat.st_size,stat.st_mtime_ns,method,args], sort_keys=True)
        key = hashlib.sha256(raw.encode()).hexdigest()
        if key in self.memory:
            self.hits += 1
            self.memory.move_to_end(key)
            return self.memory[key][0]
        extension = ".npy" if method == "render" else ".json"
        filename = self.directory/(key+extension) if self.directory else None
        value = None
        if filename and filename.is_file():
            try:
                value = np.load(filename, allow_pickle=False) if method == "render" else json.loads(filename.read_text(encoding="utf-8"))
                if method == "extract_text":
                    value = [PdfTextItem(**item) for item in value]
                self.hits += 1
            except (OSError, ValueError):
                value = None
        if value is None:
            value = getattr(self.engine,method)(path,*args)
            if filename:
                temp = filename.with_suffix(filename.suffix+f".{os.getpid()}.tmp")
                try:
                    if method == "render":
                        with temp.open("wb") as stream:
                            np.save(stream,value,allow_pickle=False)
                    else:
                        data = [i.to_dict() for i in value] if method == "extract_text" else value
                        temp.write_text(json.dumps(data),encoding="utf-8")
                    temp.replace(filename)
                    self.writes += 1
                    if self.writes % 20 == 0:
                        self._trim_disk()
                except OSError:
                    temp.unlink(missing_ok=True)
        size = value.nbytes if isinstance(value,np.ndarray) else len(repr(value))*2
        if size < self.limit:
            self.memory[key] = (value,size)
            self.bytes += size
            while self.bytes > self.limit:
                _,(_,old_size)=self.memory.popitem(last=False)
                self.bytes -= old_size
        return value

    def _trim_disk(self):
        entries=[]
        for path in self.directory.iterdir():
            if path.suffix not in (".json",".npy",".npz"):
                continue
            try:
                stat=path.stat()
                entries.append((stat.st_mtime,stat.st_size,path))
            except OSError:
                pass
        total=sum(entry[1] for entry in entries)
        for _,size,path in sorted(entries):
            if total <= 256*1024*1024:
                break
            try:
                path.unlink()
                total-=size
            except OSError:
                pass

    def inspect(self,path):
        return self._call("inspect",path)
    def extract_text(self,path,page):
        return self._call("extract_text",path,page)
    def extract_vectors(self,path,page):
        return self._call("extract_vectors",path,page)
    def render(self,path,page,scale,rect=None):
        return self._call("render",path,page,scale,rect)


    def open_vector_page(self,path,page):
        # Native handles belong to the operation, never to disk or RAM caches.
        native=self.engine.open_vector_page(path,page,cache_directory=self.directory)
        if self.directory:self._trim_disk()
        return native
