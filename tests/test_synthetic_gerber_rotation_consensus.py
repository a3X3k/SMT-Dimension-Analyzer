"""Synthetic rotation and same-MPN consensus integration regressions."""
import pytest

from models import CadRecord, UniquePart
from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_project_dimensions


def _doc(tmp_path, name, rectangles):
    path = tmp_path / name
    commands = []
    for cx, cy, half_x, half_y in rectangles:
        x1, x2 = int(round((cx-half_x)*10000)), int(round((cx+half_x)*10000))
        y1, y2 = int(round((cy-half_y)*10000)), int(round((cy+half_y)*10000))
        commands.extend([
            f"X{x1:06d}Y{y1:06d}D02*",
            f"X{x2:06d}Y{y1:06d}D01*",
            f"X{x2:06d}Y{y2:06d}D01*",
            f"X{x1:06d}Y{y2:06d}D01*",
            f"X{x1:06d}Y{y1:06d}D01*",
        ])
    path.write_text("%FSLAX24Y24*%%MOMM*%%ADD10C,0.100*%D10*" + "".join(commands) + "M02*", encoding="utf-8")
    return parse_gerber(path)


def test_90_degree_rotated_outline_keeps_long_side_as_length(tmp_path):
    doc = _doc(tmp_path, "rotated.gto", [(10, 20, 1, 2)])
    cad = [CadRecord(ref="U1", x=10, y=20, rotation=90, layer="Top")]
    part = UniquePart(mpn="ROT-1", refs=["U1"], representative_ref="U1")
    result = derive_project_dimensions([part], cad, [doc])["ROT-1"]
    assert result.length_mm == pytest.approx(4.1, abs=0.001)
    assert result.width_mm == pytest.approx(2.1, abs=0.001)
    assert result.accepted is False
    assert result.height_mm is None


def test_three_same_mpn_closed_outlines_produce_consensus(tmp_path):
    doc = _doc(tmp_path, "three.gto", [(10, 20, 2, 1), (30, 20, 2, 1), (50, 20, 2, 1)])
    cad = [CadRecord(ref=f"U{i+1}", x=x, y=20, rotation=0, layer="Top") for i, x in enumerate((10, 30, 50))]
    part = UniquePart(mpn="SAME-1", refs=["U1", "U2", "U3"], representative_ref="U1")
    result = derive_project_dimensions([part], cad, [doc])["SAME-1"]
    assert result.length_mm == pytest.approx(4.1, abs=0.001)
    assert result.width_mm == pytest.approx(2.1, abs=0.001)
    assert "3/3" in result.remarks
    assert result.confidence == "HIGH"
    assert result.accepted is False
