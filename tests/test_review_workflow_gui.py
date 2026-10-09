import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from models import UniquePart
from dimensions.gerber_dimension import GerberDimensionResult


def test_manual_review_accept_reject_and_edit():
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    part=UniquePart("P123",["R1"],"R1")
    dim=GerberDimensionResult(ref="R1",length_mm=2.0,width_mm=1.0,
        source="Gerber Silkscreen - Proposed",accepted=False)
    w.state.unique_parts=[part]
    w.state.dimension_results={"P123":dim}
    w._populate()
    w.table.selectRow(0)
    w._accept_dimension()
    assert dim.accepted and dim.status=="USER ACCEPTED"
    w._reject_dimension()
    assert not dim.accepted and dim.status=="MANUAL REVIEW"
    w.manual_l.setValue(3.5)
    w.manual_w.setValue(1.75)
    w._apply_adjust()
    assert (dim.length_mm,dim.width_mm)==(3.5,1.75)
    assert dim.source=="USER - Manual Body Adjustment"
    assert dim.manual_body_override
    assert not dim.accepted
    w._accept_dimension()
    assert dim.accepted and dim.status=="USER ACCEPTED"
    w.close()
