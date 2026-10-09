"""Regression tests for CAD mil-to-mm and Gerber alignment coordinate frames."""
import pytest
from parsers.cad_parser import parse_cad
from dimensions.gerber_dimension import _forward, _inverse


@pytest.mark.parametrize("mil_x,mil_y",[
    (1000,2000),(-500,250),(0,0),(2312.31,-34.42)
])
def test_mil_placement_is_in_same_mm_frame_as_gerber(tmp_path,mil_x,mil_y):
    p=tmp_path/"CAD.txt"
    p.write_text(f"refdes\\tsymbol_x\\tsymbol_y\\trotation\\tmirror\\n"
                 f"R1\\t{mil_x}\\t{mil_y}\\t90\\tTop\\n")
    cad=parse_cad(p,units="mils")[0]
    gx,gy=mil_x*.0254,mil_y*.0254
    assert cad.x==pytest.approx(gx,abs=1e-9)
    assert cad.y==pytest.approx(gy,abs=1e-9)
    assert _inverse(gx,gy,0,0,0)==pytest.approx((cad.x,cad.y),abs=1e-9)


@pytest.mark.parametrize("angle",[-90,0,45,90,180])
def test_gerber_alignment_inverse_matches_overlay(angle):
    point=(25.4,-12.7)
    dx,dy=3.125,-4.5
    overlay=_forward(*point,dx,dy,angle)
    recovered=_inverse(*overlay,dx,dy,angle)
    assert recovered==pytest.approx(point,abs=1e-9)


def test_cad_rotation_is_not_scaled_by_mils_conversion(tmp_path):
    p=tmp_path/"CAD.txt"
    p.write_text("refdes\\tsymbol_x\\tsymbol_y\\trotation\\tmirror\\n"
                 "U1\\t1000\\t2000\\t225\\tBottom\\n")
    cad=parse_cad(p,units="mils")[0]
    assert cad.rotation==225
    assert cad.layer=="Bottom"
