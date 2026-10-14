from pathlib import Path
import re
import pandas as pd
from models import BomRecord, UniquePart

REF_ALIASES = {"ref","reference","refdes","designator","reference designator","ref designator"}
PN_ALIASES = {"pn","mpn","part number","partnumber","manufacturer part number","manufacturer pn","mfr pn"}
IPN_ALIASES = {"ipn","internal p n","internal pn","internal part number","item number"}
DESCRIPTION_ALIASES = {"description","part description","component description","item description","desc"}

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

def parse_bom(path, ref_col=None, pn_col=None, ipn_col=None, description_col=None):
    path = Path(path); df = _read(path).fillna("")
    auto_ref, auto_pn = detect_columns(df)
    ref_col = ref_col or auto_ref
    if pn_col is None and ipn_col is None:
        pn_col = auto_pn
        if pn_col is None:
            cols = {_norm_col(c): c for c in df.columns}
            ipn_col = next((orig for n, orig in cols.items() if n in IPN_ALIASES), None)
    if not ref_col or not (pn_col or ipn_col):
        raise ValueError("Reference and at least one of MPN or IPN must be mapped.")
    out=[]
    for _, row in df.iterrows():
        ref = str(row[ref_col]).strip()
        mpn = str(row[pn_col]).strip() if pn_col else ""
        ipn = str(row[ipn_col]).strip() if ipn_col else ""
        description = str(row[description_col]).strip() if description_col else ""
        identity = mpn or ipn
        if ref and identity:
            refs=[x.strip() for x in ref.split(",") if x.strip()]
            raw=row.to_dict(); raw.update({"mapped_mpn":mpn,"mapped_ipn":ipn,"mapped_description":description})
            out.extend(BomRecord(ref=x, mpn=identity, raw=raw) for x in refs)
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
    cols = {_norm_col(c): c for c in df.columns}
    ipn = next((orig for n, orig in cols.items() if n in IPN_ALIASES), None)
    description = next((orig for n, orig in cols.items() if n in DESCRIPTION_ALIASES), None)
    return df, {"ref": ref, "mpn": pn, "ipn": ipn, "description": description}
