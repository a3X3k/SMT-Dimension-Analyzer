from pathlib import Path
import csv, re
import pandas as pd
from models import CadRecord

ALIASES={
 "ref":{"ref","reference","refdes","ref des","ref desig","ref designator","designator","reference designator","component","component ref","component reference","comp ref","symbol"},
 "mpn":{"pn","mpn","ipn","part number","partnumber","part no","part number manufacturer","manufacturer part number"},
 "x":{"x","x position","x location","pos x","center x","centre x","x coord","x coordinate","location x","mid x"},
 "y":{"y","y position","y location","pos y","center y","centre y","y coord","y coordinate","location y","mid y"},
 "rotation":{"rotation","rot","angle","theta","orientation","rotation angle","component rotation"},
 "layer":{"layer","side","board side","pcb side","mount side","surface"}}

def _norm(v): return re.sub(r"[^a-z0-9]+"," ",str(v).strip().lower()).strip()
def _float(v):
    try:
        s=str(v).strip().replace(",","")
        m=re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?",s)
        return float(m.group(0)) if m else None
    except: return None

def _raw_table(path, header=None):
    p=Path(path); ext=p.suffix.lower()
    if ext in {".xlsx",".xls"}: return pd.read_excel(p,dtype=str,header=header)
    if ext==".csv": return pd.read_csv(p,dtype=str,sep=None,engine="python",header=header)
    if ext==".txt":
        sample=p.read_text(encoding="utf-8",errors="replace")[:8192]
        try: dialect=csv.Sniffer().sniff(sample, delimiters=",\t; "); sep=dialect.delimiter
        except csv.Error: sep=None
        return pd.read_csv(p,dtype=str,sep=sep,engine="python",header=header)
    raise ValueError(f"Unsupported CAD format: {ext}")

def detect_columns(df):
    found={}
    for logical, aliases in ALIASES.items():
        found[logical]=next((col for col in df.columns if _norm(col) in aliases), None)
    return found

def _header_score(values):
    normalized=[_norm(v) for v in values if str(v).strip() and str(v).lower()!="nan"]
    hits={k for k,a in ALIASES.items() if any(v in a for v in normalized)}
    # Reference is essential; coordinates strongly identify a placement table.
    return (4 if "ref" in hits else 0)+(2 if "x" in hits else 0)+(2 if "y" in hits else 0)+len(hits),hits

def _read(path):
    # CAD exports frequently prepend report titles/project metadata before the
    # actual placement headings. Inspect a bounded prefix and choose the most
    # CAD-like row instead of assuming row 1.
    raw=_raw_table(path,header=None).fillna("")
    best=(-1,-1,set())
    for i in range(min(len(raw),40)):
        score,hits=_header_score(raw.iloc[i].tolist())
        if score>best[0]: best=(score,i,hits)
    if best[0]>=4 and "ref" in best[2]:
        return _raw_table(path,header=best[1])
    # Preserve legacy behaviour/error diagnostics when no plausible row exists.
    return _raw_table(path,header=0)

def parse_cad(path, mapping=None):
    df=_read(path).fillna(""); cols=detect_columns(df); cols.update(mapping or {})
    if not cols.get("ref"):
        seen=", ".join(str(x) for x in list(df.columns)[:20])
        raise ValueError(f"Could not detect Reference column; manual mapping is required. Detected headings: {seen or '(none)'}")
    out=[]
    for _,row in df.iterrows():
        ref=str(row[cols["ref"]]).strip()
        if not ref: continue
        get=lambda k: str(row[cols[k]]).strip() if cols.get(k) else ""
        out.append(CadRecord(ref=ref,mpn=get("mpn"),x=_float(get("x")),y=_float(get("y")),rotation=_float(get("rotation")),layer=get("layer"),raw={**row.to_dict(),"_engineering_units":"mm"}))
    return out

def inspect_cad(path):
    df=_read(path).fillna("")
    return df,detect_columns(df)
