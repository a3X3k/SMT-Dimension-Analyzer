from dataclasses import dataclass
from urllib.parse import quote_plus

@dataclass
class LookupLink:
    provider:str
    url:str

def lookup_links(mpn):
    q=quote_plus(str(mpn).strip())
    return [
        LookupLink("Manufacturer / web search",f"https://www.google.com/search?q={q}+datasheet+dimensions+package"),
        LookupLink("Octopart search",f"https://octopart.com/search?q={q}"),
        LookupLink("DigiKey search",f"https://www.digikey.com/en/products/result?keywords={q}"),
        LookupLink("Mouser search",f"https://www.mouser.com/c/?q={q}"),
    ]
