"""Real KiCad 4.6 silkscreen format and CAD/BOM/Gerber/export integration."""
from openpyxl import load_workbook
from models import UniquePart
from parsers.cad_parser import parse_cad
from parsers.bom_parser import parse_bom,group_unique_parts
from matching.bom_cad_matcher import match_bom_to_cad
from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_project_dimensions
from dimensions.shape_model import build_project_shapes
from export.excel_export import export_excel
from export.text_export import export_text


def test_kicad_46_silkscreen_sample(tmp_path):
    # Header and coordinate format taken from an uploaded KiCad 10 .gto file.
    p=tmp_path/"AIS140_Tracker_v2_opt_p6-F_Silkscreen.gto"
    p.write_text("%TF.GenerationSoftware,KiCad,Pcbnew,10.0.4*%\n"
        "%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n"
        "%ADD10C,0.200000*%\nD10*\n"
        "X86285718Y-2754957D02*\nX87000004Y-2754957D01*\nM02*\n")
    doc=parse_gerber(p)
    assert doc.layer=="Top Silkscreen"
    assert doc.units=="mm"
    assert len(doc.primitives)==1
    assert doc.primitives[0].x==86.285718
    assert doc.primitives[0].y==-2.754957
    assert doc.primitives[0].x2==87.000004


def test_cad_bom_gerber_to_excel_and_txt(tmp_path):
    cad_path=tmp_path/"CAD.txt"
    cad_path.write_text("refdes\tsymbol_x\tsymbol_y\trotation\tmirror\n"
        "R1\t1000\t2000\t90\tTop\n")
    bom_path=tmp_path/"BOM.txt"
    bom_path.write_text("RefDes\tMPN\nR1\tMPN-100\n")
    gerber_path=tmp_path/"board.gto"
    gerber_path.write_text("%FSLAX24Y24*%%MOMM*%%ADD10C,0.2*%"
        "D10*X025400Y050800D02*X035400Y050800D01*M02*")
    cad=parse_cad(cad_path,units="mils")
    bom=parse_bom(bom_path)
    stats=match_bom_to_cad(cad,bom)
    assert stats["matched"]=={"R1"}
    assert cad[0].mpn=="MPN-100"
    parts=group_unique_parts(bom)
    docs=[parse_gerber(gerber_path)]
    assert docs[0].layer=="Top Silkscreen"
    assert docs[0].primitives
    results=derive_project_dimensions(parts,cad,docs,alignment=(0,0,0))
    shapes=build_project_shapes(parts,cad,results,{})
    x=tmp_path/"dimensions.xlsx"
    t=tmp_path/"dimensions.txt"
    export_excel(x,parts,{c.ref:c for c in cad},results,shapes)
    export_text(t,parts,results,shapes)
    assert x.is_file() and t.is_file()
    wb=load_workbook(x,data_only=True)
    assert wb["Shape Dimensions"]["A2"].value=="MPN-100"
    assert wb["Processing Log"]["A2"].value=="MPN-100"
    assert t.read_text().splitlines()[1].startswith("MPN-100\tR1\t")
