from parsers.bom_parser import parse_bom, group_unique_parts
from parsers.cad_parser import parse_cad
from parsers.gerber_parser import parse_gerber, classify_gerber

def test_tab_txt_bom_internal_pn_and_multi_refs(tmp_path):
    p=tmp_path/'bom.txt'; p.write_text('Internal P/N\tRef.Designator\nP1\tC1,C2,C3\nP2\tR1\n')
    r=parse_bom(p); assert [x.ref for x in r[:3]]==['C1','C2','C3']; assert len(group_unique_parts(r))==2

def test_cad_location_headers(tmp_path):
    p=tmp_path/'cad.txt'; p.write_text('Reference\tX location\tY location\tAngle\tSide\nC1\t12.3\t-4.5\t90\tTop\n')
    r=parse_cad(p)[0]; assert r.x==12.3 and r.y==-4.5 and r.rotation==90 and r.layer=='Top'

def test_allegro_art_extended_commands_and_units(tmp_path):
    p=tmp_path/'Silkscreen_top.art'; p.write_text('%FSLAX55Y55*MOIN*%\n%ADD10C,.010*%\nD10*\nX100000Y200000D02*\nX200000D01*\n')
    d=parse_gerber(p); assert d.layer=='Top Silkscreen'; assert d.units=='inch'; assert len(d.primitives)==1
    q=d.primitives[0]; assert round(q.x,3)==25.4 and round(q.y,3)==50.8 and round(q.x2,3)==50.8 and round(q.y2,3)==50.8
    assert classify_gerber(tmp_path/'Soldermask_top.art')=='Top Solder Mask'
