from dataclasses import dataclass
from models import CadRecord, UniquePart
from matching.reference_matcher import normalize_ref

@dataclass
class RepresentativeSelectionSummary:
    total_parts: int = 0
    cad_selected: int = 0
    retained_original: int = 0
    duplicate_only: int = 0

def select_cad_aware_representatives(parts: list[UniquePart], cad_records: list[CadRecord]) -> RepresentativeSelectionSummary:
    summary=RepresentativeSelectionSummary(total_parts=len(parts))
    counts={}
    for rec in cad_records:
        key=normalize_ref(rec.ref)
        if key: counts[key]=counts.get(key,0)+1
    if not counts:
        summary.retained_original=len(parts); return summary
    for part in parts:
        unique_matches=[ref for ref in part.refs if counts.get(normalize_ref(ref),0)==1]
        if unique_matches:
            part.representative_ref=unique_matches[0]; summary.cad_selected+=1; continue
        if any(counts.get(normalize_ref(ref),0)>1 for ref in part.refs): summary.duplicate_only+=1
        summary.retained_original+=1
    return summary
