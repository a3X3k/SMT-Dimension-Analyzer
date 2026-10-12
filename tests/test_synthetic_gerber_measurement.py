"""End-to-end synthetic Gerber geometry must drive measurements, not hardcoded dimensions."""
import pytest

from models import CadRecord, UniquePart
from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_project_dimensions


def test_closed_silkscreen_body_is_measured_and_requires_review(tmp_path):
    path = tmp_path / "body.gto"
    # 4 x 2 mm rectangular centreline outline, centred at (10, 20) mm.
    # Aperture stroke is 0.1 mm; measured body envelope is ~4.1 x 2.1 mm.
    path.write_text(
        "%FSLAX24Y24*%%MOMM*%%ADD10C,0.100*%"
        "D10*X080000Y190000D02*X120000Y190000D01*"
        "X120000Y210000D01*X080000Y210000D01*"
        "X080000Y190000D01*M02*",
        encoding="utf-8",
    )
    doc = parse_gerber(path)
    cad = [CadRecord(ref="U1", x=10, y=20, rotation=0, layer="Top")]
    parts = [UniquePart(mpn="CHIP-A", refs=["U1"], representative_ref="U1")]
    results = derive_project_dimensions(parts, cad, [doc])
    result = results["CHIP-A"]
    assert result.source == "Gerber Silkscreen - Proposed"
    assert result.length_mm == pytest.approx(4.1, abs=0.001)
    assert result.width_mm == pytest.approx(2.1, abs=0.001)
    assert result.gerber_x == pytest.approx(10.0)
    assert result.gerber_y == pytest.approx(20.0)
    assert result.accepted is False
    assert result.height_mm is None
    assert len(result.primitive_ids) == 4
