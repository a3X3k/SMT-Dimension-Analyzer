"""Offscreen visual workspace tests: overlay geometry and alignment invalidation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QGraphicsPathItem
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
        paths=[i for i in w.scene.items() if isinstance(i,QGraphicsPathItem)]
        assert len(paths)==1
        path=paths[0].path()
        assert path.elementCount()==2
        start=path.elementAt(0); end=path.elementAt(1)
        assert abs((end.x-start.x)**2+(end.y-start.y)**2-1.0)<1e-7
        return start
    initial=gerber_line()
    assert abs(initial.x-25.4)<1e-8
    assert abs(initial.y+50.8)<1e-8
    w.set_alignment(1.0,-2.0,0)
    shifted=gerber_line()
    assert abs(shifted.x-26.4)<1e-8
    assert abs(shifted.y+48.8)<1e-8
    assert cad[0].x==25.4 and cad[0].y==50.8
    w.set_alignment(0,0,90)
    rotated=gerber_line()
    assert abs(rotated.x+50.8)<1e-8
    assert abs(rotated.y+25.4)<1e-8
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


def test_both_origin_crosshairs_render_and_follow_independent_positions():
    _app()
    w=PCBWorkspace()
    w.set_crosshair_origins(10,20,30,40)
    labels=[i.text() for i in w.scene.items() if hasattr(i,"text")]
    assert "CAD origin (0,0)" in labels
    assert "Gerber origin (0,0)" in labels
    assert len([i for i in w.scene.items() if i.__class__.__name__=="QGraphicsLineItem"])==4
    cad=next(i for i in w.scene.items() if hasattr(i,"text") and i.text()=="CAD origin (0,0)")
    gerber=next(i for i in w.scene.items() if hasattr(i,"text") and i.text()=="Gerber origin (0,0)")
    assert abs(cad.pos().x()-11)<1e-8 and abs(cad.pos().y()+19)<1e-8
    assert abs(gerber.pos().x()-31)<1e-8 and abs(gerber.pos().y()+39)<1e-8
    w.set_alignment(5,-2,0)
    gerber=next(i for i in w.scene.items() if hasattr(i,"text") and i.text()=="Gerber origin (0,0)")
    assert abs(gerber.pos().x()-36)<1e-8 and abs(gerber.pos().y()+37)<1e-8
    w.close()


def test_top_and_bottom_origin_and_alignment_settings_are_independent():
    _app()
    w=MainWindow()
    w.cad_origin_x.setValue(12)
    w.cad_origin_y.setValue(22)
    w.gerber_origin_x.setValue(32)
    w.gerber_origin_y.setValue(42)
    w.xoff.setValue(1.25)
    w.side_selector.setCurrentText("Bottom")
    assert w.cad_origin_x.value()==0 and w.gerber_origin_x.value()==0
    assert w.xoff.value()==0
    w.cad_origin_x.setValue(13)
    w.cad_origin_y.setValue(23)
    w.gerber_origin_x.setValue(33)
    w.gerber_origin_y.setValue(43)
    w.xoff.setValue(-2.5)
    w.side_selector.setCurrentText("Top")
    assert (w.cad_origin_x.value(),w.cad_origin_y.value())==(12,22)
    assert (w.gerber_origin_x.value(),w.gerber_origin_y.value())==(32,42)
    assert w.xoff.value()==1.25
    assert w.workspace.cad_origin==(12,22)
    assert w.workspace.gerber_origin==(32,42)
    w.side_selector.setCurrentText("Bottom")
    assert (w.cad_origin_x.value(),w.cad_origin_y.value())==(13,23)
    assert (w.gerber_origin_x.value(),w.gerber_origin_y.value())==(33,43)
    assert w.xoff.value()==-2.5
    w.close()


def test_large_gerber_layer_uses_one_graphics_path():
    _app()
    w=PCBWorkspace()
    doc=GerberDocument(path=Path("large.gto"),layer="Top Silkscreen",
        primitives=[Primitive(kind="line",x=float(i),y=1,x2=float(i)+0.5,y2=1)
                    for i in range(5000)])
    w.set_data(gerbers=[doc])
    assert len([i for i in w.scene.items() if isinstance(i,QGraphicsPathItem)])==1
    w.set_alignment(1,2,0)
    assert len([i for i in w.scene.items() if isinstance(i,QGraphicsPathItem)])==1
    w.close()


def test_gerber_layers_move_together_from_layers_tab():
    _app()
    w=MainWindow()
    w.gerber_group_x.setValue(-1.5)
    w.gerber_group_y.setValue(2.25)
    assert w.xoff.value()==-1.5 and w.yoff.value()==2.25
    assert w.workspace.dx==-1.5 and w.workspace.dy==2.25
    assert w.workspace._tx(10,20)==(8.5,22.25)
    w.xoff.setValue(3.0)
    assert w.gerber_group_x.value()==3.0
    assert w.layer_table.columnCount()==3
    w.close()
