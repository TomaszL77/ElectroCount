"""Document coordinates are display-page points, top-left origin; never screen pixels."""
from dataclasses import asdict, dataclass, field
from math import hypot
from uuid import uuid4


def uid():
    return uuid4().hex


@dataclass
class Document:
    path: str
    name: str = ""
    source_hash: str = ""
    id: str = field(default_factory=uid)


@dataclass
class Detection:
    group: str
    page: int
    rect: list[float]
    score: float = 1.0
    decision: str = "review"
    source: str = "automatic"
    id: str = field(default_factory=uid)
    label: str = ""
    label_bbox: list | None = None
    graphic_score: float = 0.0
    text_score: float = 0.0
    spatial_association_score: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    requested_group: str = ""
    previous_decision: str = ""
    template_score: float | None = None
    feature_score: float = 0.0
    geometry_score: float = 0.0
    verification_method: str = ""
    verification_details: dict = field(default_factory=dict)
    candidate_source: str = ""
    signals: dict = field(default_factory=dict)


@dataclass
class Group:
    name: str
    color: str = "#42b8ac"
    description: str = ""
    visible: bool = True
    template: dict | None = None
    id: str = field(default_factory=uid)
    label: str = ""
    possible_label: str = ""


@dataclass
class Project:
    name: str = "Nowy projekt"
    source: str = ""
    source_hash: str = ""
    pages: list = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)
    active: str = ""
    page: int = 0
    threshold: float = 0.82
    overlap: float = 0.45
    proximity: float = 0.22
    allowed: list = field(default_factory=list)
    resolutions: list = field(default_factory=list)
    view: dict = field(default_factory=dict)
    symbol_serial: int = 0
    documents: list[Document] = field(default_factory=list)
    discoveries: list = field(default_factory=list)
    text_items: dict = field(default_factory=dict)
    analysis_reports: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.documents and self.source:
            from pathlib import Path
            self.documents = [Document(self.source, Path(self.source).name, self.source_hash)]
        for index, page in enumerate(self.pages):
            if self.documents:
                page.setdefault("document_id", self.documents[0].id)
                page.setdefault("source_page", index)

    def page_location(self, index):
        page = self.pages[index]
        document = next(d for d in self.documents if d.id == page["document_id"])
        return document.path, page["source_page"]

    def append_document(self, document, pages):
        self.documents.append(document)
        for index, page in enumerate(pages):
            self.pages.append({**page, "document_id": document.id, "source_page": index})
        if not self.source:
            self.source = document.path

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["documents"] = [Document(**d) for d in data.get("documents", [])]
        data["groups"] = [Group(**g) for g in data.get("groups", [])]
        data["detections"] = [Detection(**d) for d in data.get("detections", [])]
        return cls(**data)

    def active_group(self):
        return next((g for g in self.groups if g.id == self.active), None)


def overlap_metrics(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax+aw, bx+bw)-max(ax, bx)) * max(0, min(ay+ah, by+bh)-max(ay, by))
    union = aw*ah + bw*bh - intersection
    return intersection / max(union, 1e-9), intersection / max(min(aw*ah, bw*bh), 1e-9)


def near(a, b, overlap=0.45, proximity=0.22):
    iou, coverage = overlap_metrics(a, b)
    distance = hypot(a[0]+a[2]/2-b[0]-b[2]/2, a[1]+a[3]/2-b[1]-b[3]/2)
    return iou >= overlap or coverage >= 0.8 or distance < proximity * min(a[2], a[3], b[2], b[3])


class ConflictEngine:
    def pairs(self, project):
        """Sweep on X, within a page; hidden groups still participate."""
        allowed = {tuple(sorted(pair)) for pair in project.allowed}
        by_page = {}
        for d in project.detections:
            if d.decision != "rejected":
                by_page.setdefault(d.page, []).append(d)
        result = []
        for detections in by_page.values():
            ordered = sorted(detections, key=lambda d: d.rect[0])
            for i, a in enumerate(ordered):
                for b in ordered[i+1:]:
                    if b.rect[0] > a.rect[0]+a.rect[2]+project.proximity*min(a.rect[2:]):
                        break
                    pair = tuple(sorted((a.id, b.id)))
                    if pair not in allowed and near(a.rect, b.rect, project.overlap, project.proximity):
                        result.append(pair)
        return result

    def components(self, project):
        components = []
        for a, b in self.pairs(project):
            merged = {a, b}
            remaining = []
            for component in components:
                if component & merged:
                    merged |= component
                else:
                    remaining.append(component)
            components = remaining + [merged]
        return components


def counts(project, group, conflict_ids):
    ds = [d for d in project.detections if d.group == group and d.decision != "rejected"]
    return (sum(d.decision == "accepted" and d.id not in conflict_ids for d in ds),
            sum(d.decision == "review" and d.id not in conflict_ids for d in ds),
            sum(d.id in conflict_ids for d in ds))
