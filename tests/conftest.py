import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas
from PySide6.QtWidgets import QApplication


def make_pdf(path):
    c = canvas.Canvas(str(path), pagesize=(900, 650))
    c.setTitle("ElectroCount - syntetyczny rzut testowy")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 604, "ELECTROCOUNT / RZUT TESTOWY")
    c.setFont("Helvetica", 10)
    c.drawString(40, 582, "Dokument syntetyczny. 12 opraw, 4 gniazda. Nie jest dokumentacja wykonawcza.")
    c.setStrokeColorRGB(0.65, 0.7, 0.75)
    c.setLineWidth(2)
    c.rect(40, 80, 810, 465)
    for x in (310, 580):
        c.line(x, 80, x, 545)
    c.line(40, 310, 850, 310)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    positions = [(110+col*180, 180+row*140) for row in range(3) for col in range(4)]
    for index, (x, y) in enumerate(positions):
        c.rect(x, y, 28, 12)
        c.line(x, y, x+28, y+12)
        c.line(x+28, y, x, y+12)
        c.setFont("Helvetica", 9)
        c.drawString(x+35, y+3, "A1" if index < 8 else "QP14")
    for x in (170, 350, 530, 710):
        c.circle(x, 110, 7)
        c.line(x-3, 103, x-3, 117)
        c.line(x+3, 103, x+3, 117)
    c.showPage()
    c.setPageRotation(90)
    c.setFont("Helvetica", 18)
    c.drawString(50, 100, "STRONA OBROCONA / TEST")
    c.rect(90, 150, 28, 12)
    c.save()
    return {"page": 0, "rect": [106, 650-192-4, 36, 20]}


@pytest.fixture
def document(tmp_path):
    path = tmp_path/"test.pdf"
    template = make_pdf(path)
    return path, template


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])



@pytest.fixture(autouse=True)
def isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ELECTROCOUNT_SKIP_PROFILE","1")
    monkeypatch.setenv("ELECTROCOUNT_DATA_DIR",str(tmp_path/"app-data"))
    monkeypatch.setenv("ELECTROCOUNT_SETTINGS_PATH",str(tmp_path/"settings.ini"))
