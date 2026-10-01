from models import UniquePart, CadRecord
from dimensions.gerber_dimension import GerberDimensionResult
from dimensions.shape_model import build_shape_model, recognize_package_family
from lookup.mpn_lookup import MpnData

def test_package_family_recognition():
    assert recognize_package_family("VQFN-32")[0] == "QFN/DFN"
    assert recognize_package_family("BGA")[0] == "BGA"
    assert recognize_package_family("")[0] == "UNKNOWN"

def test_gerber_paste_never_becomes_physical_pin_data():
    part=UniquePart("ABC",["U1"],"U1")
    dim=GerberDimensionResult(ref="U1",length_mm=4.0,width_mm=4.0,pad_count=32,pitch_mm=0.5,pad_rows=4,pad_columns=8)
    lookup=MpnData(query="ABC",package_type="VQFN-32",status="NOT FOUND")
    s=build_shape_model(part,dimension=dim,lookup=lookup)
    assert s.pin_count is None and s.pin_pitch_mm is None
    assert s.bga_rows is None and s.bga_columns is None and s.ball_pitch_mm is None

def test_exact_lookup_physical_data_has_priority():
    part=UniquePart("ABC",["U1"],"U1")
    dim=GerberDimensionResult(ref="U1",length_mm=5.0,width_mm=5.0,pad_count=40,pitch_mm=0.4)
    lookup=MpnData(query="ABC",matched_mpn="ABC",package_type="QFN",body_length_mm=4.0,body_width_mm=4.0,pin_count=32,pin_pitch_mm=0.5,source="Manufacturer",confidence="HIGH",status="EXACT MPN MATCH")
    s=build_shape_model(part,dimension=dim,lookup=lookup)
    assert (s.body_length_mm,s.body_width_mm)==(4.0,4.0)
    assert (s.pin_count,s.pin_pitch_mm)==(32,0.5)

def test_odb_body_fills_before_gerber():
    part=UniquePart("ABC",["U1"],"U1")
    cad=CadRecord("U1",raw={"source":"ODB++","package":"QFN","length_mm":4.0,"width_mm":3.0,"height_mm":1.0})
    dim=GerberDimensionResult(ref="U1",length_mm=5.0,width_mm=5.0)
    s=build_shape_model(part,cad=cad,dimension=dim)
    assert (s.body_length_mm,s.body_width_mm,s.body_height_mm)==(4.0,3.0,1.0)
    assert s.source=="ODB++"
