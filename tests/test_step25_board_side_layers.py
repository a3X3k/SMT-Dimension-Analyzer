"""Step 25: top/bottom PCB workspace isolation and independent layer visibility."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from pathlib import Path
from models import CadRecord
from parsers.gerber_parser import GerberDocument, Primitive
from ui.pcb_workspace import PCBWorkspace


def test_board_side_filters_cad_and_gerber():
    app=QApplication.instance() or QApplication([])
    view=PCBWorkspace()
    top=GerberDocument(Path("top.gto"),"Top Silkscreen",primitives=[
        Primitive("line",0,0,2,0)])
    bottom=GerberDocument(Path("bottom.gbo"),"Bottom Silkscreen",primitives=[
        Primitive("line",0,0,3,0)])
    view.set_data(cad=[
        CadRecord("U1",x=1,y=1,layer="Top"),
        CadRecord("U2",x=2,y=2,layer="Bottom"),
    ],gerbers=[top,bottom])
    assert view._cad_on_side(view.cad[0])
    assert not view._cad_on_side(view.cad[1])
    assert view._gerber_on_side(top)
    assert not view._gerber_on_side(bottom)
    view.set_board_side("Bottom")
    assert not view._cad_on_side(view.cad[0])
    assert view._cad_on_side(view.cad[1])
    assert not view._gerber_on_side(top)
    assert view._gerber_on_side(bottom)
    view.set_layer_visible(bottom.path,False)
    assert str(bottom.path) not in view.visible_layers
    view.set_board_side("Top")
    view.set_board_side("Bottom")
    assert str(bottom.path) not in view.visible_layers
