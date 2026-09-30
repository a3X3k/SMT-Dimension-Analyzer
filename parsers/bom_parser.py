from pathlib import Path
import re
import pandas as pd
from models import BomRecord, UniquePart

REF_ALIASES = {"ref","reference","refdes","designator","reference designator","ref designator"}
PN_ALIASES = {"pn","mpn","ipn","part number","partnumber","manufacturer part number","internal p n","internal pn"}

def _norm_col(v):
    return re.sub(r"[^a-z0-9]+", " ", str(v).strip().lower()).strip()

def _read(path: Path):
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xls"}: return pd.read_excel(path, dtype=str)
    if ext == ".csv": return pd.read_csv(path, dtype=str, sep=None, engine="python")
    if ext == ".txt": return pd.read_csv(path, dtype=str, sep=None, engine="python")
    raise ValueError(f"Unsupported BOM format: {ext}")

def detect_columns(df):
    cols = {_norm_col(c): c for c in df.columns}
    ref = next((orig for n, orig in cols.items() if n in REF_ALIASES), None)
    pn = next((orig for n, orig in cols.items() if n in PN_ALIASES), None)
    return ref, pn

def parse_bom(path, ref_col=None, pn_col=None):
    path = Path(path); df = _read(path).fillna("")
    auto_ref, auto_pn = detect_columns(df)
    ref_col, pn_col = ref_col or auto_ref, pn_col or auto_pn
    if not ref_col or not pn_col:
        raise ValueError("Could not detect Reference and PN/MPN columns; manual mapping is required.")
    out=[]
    for _, row in df.iterrows():
        ref, mpn = str(row[ref_col]).strip(), str(row[pn_col]).strip()
        if ref and mpn:
            refs=[x.strip() for x in ref.split(",") if x.strip()]
            out.extend(BomRecord(ref=x, mpn=mpn, raw=row.to_dict()) for x in refs)
    return out

def group_unique_parts(records):
    groups={}
    for r in records:
        key=r.mpn.strip().upper()
        groups.setdefault(key, {"mpn":r.mpn.strip(), "refs":[]})["refs"].append(r.ref.strip())
    return [UniquePart(mpn=v["mpn"], refs=v["refs"], representative_ref=v["refs"][0]) for v in groups.values()]

def inspect_bom(path):
    path = Path(path); df = _read(path).fillna("")
    ref, pn = detect_columns(df)
    return df, {"ref": ref, "mpn": pn}
