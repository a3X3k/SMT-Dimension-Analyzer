def export_text(path, unique_parts, dimension_results=None):
    dimension_results=dimension_results or {}
    with open(path,"w",encoding="utf-8") as f:
        f.write("PN/MPN\tREF\tBODY_L_MM\tBODY_W_MM\tBODY_H_MM\tPAD_PIN_COUNT_CANDIDATE\tPITCH_MM_CANDIDATE\tROWS\tCOLUMNS\tSOURCE\tSTATUS\tACCEPTED\n")
        for p in unique_parts:
            r=dimension_results.get(p.mpn)
            val=lambda n:"" if r is None or getattr(r,n,None) is None else str(getattr(r,n))
            f.write("\t".join([p.mpn,p.representative_ref,val("length_mm"),val("width_mm"),val("height_mm"),val("pad_count"),val("pitch_mm"),val("pad_rows"),val("pad_columns"),getattr(r,"source","") if r else "",getattr(r,"status","NOT ACCEPTED") if r else "NOT ACCEPTED","YES" if getattr(r,"accepted",False) else "NO"])+"\n")
