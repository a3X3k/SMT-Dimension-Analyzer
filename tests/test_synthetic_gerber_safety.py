"""Synthetic negative cases protect against false Gerber body dimensions."""
from models import CadRecord, UniquePart
from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_project_dimensions


def _fixture(tmp_path, commands):
    path = tmp_path / "safety.gto"
    path.write_text(
        "%FSLAX24Y24*%%MOMM*%%ADD10C,0.100*%"
        "D10*" + commands + "M02*",
        encoding="utf-8",
    )
    return parse_gerber(path)


def _measure(doc, cad):
    part = UniquePart(mpn="SYNTH-1", refs=["U1"], representative_ref="U1")
    return derive_project_dimensions([part], cad, [doc])["SYNTH-1"]


def test_disconnected_silkscreen_strokes_do_not_create_body(tmp_path):
    doc = _fixture(
        tmp_path,
        "X080000Y190000D02*X090000Y190000D01*"
        "X110000Y190000D02*X120000Y190000D01*",
    )
    result = _measure(doc, [CadRecord(ref="U1", x=10, y=20, rotation=0, layer="Top")])
    assert result.length_mm is None and result.width_mm is None
    assert result.accepted is False


def test_body_at_unrelated_location_is_not_borrowed(tmp_path):
    doc = _fixture(
        tmp_path,
        "X300000Y300000D02*X340000Y300000D01*"
        "X340000Y320000D01*X300000Y320000D01*"
        "X300000Y300000D01*",
    )
    result = _measure(doc, [CadRecord(ref="U1", x=10, y=20, rotation=0, layer="Top")])
    assert result.length_mm is None and result.width_mm is None
    assert result.accepted is False


def test_neighbor_center_inside_outline_rejects_ambiguous_body(tmp_path):
    doc = _fixture(
        tmp_path,
        "X080000Y190000D02*X120000Y190000D01*"
        "X120000Y210000D01*X080000Y210000D01*"
        "X080000Y190000D01*",
    )
    cad = [
        CadRecord(ref="U1", x=10, y=20, rotation=0, layer="Top"),
        CadRecord(ref="U2", x=11, y=20, rotation=0, layer="Top"),
    ]
    result = _measure(doc, cad)
    assert result.length_mm is None and result.width_mm is None
    assert result.accepted is False
