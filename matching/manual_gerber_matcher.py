from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ManualGerberMatch:
    ref: str
    gerber_path: str
    layer: str
    primitive_indices: list[int] = field(default_factory=list)
    min_x: float|None = None; min_y: float|None = None; max_x: float|None = None; max_y: float|None = None
    center_x: float|None = None; center_y: float|None = None
    delta_x: float|None = None; delta_y: float|None = None
    status: str = 'MATCHED'
    confirmed_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))

    @property
    def length_mm(self):
        if None in (self.min_x,self.max_x,self.min_y,self.max_y): return None
        return max(self.max_x-self.min_x, self.max_y-self.min_y)
    @property
    def width_mm(self):
        if None in (self.min_x,self.max_x,self.min_y,self.max_y): return None
        return min(self.max_x-self.min_x, self.max_y-self.min_y)

def primitive_bbox(doc,p):
    hx=hy=0.0
    a=doc.apertures.get(p.aperture) if p.aperture else None
    if a and a.params:
        scale=25.4 if doc.units=='inch' else 1.0; vals=[v*scale for v in a.params]
        if a.shape.upper() in {'C','P'}: hx=hy=vals[0]/2
        elif a.shape.upper() in {'R','O'}: hx=vals[0]/2; hy=(vals[1] if len(vals)>1 else vals[0])/2
    xs=[v for v in (p.x,p.x2) if v is not None]; ys=[v for v in (p.y,p.y2) if v is not None]
    if not xs or not ys:return None
    return min(xs)-hx,min(ys)-hy,max(xs)+hx,max(ys)+hy

def build_manual_match(ref,cad,doc,indices):
    boxes=[primitive_bbox(doc,doc.primitives[i]) for i in indices if 0<=i<len(doc.primitives)]
    boxes=[b for b in boxes if b]
    if not boxes: raise ValueError('Select at least one Gerber geometry item.')
    b=(min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes))
    cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2
    dx=cx-cad.x if cad and cad.x is not None else None; dy=cy-cad.y if cad and cad.y is not None else None
    return ManualGerberMatch(ref,str(doc.path),doc.layer,list(indices),*b,cx,cy,dx,dy)
