from dataclasses import dataclass
from typing import Optional
from models import CadRecord, UniquePart

def normalize_ref(value: str) -> str:
    return ''.join(str(value).strip().upper().split())

@dataclass
class ReferenceMatch:
    mpn: str
    representative_ref: str
    cad: Optional[CadRecord]
    status: str
    warning: str = ''

def match_representatives(parts: list[UniquePart], cad_records: list[CadRecord]) -> list[ReferenceMatch]:
    by_ref={}
    duplicates=set()
    for rec in cad_records:
        key=normalize_ref(rec.ref)
        if key in by_ref:
            duplicates.add(key)
        else:
            by_ref[key]=rec
    results=[]
    for part in parts:
        key=normalize_ref(part.representative_ref)
        if key in duplicates:
            results.append(ReferenceMatch(part.mpn,part.representative_ref,None,'WARNING','Duplicate reference in CAD data'))
        elif key not in by_ref:
            results.append(ReferenceMatch(part.mpn,part.representative_ref,None,'NOT AVAILABLE','Representative reference not found in CAD data'))
        else:
            cad=by_ref[key]; warning=''; status='MATCHED'
            if cad.mpn and cad.mpn.strip().upper()!=part.mpn.strip().upper():
                status='WARNING'; warning=f'CAD MPN differs: {cad.mpn}'
            results.append(ReferenceMatch(part.mpn,part.representative_ref,cad,status,warning))
    return results
