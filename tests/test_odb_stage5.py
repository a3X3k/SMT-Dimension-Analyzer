import tarfile
from parsers.odb_parser import parse_odb
from dimensions.odb_dimension import derive_odb_dimensions, merge_priority
from models import UniquePart
from dimensions.gerber_dimension import GerberDimensionResult

def make_odb(tmp_path):
    root=tmp_path/'odb'
    p=root/'jobs'/'demo'/'steps'/'pcb'/'layers'/'comp_+_top'
    p.mkdir(parents=True)
    (root/'matrix').write_text('UNITS=MM'+chr(10))
    component_lines=[
        'REF=C101 X=10.0 Y=20.0 ROT=90 SIDE=TOP PACKAGE=0603 LENGTH=1.6 WIDTH=0.8 HEIGHT=0.8',
        'REF=R1 X=1 Y=2 ROT=0 SIDE=TOP PACKAGE=0402',
    ]
    (p/'components').write_text(chr(10).join(component_lines)+chr(10))
    return root

def test_odb_directory_semantics(tmp_path):
    d=parse_odb(make_odb(tmp_path)); assert d.jobs==['demo']; assert 'demo/pcb' in d.steps; assert len(d.components)==2
    c=d.components[0]; assert c.ref=='C101' and c.length_mm==1.6 and c.height_mm==0.8

def test_odb_archive_safe_parse(tmp_path):
    root=make_odb(tmp_path); tgz=tmp_path/'job.tgz'
    with tarfile.open(tgz,'w:gz') as t:t.add(root,arcname='board')
    d=parse_odb(tgz); assert len(d.components)==2

def test_odb_priority_over_gerber(tmp_path):
    d=parse_odb(make_odb(tmp_path)); parts=[UniquePart('PN1',['C101'],'C101')]
    o=derive_odb_dimensions(parts,d)
    g={'PN1':GerberDimensionResult(ref='C101',length_mm=2.0,width_mm=1.0,source='Gerber Derived - Silkscreen',confidence='MEDIUM',status='GERBER DERIVED')}
    m=merge_priority(o,g); assert m['PN1'].source=='ODB++' and m['PN1'].length_mm==1.6

def test_placement_does_not_invent_body(tmp_path):
    d=parse_odb(make_odb(tmp_path)); parts=[UniquePart('PN2',['R1'],'R1')]
    r=derive_odb_dimensions(parts,d)['PN2']; assert r.length_mm is None and r.status=='NOT AVAILABLE / MANUAL REVIEW'


def _make_units_odb(tmp_path, units, line):
    root=tmp_path/('odb_'+units.lower())
    p=root/'jobs'/'demo'/'steps'/'pcb'/'layers'/'comp_+_top'
    p.mkdir(parents=True)
    (root/'matrix').write_text('UNITS='+units+chr(10))
    (p/'components').write_text(line+chr(10))
    return root

def test_odb_inch_values_convert_to_mm(tmp_path):
    root=_make_units_odb(tmp_path,'INCH','REF=U1 X=1 Y=2 SIDE=TOP LENGTH=0.1 WIDTH=0.05 HEIGHT=0.02')
    d=parse_odb(root); c=d.components[0]
    assert d.units=='INCH'
    assert round(c.x,4)==25.4 and round(c.y,4)==50.8
    assert round(c.length_mm,4)==2.54 and round(c.width_mm,4)==1.27 and round(c.height_mm,4)==0.508

def test_odb_mil_values_convert_to_mm(tmp_path):
    root=_make_units_odb(tmp_path,'MIL','REF=U1 X=1000 Y=2000 SIDE=TOP LENGTH=100 WIDTH=50 HEIGHT=20')
    d=parse_odb(root); c=d.components[0]
    assert d.units=='MIL'
    assert round(c.x,4)==25.4 and round(c.length_mm,4)==2.54 and round(c.height_mm,4)==0.508

def test_odb_unknown_units_withhold_numeric_values(tmp_path):
    root=tmp_path/'odb_unknown'; p=root/'jobs'/'demo'/'steps'/'pcb'/'layers'/'comp_+_top'; p.mkdir(parents=True)
    (p/'components').write_text('REF=U1 X=1 Y=2 SIDE=TOP LENGTH=3 WIDTH=4 HEIGHT=5'+chr(10))
    d=parse_odb(root); c=d.components[0]
    assert d.units=='UNKNOWN'
    assert c.x is None and c.y is None and c.length_mm is None and c.width_mm is None and c.height_mm is None
    assert any('units not found' in w.lower() for w in d.warnings)

def test_odb_conflicting_units_withhold_numeric_values(tmp_path):
    root=tmp_path/'odb_conflict'; p=root/'jobs'/'demo'/'steps'/'pcb'/'layers'/'comp_+_top'; p.mkdir(parents=True)
    (root/'matrix').write_text('UNITS=MM'+chr(10)); (root/'misc').write_text('UNITS=INCH'+chr(10))
    (p/'components').write_text('REF=U1 X=1 Y=2 SIDE=TOP LENGTH=3 WIDTH=4'+chr(10))
    d=parse_odb(root); c=d.components[0]
    assert d.units=='UNKNOWN' and c.x is None and c.length_mm is None
    assert any('conflicting' in w.lower() for w in d.warnings)


def test_semantic_odb_dimensions_are_trusted_for_review(tmp_path):
    d=parse_odb(make_odb(tmp_path)); parts=[UniquePart('PN1',['C101'],'C101')]
    r=derive_odb_dimensions(parts,d)['PN1']
    assert r.accepted is True
    assert r.status=='ODB++ VERIFIED'
    assert r.source=='ODB++' and r.confidence=='HIGH'

def test_odb_height_merges_without_accepting_unreviewed_gerber_body(tmp_path):
    root=_make_units_odb(tmp_path,'MM','REF=U1 X=1 Y=2 SIDE=TOP HEIGHT=0.8')
    d=parse_odb(root); parts=[UniquePart('PN1',['U1'],'U1')]
    o=derive_odb_dimensions(parts,d)
    g={'PN1':GerberDimensionResult(ref='U1',length_mm=2.0,width_mm=1.0,source='Gerber Silkscreen - Proposed',confidence='MEDIUM',status='WAITING FOR USER ACCEPTANCE',accepted=False)}
    m=merge_priority(o,g)['PN1']
    assert m.length_mm==2.0 and m.width_mm==1.0 and m.height_mm==0.8
    assert m.accepted is False
    assert 'Height from ODB++' in m.remarks


def test_odb_case_insensitive_layout_and_native_cmp_record(tmp_path):
    root=tmp_path/'wrapped'/'JOBS'/'job1'/'STEPS'/'pcb'/'LAYERS'/'COMP_+_TOP'
    root.mkdir(parents=True)
    (tmp_path/'wrapped'/'matrix').write_text('UNITS=MM\n')
    (root/'COMPONENTS').write_text('CMP 10.5 20.25 90 N U17 QFN32\n')
    d=parse_odb(tmp_path/'wrapped')
    assert d.jobs==['job1'] and len(d.components)==1
    q=d.components[0]
    assert q.ref=='U17' and q.x==10.5 and q.y==20.25 and q.rotation==90 and q.package=='QFN32'


def test_zuken_root_steps_component_records_use_native_inches(tmp_path):
    root=tmp_path/'zuken'; layer=root/'steps'/'board.pcb'/'layers'/'comp_+_top'
    layer.mkdir(parents=True)
    feat=root/'steps'/'board.pcb'/'layers'/'signal'/'features'; feat.parent.mkdir(parents=True)
    feat.write_text('#\n#Units\n#\nU MM\n')
    (root/'misc').mkdir(); (root/'misc'/'info').write_text('ODB_VERSION_MAJOR=7\nODB_SOURCE=ZUKEN CR-8000 Board Designer\n')
    (layer/'components').write_text('@0 .comp_mount_type\nCMP 2 2.87401575 1.81496063 180 N U2600 M3203001350 ;0=1\n')
    d=parse_odb(root)
    assert len(d.components)==1 and d.units=='MM'
    q=d.components[0]
    assert q.ref=='U2600' and q.mpn==''
    assert round(q.x,3)==73.0 and round(q.y,3)==46.1 and q.rotation==180 and q.side=='TOP' and q.package=='M3203001350'


def test_indexed_native_cmp_record(tmp_path):
    root=tmp_path/'odb'; layer=root/'steps'/'board'/'layers'/'comp_+_top'
    layer.mkdir(parents=True)
    feat=root/'steps'/'board'/'layers'/'signal'/'features'; feat.parent.mkdir(parents=True)
    feat.write_text('U MM\n')
    (layer/'components').write_text('CMP 17 1.25 2.5 90 N R42 PKG_A ;3=1\n')
    d=parse_odb(root); q=d.components[0]
    assert q.ref=='R42' and q.package=='PKG_A' and q.rotation==90
    assert round(q.x,3)==31.75 and round(q.y,3)==63.5
