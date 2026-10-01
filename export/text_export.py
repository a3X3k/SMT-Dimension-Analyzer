def export_text(path, unique_parts, dimension_results=None, shape_models=None):
    dimension_results=dimension_results or {}; shape_models=shape_models or {}
    with open(path,"w",encoding="utf-8") as f:
        headers=["MPN","REF","MANUFACTURER","PACKAGE_TYPE","PACKAGE_FAMILY","BODY_L_MM","BODY_W_MM","BODY_H_MM","OVERALL_L_MM","OVERALL_W_MM","PIN_COUNT","PIN_PITCH_MM","LEAD_W_MM","LEAD_L_MM","BGA_ROWS","BGA_COLUMNS","BALL_PITCH_MM","GERBER_L_MM","GERBER_W_MM","DIMENSION_SOURCE","SOURCE_URL","CONFIDENCE","VERIFICATION","USER_ACCEPTED","REMARKS"]
        f.write("\t".join(headers)+"\n")
        for p in unique_parts:
            r=dimension_results.get(p.mpn); s=shape_models.get(p.mpn)
            def v(obj,name):
                x=getattr(obj,name,None) if obj else None
                return "" if x is None else str(x).replace("\t"," ").replace("\n"," ")
            accepted=bool(getattr(s,"user_accepted",False) or getattr(r,"accepted",False))
            gerber_source=bool(s and str(getattr(s,"source","")).lower().startswith("gerber"))
            body_l=v(s,"body_length_mm"); body_w=v(s,"body_width_mm"); body_h=v(s,"body_height_mm")
            if gerber_source and not accepted:
                body_l=body_w=body_h=""
            row=[
                p.mpn,p.representative_ref,v(s,"manufacturer"),v(s,"package_type"),v(s,"package_family"),
                body_l or (v(r,"length_mm") if accepted else ""),body_w or (v(r,"width_mm") if accepted else ""),body_h or (v(r,"height_mm") if accepted else ""),
                v(s,"overall_length_mm"),v(s,"overall_width_mm"),v(s,"pin_count"),v(s,"pin_pitch_mm"),v(s,"lead_width_mm"),v(s,"lead_length_mm"),
                v(s,"bga_rows"),v(s,"bga_columns"),v(s,"ball_pitch_mm"),v(r,"length_mm"),v(r,"width_mm"),
                v(s,"source") or v(r,"source"),v(s,"source_url"),v(s,"confidence") or v(r,"confidence"),v(s,"verification") or v(r,"status"),
                "YES" if accepted else "NO",v(s,"remarks") or v(r,"remarks")]
            f.write("\t".join(str(x) for x in row)+"\n")
