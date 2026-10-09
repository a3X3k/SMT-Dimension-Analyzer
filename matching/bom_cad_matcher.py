"""Reconcile BOM part numbers with CAD placements using reference designators."""

def match_bom_to_cad(cad_records, bom_records):
    """Return reference-match statistics; reject conflicting BOM assignments."""
    cad_by_ref = {}
    for cad in cad_records:
        key = cad.ref.strip().upper()
        if not key or key in {"#NAME?", "#REF!", "#VALUE!", "#N/A"}:
            raise ValueError(f"Invalid CAD reference {key!r}; correct the source CAD file before BOM matching")
        if key in cad_by_ref:
            raise ValueError(f"Duplicate CAD reference: {key}")
        cad_by_ref[key] = cad

    bom_by_ref = {}
    for bom in bom_records:
        key = bom.ref.strip().upper()
        mpn = bom.mpn.strip()
        if not key or not mpn:
            continue
        if key in bom_by_ref and bom_by_ref[key].upper() != mpn.upper():
            raise ValueError(
                f"Conflicting BOM part numbers for {key}: "
                f"{bom_by_ref[key]} and {mpn}"
            )
        bom_by_ref[key] = mpn

    # Clear previous BOM assignments before applying the new import.
    for cad in cad_records:
        cad.mpn = bom_by_ref.get(cad.ref.strip().upper(), "")

    cad_refs = set(cad_by_ref)
    bom_refs = set(bom_by_ref)
    return {
        "matched": cad_refs & bom_refs,
        "bom_only": bom_refs - cad_refs,
        "cad_only": cad_refs - bom_refs,
    }
