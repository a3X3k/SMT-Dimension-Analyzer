"""Conservative component review proposals from accepted CAD + Gerber geometry."""
from dataclasses import dataclass, field
from math import hypot, radians, sin, cos
SILK_LAYERS={"Top Silkscreen","Bottom Silkscreen"}; PASTE_LAYERS={"Top Paste","Bottom Paste"}

@dataclass
class GerberDimensionResult:
    ref:str; length_mm:float|None=None; width_mm:float|None=None; height_mm:float|None=None
    source:str=""; confidence:str=""; status:str="NOT AVAILABLE / MANUAL REVIEW"; remarks:str=""
    gerber_x:float|None=None; gerber_y:float|None=None; layer:str=""
    body_bbox:tuple|None=None; primitive_ids:list[int]=field(default_factory=list)
    pad_count:int|None=None; pitch_mm:float|None=None; pad_rows:int|None=None; pad_columns:int|None=None
    accepted:bool=False

def _side(s):
    s=(s or "").lower()
    return "bottom" if "bottom" in s or s in {"b","bot"} else "top" if "top" in s or s=="t" else ""

def _half(doc,code):
    a=doc.apertures.get(code) if code else None
    if not a or not a.params:return 0.,0.
    scale=25.4 if doc.units=="inch" else 1.; p=[v*scale for v in a.params]; shape=a.shape.upper()
    if shape in {"C","P"}:return p[0]/2,p[0]/2
    if shape in {"R","O"}:return p[0]/2,(p[1] if len(p)>1 else p[0])/2
    return 0.,0.

def _bbox(doc,p):
    hx,hy=_half(doc,p.aperture); xs=[v for v in (p.x,p.x2) if v is not None]; ys=[v for v in (p.y,p.y2) if v is not None]
    return None if not xs or not ys else (min(xs)-hx,min(ys)-hy,max(xs)+hx,max(ys)+hy)

def _near(b,x,y,r): return b and not (b[2]<x-r or b[0]>x+r or b[3]<y-r or b[1]>y+r)

def _forward(x,y,dx,dy,angle):
    a=radians(angle); return x*cos(a)-y*sin(a)+dx, x*sin(a)+y*cos(a)+dy

def _inverse(x,y,dx,dy,angle):
    a=radians(-angle); x-=dx; y-=dy
    return x*cos(a)-y*sin(a), x*sin(a)+y*cos(a)

def _transform_bbox(b,dx,dy,angle):
    pts=[_forward(b[0],b[1],dx,dy,angle),_forward(b[0],b[3],dx,dy,angle),_forward(b[2],b[1],dx,dy,angle),_forward(b[2],b[3],dx,dy,angle)]
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)
def _union(bs): return min(b[0] for b in bs),min(b[1] for b in bs),max(b[2] for b in bs),max(b[3] for b in bs)

def _body_candidate(doc,x,y,r,tol=.08):
    # Use only connected line/arc loops enclosing the CAD origin. This avoids
    # treating nearby reference text and disconnected silk strokes as a body.
    segs=[]
    for i,p in enumerate(doc.primitives):
        if p.polarity!="DARK" or p.kind not in {"line","arc"} or None in (p.x,p.y,p.x2,p.y2):continue
        b=_bbox(doc,p)
        if _near(b,x,y,r):segs.append((i,p,b))
    if len(segs)<3:return None,[]
    def close(a,b):return hypot(a[0]-b[0],a[1]-b[1])<=tol
    unused=set(range(len(segs))); loops=[]
    while unused:
        first=unused.pop(); chain=[first]; p=segs[first][1]
        start=(p.x,p.y); end=(p.x2,p.y2)
        changed=True
        while changed and unused:
            changed=False
            for j in list(unused):
                q=segs[j][1]; a=(q.x,q.y); b=(q.x2,q.y2)
                if close(end,a):end=b
                elif close(end,b):end=a
                else:continue
                chain.append(j); unused.remove(j); changed=True; break
        if len(chain)>=3 and close(end,start):
            box=_union([segs[j][2] for j in chain])
            if box[0]-tol<=x<=box[2]+tol and box[1]-tol<=y<=box[3]+tol:
                loops.append((box,[segs[j][0] for j in chain]))
    if not loops:return None,[]
    loops.sort(key=lambda z:(z[0][2]-z[0][0])*(z[0][3]-z[0][1]))
    return loops[0]

def _pitch(values):
    vals=sorted(set(round(v,4) for v in values))
    ds=[round(vals[i+1]-vals[i],4) for i in range(len(vals)-1) if vals[i+1]-vals[i]>.05]
    if not ds:return None
    # Most repeated spacing, rounded enough to absorb Gerber numerical noise.
    bins={}
    for d in ds:
        k=round(d,2); bins[k]=bins.get(k,0)+1
    return min(((-n,k) for k,n in bins.items()))[1]

def _pad_geometry(doc,x,y,r):
    pts=[]
    for p in doc.primitives:
        if p.kind!="flash" or p.polarity!="DARK" or p.x is None or p.y is None:continue
        if abs(p.x-x)<=r and abs(p.y-y)<=r:pts.append((p.x,p.y))
    if not pts:return None,None,None,None
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; ux=sorted(set(round(v,3) for v in xs)); uy=sorted(set(round(v,3) for v in ys))
    px,py=_pitch(xs),_pitch(ys); candidates=[v for v in (px,py) if v]
    return len(pts),(min(candidates) if candidates else None),len(uy),len(ux)

def derive_gerber_dimension(ref,x,y,cad_layer,documents,search_radius_mm=4.0,alignment=(0.0,0.0,0.0)):
    if x is None or y is None:return GerberDimensionResult(ref,remarks="CAD X/Y required.")
    side=_side(cad_layer); docs=[d for d in documents if not side or _side(d.layer)==side]
    dx,dy,angle=alignment; gx,gy=_inverse(x,y,dx,dy,angle)
    result=None
    for wanted,source,conf in [(SILK_LAYERS,"Gerber Silkscreen - Proposed","MEDIUM")]:
        for d in docs:
            if d.layer not in wanted:continue
            b,ids=_body_candidate(d,gx,gy,search_radius_mm)
            if not b:continue
            l,w=b[2]-b[0],b[3]-b[1]; cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
            if not(.15<=l<=50 and .15<=w<=50 and hypot(cx-gx,cy-gy)<=2.5):continue
            raw_l,raw_w=l,w
            b_aligned=_transform_bbox(b,dx,dy,angle); acx,acy=_forward(cx,cy,dx,dy,angle)
            result=GerberDimensionResult(ref,round(max(raw_l,raw_w),4),round(min(raw_l,raw_w),4),None,source,conf,"WAITING FOR USER ACCEPTANCE",
                "Closed silkscreen outline proposal only. Disconnected nearby strokes/text are excluded. Use only after user acceptance when reliable MPN/manufacturer dimensions are unavailable. Height not inferred.",round(acx,4),round(acy,4),d.layer,b_aligned,ids)
            break
        if result:break
    if not result:result=GerberDimensionResult(ref,remarks="No reliable MPN/manufacturer dimensions supplied and no credible silkscreen body proposal; manual review required.")
    for d in docs:
        if d.layer in PASTE_LAYERS:
            n,pitch,rows,cols=_pad_geometry(d,gx,gy,search_radius_mm)
            if n:
                result.pad_count=n; result.pitch_mm=pitch; result.pad_rows=rows; result.pad_columns=cols
                result.remarks += " Paste flashes are reported as pad/ball candidates; they are not automatically physical pin dimensions."
                break
    return result

def derive_project_dimensions(unique_parts,cad_records,documents,search_radius_mm=4.0,alignment=(0.0,0.0,0.0)):
    by_ref={c.ref.strip().upper():c for c in cad_records}; out={}
    for p in unique_parts:
        c=by_ref.get(p.representative_ref.strip().upper())
        out[p.mpn]=derive_gerber_dimension(p.representative_ref,getattr(c,"x",None),getattr(c,"y",None),getattr(c,"layer",""),documents,search_radius_mm,alignment) if c else GerberDimensionResult(p.representative_ref,remarks="Representative reference not found in CAD.")
    return out


def apply_manual_matches(unique_parts, automatic_results, manual_matches):
    """Preserve Stage-6 explicit primitive selections as highest-confidence user-confirmed Gerber results."""
    out=dict(automatic_results)
    for p in unique_parts:
        m=manual_matches.get(p.representative_ref.strip().upper())
        if not m or getattr(m,"length_mm",None) is None or getattr(m,"width_mm",None) is None: continue
        out[p.mpn]=GerberDimensionResult(
            ref=p.representative_ref,length_mm=round(m.length_mm,4),width_mm=round(m.width_mm,4),height_mm=None,
            source=f"Gerber Derived - User Confirmed ({m.layer})",confidence="USER CONFIRMED",status="USER ACCEPTED",
            remarks=f"Manual CAD/Gerber primitive selection confirmed {m.confirmed_at}. Height not inferred.",
            gerber_x=m.center_x,gerber_y=m.center_y,layer=m.layer,body_bbox=getattr(m,"bbox",None),
            primitive_ids=list(getattr(m,"primitive_ids",[]) or []),accepted=True)
    return out
