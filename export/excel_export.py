from openpyxl import Workbook
from openpyxl.styles import Font
from datetime import datetime

def export_excel(path, unique_parts, cad_by_ref=None, dimension_results=None):
    cad_by_ref=cad_by_ref or {}; dimension_results=dimension_results or {}; wb=Workbook(); ws=wb.active; ws.title="Shape Dimensions"
    headers=["PN / MPN","Representative Ref","Manufacturer","Package / Type","Body Length (mm)","Body Width (mm)","Body Height (mm)","Overall Length (mm)","Overall Width (mm)","Pin / Ball Count Candidate","Pin / Ball Pitch Candidate (mm)","Pad Rows","Pad Columns","Dimension Source","Source URL","Confidence","Status","User Accepted","Remarks"]
    ws.append(headers)
    for p in unique_parts:
        r=dimension_results.get(p.mpn)
        ws.append([p.mpn,p.representative_ref,"","",getattr(r,"length_mm",None),getattr(r,"width_mm",None),getattr(r,"height_mm",None),"","",getattr(r,"pad_count",None),getattr(r,"pitch_mm",None),getattr(r,"pad_rows",None),getattr(r,"pad_columns",None),getattr(r,"source",""),"",getattr(r,"confidence",""),getattr(r,"status","NOT ACCEPTED"),"YES" if getattr(r,"accepted",False) else "NO",getattr(r,"remarks","")])
    v=wb.create_sheet("Location Verification"); v.append(["PN","Ref","CAD X (mm)","CAD Y (mm)","CAD Rotation (deg)","Gerber X (mm)","Gerber Y (mm)","Delta X (mm)","Delta Y (mm)","Status"])
    for p in unique_parts:
        c=cad_by_ref.get(p.representative_ref); r=dimension_results.get(p.mpn); gx=getattr(r,"gerber_x",None); gy=getattr(r,"gerber_y",None); cx=getattr(c,"x",None); cy=getattr(c,"y",None)
        dx=round(abs(cx-gx),4) if cx is not None and gx is not None else None; dy=round(abs(cy-gy),4) if cy is not None and gy is not None else None
        status="PASS" if dx is not None and dy is not None and dx<=.10 and dy<=.10 else ("WARNING" if dx is not None else "NOT AVAILABLE")
        v.append([p.mpn,p.representative_ref,cx,cy,getattr(c,"rotation",None),gx,gy,dx,dy,status])
    log=wb.create_sheet("Processing Log"); log.append(["PN","Ref","Source attempted","Source selected","Accepted","Warning / Remarks","Date/time"])
    now=datetime.now().isoformat(timespec="seconds")
    for p in unique_parts:
        r=dimension_results.get(p.mpn); log.append([p.mpn,p.representative_ref,"Silkscreen; Solder Paste; MPN lookup",getattr(r,"source",""),"YES" if getattr(r,"accepted",False) else "NO",getattr(r,"remarks",""),now])
    for sheet in wb.worksheets:
        for cell in sheet[1]: cell.font=Font(bold=True)
        sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions
        for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=min(max(len(str(x.value or "")) for x in col)+2,42)
    wb.save(path)
