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
    body_length_source:str=""
    body_width_source:str=""
    body_height_source:str=""
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
    family,_=recognize_package_family(package,getattr(part,"mpn",""))
    s=ShapeModel(mpn=part.mpn,ref=part.representative_ref,package_family=family,package_type=package,manufacturer=manufacturer)

    # Source/confidence describe dimensional evidence only. Exact MPN metadata
    # alone must never claim that dimensions came from the lookup provider.
    lookup_dim_fields=(
        "body_length_mm","body_width_mm","body_height_mm","pin_count","pin_pitch_mm",
        "lead_width_mm","lead_length_mm","bga_rows","bga_columns","ball_pitch_mm",
    )
    lookup_supplied=False
    if lookup and getattr(lookup,"status","")=="EXACT MPN MATCH":
        for name in lookup_dim_fields:
            v=getattr(lookup,name,None)
            if v is not None:
                setattr(s,name,v)
                if name in ("body_length_mm","body_width_mm","body_height_mm"):
                    setattr(s,name.replace("_mm","_source"),getattr(lookup,"source","") or "Exact MPN lookup")
                lookup_supplied=True
        if lookup_supplied:
            s.source=getattr(lookup,"source","") or "Exact MPN lookup"
            s.source_url=getattr(lookup,"datasheet_url","") or getattr(lookup,"source_url","")
            s.confidence=getattr(lookup,"confidence","") or "HIGH"

    raw=(getattr(cad,"raw",{}) or {}) if cad else {}
    gerber_supplied=False
    if dimension:
        manual_override=bool(getattr(dimension,"manual_body_override",False))
        for dst,src in (("body_length_mm","length_mm"),("body_width_mm","width_mm"),("body_height_mm","height_mm")):
            if getattr(s,dst) is None:
                v=getattr(dimension,src,None)
                if v is not None:
                    setattr(s,dst,v)
                    field_source="USER" if manual_override else (getattr(dimension,"source","") or "Gerber")
                    setattr(s,dst.replace("_mm","_source"),field_source)
                    gerber_supplied=gerber_supplied or not manual_override
        if gerber_supplied:
            dim_source=getattr(dimension,"source","")
            if s.source:
                s.source=f"{s.source} + {dim_source or 'Gerber'}"
            else:
                s.source=dim_source
                s.confidence=getattr(dimension,"confidence","") or "NONE"
        # Acceptance applies only to dimensions actually supplied by the
        # review-gated Gerber result. Trusted lookup dimensions must not
        # become user-accepted merely because a separate Gerber proposal was.
        s.user_accepted=bool((gerber_supplied or manual_override) and getattr(dimension,"accepted",False))
        s.verification=getattr(dimension,"status","NOT AVAILABLE") if gerber_supplied else ("USER REVIEW" if manual_override else "NOT REQUIRED")
        s.remarks=getattr(dimension,"remarks","")

    # Do not derive dimension confidence from package-family recognition.
    # Package classification and physical dimension provenance are separate.
    return s

def build_project_shapes(unique_parts,cad_records,dimension_results,lookup_results):
    by_ref={c.ref.strip().upper():c for c in cad_records}
    return {p.mpn:build_shape_model(p,by_ref.get(p.representative_ref.strip().upper()),dimension_results.get(p.mpn),lookup_results.get(p.mpn)) for p in unique_parts}
