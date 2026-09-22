"""Compatibility controller, no automatic hardware-dependent quality selection."""
from PySide6.QtCore import QObject,Signal
from .performance import PerformanceMode,execution_plan,ExecutionPlan

class PerformanceController(QObject):
    changed=Signal()
    notice=Signal(str)
    def __init__(self,settings,parent=None):
        super().__init__(parent)
        self.settings=settings;self.report={};self.process=None
        self.mode=PerformanceMode.AUTO;self.plan=execution_plan()
        self.state='Stały algorytm · CPU · bez doboru jakości do sprzętu'
    def set_mode(self,mode):
        self.plan=execution_plan();self.changed.emit()
    def apply_fallback(self,plan):
        self.plan=ExecutionPlan(**plan);self.changed.emit()
        self.notice.emit('Ograniczono pamięć podręczną. Jakość analizy pozostaje bez zmian.')
    def start(self,force=False): self.changed.emit()
    def close(self): pass
