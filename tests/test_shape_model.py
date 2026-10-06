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


def test_exact_lookup_without_dimensions_does_not_claim_dimension_provenance():
    part=UniquePart("ABC",["U1"],"U1")
    lookup=MpnData(query="ABC",matched_mpn="ABC",manufacturer="Acme",package_type="QFN",source="DigiKey",source_url="https://example.invalid/product",confidence="HIGH",status="EXACT MPN MATCH")
    s=build_shape_model(part,lookup=lookup)
    assert s.manufacturer=="Acme" and s.package_type=="QFN"
    assert s.body_length_mm is None and s.body_width_mm is None
    assert s.source=="" and s.source_url=="" and s.confidence=="NONE"

def test_exact_lookup_metadata_does_not_mask_gerber_dimension_source():
    part=UniquePart("ABC",["U1"],"U1")
    lookup=MpnData(query="ABC",matched_mpn="ABC",package_type="QFN",source="DigiKey",confidence="HIGH",status="EXACT MPN MATCH")
    dim=GerberDimensionResult(ref="U1",length_mm=5.0,width_mm=4.0,source="Gerber Silkscreen - Proposed",confidence="MEDIUM")
    s=build_shape_model(part,dimension=dim,lookup=lookup)
    assert (s.body_length_mm,s.body_width_mm)==(5.0,4.0)
    assert s.source=="Gerber Silkscreen - Proposed" and s.confidence=="MEDIUM"

def test_mixed_lookup_and_odb_dimension_provenance_is_explicit():
    part=UniquePart("ABC",["U1"],"U1")
    lookup=MpnData(query="ABC",matched_mpn="ABC",body_height_mm=1.0,source="Manufacturer",confidence="HIGH",status="EXACT MPN MATCH")
    cad=CadRecord("U1",raw={"source":"ODB++","length_mm":4.0,"width_mm":3.0})
    s=build_shape_model(part,cad=cad,lookup=lookup)
    assert (s.body_length_mm,s.body_width_mm,s.body_height_mm)==(4.0,3.0,1.0)
    assert s.source=="Manufacturer + ODB++" and s.confidence=="HIGH"


def test_txt_export_hides_unaccepted_gerber_body_but_keeps_candidate(tmp_path):
    from export.text_export import export_text
    part=UniquePart("ABC",["U1"],"U1")
    dim=GerberDimensionResult(ref="U1",length_mm=5.0,width_mm=4.0,source="Gerber Silkscreen - Proposed",confidence="MEDIUM",accepted=False)
    s=build_shape_model(part,dimension=dim)
    out=tmp_path/"out.txt"
    export_text(out,[part],{"ABC":dim},{"ABC":s})
    headers,values=out.read_text().splitlines()
    row=dict(zip(headers.split("\t"),values.split("\t")))
    assert row["BODY_L_MM"]=="" and row["BODY_W_MM"]==""
    assert row["GERBER_L_MM"]=="5.0" and row["GERBER_W_MM"]=="4.0"
    assert row["USER_ACCEPTED"]=="NO"

def test_txt_export_promotes_accepted_gerber_body(tmp_path):
    from export.text_export import export_text
    part=UniquePart("ABC",["U1"],"U1")
    dim=GerberDimensionResult(ref="U1",length_mm=5.0,width_mm=4.0,source="Gerber Silkscreen - Proposed",confidence="MEDIUM",accepted=True)
    s=build_shape_model(part,dimension=dim)
    out=tmp_path/"out.txt"
    export_text(out,[part],{"ABC":dim},{"ABC":s})
    headers,values=out.read_text().splitlines()
    row=dict(zip(headers.split("\t"),values.split("\t")))
    assert row["BODY_L_MM"]=="5.0" and row["BODY_W_MM"]=="4.0"
    assert row["USER_ACCEPTED"]=="YES"


def test_review_ui_labels_distinguish_paste_candidates_and_provenance():
    from pathlib import Path
    source=Path("ui/main_window.py").read_text(encoding="utf-8")
    assert "Paste Envelope L×W (mm)" in source
    assert "Paste Pad L×W / Count / Pitch (mm)" in source
    assert "Paste geometry only — not body size" in source
    assert "Dimension Source / Confidence" in source
    assert "Review Status" in source
    assert "Confidence {getattr(x,'confidence','') or 'NONE'}" in source
    assert "Accepted {'YES' if getattr(x,'accepted',False) else 'NO'}" in source


def test_exports_keep_unaccepted_paste_but_gate_body_dimensions(tmp_path):
    from models import UniquePart
    from dimensions.gerber_dimension import GerberDimensionResult
    from dimensions.shape_model import build_shape_model
    from export.excel_export import export_excel
    from export.text_export import export_text
    from openpyxl import load_workbook

    part=UniquePart('MPN1',['U1'],'U1')
    result=GerberDimensionResult(
        'U1',length_mm=4.0,width_mm=2.0,
        source='Gerber Silkscreen - Proposed',confidence='MEDIUM',
        paste_length_mm=5.2,paste_width_mm=2.6,
        paste_pad_length_mm=1.0,paste_pad_width_mm=.5,
        accepted=False)
    shape=build_shape_model(part,dimension=result)

    xlsx=tmp_path/'out.xlsx'
    txt=tmp_path/'out.txt'
    export_excel(xlsx,[part],{}, {'MPN1':result})
    export_text(txt,[part],{'MPN1':result},{'MPN1':shape})

    ws=load_workbook(xlsx,data_only=True)['Shape Dimensions']
    headers=[c.value for c in ws[1]]
    row=[c.value for c in ws[2]]
    data=dict(zip(headers,row))
    assert data['Body Length (mm)'] is None
    assert data['Body Width (mm)'] is None
    assert data['Paste Envelope Length (mm)']==5.2
    assert data['Paste Pad Length (mm)']==1.0

    lines=txt.read_text(encoding='utf-8').splitlines()
    data=dict(zip(lines[0].split('\t'),lines[1].split('\t')))
    assert data['BODY_L_MM']==''
    assert data['BODY_W_MM']==''
    assert data['PASTE_ENVELOPE_L_MM']=='5.2'
    assert data['PASTE_PAD_L_MM']=='1.0'
    assert data['USER_ACCEPTED']=='NO'


def test_exact_mpn_structured_metric_dimension_extraction_is_conservative():
    from lookup.mpn_lookup import _exact_metric_dimensions
    product={'Parameters':[
        {'ParameterText':'Length - Overall','ValueText':'4.90 mm'},
        {'ParameterText':'Width - Overall','ValueText':'3.90mm'},
        {'ParameterText':'Height - Seated (Max)','ValueText':'1.75 mm'},
        {'ParameterText':'Body Length','ValueText':'0.25 in'},
    ]}
    d=_exact_metric_dimensions(product)
    assert d=={'body_length_mm':4.9,'body_width_mm':3.9,'body_height_mm':1.75}

def test_exact_mpn_dimension_extraction_does_not_guess_units():
    from lookup.mpn_lookup import _exact_metric_dimensions
    product={'Parameters':[
        {'ParameterText':'Body Length','ValueText':'0.25 in'},
        {'ParameterText':'Body Width','ValueText':'250 mil'},
        {'ParameterText':'Body Height','ValueText':'unknown'},
    ]}
    assert _exact_metric_dimensions(product)=={}
