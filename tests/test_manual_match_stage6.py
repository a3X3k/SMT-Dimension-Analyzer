from pathlib import Path
from models import CadRecord,UniquePart
from parsers.gerber_parser import GerberDocument,Primitive,Aperture
from matching.manual_gerber_matcher import build_manual_match
from dimensions.gerber_dimension import GerberDimensionResult,apply_manual_matches
from database.database import init_db,save_manual_match
import sqlite3

def fixture():
    d=GerberDocument(Path('top.gto'),'Top Silkscreen'); d.apertures[10]=Aperture(10,'C',[0.2]); d.primitives=[Primitive('line',9,19,11,19,aperture=10),Primitive('line',11,19,11,21,aperture=10),Primitive('line',11,21,9,21,aperture=10),Primitive('line',9,21,9,19,aperture=10)]; return d

def test_manual_match_bbox_and_delta():
    m=build_manual_match('C1',CadRecord('C1',x=10,y=20),fixture(),[0,1,2,3]); assert round(m.center_x,3)==10 and round(m.center_y,3)==20; assert m.length_mm>2 and m.width_mm>2

def test_manual_override():
    m=build_manual_match('C1',CadRecord('C1',x=10,y=20),fixture(),[0,1,2,3]); p=UniquePart('P1',['C1'],'C1'); auto={'P1':GerberDimensionResult('C1',1,1,source='auto')}; r=apply_manual_matches([p],auto,{'C1':m})['P1']; assert 'User Confirmed' in r.source and r.confidence=='USER CONFIRMED'

def test_manual_match_db(tmp_path):
    db=init_db(tmp_path/'x.db'); m=build_manual_match('C1',CadRecord('C1',x=10,y=20),fixture(),[0]); save_manual_match(db,m)
    with sqlite3.connect(db) as c: assert c.execute('select count(*) from manual_gerber_matches').fetchone()[0]==1
