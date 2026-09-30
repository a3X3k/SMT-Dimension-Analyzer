import sqlite3
from pathlib import Path
SCHEMA='''
CREATE TABLE IF NOT EXISTS components(id INTEGER PRIMARY KEY, mpn TEXT UNIQUE, manufacturer TEXT, package TEXT, length_mm REAL, width_mm REAL, height_mm REAL, source TEXT, source_url TEXT, source_date TEXT, confidence TEXT, verified INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, project_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS component_results(id INTEGER PRIMARY KEY, project_id INTEGER, mpn TEXT, representative_ref TEXT, length_mm REAL, width_mm REAL, height_mm REAL, source TEXT, status TEXT, FOREIGN KEY(project_id) REFERENCES projects(id));
'''
def init_db(path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(p) as con: con.executescript(SCHEMA)
    return p

def ensure_manual_match_schema(path):
    with sqlite3.connect(path) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS manual_gerber_matches(
            id INTEGER PRIMARY KEY, ref TEXT UNIQUE, gerber_path TEXT, layer TEXT,
            primitive_indices TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL,
            center_x REAL, center_y REAL, delta_x REAL, delta_y REAL, status TEXT, confirmed_at TEXT)''')

def save_manual_match(path, m):
    import json
    ensure_manual_match_schema(path)
    with sqlite3.connect(path) as con:
        con.execute('''INSERT INTO manual_gerber_matches(ref,gerber_path,layer,primitive_indices,min_x,min_y,max_x,max_y,center_x,center_y,delta_x,delta_y,status,confirmed_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ref) DO UPDATE SET gerber_path=excluded.gerber_path,layer=excluded.layer,primitive_indices=excluded.primitive_indices,min_x=excluded.min_x,min_y=excluded.min_y,max_x=excluded.max_x,max_y=excluded.max_y,center_x=excluded.center_x,center_y=excluded.center_y,delta_x=excluded.delta_x,delta_y=excluded.delta_y,status=excluded.status,confirmed_at=excluded.confirmed_at''',
        (m.ref,m.gerber_path,m.layer,json.dumps(m.primitive_indices),m.min_x,m.min_y,m.max_x,m.max_y,m.center_x,m.center_y,m.delta_x,m.delta_y,m.status,m.confirmed_at))

def delete_manual_match(path, ref):
    ensure_manual_match_schema(path)
    with sqlite3.connect(path) as con: con.execute('DELETE FROM manual_gerber_matches WHERE ref=?',(ref,))
