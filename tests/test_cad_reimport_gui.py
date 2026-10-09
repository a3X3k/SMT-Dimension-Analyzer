"""Regression: replacing a board must invalidate every dependent dataset."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog
from models import BomRecord, CadRecord, UniquePart
from parsers.gerber_parser import GerberDocument, Primitive
from dimensions.gerber_dimension import GerberDimensionResult
from ui.main_window import MainWindow


def test_cad_reimport_discards_previous_board_state():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    old = CadRecord(ref="R1", x=10, y=20, rotation=0)
    window.state.cad_records = [old]
    window.state.cad_path = Path("old.csv")
    window.state.bom_path = Path("old-bom.csv")
    window.state.bom_records = [BomRecord(ref="R1", mpn="OLD")]
    window.state.unique_parts = [UniquePart("OLD", ["R1"], "R1")]
    window.state.gerber_paths = [Path("old.gto")]
    window.state.gerber_documents = [GerberDocument(path=Path("old.gto"), layer="Top Silkscreen",
        primitives=[Primitive(kind="line", x=10, y=20, x2=11, y2=20)])]
    window.state.dimension_results = {"OLD": GerberDimensionResult(ref="R1", length_mm=3, accepted=True)}
    window.state.shape_models = {"OLD": object()}
    window.state.mpn_lookup_results = {"OLD": object()}
    window.state.manual_gerber_matches = {"R1": "old"}
    window.workspace.set_data(cad=[old], gerbers=window.state.gerber_documents)
    window._populate()
    window.xoff.setValue(2)
    window.yoff.setValue(-3)
    window.aoff.setValue(10)
    new = CadRecord(ref="C1", x=1, y=2, rotation=90)
    with patch.object(QFileDialog, "getOpenFileName", return_value=("new.csv", "")), \
         patch("ui.main_window.inspect_cad", return_value=(type("DF", (), {"columns": ["Ref", "X", "Y", "Rotation"]})(), {})), \
         patch("ui.mapping_dialog.ColumnMappingDialog") as dialog, \
         patch.object(QInputDialog, "getItem", return_value=("Millimetres (mm)", True)), \
         patch("ui.main_window.parse_cad", return_value=[new]):
        dialog.return_value.exec.return_value = QDialog.Accepted
        dialog.return_value.mapping.return_value = {}
        window.import_cad()
    assert window.state.cad_path == Path("new.csv")
    assert window.state.cad_records == [new]
    assert window.state.bom_path is None and window.state.bom_records == []
    assert window.state.unique_parts == []
    assert window.state.gerber_paths == [] and window.state.gerber_documents == []
    assert window.state.dimension_results == {} and window.state.shape_models == {}
    assert window.state.mpn_lookup_results == {} and window.state.manual_gerber_matches == {}
    assert window.dx == window.dy == window.da == 0
    assert window.xoff.value() == window.yoff.value() == window.aoff.value() == 0
    assert window.table.rowCount() == 0 and window.layer_table.rowCount() == 0
    assert not window.analyze_top.isEnabled() and not window.export_top.isEnabled()
    assert window.bom_btn.isEnabled() and window.gerber_btn.isEnabled()
    assert "not loaded" in window.bom_info.text()
    assert "not loaded" in window.gerber_info.text()
    assert window.tabs.currentIndex() == 0
    window.close()
