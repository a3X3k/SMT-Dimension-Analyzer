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
