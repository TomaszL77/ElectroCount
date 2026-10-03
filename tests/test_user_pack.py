"""Optional local real-document integration suite; never used as training data."""
import os
from pathlib import Path
import pytest
from electrocount.main_window import MainWindow
from electrocount.domain import Group,Detection
from electrocount.project_manager import ProjectManager
from test_ui import wait
