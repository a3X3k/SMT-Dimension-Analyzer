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


def test_end_to_end_cad_bom_gerber_review_export(tmp_path):
    from dimensions.gerber_dimension import derive_project_dimensions
    from dimensions.shape_model import build_project_shapes
    from export.text_export import export_text
    from matching.representative_selector import select_cad_aware_representatives

    cad=tmp_path/'cad.txt'
    cad.write_text('Reference\tX location\tY location\tAngle\tSide\nU1\t10\t20\t0\tTop\nU2\t30\t40\t90\tBottom\n')
    bom=tmp_path/'bom.txt'
    bom.write_text('Internal P/N\tRef.Designator\nPN-A\tU1\nPN-B\tU2\n')
    silk=tmp_path/'Silkscreen_top.art'
    silk.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.010*%\nD10*\nX009000Y019500D02*\nX011000Y019500D01*\nX011000Y020500D01*\nX009000Y020500D01*\nX009000Y019500D01*\nM02*')

    cad_records=parse_cad(cad)
    parts=group_unique_parts(parse_bom(bom))
    select_cad_aware_representatives(parts,cad_records)
    docs=[parse_gerber(silk)]
    dims=derive_project_dimensions(parts,cad_records,docs)
    assert dims['PN-A'].status=='WAITING FOR USER ACCEPTANCE'
    assert dims['PN-B'].length_mm is None

    shapes=build_project_shapes(parts,cad_records,dims,{})
    proposed=tmp_path/'proposed.txt'
    export_text(proposed,parts,{},shapes)
    headers,*rows=proposed.read_text().splitlines()
    first=dict(zip(headers.split(chr(9)),rows[0].split(chr(9))))
    assert first['BODY_L_MM']=='' and first['GERBER_L_MM']==''
    assert first['USER_ACCEPTED']=='NO'

    dims['PN-A'].accepted=True
    dims['PN-A'].status='USER ACCEPTED'
    shapes=build_project_shapes(parts,cad_records,dims,{})
    final=tmp_path/'accepted.txt'
    export_text(final,parts,{'PN-A':dims['PN-A']},shapes)
    headers,*rows=final.read_text().splitlines()
    first=dict(zip(headers.split(chr(9)),rows[0].split(chr(9))))
    assert first['BODY_L_MM']!='' and first['BODY_W_MM']!=''
    assert first['GERBER_L_MM']!='' and first['USER_ACCEPTED']=='YES'
