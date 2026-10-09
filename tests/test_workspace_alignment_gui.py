"""Offscreen visual workspace tests: overlay geometry and alignment invalidation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QGraphicsLineItem
from models import CadRecord,UniquePart
from parsers.gerber_parser import GerberDocument,Primitive
from dimensions.gerber_dimension import GerberDimensionResult
from ui.pcb_workspace import PCBWorkspace
from ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_overlay_uses_mm_coordinates_and_alignment():
    _app()
    w=PCBWorkspace()
    cad=[CadRecord(ref="R1",x=25.4,y=50.8,rotation=90)]
    doc=GerberDocument(path=Path("top.gto"),layer="Top Silkscreen",
        primitives=[Primitive(kind="line",x=25.4,y=50.8,x2=26.4,y2=50.8)])
    w.set_data(cad=cad,gerbers=[doc])
    def gerber_line():
        lines=[i for i in w.scene.items() if isinstance(i,QGraphicsLineItem)]
        return next(i.line() for i in lines if abs(i.line().length()-1.0)<1e-7)
    initial=gerber_line()
    assert abs(initial.x1()-25.4)<1e-8
    assert abs(initial.y1()+50.8)<1e-8
    w.set_alignment(1.0,-2.0,0)
    shifted=gerber_line()
    assert abs(shifted.x1()-26.4)<1e-8
    assert abs(shifted.y1()+48.8)<1e-8
    assert cad[0].x==25.4 and cad[0].y==50.8
    w.set_alignment(0,0,90)
    rotated=gerber_line()
    assert abs(rotated.x1()+50.8)<1e-8
    assert abs(rotated.y1()+25.4)<1e-8
    w.close()


def test_alignment_change_requires_fresh_analysis():
    _app()
    w=MainWindow()
    part=UniquePart("MPN",["R1"],"R1")
    w.state.unique_parts=[part]
    w.state.dimension_results={"MPN":GerberDimensionResult(ref="R1",length_mm=2,width_mm=1)}
    w._populate()
    w.xoff.setValue(0.01)
    assert w.state.dimension_results=={}
    assert w.state.shape_models=={}
    assert w.table.item(0,10).text()=="RE-ANALYZE AFTER ALIGNMENT"
    w.close()


def test_layer_reassignment_invalidates_visible_review():
    _app()
    w=MainWindow()
    part=UniquePart("MPN",["R1"],"R1")
    w.state.unique_parts=[part]
    w.state.dimension_results={"MPN":GerberDimensionResult(ref="R1",length_mm=2,width_mm=1,accepted=True)}
    w.state.shape_models={"MPN":object()}
    w._populate()
    w.table.setItem(0,4,__import__("PySide6.QtWidgets",fromlist=["QTableWidgetItem"]).QTableWidgetItem("2.0"))
    doc=GerberDocument(path=Path("top.gto"),layer="Top Silkscreen")
    w.state.gerber_documents=[doc]
    w._assign_layer(doc,"Other / Ignore")
    assert doc.layer=="Other / Ignore"
    assert w.state.dimension_results=={}
    assert w.state.shape_models=={}
    assert w.table.item(0,10).text()=="RE-ANALYZE AFTER LAYER CHANGE"
    assert w.table.item(0,4).text()==""
    assert "Re-analyze" in w.review_info.text()
    w.close()
