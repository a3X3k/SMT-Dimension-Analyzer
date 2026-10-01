"""Conservative RS-274-X / Gerber X2 geometry parser."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re

LAYER_EXTENSIONS={".gtl":"Top Copper",".gbl":"Bottom Copper",".gto":"Top Silkscreen",".gbo":"Bottom Silkscreen",".gts":"Top Solder Mask",".gbs":"Bottom Solder Mask",".gtp":"Top Paste",".gbp":"Bottom Paste"}
GENERIC={".gbr",".ger",".pho",".art"}

@dataclass
class Aperture:
    code:int; shape:str; params:list[float]=field(default_factory=list)
@dataclass
class Primitive:
    kind:str; x:float|None=None; y:float|None=None; x2:float|None=None; y2:float|None=None
    i:float|None=None; j:float|None=None; aperture:int|None=None; polarity:str="DARK"; region:bool=False; clockwise:bool|None=None
@dataclass
class GerberDocument:
    path:Path; layer:str; units:str="mm"; format_int:int=2; format_dec:int=4; zero_suppression:str="L"
    apertures:dict[int,Aperture]=field(default_factory=dict); primitives:list[Primitive]=field(default_factory=list)
    attributes:dict[str,str]=field(default_factory=dict); warnings:list[str]=field(default_factory=list)
    def bounds(self):
        pts=[]
        for p in self.primitives:
            if p.x is not None and p.y is not None: pts.append((p.x,p.y))
            if p.x2 is not None and p.y2 is not None: pts.append((p.x2,p.y2))
        if not pts:return None
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        return min(xs),min(ys),max(xs),max(ys)

def classify_gerber(path):
    p=Path(path); ext=p.suffix.lower(); name=p.stem.lower().replace('-', '_').replace(' ', '_')
    if ext in LAYER_EXTENSIONS:return LAYER_EXTENSIONS[ext]
    if ext == '.art':
        side='Top' if 'top' in name else 'Bottom' if 'bottom' in name or 'bot' in name else ''
        if 'silk' in name and side:return f'{side} Silkscreen'
        if ('soldermask' in name or 'solder_mask' in name) and side:return f'{side} Solder Mask'
        if ('solderpaste' in name or 'solder_paste' in name or 'paste' in name) and side:return f'{side} Paste'
    if ext in GENERIC:return "Manual Mapping Required"
    return "Unknown"

def _tokenize(text):
    out=[]
    for m in re.finditer(r'%([^%]*)%|([^*%]+)\*', text, re.S):
        block=m.group(1) or m.group(2)
        if not block: continue
        out.extend(x for x in block.split('*') if x.strip())
    return out

def _coord(raw, doc):
    if raw is None:return None
    sign=-1 if raw.startswith('-') else 1; raw=raw.lstrip('+-')
    if '.' in raw:return sign*float(raw)
    width=doc.format_int+doc.format_dec
    if len(raw)<width:
        raw=(raw.rjust(width,'0') if doc.zero_suppression=='L' else raw.ljust(width,'0'))
    return sign*(int(raw)/(10**doc.format_dec))

def parse_gerber(path, layer_override=None):
    path=Path(path); text=path.read_text(encoding='utf-8',errors='ignore').replace('\r','').replace('\n','')
    doc=GerberDocument(path=path,layer=layer_override or classify_gerber(path))
    x=y=0.0; aperture=None; interpolation='LINEAR'; region=False; polarity='DARK'; last_d=2
    for raw in _tokenize(text):
        cmd=raw.strip().rstrip('*')
        if not cmd:continue
        if cmd.startswith('FS'):
            m=re.search(r'FS([LT])A?X(\d)(\d)Y(\d)(\d)',cmd)
            if m: doc.zero_suppression=m.group(1); doc.format_int=int(m.group(2)); doc.format_dec=int(m.group(3))
            continue
        if cmd.startswith('MO'):
            doc.units='mm' if 'MM' in cmd else 'inch' if 'IN' in cmd else doc.units; continue
        if cmd.startswith('ADD'):
            m=re.match(r'ADD(\d+)([A-Za-z0-9_]+)(?:,(.*))?',cmd)
            if m:
                vals=[]
                if m.group(3):
                    for v in re.split(r'[Xx]',m.group(3)):
                        try: vals.append(float(v))
                        except ValueError: pass
                doc.apertures[int(m.group(1))]=Aperture(int(m.group(1)),m.group(2),vals)
            continue
        if cmd.startswith('LP'):
            polarity='DARK' if cmd.startswith('LPD') else 'CLEAR'; continue
        if cmd.startswith('TF.') or cmd.startswith('TA.') or cmd.startswith('TO.'):
            key,*rest=cmd.split(',',1); doc.attributes[key]=rest[0] if rest else ''; continue
        if cmd.startswith('AM'):
            doc.warnings.append('Aperture macro definition preserved but macro geometry is not expanded yet.'); continue
        if cmd.startswith('G04'): continue
        if 'G36' in cmd: region=True
        if 'G37' in cmd: region=False
        if 'G01' in cmd: interpolation='LINEAR'
        if 'G02' in cmd: interpolation='CW_ARC'
        if 'G03' in cmd: interpolation='CCW_ARC'
        sm=re.fullmatch(r'D(\d+)',cmd)
        if sm and int(sm.group(1))>=10: aperture=int(sm.group(1)); continue
        mx=re.search(r'X([+-]?\d+(?:\.\d+)?)',cmd); my=re.search(r'Y([+-]?\d+(?:\.\d+)?)',cmd)
        mi=re.search(r'I([+-]?\d+(?:\.\d+)?)',cmd); mj=re.search(r'J([+-]?\d+(?:\.\d+)?)',cmd); md=re.search(r'D0?([123])',cmd)
        if not (mx or my or md): continue
        nx=_coord(mx.group(1),doc) if mx else x; ny=_coord(my.group(1),doc) if my else y
        d=int(md.group(1)) if md else last_d; last_d=d
        scale=25.4 if doc.units=='inch' else 1.0
        if d==1:
            kind='line' if interpolation=='LINEAR' else 'arc'
            doc.primitives.append(Primitive(kind,x*scale,y*scale,nx*scale,ny*scale,(_coord(mi.group(1),doc)*scale if mi else None),(_coord(mj.group(1),doc)*scale if mj else None),aperture,polarity,region,(interpolation=="CW_ARC" if kind=="arc" else None)))
        elif d==3:
            doc.primitives.append(Primitive('flash',nx*scale,ny*scale,aperture=aperture,polarity=polarity,region=region))
        x,y=nx,ny
    return doc

def parse_gerber_files(paths, layer_overrides=None):
    layer_overrides=layer_overrides or {}
    out=[]
    for p in paths:
        try: out.append(parse_gerber(p,layer_overrides.get(str(p)) or layer_overrides.get(Path(p).name)))
        except Exception as e:
            d=GerberDocument(Path(p),layer_overrides.get(str(p),classify_gerber(p))); d.warnings.append(f'Parse error: {e}'); out.append(d)
    return out

def parse_component_dimensions(paths):
    result=[]
    for d in parse_gerber_files(paths):
        result.append({"path":str(d.path),"layer":d.layer,"primitive_count":len(d.primitives),"bounds_mm":d.bounds(),"status":"NOT AVAILABLE / MANUAL REVIEW","warnings":d.warnings})
    return result
