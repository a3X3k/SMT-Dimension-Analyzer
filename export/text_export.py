def export_text(path, unique_parts, dimension_results=None):
    dimension_results=dimension_results or {}
    with open(path,"w",encoding="utf-8") as f:
        for p in unique_parts:
            r=dimension_results.get(p.mpn)
            val=lambda n:"" if r is None or getattr(r,n,None) is None else str(getattr(r,n))
            fields=[
                f"PN={p.mpn}",f"REF={p.representative_ref}",f"LENGTH={val('length_mm')}",f"WIDTH={val('width_mm')}",
                f"HEIGHT={val('height_mm')}",f"PAD_PIN_COUNT_CANDIDATE={val('pad_count')}",f"PITCH_MM_CANDIDATE={val('pitch_mm')}",
                f"ROWS={val('pad_rows')}",f"COLUMNS={val('pad_columns')}",f"SOURCE={getattr(r,'source','') if r else ''}",
                f"STATUS={getattr(r,'status','NOT ACCEPTED') if r else 'NOT ACCEPTED'}",f"ACCEPTED={'YES' if getattr(r,'accepted',False) else 'NO'}"
            ]
            f.write(",".join(fields)+"\n")
