from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_gerber_dimension

def _write_rect(path,cx,cy,w,h):
    def q(v): return str(int(round(v*10000))).zfill(6)
    x1,x2=cx-w/2,cx+w/2; y1,y2=cy-h/2,cy+h/2
    path.write_text(f'%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.010*%\nD10*\nX{q(x1)}Y{q(y1)}D02*\nX{q(x2)}Y{q(y1)}D01*\nX{q(x2)}Y{q(y2)}D01*\nX{q(x1)}Y{q(y2)}D01*\nX{q(x1)}Y{q(y1)}D01*\nM02*')

def test_silkscreen_preferred(tmp_path):
    silk=tmp_path/'a.GTO'; paste=tmp_path/'a.GTP'; _write_rect(silk,10,20,1.6,.8); _write_rect(paste,10,20,1.2,.6)
    r=derive_gerber_dimension('C1',10,20,'Top',[parse_gerber(silk),parse_gerber(paste)])
    assert r.status=='GERBER DERIVED'; assert 'Silkscreen' in r.source; assert 1.59 < r.length_mm < 1.62; assert r.height_mm is None

def test_paste_fallback(tmp_path):
    paste=tmp_path/'a.GTP'; _write_rect(paste,5,6,1.0,.5)
    r=derive_gerber_dimension('R1',5,6,'Top',[parse_gerber(paste)])
    assert 'Solder Paste' in r.source and r.confidence=='LOW'; assert r.length_mm > .99

def test_wrong_side_not_used(tmp_path):
    silk=tmp_path/'a.GBO'; _write_rect(silk,10,20,2,1)
    r=derive_gerber_dimension('C1',10,20,'Top',[parse_gerber(silk)])
    assert r.status=='NOT AVAILABLE / MANUAL REVIEW'

def test_requires_cad_location(tmp_path):
    r=derive_gerber_dimension('U1',None,None,'Top',[])
    assert r.status=='NOT AVAILABLE / MANUAL REVIEW' and 'CAD X/Y' in r.remarks
