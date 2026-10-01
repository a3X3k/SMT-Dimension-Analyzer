from parsers.gerber_parser import parse_gerber
from dimensions.gerber_dimension import derive_gerber_dimension

def _write_rect(path,cx,cy,w,h):
    def q(v): return str(int(round(v*10000))).zfill(6)
    x1,x2=cx-w/2,cx+w/2; y1,y2=cy-h/2,cy+h/2
    path.write_text(f'%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.010*%\nD10*\nX{q(x1)}Y{q(y1)}D02*\nX{q(x2)}Y{q(y1)}D01*\nX{q(x2)}Y{q(y2)}D01*\nX{q(x1)}Y{q(y2)}D01*\nX{q(x1)}Y{q(y1)}D01*\nM02*')

def test_silkscreen_preferred(tmp_path):
    silk=tmp_path/'a.GTO'; paste=tmp_path/'a.GTP'; _write_rect(silk,10,20,1.6,.8); _write_rect(paste,10,20,1.2,.6)
    r=derive_gerber_dimension('C1',10,20,'Top',[parse_gerber(silk),parse_gerber(paste)])
    assert r.status=='WAITING FOR USER ACCEPTANCE'; assert 'Silkscreen' in r.source; assert 1.59 < r.length_mm < 1.62; assert r.height_mm is None

def test_paste_fallback(tmp_path):
    paste=tmp_path/'a.GTP'; _write_rect(paste,5,6,1.0,.5)
    r=derive_gerber_dimension('R1',5,6,'Top',[parse_gerber(paste)])
    assert r.status=='NOT AVAILABLE / MANUAL REVIEW'; assert r.length_mm is None

def test_wrong_side_not_used(tmp_path):
    silk=tmp_path/'a.GBO'; _write_rect(silk,10,20,2,1)
    r=derive_gerber_dimension('C1',10,20,'Top',[parse_gerber(silk)])
    assert r.status=='NOT AVAILABLE / MANUAL REVIEW'

def test_requires_cad_location(tmp_path):
    r=derive_gerber_dimension('U1',None,None,'Top',[])
    assert r.status=='NOT AVAILABLE / MANUAL REVIEW' and 'CAD X/Y' in r.remarks


def _write_rotated_rect(path,cx,cy,w,h,angle):
    from math import cos,sin,radians
    a=radians(angle); ca,sa=cos(a),sin(a)
    corners=[]
    for x,y in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)):
        corners.append((cx+x*ca-y*sa,cy+x*sa+y*ca))
    def q(v): return str(int(round(v*10000))).zfill(6)
    lines=['%FSLAX24Y24*%','%MOMM*%','%ADD10C,0.010*%','D10*']
    x,y=corners[0]; lines.append(f'X{q(x)}Y{q(y)}D02*')
    for x,y in corners[1:]+corners[:1]: lines.append(f'X{q(x)}Y{q(y)}D01*')
    lines.append('M02*'); path.write_text(chr(10).join(lines))

def test_component_rotation_does_not_inflate_body_size(tmp_path):
    silk=tmp_path/'rotated.GTO'; _write_rotated_rect(silk,10,20,4.0,2.0,45)
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(silk)],search_radius_mm=5.0,cad_rotation=45.0)
    assert 3.99 < r.length_mm < 4.02
    assert 1.99 < r.width_mm < 2.02

def test_global_alignment_rotation_does_not_change_physical_size(tmp_path):
    silk=tmp_path/'aligned.GTO'; _write_rotated_rect(silk,10,20,4.0,2.0,30)
    # Gerber center (10,20) rotated +30 deg into CAD space; CAD component rotation is 30+30=60 deg.
    from math import cos,sin,radians
    a=radians(30.0)
    cad_x=10*cos(a)-20*sin(a)
    cad_y=10*sin(a)+20*cos(a)
    r=derive_gerber_dimension('U1',cad_x,cad_y,'Top',[parse_gerber(silk)],search_radius_mm=5.0,cad_rotation=60.0,alignment=(0.0,0.0,30.0))
    assert 3.99 < r.length_mm < 4.02
    assert 1.99 < r.width_mm < 2.02
