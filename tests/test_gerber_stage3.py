from parsers.gerber_parser import parse_gerber

def write(tmp_path,name,s):
    p=tmp_path/name; p.write_text(s); return p

def test_rs274x_flash_line_and_units(tmp_path):
    p=write(tmp_path,'a.GTL','%FSLAX24Y24*%%MOMM*%%ADD10C,0.500*%D10*X010000Y020000D02*X030000Y020000D01*X040000Y050000D03*M02*')
    d=parse_gerber(p)
    assert d.layer=='Top Copper' and d.units=='mm' and 10 in d.apertures
    assert [x.kind for x in d.primitives]==['line','flash']
    assert d.primitives[0].x==1.0 and d.primitives[0].x2==3.0
    assert d.bounds()==(1.0,2.0,4.0,5.0)

def test_x2_attributes_polarity_and_arc(tmp_path):
    p=write(tmp_path,'x.gbr','%FSLAX24Y24*%%MOMM*%%TF.FileFunction,Copper,L1,Top*%%ADD10C,0.2*%%LPC*%D10*X000000Y000000D02*G03X010000Y010000I005000J005000D01*M02*')
    d=parse_gerber(p, 'Top Copper')
    assert d.attributes['TF.FileFunction']=='Copper,L1,Top'
    assert d.primitives[0].kind=='arc' and d.primitives[0].polarity=='CLEAR'
    assert d.primitives[0].i==0.5 and d.primitives[0].j==0.5

def test_inch_normalizes_to_mm(tmp_path):
    p=write(tmp_path,'i.GTO','%FSLAX24Y24*%%MOIN*%%ADD10C,0.01*%D10*X010000Y010000D03*M02*')
    d=parse_gerber(p)
    assert round(d.primitives[0].x,3)==25.4

def test_region_and_no_body_guess(tmp_path):
    p=write(tmp_path,'r.GTP','%FSLAX24Y24*%%MOMM*%%ADD10R,1X1*%D10*G36*X000000Y000000D02*X010000Y000000D01*X010000Y010000D01*G37*M02*')
    d=parse_gerber(p)
    assert len(d.primitives)==2 and all(x.region for x in d.primitives)
