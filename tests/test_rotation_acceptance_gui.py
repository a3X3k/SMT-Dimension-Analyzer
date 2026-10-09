"""Acceptance guards: CAD rotation is not independent Gerber angle evidence."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication
from models import CadRecord, UniquePart
from dimensions.gerber_dimension import GerberDimensionResult
from dimensions.shape_model import build_shape_model
from export.excel_export import export_excel
from ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_cad_angle_does_not_imply_verified_rotation(tmp_path):
    part = UniquePart("MPN-ROT", ["U1"], "U1")
    cad = {"U1": CadRecord(ref="U1", x=10, y=20, rotation=90)}
    dimension = GerberDimensionResult(
        ref="U1", length_mm=3, width_mm=2,
        gerber_x=10, gerber_y=20, source="Gerber Silkscreen - Proposed",
        accepted=True,
    )
    out = tmp_path / "rotation.xlsx"
    export_excel(out, [part], cad, {"MPN-ROT": dimension},
                 {"MPN-ROT": build_shape_model(part, dimension=dimension)})
    sheet = load_workbook(out, read_only=True, data_only=True)["Location Verification"]
    rows = list(sheet.values)
    record = dict(zip(rows[0], rows[1]))
    assert record["Rotation Check"] in ("NOT AVAILABLE", "NOT VERIFIED")
    assert record["Status"] == "POSITION PASS / ROTATION NOT VERIFIED"


def test_windows_gui_initial_acceptance_gates():
    _app()
    window = MainWindow()
    assert window.cad_btn.isEnabled()
    assert not window.bom_btn.isEnabled()
    assert not window.gerber_btn.isEnabled()
    assert not window.analyze_top.isEnabled()
    assert not window.export_top.isEnabled()
    assert "Import CAD" in window.next_step.text()
    window.state.cad_records = [CadRecord(ref="R1", x=1, y=2, rotation=90)]
    window._update_status()
    assert window.bom_btn.isEnabled()
    assert window.gerber_btn.isEnabled()
    assert not window.analyze_top.isEnabled()
    assert not window.export_top.isEnabled()
    window.close()
