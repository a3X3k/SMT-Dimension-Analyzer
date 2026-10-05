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


def _write_rounded_rect(path,cx,cy,w,h,r):
    def q(v): return str(int(round(v*10000))).zfill(6)
    def qi(v):
        n=int(round(v*10000))
        return ('-' if n<0 else '')+str(abs(n)).zfill(6)
    x1,x2=cx-w/2,cx+w/2; y1,y2=cy-h/2,cy+h/2
    lines=['%FSLAX24Y24*%','%MOMM*%','%ADD10C,0.010*%','D10*',
           f'X{q(x1+r)}Y{q(y1)}D02*',f'X{q(x2-r)}Y{q(y1)}D01*',
           'G03*',f'X{q(x2)}Y{q(y1+r)}I{qi(0)}J{qi(r)}D01*',
           'G01*',f'X{q(x2)}Y{q(y2-r)}D01*',
           'G03*',f'X{q(x2-r)}Y{q(y2)}I{qi(-r)}J{qi(0)}D01*',
           'G01*',f'X{q(x1+r)}Y{q(y2)}D01*',
           'G03*',f'X{q(x1)}Y{q(y2-r)}I{qi(0)}J{qi(-r)}D01*',
           'G01*',f'X{q(x1)}Y{q(y1+r)}D01*',
           'G03*',f'X{q(x1+r)}Y{q(y1)}I{qi(r)}J{qi(0)}D01*','M02*']
    path.write_text(chr(10).join(lines))

def test_arc_extrema_preserve_rounded_body_size(tmp_path):
    silk=tmp_path/'rounded.GTO'; _write_rounded_rect(silk,10,20,4.0,2.0,.5)
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(silk)],search_radius_mm=5.0)
    assert r.status=='WAITING FOR USER ACCEPTANCE'
    assert 3.99 < r.length_mm < 4.02
    assert 1.99 < r.width_mm < 2.02

def test_bottom_side_rotated_body_keeps_local_dimensions(tmp_path):
    silk=tmp_path/'rotated.GBO'; _write_rotated_rect(silk,10,20,4.0,2.0,30)
    r=derive_gerber_dimension('U1',10,20,'Bottom',[parse_gerber(silk)],search_radius_mm=5.0,cad_rotation=30.0)
    assert 3.99 < r.length_mm < 4.02
    assert 1.99 < r.width_mm < 2.02


def _write_open_rect(path,cx,cy,w,h,angle=0):
    from math import cos,sin,radians
    a=radians(angle); ca,sa=cos(a),sin(a)
    def tr(x,y): return cx+x*ca-y*sa,cy+x*sa+y*ca
    def q(v): return str(int(round(v*10000))).zfill(6)
    segs=[((-w/2,-h/2),(-w/2,h/2)),((w/2,-h/2),(w/2,h/2)),
          ((-w/2,-h/2),(w*.20,-h/2)),((-w*.20,h/2),(w/2,h/2))]
    lines=['%FSLAX24Y24*%','%MOMM*%','%ADD10C,0.010*%','D10*']
    for a0,b0 in segs:
        x1,y1=tr(*a0); x2,y2=tr(*b0)
        lines.extend((f'X{q(x1)}Y{q(y1)}D02*',f'X{q(x2)}Y{q(y2)}D01*'))
    lines.append('M02*'); path.write_text(chr(10).join(lines))

def test_open_silkscreen_reconstructed_for_review(tmp_path):
    silk=tmp_path/'open.GTO'; _write_open_rect(silk,10,20,4.0,2.0)
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(silk)],search_radius_mm=5.0)
    assert r.source=='Gerber Silkscreen - Reconstructed'
    assert r.confidence=='LOW' and r.accepted is False
    assert 3.99 < r.length_mm < 4.02 and 1.99 < r.width_mm < 2.02

def test_rotated_open_silkscreen_reconstructed_in_component_axes(tmp_path):
    silk=tmp_path/'open_rot.GBO'; _write_open_rect(silk,10,20,4.0,2.0,30)
    r=derive_gerber_dimension('U1',10,20,'Bottom',[parse_gerber(silk)],search_radius_mm=5.0,cad_rotation=30)
    assert r.source=='Gerber Silkscreen - Reconstructed'
    assert 3.99 < r.length_mm < 4.02 and 1.99 < r.width_mm < 2.02

def test_ambiguous_single_open_stroke_is_not_body(tmp_path):
    p=tmp_path/'ambiguous.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.010*%\nD10*\nX090000Y200000D02*\nX110000Y200000D01*\nM02*')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5.0)
    assert r.length_mm is None and r.status=='NOT AVAILABLE / MANUAL REVIEW'


def test_project_uses_clearer_same_mpn_instance(tmp_path):
    from models import UniquePart, CadRecord
    from dimensions.gerber_dimension import derive_project_dimensions
    silk=tmp_path/'multi.GTO'
    _write_rect(silk,30,20,4.0,2.0)
    parts=[UniquePart('PN1',['U1','U2'],'U1')]
    cad=[CadRecord('U1',x=10,y=20,rotation=0,layer='Top'),CadRecord('U2',x=30,y=20,rotation=0,layer='Top')]
    r=derive_project_dimensions(parts,cad,[parse_gerber(silk)],search_radius_mm=5.0)['PN1']
    assert r.ref=='U2'
    assert r.source=='Gerber Silkscreen - Proposed'
    assert 3.99 < r.length_mm < 4.02


def test_same_mpn_consensus_rejects_outlier():
    from dimensions.gerber_dimension import GerberDimensionResult,_consensus_cluster
    rs=[GerberDimensionResult('U1',5.00,3.00),GerberDimensionResult('U2',5.04,3.02),
        GerberDimensionResult('U3',4.98,3.01),GerberDimensionResult('U4',7.20,4.00)]
    cluster=_consensus_cluster(rs)
    assert len(cluster)==3
    assert {r.ref for r in cluster}=={'U1','U2','U3'}

def test_same_mpn_consensus_requires_both_dimensions_to_agree():
    from dimensions.gerber_dimension import GerberDimensionResult,_consensus_cluster
    rs=[GerberDimensionResult('U1',5.00,3.00),GerberDimensionResult('U2',5.05,3.40)]
    assert len(_consensus_cluster(rs))==1


def test_neighbor_center_inside_candidate_rejects_body(tmp_path):
    silk=tmp_path/'dense.GTO'; _write_rect(silk,10,20,4.0,2.0)
    doc=parse_gerber(silk)
    clean=derive_gerber_dimension('U1',10,20,'Top',[doc],search_radius_mm=5.0,neighbor_positions=[(15,20)])
    assert clean.length_mm is not None
    blocked=derive_gerber_dimension('U1',10,20,'Top',[doc],search_radius_mm=5.0,neighbor_positions=[(11,20)])
    assert blocked.length_mm is None
    assert blocked.status=='NOT AVAILABLE / MANUAL REVIEW'

def test_neighbor_on_other_side_does_not_contaminate_project_candidate(tmp_path):
    from models import UniquePart, CadRecord
    from dimensions.gerber_dimension import derive_project_dimensions
    silk=tmp_path/'dense2.GTO'; _write_rect(silk,10,20,4.0,2.0)
    parts=[UniquePart('PN1',['U1'],'U1')]
    cad=[CadRecord('U1',x=10,y=20,rotation=0,layer='Top'),
         CadRecord('U2',x=11,y=20,rotation=0,layer='Bottom')]
    r=derive_project_dimensions(parts,cad,[parse_gerber(silk)],search_radius_mm=5.0)['PN1']
    assert r.length_mm is not None


def test_three_sided_open_silk_can_be_reconstructed(tmp_path):
    p=tmp_path/'three.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\nX80000Y190000D02*X80000Y210000D01*\nX120000Y190000D02*X120000Y210000D01*\nX80000Y190000D02*X95000Y190000D01*\nX105000Y190000D02*X120000Y190000D01*\nM02*\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5)
    assert r.source=='Gerber Silkscreen - Reconstructed'
    assert r.confidence=='LOW' and not r.accepted
    assert abs(r.length_mm-4.1)<.15 and abs(r.width_mm-2.1)<.15

def test_three_sided_asymmetric_silk_is_rejected(tmp_path):
    p=tmp_path/'asym.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\nX80000Y190000D02*X80000Y210000D01*\nX125000Y190000D02*X125000Y210000D01*\nX80000Y190000D02*X95000Y190000D01*\nX105000Y190000D02*X125000Y190000D01*\nM02*\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5)
    assert r.length_mm is None


def test_fragmented_open_edges_reconstruct_body(tmp_path):
    p=tmp_path/'fragmented.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\n'
        'X80000Y190000D02*X80000Y198000D01*\nX80000Y202000D02*X80000Y210000D01*\n'
        'X120000Y190000D02*X120000Y198000D01*\nX120000Y202000D02*X120000Y210000D01*\n'
        'X80000Y190000D02*X98000Y190000D01*\nX102000Y190000D02*X120000Y190000D01*\n'
        'X80000Y210000D02*X98000Y210000D01*\nX102000Y210000D02*X120000Y210000D01*\nM02*\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5)
    assert r.source=='Gerber Silkscreen - Reconstructed'
    assert abs(r.length_mm-4.1)<.15 and abs(r.width_mm-2.1)<.15
    assert len(r.primitive_ids)==8 and not r.accepted

def test_large_fragment_gap_does_not_merge_into_edge(tmp_path):
    p=tmp_path/'large_gap.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\n'
        'X80000Y190000D02*X80000Y194000D01*\nX80000Y206000D02*X80000Y210000D01*\n'
        'X120000Y190000D02*X120000Y194000D01*\nX120000Y206000D02*X120000Y210000D01*\n'
        'X80000Y190000D02*X120000Y190000D01*\nX80000Y210000D02*X120000Y210000D01*\nM02*\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5)
    assert r.length_mm is None


def test_broad_arc_closed_loop_is_rejected_from_body_proposal(tmp_path):
    p=tmp_path/'broad_arc.GTO'
    p.write_text('%FSLAX24Y24*%\\n%MOMM*%\\n%ADD10C,0.10*%\\nG75*\\nD10*\\n'
        'X80000Y190000D02*X80000Y210000D01*\\nX120000Y190000D02*X120000Y210000D01*\\n'
        'X80000Y190000D02*X120000Y190000D01*\\n'
        'X80000Y210000D02*G03X120000Y210000I20000J0D01*\\nM02*\\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(p)],search_radius_mm=5)
    assert r.length_mm is None

