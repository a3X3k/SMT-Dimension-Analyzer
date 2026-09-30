"""Conservative Gerber-derived component L/W estimation.

Project policy (Stage 4): prefer silkscreen geometry, then solder-paste geometry.
Results are GERBER DERIVED, never manufacturer-exact. Height is never inferred.
"""
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from parsers.gerber_parser import GerberDocument, Primitive

SILK_LAYERS={"Top Silkscreen","Bottom Silkscreen"}
PASTE_LAYERS={"Top Paste","Bottom Paste"}

@dataclass
class GerberDimensionResult:
    ref:str; length_mm:float|None=None; width_mm:float|None=None; height_mm:float|None=None
    source:str=""; confidence:str=""; status:str="NOT AVAILABLE / MANUAL REVIEW"; remarks:str=""
    gerber_x:float|None=None; gerber_y:float|None=None; layer:str=""

def _side(layer):
    s=(layer or '').strip().lower()
    if 'bottom' in s or s in {'b','bot','bottom'}: return 'bottom'
    if 'top' in s or s in {'t','top'}: return 'top'
    return ''

def _aperture_half(doc, code):
    a=doc.apertures.get(code) if code else None
    if not a or not a.params: return (0.0,0.0)
    scale=25.4 if doc.units=='inch' else 1.0
    p=[v*scale for v in a.params]
    shape=a.shape.upper()
    if shape in {'C','P'}: return (p[0]/2,p[0]/2)
    if shape in {'R','O'}: return (p[0]/2,(p[1] if len(p)>1 else p[0])/2)
    return (0.0,0.0)

def _bbox(doc,p):
    hx,hy=_aperture_half(doc,p.aperture)
    xs=[v for v in (p.x,p.x2) if v is not None]; ys=[v for v in (p.y,p.y2) if v is not None]
    if not xs or not ys:return None
    return min(xs)-hx,min(ys)-hy,max(xs)+hx,max(ys)+hy

def _near_bbox(b,x,y,r):
    return b and not (b[2]<x-r or b[0]>x+r or b[3]<y-r or b[1]>y+r)

def _union(boxes):
    return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)

def _candidate(doc,x,y,radius):
    boxes=[_bbox(doc,p) for p in doc.primitives if p.polarity=='DARK']
    boxes=[b for b in boxes if _near_bbox(b,x,y,radius)]
    if not boxes:return None
    boxes=[b for b in boxes if abs((b[0]+b[2])/2-x)<=radius and abs((b[1]+b[3])/2-y)<=radius]
    if not boxes:return None
    return _union(boxes)

def _valid(b,x,y,max_center_offset=1.5):
    if not b:return False
    l=b[2]-b[0]; w=b[3]-b[1]; cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2
    return 0.15<=l<=30 and 0.15<=w<=30 and hypot(cx-x,cy-y)<=max_center_offset

def derive_gerber_dimension(ref,x,y,cad_layer,documents,search_radius_mm=3.0):
    if x is None or y is None:
        return GerberDimensionResult(ref,remarks='CAD X/Y required for Gerber correlation.')
    side=_side(cad_layer)
    docs=[d for d in documents if not side or _side(d.layer)==side]
    for wanted,source,confidence in [(SILK_LAYERS,'Gerber Derived - Silkscreen','MEDIUM'),(PASTE_LAYERS,'Gerber Derived - Solder Paste','LOW')]:
        for d in docs:
            if d.layer not in wanted: continue
            b=_candidate(d,x,y,search_radius_mm)
            if not _valid(b,x,y): continue
            l=b[2]-b[0]; w=b[3]-b[1]; cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2
            length,width=max(l,w),min(l,w)
            return GerberDimensionResult(ref,round(length,4),round(width,4),None,source,confidence,'GERBER DERIVED',
                'Estimated from local geometry around CAD reference; verify during review. Height not inferred.',round(cx,4),round(cy,4),d.layer)
    return GerberDimensionResult(ref,remarks='No unambiguous local silkscreen/paste geometry found; manual review required.')

def derive_project_dimensions(unique_parts,cad_records,documents,search_radius_mm=3.0):
    by_ref={c.ref.strip().upper():c for c in cad_records}; out={}
    for p in unique_parts:
        c=by_ref.get(p.representative_ref.strip().upper())
        out[p.mpn]=derive_gerber_dimension(p.representative_ref,getattr(c,'x',None),getattr(c,'y',None),getattr(c,'layer',''),documents,search_radius_mm) if c else GerberDimensionResult(p.representative_ref,remarks='Representative reference not found in CAD.')
    return out

def apply_manual_matches(unique_parts, automatic_results, manual_matches):
    out=dict(automatic_results)
    for p in unique_parts:
        m=manual_matches.get(p.representative_ref.strip().upper())
        if not m or m.length_mm is None or m.width_mm is None: continue
        out[p.mpn]=GerberDimensionResult(p.representative_ref,round(m.length_mm,4),round(m.width_mm,4),None,
            f'Gerber Derived - User Confirmed ({m.layer})','USER CONFIRMED','GERBER DERIVED',
            f'Manual CAD↔Gerber match confirmed {m.confirmed_at}. Height not inferred.',m.center_x,m.center_y,m.layer)
    return out
