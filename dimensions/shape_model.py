"""Neutral component shape model and conservative package-family recognition.

All dimensional values in this module are millimetres. Recognition is advisory:
it never invents missing physical dimensions.
"""
from dataclasses import dataclass
import re

@dataclass
class ShapeModel:
    mpn:str
    ref:str
    package_family:str="UNKNOWN"
    package_type:str=""
    manufacturer:str=""
    body_length_mm:float|None=None
    body_width_mm:float|None=None
    body_height_mm:float|None=None
    overall_length_mm:float|None=None
    overall_width_mm:float|None=None
    pin_count:int|None=None
    pin_pitch_mm:float|None=None
    lead_width_mm:float|None=None
    lead_length_mm:float|None=None
    bga_rows:int|None=None
    bga_columns:int|None=None
    ball_pitch_mm:float|None=None
    source:str=""
    source_url:str=""
    confidence:str="NONE"
    verification:str="NOT AVAILABLE"
    user_accepted:bool=False
    remarks:str=""

_FAMILY_PATTERNS=(
    ("BGA",r"\b(?:BGA|FBGA|LFBGA|TFBGA|WLCSP)\b"),
    ("QFN/DFN",r"\b(?:QFN|DFN|SON|WSON|VQFN|TQFN)\b"),
    ("QFP",r"\b(?:QFP|TQFP|LQFP|VQFP)\b"),
    ("SOIC/TSSOP",r"\b(?:SOIC|SO|SOP|SSOP|TSSOP|MSOP|TSOP)\b"),
)
_CHIP_CODES={"01005","0201","0402","0603","0805","1206","1210","1812","2010","2512"}

def recognize_package_family(package_type="",mpn=""):
    text=f"{package_type} {mpn}".upper().replace("-"," ")
    for family,pat in _FAMILY_PATTERNS:
        if re.search(pat,text):return family,"HIGH" if package_type else "MEDIUM"
    tokens=set(re.findall(r"\b\d{4,5}\b",text))
    if tokens&_CHIP_CODES:return "CHIP","MEDIUM"
    return "UNKNOWN","NONE"

def build_shape_model(part,cad=None,dimension=None,lookup=None):
    package=(getattr(lookup,"package_type","") or (getattr(cad,"raw",{}) or {}).get("package","") or "")
    manufacturer=getattr(lookup,"manufacturer","") or ""
    family,fam_conf=recognize_package_family(package,getattr(part,"mpn",""))
    s=ShapeModel(mpn=part.mpn,ref=part.representative_ref,package_family=family,package_type=package,manufacturer=manufacturer)

    # Priority: exact structured manufacturer/MPN data, then ODB++ semantic
    # dimensions, then reviewed/proposed Gerber body. Missing fields stay blank.
    if lookup and getattr(lookup,"status","")=="EXACT MPN MATCH":
        for dst,src in (
            ("body_length_mm","body_length_mm"),("body_width_mm","body_width_mm"),("body_height_mm","body_height_mm"),
            ("pin_count","pin_count"),("pin_pitch_mm","pin_pitch_mm"),("lead_width_mm","lead_width_mm"),("lead_length_mm","lead_length_mm"),
            ("bga_rows","bga_rows"),("bga_columns","bga_columns"),("ball_pitch_mm","ball_pitch_mm")):
            v=getattr(lookup,src,None)
            if v is not None:setattr(s,dst,v)
        s.source=getattr(lookup,"source","") or "Exact MPN lookup"
        s.source_url=getattr(lookup,"datasheet_url","") or getattr(lookup,"source_url","")
        s.confidence=getattr(lookup,"confidence","") or "HIGH"

    raw=(getattr(cad,"raw",{}) or {}) if cad else {}
    if raw.get("source")=="ODB++":
        for dst,key in (("body_length_mm","length_mm"),("body_width_mm","width_mm"),("body_height_mm","height_mm")):
            if getattr(s,dst) is None and raw.get(key) is not None:setattr(s,dst,raw[key])
        if any(raw.get(k) is not None for k in ("length_mm","width_mm","height_mm")) and not s.source:
            s.source="ODB++"; s.confidence="HIGH"

    if dimension:
        if s.body_length_mm is None:s.body_length_mm=getattr(dimension,"length_mm",None)
        if s.body_width_mm is None:s.body_width_mm=getattr(dimension,"width_mm",None)
        if s.body_height_mm is None:s.body_height_mm=getattr(dimension,"height_mm",None)
        if not s.source and (s.body_length_mm is not None or s.body_width_mm is not None):
            s.source=getattr(dimension,"source",""); s.confidence=getattr(dimension,"confidence","")
        s.user_accepted=bool(getattr(dimension,"accepted",False))
        s.verification=getattr(dimension,"status","NOT AVAILABLE")
        s.remarks=getattr(dimension,"remarks","")
        # Paste-derived values remain candidates only; do not convert them to
        # physical lead/ball dimensions automatically.
        pass
    if s.confidence=="NONE" and fam_conf!="NONE":s.confidence=fam_conf
    return s

def build_project_shapes(unique_parts,cad_records,dimension_results,lookup_results):
    by_ref={c.ref.strip().upper():c for c in cad_records}
    return {p.mpn:build_shape_model(p,by_ref.get(p.representative_ref.strip().upper()),dimension_results.get(p.mpn),lookup_results.get(p.mpn)) for p in unique_parts}
