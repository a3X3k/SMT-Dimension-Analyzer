"""Structured MPN lookup with conservative exact-match rules."""
from dataclasses import dataclass
from datetime import date
import json, os
from urllib.parse import quote
from urllib.request import Request, urlopen

@dataclass
class MpnData:
    query:str; matched_mpn:str=""; manufacturer:str=""; package_type:str=""
    body_length_mm:float|None=None; body_width_mm:float|None=None; body_height_mm:float|None=None
    pin_count:int|None=None; pin_pitch_mm:float|None=None; lead_width_mm:float|None=None; lead_length_mm:float|None=None
    bga_rows:int|None=None; bga_columns:int|None=None; ball_pitch_mm:float|None=None
    source:str=""; source_url:str=""; datasheet_url:str=""; confidence:str=""; status:str="NOT FOUND"; lookup_date:str=""

def _get_json(url,headers=None,data=None):
    req=Request(url,data=(json.dumps(data).encode() if data is not None else None),headers={"Accept":"application/json","Content-Type":"application/json",**(headers or {})})
    with urlopen(req,timeout=15) as r:return json.loads(r.read().decode("utf-8"))


def _number_mm(value):
    """Parse an explicitly metric numeric value without guessing units."""
    if value is None:return None
    # A bare number from a distributor parameter does not prove units.
    # Accept only values that explicitly declare millimetres.
    import re
    s=str(value).strip()
    m=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*mm",s,re.I)
    return float(m.group(1)) if m else None

def _parameters(product):
    """Normalize distributor parameter arrays to a name/value mapping."""
    raw=product.get("Parameters") or product.get("ProductParameters") or []
    out={}
    for item in raw:
        if not isinstance(item,dict):continue
        name=str(item.get("ParameterText") or item.get("Parameter") or item.get("Name") or "").strip().lower()
        value=item.get("ValueText") if "ValueText" in item else item.get("Value")
        if name and value is not None:out[name]=value
    return out

def _exact_metric_dimensions(product):
    """Extract only explicit metric body/package dimensions from structured fields."""
    params=_parameters(product)
    aliases={
        "body_length_mm":("length - overall","package / case length","body length"),
        "body_width_mm":("width - overall","package / case width","body width"),
        "body_height_mm":("height - seated (max)","height - seated","package / case height","body height"),
    }
    out={}
    for field,names in aliases.items():
        for name in names:
            if name in params:
                v=_number_mm(params[name])
                if v is not None:out[field]=v;break
    return out

class MouserProvider:
    name="Mouser"
    def available(self):return bool(os.getenv("MOUSER_API_KEY"))
    def lookup(self,mpn):
        key=os.getenv("MOUSER_API_KEY","")
        if not key:return None
        url=f"https://api.mouser.com/api/v1/search/partnumber?apiKey={quote(key)}"
        data=_get_json(url,data={"SearchByPartRequest":{"mouserPartNumber":mpn,"partSearchOptions":"Exact"}})
        parts=((data.get("SearchResults") or {}).get("Parts") or [])
        exact=[p for p in parts if str(p.get("ManufacturerPartNumber","")).strip().upper()==mpn.strip().upper()]
        if len(exact)!=1:return None
        p=exact[0]; dims=_exact_metric_dimensions(p)
        return MpnData(query=mpn,matched_mpn=p.get("ManufacturerPartNumber",""),manufacturer=p.get("Manufacturer",""),package_type=p.get("Packaging",""),
            source=self.name,source_url=p.get("ProductDetailUrl",""),datasheet_url=p.get("DataSheetUrl",""),confidence="HIGH",status="EXACT MPN MATCH",lookup_date=str(date.today()),**dims)

class DigiKeyProvider:
    name="DigiKey"
    def available(self):return bool(os.getenv("DIGIKEY_CLIENT_ID") and os.getenv("DIGIKEY_ACCESS_TOKEN"))
    def lookup(self,mpn):
        cid=os.getenv("DIGIKEY_CLIENT_ID",""); token=os.getenv("DIGIKEY_ACCESS_TOKEN","")
        if not(cid and token):return None
        url="https://api.digikey.com/products/v4/search/keyword"
        headers={"Authorization":f"Bearer {token}","X-DIGIKEY-Client-Id":cid,"X-DIGIKEY-Locale-Site":"US","X-DIGIKEY-Locale-Language":"en","X-DIGIKEY-Locale-Currency":"USD"}
        body={"Keywords":mpn,"Limit":10,"Offset":0}
        data=_get_json(url,headers,data=body); products=data.get("Products") or []
        exact=[p for p in products if str(p.get("ManufacturerProductNumber","")).strip().upper()==mpn.strip().upper()]
        if len(exact)!=1:return None
        p=exact[0]; vars=p.get("ProductVariations") or []; package=((vars[0].get("PackageType") or {}).get("Name","") if vars else ""); dims=_exact_metric_dimensions(p)
        return MpnData(query=mpn,matched_mpn=p.get("ManufacturerProductNumber",""),manufacturer=(p.get("Manufacturer") or {}).get("Name",""),package_type=package,
            source=self.name,source_url=p.get("ProductUrl",""),datasheet_url=p.get("DatasheetUrl",""),confidence="HIGH",status="EXACT MPN MATCH",lookup_date=str(date.today()),**dims)

def lookup_mpn(mpn):
    result=MpnData(query=str(mpn),lookup_date=str(date.today()))
    errors=[]
    for provider in (DigiKeyProvider(),MouserProvider()):
        if not provider.available():continue
        try:
            found=provider.lookup(str(mpn).strip())
            if found:return found
        except Exception as e:errors.append(f"{provider.name}: {e}")
    if errors: result.status="LOOKUP ERROR"; result.confidence="NONE"
    else: result.status="NOT FOUND / PROVIDER NOT CONFIGURED"; result.confidence="NONE"
    return result
