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



def test_paste_envelope_is_reported_separately_from_silkscreen_body(tmp_path):
    silk=tmp_path/'body.GTO'
    silk.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\n'
        'X80000Y190000D02*X120000Y190000D01*X120000Y210000D01*X80000Y210000D01*X80000Y190000D01*\nM02*\n')
    paste=tmp_path/'pads.GTP'
    paste.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10R,1.0X0.5*%\nD10*\n'
        'X75000Y195000D03*\nX125000Y195000D03*\nX75000Y205000D03*\nX125000Y205000D03*\nM02*\n')
    r=derive_gerber_dimension('U1',10,20,'Top',[parse_gerber(silk),parse_gerber(paste)],search_radius_mm=4)
    assert abs(r.length_mm-4.1)<.15 and abs(r.width_mm-2.1)<.15
    assert r.pad_count==4
    assert abs(r.paste_length_mm-6.0)<.01 and abs(r.paste_width_mm-1.5)<.01
    assert abs(r.paste_pad_length_mm-1.0)<.01 and abs(r.paste_pad_width_mm-.5)<.01
    assert r.paste_length_mm != r.length_mm


def test_kicad_roundrect_macro_extents_drive_paste_dimensions(tmp_path):
    p=tmp_path/'roundrect.GTP'
    p.write_text('%FSLAX46Y46*%\n%MOMM*%\n%AMRoundRect*0 comment*%\n'
        '%ADD10RoundRect,1.20X0.60X0.15*%\nD10*\n'
        'X9000000Y20000000D03*\nX11000000Y20000000D03*\nM02*\n')
    d=parse_gerber(p)
    a=d.apertures[10]
    assert a.macro_bounds==(1.2,.6)
    r=derive_gerber_dimension('U1',10,20,'Top',[d],search_radius_mm=3)
    assert r.pad_count==2
    assert abs(r.paste_length_mm-3.2)<.01
    assert abs(r.paste_width_mm-.6)<.01
    assert abs(r.paste_pad_length_mm-1.2)<.01
    assert abs(r.paste_pad_width_mm-.6)<.01


def test_shallow_arc_closed_loop_remains_valid_body_evidence(tmp_path):
    # Three straight sides plus a shallow top arc. Its bulge is small enough
    # to be legitimate silkscreen edge variation, so it must not be discarded
    # by the broad-arc safety guard.
    p=tmp_path/'shallow_arc.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nG75*\nD10*\n'
        'X80000Y190000D02*X80000Y210000D01*\n'
        'X120000Y190000D02*X120000Y210000D01*\n'
        'X80000Y190000D02*X120000Y190000D01*\n'
        'X80000Y210000D02*G03X120000Y210000I20000J100000D01*\nM02*\n')
    d=parse_gerber(p)
    r=derive_gerber_dimension('U1',10,20,'Top',[d],search_radius_mm=5)
    assert r.length_mm is not None
    assert r.width_mm is not None
    assert r.source=='Gerber Silkscreen - Proposed'


def test_consensus_cluster_is_pairwise_and_order_independent():
    from dimensions.gerber_dimension import GerberDimensionResult,_consensus_cluster
    # B bridges A and C under a seed-only rule, while A and C disagree by
    # more than tolerance. Consensus must never claim all three agree.
    a=GerberDimensionResult('A',length_mm=4.00,width_mm=2.00)
    b=GerberDimensionResult('B',length_mm=4.10,width_mm=2.00)
    c=GerberDimensionResult('C',length_mm=4.20,width_mm=2.00)
    first=_consensus_cluster([a,b,c],tol=.15)
    second=_consensus_cluster([c,b,a],tol=.15)
    assert len(first)==2
    assert sorted((x.length_mm,x.width_mm) for x in first)==sorted((x.length_mm,x.width_mm) for x in second)
    assert max(x.length_mm for x in first)-min(x.length_mm for x in first)<=.15


def test_plausibility_notes_flag_extreme_geometry_without_inventing_dimensions():
    from dimensions.gerber_dimension import GerberDimensionResult,_plausibility_notes
    tiny=GerberDimensionResult('U1',length_mm=4.0,width_mm=.1)
    assert "body side below 0.20 mm" in _plausibility_notes(tiny)
    extreme=GerberDimensionResult('U2',length_mm=60.0,width_mm=1.0)
    assert "body aspect ratio above 25:1" in _plausibility_notes(extreme)
    normal=GerberDimensionResult('U3',length_mm=4.0,width_mm=2.0,paste_length_mm=4.5,paste_width_mm=2.5)
    assert _plausibility_notes(normal)==[]


def test_project_confidence_requires_repeatable_closed_geometry(tmp_path):
    from models import CadRecord,UniquePart
    from dimensions.gerber_dimension import derive_project_dimensions
    p=tmp_path/'repeatable.GTO'
    p.write_text('%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.10*%\nD10*\n'
        'X80000Y190000D02*X120000Y190000D01*X120000Y210000D01*X80000Y210000D01*X80000Y190000D01*\n'
        'X180000Y190000D02*X220000Y190000D01*X220000Y210000D01*X180000Y210000D01*X180000Y190000D01*\n'
        'X280000Y190000D02*X320000Y190000D01*X320000Y210000D01*X280000Y210000D01*X280000Y190000D01*\nM02*\n')
    d=parse_gerber(p)
    part=UniquePart('MPN1',['U1','U2','U3'],'U1')
    cad=[CadRecord('U1','MPN1',10,20,0,'Top'),CadRecord('U2','MPN1',20,20,0,'Top'),CadRecord('U3','MPN1',30,20,0,'Top')]
    r=derive_project_dimensions([part],cad,[d])['MPN1']
    assert r.confidence=='HIGH'
    assert r.accepted is False
    assert 'at least 3 same-MPN' in r.remarks
