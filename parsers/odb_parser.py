from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re, tarfile, zipfile, tempfile, shutil

SUPPORTED_ARCHIVES=(".tgz",".tar.gz",".tar",".zip")

@dataclass
class OdbComponent:
    ref: str
    x: Optional[float]=None; y: Optional[float]=None; rotation: Optional[float]=None
    side: str=""; package: str=""; mpn: str=""
    length_mm: Optional[float]=None; width_mm: Optional[float]=None; height_mm: Optional[float]=None
    source_file: str=""; raw: dict=field(default_factory=dict)

@dataclass
class OdbDocument:
    root: Path; components: list[OdbComponent]=field(default_factory=list); jobs: list[str]=field(default_factory=list)
    steps: list[str]=field(default_factory=list); warnings: list[str]=field(default_factory=list)
    units: str="UNKNOWN"

def select_odb_source(path):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(path)
    if p.is_dir(): return p
    if not any(p.name.lower().endswith(x) for x in SUPPORTED_ARCHIVES): raise ValueError("Unsupported ODB++ source")
    return p

def _safe_extract(source: Path, dest: Path):
    def safe(target: Path):
        if not str(target.resolve()).startswith(str(dest.resolve())): raise ValueError("Unsafe path in ODB++ archive")
    if source.name.lower().endswith('.zip'):
        with zipfile.ZipFile(source) as z:
            for i in z.infolist(): safe(dest/i.filename)
            z.extractall(dest)
    else:
        with tarfile.open(source, 'r:*') as t:
            for m in t.getmembers(): safe(dest/m.name)
            t.extractall(dest, filter='data')

def _num(s):
    try:return float(s)
    except:return None

def _detect_units(root: Path):
    patterns=[re.compile(r'(?im)^\s*UNITS?\s*[=:]\s*(MM|INCH|IN|MIL)\b')]
    found=set()
    for name in ('matrix','misc','info'):
        for p in root.rglob(name):
            if not p.is_file(): continue
            try: text=p.read_text(errors='replace')[:1000000]
            except Exception: continue
            for pat in patterns:
                for m in pat.finditer(text):
                    u=m.group(1).upper(); found.add('MM' if u=='MM' else ('MIL' if u=='MIL' else 'INCH'))
    return found

def _scale_to_mm(units):
    return {'MM':1.0,'INCH':25.4,'MIL':0.0254}.get(units)

def _convert_component_to_mm(c, scale):
    for name in ('x','y','length_mm','width_mm','height_mm'):
        v=getattr(c,name)
        if v is not None:
            setattr(c,name,v*scale)
    c.raw=dict(c.raw or {})
    c.raw['source_units']='MM' if scale==1.0 else ('INCH' if scale==25.4 else 'MIL')
    return c

def _parse_component_line(line, side, source_file):
    kv={k.upper():v.strip('"') for k,v in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("[^"]*"|\S+)',line)}
    if kv:
        ref=kv.get('REF') or kv.get('REFDES') or kv.get('REF_DES') or kv.get('NAME') or kv.get('COMP_NAME')
        if ref:
            return OdbComponent(ref=ref,x=_num(kv.get('X') or kv.get('X_CENTER')),y=_num(kv.get('Y') or kv.get('Y_CENTER')),rotation=_num(kv.get('ROT') or kv.get('ROTATION') or kv.get('ANGLE')),side=(kv.get('SIDE') or side).upper(),package=kv.get('PKG') or kv.get('PACKAGE') or kv.get('FOOTPRINT') or '',mpn=kv.get('MPN') or kv.get('PART') or kv.get('PART_NUMBER') or '',height_mm=_num(kv.get('HEIGHT') or kv.get('H')),length_mm=_num(kv.get('LENGTH') or kv.get('L')),width_mm=_num(kv.get('WIDTH') or kv.get('W')),source_file=source_file,raw=kv)
    toks=line.split()
    # Native ODB++: CMP <index> <x> <y> <angle> <mirror> <refdes> <package> ...
    # The five uploaded production jobs all use this form.
    if toks and toks[0].upper()=='CMP' and len(toks)>=7 and toks[1].lstrip('+-').isdigit() and _num(toks[2]) is not None and _num(toks[3]) is not None:
        return OdbComponent(ref=toks[6].strip('"'),x=float(toks[2]),y=float(toks[3]),rotation=_num(toks[4]),side=side,package=toks[7].strip('"') if len(toks)>7 else '',source_file=source_file,raw={'line':line,'component_index':toks[1]})
    # Alternate simplified form: CMP <x> <y> <angle> <mirror> <ref> ...
    if toks and toks[0].upper() in {'CMP','COMP'} and len(toks)>=6 and _num(toks[1]) is not None and _num(toks[2]) is not None:
        return OdbComponent(ref=toks[5].strip('"'),x=float(toks[1]),y=float(toks[2]),rotation=_num(toks[3]),side=side,package=toks[6].strip('"') if len(toks)>6 else '',source_file=source_file,raw={'line':line})
    if toks and toks[0].upper() in {'CMP','COMP','COMPONENT','C'} and len(toks)>=4:
        if _num(toks[2]) is not None and _num(toks[3]) is not None:
            return OdbComponent(ref=toks[1],x=float(toks[2]),y=float(toks[3]),rotation=_num(toks[4]) if len(toks)>4 else None,side=side,package=toks[5] if len(toks)>5 else '',source_file=source_file,raw={'line':line})
    return None

def _parse_components_file(path: Path, side: str, warnings, default_units=None):
    out=[]
    try: text=path.read_text(errors='replace')
    except Exception as e: warnings.append(f"Cannot read {path}: {e}"); return out
    explicit=re.search(r'(?im)^\\s*U\\s+(MM|INCH|IN|MIL)\\s*$',text)
    component_units=(explicit.group(1).upper() if explicit else (default_units or 'INCH'))
    if component_units=='IN': component_units='INCH'
    scale=_scale_to_mm(component_units) or 1.0
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith(('#',';','@')) or s.startswith(('PRP ','TOP ','BOT ')): continue
        item=_parse_component_line(s,side,str(path))
        if item:
            item=_convert_component_to_mm(item,scale)
            item.raw['component_file_units']=component_units
            out.append(item)
    return out

def parse_odb(path) -> OdbDocument:
    source=select_odb_source(path); tmp=None
    if source.is_file():
        tmp=Path(tempfile.mkdtemp(prefix='smt_odb_')); _safe_extract(source,tmp); root=tmp
    else: root=source
    doc=OdbDocument(root=source)
    try:
        units=_detect_units(root)
        if not units:
            feature_units=set()
            pat=re.compile(r'(?im)^\\s*U\\s+(MM|INCH|IN|MIL)\\s*$')
            for p in root.rglob('features'):
                try: txt=p.read_text(errors='replace')[:4096]
                except Exception: continue
                for m in pat.finditer(txt):
                    u=m.group(1).upper()
                    feature_units.add('MM' if u=='MM' else ('MIL' if u=='MIL' else 'INCH'))
            units=feature_units
        if len(units)==1:
            doc.units=next(iter(units))
        elif len(units)>1:
            doc.warnings.append("Conflicting ODB++ unit declarations found; dimensional values are withheld for manual review.")
        else:
            doc.warnings.append("ODB++ units not found; dimensional values are withheld for manual review.")
        # Archives often contain a wrapper directory and some exporters vary
        # case. Search semantically instead of requiring root/jobs exactly.
        jobsdirs=[p for p in root.rglob('*') if p.is_dir() and p.name.lower()=='jobs']
        for jobsdir in jobsdirs:
            for job in jobsdir.iterdir():
                if not job.is_dir(): continue
                doc.jobs.append(job.name)
                steps=next((p for p in job.iterdir() if p.is_dir() and p.name.lower()=='steps'),job/'steps')
                if not steps.is_dir(): continue
                for step in steps.iterdir():
                    if not step.is_dir(): continue
                    doc.steps.append(f"{job.name}/{step.name}")
                    layers=next((p for p in step.iterdir() if p.is_dir() and p.name.lower()=='layers'),step/'layers')
                    if layers.is_dir():
                        for layer in layers.iterdir():
                            lname=layer.name.lower()
                            side='TOP' if ('top' in lname or lname.endswith('_+_top')) else ('BOTTOM' if ('bot' in lname or 'bottom' in lname) else '')
                            comp=next((p for p in layer.iterdir() if p.is_file() and p.name.lower() in {'components','component','comps'}),layer/'components')
                            if comp.is_file() and ('comp' in lname or side): doc.components.extend(_parse_components_file(comp,side,doc.warnings,doc.units if doc.units!='UNKNOWN' else None))
                    if not doc.components:
                        for comp in (p for p in step.rglob('*') if p.is_file() and p.name.lower() in {'components','component','comps'}):
                                lname=str(comp.parent).lower(); side='TOP' if 'top' in lname else ('BOTTOM' if ('bot' in lname or 'bottom' in lname) else '')
                                doc.components.extend(_parse_components_file(comp,side,doc.warnings,doc.units if doc.units!='UNKNOWN' else None))
        # Some valid ODB++ jobs (notably Zuken CR-8000) place steps directly
        # under the job root instead of jobs/<job>/steps.
        if not doc.components:
            for steps in (p for p in root.rglob('*') if p.is_dir() and p.name.lower()=='steps'):
                job_name=steps.parent.name
                if job_name not in doc.jobs: doc.jobs.append(job_name)
                for step in steps.iterdir():
                    if not step.is_dir(): continue
                    label=f"{job_name}/{step.name}"
                    if label not in doc.steps: doc.steps.append(label)
                    layers=next((p for p in step.iterdir() if p.is_dir() and p.name.lower()=='layers'),None)
                    if not layers: continue
                    for layer in layers.iterdir():
                        if not layer.is_dir(): continue
                        lname=layer.name.lower()
                        if 'comp' not in lname: continue
                        side='TOP' if 'top' in lname else ('BOTTOM' if ('bot' in lname or 'bottom' in lname) else '')
                        comp=next((p for p in layer.iterdir() if p.is_file() and p.name.lower()=='components'),None)
                        if comp: doc.components.extend(_parse_components_file(comp,side,doc.warnings,doc.units if doc.units!='UNKNOWN' else None))
        # Component files are converted independently because their native
        # units may differ from feature-file units.
        scale=_scale_to_mm(doc.units)
        if scale is None:
            # Keep identity/package metadata but never expose ambiguous numbers as mm.
            for c in doc.components:
                c.x=c.y=c.length_mm=c.width_mm=c.height_mm=None
        if not doc.jobs: doc.warnings.append('No supported ODB++ steps layout found.')
        if not doc.components: doc.warnings.append('No supported semantic component records found; manual review required.')
        seen=set(); unique=[]
        for c in doc.components:
            k=(c.side.upper(),c.ref.upper())
            if k not in seen: seen.add(k); unique.append(c)
        doc.components=unique
        return doc
    finally:
        if tmp: shutil.rmtree(tmp,ignore_errors=True)

def parse_odb_dimensions(path):
    doc=parse_odb(path)
    return {"status":"ODB++" if doc.components else "NOT AVAILABLE / MANUAL REVIEW","components":doc.components,"warnings":doc.warnings,"jobs":doc.jobs,"steps":doc.steps}
