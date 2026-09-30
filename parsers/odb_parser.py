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

def _parse_component_line(line, side, source_file):
    kv={k.upper():v.strip('"') for k,v in re.findall(r'([A-Za-z_]+)\s*=\s*("[^"]*"|\S+)',line)}
    if kv:
        ref=kv.get('REF') or kv.get('REFDES') or kv.get('NAME')
        if ref:
            return OdbComponent(ref=ref,x=_num(kv.get('X')),y=_num(kv.get('Y')),rotation=_num(kv.get('ROT') or kv.get('ROTATION')),side=(kv.get('SIDE') or side).upper(),package=kv.get('PKG') or kv.get('PACKAGE') or '',mpn=kv.get('MPN') or kv.get('PART') or '',height_mm=_num(kv.get('HEIGHT') or kv.get('H')),length_mm=_num(kv.get('LENGTH') or kv.get('L')),width_mm=_num(kv.get('WIDTH') or kv.get('W')),source_file=source_file,raw=kv)
    toks=line.split()
    if toks and toks[0].upper() in {'CMP','COMP','COMPONENT','C'} and len(toks)>=4:
        if _num(toks[2]) is not None and _num(toks[3]) is not None:
            return OdbComponent(ref=toks[1],x=float(toks[2]),y=float(toks[3]),rotation=_num(toks[4]) if len(toks)>4 else None,side=side,package=toks[5] if len(toks)>5 else '',source_file=source_file,raw={'line':line})
    return None

def _parse_components_file(path: Path, side: str, warnings):
    out=[]
    try: text=path.read_text(errors='replace')
    except Exception as e: warnings.append(f"Cannot read {path}: {e}"); return out
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith(('#',';')): continue
        c=_parse_component_line(s,side,str(path))
        if c: out.append(c)
    return out

def parse_odb(path) -> OdbDocument:
    source=select_odb_source(path); tmp=None
    if source.is_file():
        tmp=Path(tempfile.mkdtemp(prefix='smt_odb_')); _safe_extract(source,tmp); root=tmp
    else: root=source
    doc=OdbDocument(root=source)
    try:
        for jobsdir in root.rglob('jobs'):
            if not jobsdir.is_dir(): continue
            for job in jobsdir.iterdir():
                if not job.is_dir(): continue
                doc.jobs.append(job.name)
                steps=job/'steps'
                if not steps.is_dir(): continue
                for step in steps.iterdir():
                    if not step.is_dir(): continue
                    doc.steps.append(f"{job.name}/{step.name}")
                    layers=step/'layers'
                    if layers.is_dir():
                        for layer in layers.iterdir():
                            lname=layer.name.lower()
                            side='TOP' if ('top' in lname or lname.endswith('_+_top')) else ('BOTTOM' if ('bot' in lname or 'bottom' in lname) else '')
                            comp=layer/'components'
                            if comp.is_file() and ('comp' in lname or side): doc.components.extend(_parse_components_file(comp,side,doc.warnings))
                    if not doc.components:
                        for comp in step.rglob('components'):
                            if comp.is_file():
                                lname=str(comp.parent).lower(); side='TOP' if 'top' in lname else ('BOTTOM' if ('bot' in lname or 'bottom' in lname) else '')
                                doc.components.extend(_parse_components_file(comp,side,doc.warnings))
        if not doc.jobs: doc.warnings.append('No canonical jobs/<job>/steps layout found.')
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
