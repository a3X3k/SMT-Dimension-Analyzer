from dataclasses import dataclass
from typing import Optional

@dataclass
class OdbDimensionResult:
    mpn:str; ref:str; length_mm:Optional[float]=None; width_mm:Optional[float]=None; height_mm:Optional[float]=None
    package:str=''; source:str='ODB++'; confidence:str=''; status:str='NOT AVAILABLE / MANUAL REVIEW'; remarks:str=''; accepted:bool=False

def derive_odb_dimensions(unique_parts, odb_document):
    index={c.ref.strip().upper():c for c in odb_document.components}
    results={}
    for p in unique_parts:
        c=index.get(p.representative_ref.strip().upper())
        if not c:
            results[p.mpn]=OdbDimensionResult(p.mpn,p.representative_ref,remarks='Representative Ref not found in ODB++ semantic component data.')
            continue
        if c.length_mm is not None and c.width_mm is not None:
            results[p.mpn]=OdbDimensionResult(p.mpn,p.representative_ref,c.length_mm,c.width_mm,c.height_mm,c.package,'ODB++','HIGH','ODB++ VERIFIED','Semantic ODB++ component dimensions.',True)
        elif c.height_mm is not None:
            results[p.mpn]=OdbDimensionResult(p.mpn,p.representative_ref,height_mm=c.height_mm,package=c.package,source='ODB++',confidence='MEDIUM',status='ODB++ PARTIAL',remarks='ODB++ height available; body L/W unavailable.',accepted=True)
        else:
            results[p.mpn]=OdbDimensionResult(p.mpn,p.representative_ref,package=c.package,source='ODB++',confidence='LOW',status='NOT AVAILABLE / MANUAL REVIEW',remarks='ODB++ placement found but no explicit body dimensions.')
    return results

def merge_priority(odb_results, gerber_results):
    out=dict(gerber_results or {})
    for mpn,o in (odb_results or {}).items():
        g=out.get(mpn)
        if o.length_mm is not None and o.width_mm is not None: out[mpn]=o
        elif o.height_mm is not None:
            if g:
                g.height_mm=o.height_mm
                g.remarks=(getattr(g,'remarks','')+'; Height from ODB++').strip('; ')
            else: out[mpn]=o
    return out
