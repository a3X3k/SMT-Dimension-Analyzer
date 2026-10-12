"""Synthetic, reproducible CAD -> BOM -> Gerber -> Excel/TXT acceptance smoke."""
from openpyxl import load_workbook

from parsers.cad_parser import parse_cad
from parsers.bom_parser import parse_bom, group_unique_parts
from matching.bom_cad_matcher import match_bom_to_cad
from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import GerberDimensionResult
from dimensions.shape_model import build_shape_model
from export.excel_export import export_excel
from export.text_export import export_text


def test_synthetic_cad_bom_gerber_to_reviewable_exports(tmp_path):
    cad_file = tmp_path / "placements.csv"
    cad_file.write_text(
        "Reference,X location,Y location,Angle\nU1,10,20,90\nR1,15,20,0\n",
        encoding="utf-8",
    )
    bom_file = tmp_path / "bom.csv"
    bom_file.write_text("Reference,Part Number\nU1,CHIP-A\nR1,RES-B\n", encoding="utf-8")
    gerber_file = tmp_path / "synthetic.gto"
    gerber_file.write_text(
        "%FSLAX24Y24*%%MOMM*%%ADD10C,0.100*%"
        "D10*X009000Y019000D02*X011000Y019000D01*"
        "X011000Y021000D01*X009000Y021000D01*"
        "X009000Y019000D01*M02*",
        encoding="utf-8",
    )

    cad = parse_cad(cad_file)
    bom = parse_bom(bom_file)
    stats = match_bom_to_cad(cad, bom)
    assert stats["matched"] == {"U1", "R1"}
    assert not stats["bom_only"] and not stats["cad_only"]
    assert {c.ref: c.mpn for c in cad} == {"U1": "CHIP-A", "R1": "RES-B"}

    gerber = parse_gerber(gerber_file)
    assert gerber.layer == "Top Silkscreen"
    assert gerber.primitives
    assert gerber.bounds() is not None

    parts = group_unique_parts(bom)
    dimensions = {
        "CHIP-A": GerberDimensionResult(
            ref="U1", length_mm=2.0, width_mm=2.0,
            gerber_x=10, gerber_y=20,
            source="Synthetic Gerber Silkscreen - Proposed",
            accepted=False,
        )
    }
    shapes = {p.mpn: build_shape_model(p, dimension=dimensions.get(p.mpn)) for p in parts}
    excel_path = tmp_path / "acceptance.xlsx"
    text_path = tmp_path / "acceptance.txt"
    export_excel(excel_path, parts, {c.ref: c for c in cad}, dimensions, shapes)
    export_text(text_path, parts, dimensions, shapes)
    workbook = load_workbook(excel_path, data_only=True)
    assert workbook.sheetnames == ["Shape Dimensions", "Location Verification", "Processing Log"]
    header = [cell.value for cell in workbook["Shape Dimensions"][1]]
    rows = [dict(zip(header, row)) for row in workbook["Shape Dimensions"].iter_rows(min_row=2, values_only=True)]
    assert len(rows) == 2
    chip = next(row for row in rows if row["PN / MPN"] == "CHIP-A")
    assert chip["User Accepted"] == "NO"
    assert chip["Body Length (mm)"] is None
    location = workbook["Location Verification"]
    loc_header = [c.value for c in location[1]]
    loc_rows = [dict(zip(loc_header, row)) for row in location.iter_rows(min_row=2, values_only=True)]
    assert any(row["Rotation Check"] in ("NOT AVAILABLE", "NOT VERIFIED") for row in loc_rows)
    assert text_path.exists() and "CHIP-A" in text_path.read_text(encoding="utf-8")
