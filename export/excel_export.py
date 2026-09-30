from openpyxl import Workbook
from openpyxl.styles import Font
from datetime import datetime

def export_excel(path, unique_parts, cad_by_ref=None, dimension_results=None):
    cad_by_ref=cad_by_ref or {}; dimension_results=dimension_results or {}; wb=Workbook(); ws=wb.active; ws.title="Shape Dimensions"
    headers=["PN / MPN","Representative Ref","Manufacturer","Package","Length (mm)","Width (mm)","Height (mm)","Dimension Source","Source URL","Source Date","Confidence","Status","Remarks"]
    ws.append(headers)
    for p in unique_parts:
        r=dimension_results.get(p.mpn); ws.append([p.mpn,p.representative_ref,"","",getattr(r,'length_mm',None),getattr(r,'width_mm',None),getattr(r,'height_mm',None),getattr(r,'source',''),"","",getattr(r,'confidence',''),getattr(r,'status','NOT AVAILABLE / MANUAL REVIEW'),getattr(r,'remarks','')])
    v=wb.create_sheet("Location Verification"); v.append(["PN","Ref","CAD/ODB X","CAD/ODB Y","CAD/ODB Rotation","Gerber X","Gerber Y","Gerber Rotation","Delta X","Delta Y","Delta Rotation","Status"])
    for p in unique_parts:
        c=cad_by_ref.get(p.representative_ref); r=dimension_results.get(p.mpn); gx=getattr(r,'gerber_x',None); gy=getattr(r,'gerber_y',None); cx=getattr(c,'x',None); cy=getattr(c,'y',None)
        dx=round(abs(cx-gx),4) if cx is not None and gx is not None else None; dy=round(abs(cy-gy),4) if cy is not None and gy is not None else None
        status='PASS' if dx is not None and dy is not None and dx<=0.10 and dy<=0.10 else ('WARNING' if dx is not None else 'NOT AVAILABLE')
        v.append([p.mpn,p.representative_ref,cx,cy,getattr(c,'rotation',None),gx,gy,"",dx,dy,"",status])
    log=wb.create_sheet("Processing Log"); log.append(["PN","Ref","Source attempted","Source selected","Error","Warning","Date/time"])
    now=datetime.now().isoformat(timespec='seconds')
    for p in unique_parts:
        r=dimension_results.get(p.mpn); log.append([p.mpn,p.representative_ref,"Silkscreen; Solder Paste",getattr(r,'source',''),"",getattr(r,'remarks',''),now])
    for sheet in wb.worksheets:
        for cell in sheet[1]: cell.font=Font(bold=True)
        sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions
        for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=min(max(len(str(x.value or "")) for x in col)+2,40)
    wb.save(path)
