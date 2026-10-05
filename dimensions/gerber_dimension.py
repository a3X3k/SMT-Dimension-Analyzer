"""Conservative component review proposals from accepted CAD + Gerber geometry."""
from dataclasses import dataclass, field
from math import hypot, radians, sin, cos, atan2, pi
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

def _arc_points(p):
    if p.kind!="arc" or None in (p.x,p.y,p.x2,p.y2,p.i,p.j):return []
    cx,cy=p.x+p.i,p.y+p.j; radius=hypot(p.x-cx,p.y-cy)
    if radius<=0:return []
    start=atan2(p.y-cy,p.x-cx); end=atan2(p.y2-cy,p.x2-cx)
    def on_sweep(a):
        if getattr(p,"clockwise",False):
            return ((start-a)%(2*pi))<=((start-end)%(2*pi))+1e-12
        return ((a-start)%(2*pi))<=((end-start)%(2*pi))+1e-12
    return [(cx+radius*cos(a),cy+radius*sin(a)) for a in (0,pi/2,pi,3*pi/2) if on_sweep(a)]

def _bbox(doc,p):
    hx,hy=_half(doc,p.aperture)
    pts=[(x,y) for x,y in ((p.x,p.y),(p.x2,p.y2)) if x is not None and y is not None]
    pts.extend(_arc_points(p))
    if not pts:return None
    xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
    return min(xs)-hx,min(ys)-hy,max(xs)+hx,max(ys)+hy

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

def _local_body_size(doc,ids,cx,cy,rotation):
    """Axis-aligned size after rotating selected outline geometry into component-local axes."""
    a=radians(-float(rotation or 0.0)); ca,sa=cos(a),sin(a); pts=[]
    for i in ids:
        p=doc.primitives[i]; hx,hy=_half(doc,p.aperture)
        geometry=[(px,py) for px,py in ((p.x,p.y),(p.x2,p.y2)) if px is not None and py is not None]
        geometry.extend(_arc_points(p))
        for px,py in geometry:
            lx=(px-cx)*ca-(py-cy)*sa; ly=(px-cx)*sa+(py-cy)*ca
            # Conservative aperture allowance. Circular strokes are exact here;
            # rectangular/obround strokes use their largest half-extent.
            h=max(hx,hy); pts.extend(((lx-h,ly-h),(lx+h,ly+h)))
    if not pts:return None
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return max(xs)-min(xs),max(ys)-min(ys)

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
    # Closed-loop proposals containing arcs are only accepted here when every
    # arc is geometrically straight-ish. Otherwise defer to the conservative
    # open/arc reconstruction path, which validates arc bulge explicitly.
    safe=[]
    for box,ids in loops:
        ok=True
        for i in ids:
            p=doc.primitives[i]
            if p.kind!="arc":continue
            chord=hypot(p.x2-p.x,p.y2-p.y)
            pts=_arc_points(p)
            if not pts or chord<=0:ok=False; break
            # Max distance of sampled arc extrema from the endpoint chord.
            vx,vy=p.x2-p.x,p.y2-p.y
            bulge=max(abs(vy*(q[0]-p.x)-vx*(q[1]-p.y))/chord for q in pts)
            if bulge>.45:ok=False; break
        if ok:safe.append((box,ids))
    if not safe:return None,[]
    safe.sort(key=lambda z:(z[0][2]-z[0][0])*(z[0][3]-z[0][1]))
    return safe[0]

def _open_body_candidate(doc,x,y,r,rotation,tol=.12):
    """Conservative open-silkscreen envelope in component-local axes."""
    a=radians(-float(rotation or 0.0)); ca,sa=cos(a),sin(a); segs=[]
    for i,p in enumerate(doc.primitives):
        if p.polarity!="DARK" or p.kind not in {"line","arc"} or None in (p.x,p.y,p.x2,p.y2):continue
        b=_bbox(doc,p)
        if not _near(b,x,y,r):continue
        raw=[(p.x,p.y),(p.x2,p.y2)]
        # Arc-assisted reconstruction: use a short arc only as edge evidence
        # when its endpoints describe a strongly horizontal/vertical chord.
        # Curved geometry is never used alone to invent a complete body.
        pts=[((px-x)*ca-(py-y)*sa,(px-x)*sa+(py-y)*ca) for px,py in raw]
        dx=abs(pts[1][0]-pts[0][0]); dy=abs(pts[1][1]-pts[0][1])
        if max(dx,dy)<.15:continue
        orientation="H" if dx>=dy*3 else "V" if dy>=dx*3 else None
        if p.kind=="arc" and orientation:
            ap=_arc_points(p)
            local=[((px-x)*ca-(py-y)*sa,(px-x)*sa+(py-y)*ca) for px,py in ap]
            # Reject broad arcs whose bulge is too large to represent a rounded
            # corner/edge interruption.
            if local:
                cross=[q[1] for q in local] if orientation=="H" else [q[0] for q in local]
                chord=(pts[0][1]+pts[1][1])/2 if orientation=="H" else (pts[0][0]+pts[1][0])/2
                if max(abs(v-chord) for v in cross)>.45:orientation=None
        if orientation:segs.append((i,orientation,pts))
    if len(segs)<3:return None,[]
    hs=[]; vs=[]
    for i,o,pts in segs:
        if o=="H":
            hs.append((i,(pts[0][1]+pts[1][1])/2,min(pts[0][0],pts[1][0]),max(pts[0][0],pts[1][0])))
        else:
            vs.append((i,(pts[0][0]+pts[1][0])/2,min(pts[0][1],pts[1][1]),max(pts[0][1],pts[1][1])))
    def merge_fragments(items,coord_tol=.12,gap_tol=.45):
        # Merge collinear fragments on one body edge. Gerber coordinates in the
        # regression fixture have a real 0.40 mm gap (19.8 -> 20.2), not 0.35 mm;
        # 0.45 mm admits that deliberate interruption while the large-gap safety
        # case (1.20 mm) remains separate. Keep all IDs for review provenance.
        groups=[]
        for q in sorted(items,key=lambda z:(z[1],z[2])):
            placed=False
            for g in groups:
                coord=sum(x[1] for x in g)/len(g)
                lo=min(x[2] for x in g); hi=max(x[3] for x in g)
                if abs(q[1]-coord)<=coord_tol and q[2]<=hi+gap_tol+1e-9 and q[3]>=lo-gap_tol-1e-9:
                    g.append(q); placed=True; break
            if not placed:groups.append([q])
        out=[]
        for g in groups:
            ids=tuple(x[0] for x in g); coord=sum(x[1] for x in g)/len(g)
            out.append((ids,coord,min(x[2] for x in g),max(x[3] for x in g)))
        return out
    hs=merge_fragments(hs); vs=merge_fragments(vs)
    negx=[q for q in vs if q[1]<-tol]; posx=[q for q in vs if q[1]>tol]
    negy=[q for q in hs if q[1]<-tol]; posy=[q for q in hs if q[1]>tol]
    groups=[bool(negx),bool(posx),bool(negy),bool(posy)]
    if sum(groups)<3:return None,[]
    # Four sides remain preferred. For exactly three sides, infer the missing
    # boundary only when the observed opposing pair is nearly symmetric about
    # the CAD origin. This keeps partial-silk recovery conservative.
    left=max(negx,key=lambda q:q[1]) if negx else None
    right=min(posx,key=lambda q:q[1]) if posx else None
    bottom=max(negy,key=lambda q:q[1]) if negy else None
    top=min(posy,key=lambda q:q[1]) if posy else None
    inferred=False
    if sum(groups)==3:
        inferred=True
        if left and right:
            span=right[1]-left[1]
            if abs(abs(left[1])-abs(right[1]))>max(.15,.08*span):return None,[]
            # Missing horizontal side: infer its Y from the observed horizontal
            # side, not from the X half-width. Rectangular bodies need not be square.
            observed=top if top else bottom
            inferred_y=-observed[1]
            if abs(observed[1])<.15:return None,[]
            if not bottom: bottom=(-1,inferred_y,left[1],right[1])
            elif not top: top=(-1,inferred_y,left[1],right[1])
        elif bottom and top:
            span=top[1]-bottom[1]
            if abs(abs(bottom[1])-abs(top[1]))>max(.15,.08*span):return None,[]
            observed=right if right else left
            inferred_x=-observed[1]
            if abs(observed[1])<.15:return None,[]
            if not left: left=(-1,inferred_x,bottom[1],top[1])
            elif not right: right=(-1,inferred_x,bottom[1],top[1])
        else:return None,[]
    width=right[1]-left[1]; height=top[1]-bottom[1]
    if not(.15<=width<=50 and .15<=height<=50):return None,[]
    # Require each selected edge to span a meaningful fraction of its opposing dimension.
    if min(left[3]-left[2],right[3]-right[2])<height*.25:return None,[]
    if min(bottom[3]-bottom[2],top[3]-top[2])<width*.25:return None,[]
    ids=[]
    for q in (left,right,bottom,top):
        qids=q[0]
        if isinstance(qids,tuple): ids.extend(qids)
        elif qids>=0: ids.append(qids)
    corners=[]
    aa=radians(float(rotation or 0.0)); c0,s0=cos(aa),sin(aa)
    for lx,ly in ((left[1],bottom[1]),(left[1],top[1]),(right[1],bottom[1]),(right[1],top[1])):
        corners.append((x+lx*c0-ly*s0,y+lx*s0+ly*c0))
    xs=[q[0] for q in corners]; ys=[q[1] for q in corners]
    return (min(xs),min(ys),max(xs),max(ys)),ids

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

def derive_gerber_dimension(ref,x,y,cad_layer,documents,search_radius_mm=4.0,alignment=(0.0,0.0,0.0),cad_rotation=0.0,neighbor_positions=None):
    if x is None or y is None:return GerberDimensionResult(ref,remarks="CAD X/Y required.")
    side=_side(cad_layer); docs=[d for d in documents if not side or _side(d.layer)==side]
    dx,dy,angle=alignment; gx,gy=_inverse(x,y,dx,dy,angle)
    result=None
    for wanted,source,conf in [(SILK_LAYERS,"Gerber Silkscreen - Proposed","MEDIUM")]:
        for d in docs:
            if d.layer not in wanted:continue
            b,ids=_body_candidate(d,gx,gy,search_radius_mm); reconstructed=False
            if not b:
                b,ids=_open_body_candidate(d,gx,gy,search_radius_mm,float(cad_rotation or 0.0)-angle)
                reconstructed=bool(b)
            if not b:continue
            l,w=b[2]-b[0],b[3]-b[1]; cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
            if not(.15<=l<=50 and .15<=w<=50 and hypot(cx-gx,cy-gy)<=2.5):continue
            local=_local_body_size(d,ids,gx if reconstructed else cx,gy if reconstructed else cy,float(cad_rotation or 0.0)-angle)
            raw_l,raw_w=(local if local else (l,w))
            # Dense-board protection: a body proposal may not enclose another
            # CAD component centre on the same side. This prevents borrowing a
            # neighbour's silkscreen in tightly packed areas.
            if neighbor_positions:
                margin=.05
                contaminated=False
                for nx,ny in neighbor_positions:
                    ngx,ngy=_inverse(nx,ny,dx,dy,angle)
                    if b[0]+margin < ngx < b[2]-margin and b[1]+margin < ngy < b[3]-margin:
                        contaminated=True; break
                if contaminated:continue
            b_aligned=_transform_bbox(b,dx,dy,angle); acx,acy=_forward(cx,cy,dx,dy,angle)
            actual_source="Gerber Silkscreen - Reconstructed" if reconstructed else source
            actual_conf="LOW" if reconstructed else conf
            note=(("Open/partial silkscreen reconstructed from component-local opposing edge evidence; user review required. " if reconstructed else "Closed silkscreen outline proposal only. Disconnected nearby strokes/text are excluded. "))
            result=GerberDimensionResult(ref,round(max(raw_l,raw_w),4),round(min(raw_l,raw_w),4),None,actual_source,actual_conf,"WAITING FOR USER ACCEPTANCE",
                note+"Use only after user acceptance when reliable MPN/manufacturer dimensions are unavailable. Height not inferred.",round(acx,4),round(acy,4),d.layer,b_aligned,ids)
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

def _consensus_cluster(candidates,tol=.15):
    """Largest mutually compatible L/W cluster; deterministic and outlier resistant."""
    best=[]
    for seed in candidates:
        cluster=[r for r in candidates if abs(r.length_mm-seed.length_mm)<=tol and abs(r.width_mm-seed.width_mm)<=tol]
        if len(cluster)>len(best):best=cluster
    return best

def derive_project_dimensions(unique_parts,cad_records,documents,search_radius_mm=4.0,alignment=(0.0,0.0,0.0)):
    by_ref={c.ref.strip().upper():c for c in cad_records}; out={}
    for p in unique_parts:
        candidates=[]
        # Try every CAD-backed instance of the same MPN. A single damaged or
        # clipped silkscreen must not decide the dimension for the whole part.
        for ref in p.refs:
            cad=by_ref.get(ref.strip().upper())
            if not cad:continue
            side=_side(getattr(cad,"layer",""))
            neighbors=[(getattr(n,"x",None),getattr(n,"y",None)) for n in cad_records
                       if n is not cad and _side(getattr(n,"layer",""))==side
                       and getattr(n,"x",None) is not None and getattr(n,"y",None) is not None
                       and hypot(n.x-cad.x,n.y-cad.y)<=search_radius_mm*2]
            r=derive_gerber_dimension(ref,getattr(cad,"x",None),getattr(cad,"y",None),getattr(cad,"layer",""),documents,search_radius_mm,alignment,getattr(cad,"rotation",0.0),neighbors)
            if r.length_mm is not None and r.width_mm is not None:candidates.append(r)
        if candidates:
            cluster=_consensus_cluster(candidates)
            pool=cluster if len(cluster)>=2 else candidates
            rank=lambda r:(0 if r.source=="Gerber Silkscreen - Proposed" else 1, -len(r.primitive_ids))
            best=sorted(pool,key=rank)[0]
            if len(cluster)>=2:
                ls=sorted(r.length_mm for r in cluster); ws=sorted(r.width_mm for r in cluster)
                mid=len(cluster)//2
                ml=ls[mid] if len(cluster)%2 else (ls[mid-1]+ls[mid])/2
                mw=ws[mid] if len(cluster)%2 else (ws[mid-1]+ws[mid])/2
                best.length_mm=round(ml,4); best.width_mm=round(mw,4)
                best.remarks += f" Same-MPN geometry consensus: {len(cluster)}/{len(candidates)} CAD instances agree within {0.15:.2f} mm; consensus median used."
                if best.confidence=="LOW":best.confidence="MEDIUM"
            elif len(candidates)>1:
                best.confidence="LOW"
                best.remarks += f" Same-MPN instances disagree; selected best geometry from {len(candidates)} candidates and kept LOW confidence."
            out[p.mpn]=best
        else:
            out[p.mpn]=GerberDimensionResult(p.representative_ref,remarks="No CAD-backed instance produced a credible silkscreen body proposal; manual review required.")
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
