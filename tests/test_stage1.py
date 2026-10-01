from pathlib import Path
import sqlite3
from openpyxl import Workbook, load_workbook
from parsers.bom_parser import parse_bom,group_unique_parts
from parsers.cad_parser import parse_cad
from parsers.gerber_parser import classify_gerber
from parsers.odb_parser import select_odb_source,parse_odb_dimensions
from database.database import init_db
from export.excel_export import export_excel
from export.text_export import export_text

def test_bom_grouping(tmp_path):
    p=tmp_path/'bom.csv'; p.write_text('Ref,MPN\nC101,ABC123\nC102,ABC123\nR1,XYZ9\n')
    parts=group_unique_parts(parse_bom(p)); assert len(parts)==2; assert parts[0].representative_ref=='C101'; assert parts[0].refs==['C101','C102']

def test_cad_parse(tmp_path):
    p=tmp_path/'cad.csv'; p.write_text('Reference,X,Y,Rotation,Layer\nC101,1.2,3.4,90,Top\n')
    r=parse_cad(p)[0]; assert r.ref=='C101' and r.x==1.2 and r.y==3.4 and r.rotation==90 and r.layer=='Top'

def test_layer_classification():
    assert classify_gerber('a.GTO')=='Top Silkscreen'
    assert classify_gerber('a.GTP')=='Top Paste'

def test_odb_selector(tmp_path):
    d=tmp_path/'odb'; d.mkdir(); assert select_odb_source(d)==d
    r=parse_odb_dimensions(d); assert r['status']=='NOT AVAILABLE / MANUAL REVIEW'

def test_db_init(tmp_path):
    p=init_db(tmp_path/'x.db')
    with sqlite3.connect(p) as con:
        names={r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert {'components','projects','component_results'}<=names

def test_export_framework(tmp_path):
    bom=tmp_path/'b.csv'; bom.write_text('Ref,MPN\nC1,P1\n')
    parts=group_unique_parts(parse_bom(bom))
    x=tmp_path/'Shape_Dimensions.xlsx'; t=tmp_path/'Shape_Dimensions.txt'
    export_excel(x,parts); export_text(t,parts)
    wb=load_workbook(x); assert wb.sheetnames==['Shape Dimensions','Location Verification','Processing Log']
    text=t.read_text()
    rows=text.splitlines()
    assert rows[0].split(chr(9))[:2]==['MPN','REF']
    assert rows[1].split(chr(9))[:2]==['P1','C1']
