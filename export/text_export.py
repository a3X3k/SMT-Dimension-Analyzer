def export_text(path, unique_parts, dimension_results=None):
    dimension_results=dimension_results or {}
    with open(path,"w",encoding="utf-8") as f:
        for p in unique_parts:
            r=dimension_results.get(p.mpn); val=lambda n: '' if r is None or getattr(r,n,None) is None else str(getattr(r,n))
            source=getattr(r,'source','') if r else ''; status=getattr(r,'status','NOT AVAILABLE / MANUAL REVIEW') if r else 'NOT AVAILABLE / MANUAL REVIEW'
            f.write(f"PN={p.mpn},REF={p.representative_ref},LENGTH={val('length_mm')},WIDTH={val('width_mm')},HEIGHT={val('height_mm')},SOURCE={source},STATUS={status}\n")
