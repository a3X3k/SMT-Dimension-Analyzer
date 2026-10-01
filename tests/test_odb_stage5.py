import tarfile
from parsers.odb_parser import parse_odb
from dimensions.odb_dimension import derive_odb_dimensions, merge_priority
from models import UniquePart
from dimensions.gerber_dimension import GerberDimensionResult

def make_odb(tmp_path):
    root=tmp_path/'odb'; p=root/'jobs'/'demo'/'steps'/'pcb'/'layers'/'comp_+_top'; p.mkdir(parents=True)
    (root/'matrix').write_text('UNITS=MM\\n')\n    (p/'components').write_text('REF=C101 X=10.0 Y=20.0 ROT=90 SIDE=TOP PACKAGE=0603 LENGTH=1.6 WIDTH=0.8 HEIGHT=0.8\nREF=R1 X=1 Y=2 ROT=0 SIDE=TOP PACKAGE=0402\n')
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
