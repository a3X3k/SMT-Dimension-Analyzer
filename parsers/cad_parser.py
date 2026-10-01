from pathlib import Path
import csv, re
import pandas as pd
from models import CadRecord

ALIASES={
 "ref":{"ref","reference","refdes","designator","reference designator"},
 "mpn":{"pn","mpn","ipn","part number","partnumber"},
 "x":{"x","x position","x location","pos x","center x"}, "y":{"y","y position","y location","pos y","center y"},
 "rotation":{"rotation","rot","angle"}, "layer":{"layer","side","board side"}}

def _norm(v): return re.sub(r"[^a-z0-9]+"," ",str(v).strip().lower()).strip()
def _float(v):
    try: return float(str(v).strip())
    except: return None

def _read(path):
    p=Path(path); ext=p.suffix.lower()
    if ext in {".xlsx",".xls"}: return pd.read_excel(p,dtype=str)
    if ext==".csv": return pd.read_csv(p,dtype=str,sep=None,engine="python")
    if ext==".txt":
        sample=p.read_text(encoding="utf-8",errors="replace")[:8192]
        try: dialect=csv.Sniffer().sniff(sample, delimiters=",\t; "); sep=dialect.delimiter
        except csv.Error: sep=None
        return pd.read_csv(p,dtype=str,sep=sep,engine="python")
    raise ValueError(f"Unsupported CAD format: {ext}")

def detect_columns(df):
    found={}
    for logical, aliases in ALIASES.items():
        found[logical]=next((c for c in df.columns if _norm(c) in aliases), None)
    return found

def parse_cad(path, mapping=None):
    df=_read(path).fillna(""); cols=detect_columns(df); cols.update(mapping or {})
    if not cols.get("ref"): raise ValueError("Could not detect Reference column; manual mapping is required.")
    out=[]
    for _,row in df.iterrows():
        ref=str(row[cols["ref"]]).strip()
        if not ref: continue
        get=lambda k: str(row[cols[k]]).strip() if cols.get(k) else ""
        out.append(CadRecord(ref=ref,mpn=get("mpn"),x=_float(get("x")),y=_float(get("y")),rotation=_float(get("rotation")),layer=get("layer"),raw={**row.to_dict(),"_engineering_units":"mm"}))
    return out

def inspect_cad(path):
    df = _read(path).fillna("")
    return df, detect_columns(df)
