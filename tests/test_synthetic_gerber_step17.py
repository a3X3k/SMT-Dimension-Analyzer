"""Step 17: conflicting same-MPN measurements and CAD/Gerber alignment."""
import pytest

from models import CadRecord, UniquePart
from dimensions.gerber_dimension import derive_project_dimensions
from parsers.gerber_parser import parse_gerber


def _gerber(tmp_path, outlines):
    path = tmp_path / "step17.gto"
    segments = []
    for cx, cy, half_width, half_height in outlines:
        x1, x2 = round((cx-half_width)*10000), round((cx+half_width)*10000)
        y1, y2 = round((cy-half_height)*10000), round((cy+half_height)*10000)
        segments.extend([
            f"X{x1:06d}Y{y1:06d}D02*",
            f"X{x2:06d}Y{y1:06d}D01*",
            f"X{x2:06d}Y{y2:06d}D01*",
            f"X{x1:06d}Y{y2:06d}D01*",
            f"X{x1:06d}Y{y1:06d}D01*",
        ])
    path.write_text("%FSLAX24Y24*%%MOMM*%%ADD10C,0.100*%D10*" + "".join(segments) + "M02*", encoding="utf-8")
    return parse_gerber(path)


def test_disagreeing_same_mpn_outlines_stay_low_confidence(tmp_path):
    doc = _gerber(tmp_path, [(10, 20, 2, 1), (30, 20, 3, 1)])
    cad = [CadRecord(ref="U1", x=10, y=20, rotation=0, layer="Top"),
           CadRecord(ref="U2", x=30, y=20, rotation=0, layer="Top")]
    part = UniquePart(mpn="CONFLICT-1", refs=["U1", "U2"], representative_ref="U1")
    result = derive_project_dimensions([part], cad, [doc])["CONFLICT-1"]
    assert result.length_mm is not None
    assert result.confidence == "LOW"
    assert "disagree" in result.remarks.lower()
    assert result.accepted is False
    assert result.height_mm is None


def test_translation_alignment_recovers_original_gerber_measurement(tmp_path):
    doc = _gerber(tmp_path, [(10, 20, 2, 1)])
    cad = [CadRecord(ref="U1", x=13, y=18, rotation=0, layer="Top")]
    part = UniquePart(mpn="ALIGN-1", refs=["U1"], representative_ref="U1")
    missing = derive_project_dimensions([part], cad, [doc], alignment=(0, 0, 0))["ALIGN-1"]
    aligned = derive_project_dimensions([part], cad, [doc], alignment=(3, -2, 0))["ALIGN-1"]
    assert missing.length_mm is None
    assert aligned.length_mm == pytest.approx(4.1, abs=0.001)
    assert aligned.width_mm == pytest.approx(2.1, abs=0.001)
    assert aligned.gerber_x == pytest.approx(13)
    assert aligned.gerber_y == pytest.approx(18)
    assert aligned.accepted is False


def test_rotation_alignment_recovers_body_without_automatic_acceptance(tmp_path):
    doc = _gerber(tmp_path, [(10, 20, 2, 1)])
    # Rotate Gerber coordinate (10,20) by +90 degrees -> CAD (-20,10).
    cad = [CadRecord(ref="U1", x=-20, y=10, rotation=90, layer="Top")]
    part = UniquePart(mpn="ROTALIGN-1", refs=["U1"], representative_ref="U1")
    result = derive_project_dimensions([part], cad, [doc], alignment=(0, 0, 90))["ROTALIGN-1"]
    assert result.length_mm == pytest.approx(4.1, abs=0.001)
    assert result.width_mm == pytest.approx(2.1, abs=0.001)
    assert result.gerber_x == pytest.approx(-20)
    assert result.gerber_y == pytest.approx(10)
    assert result.accepted is False
