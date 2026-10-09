from models import BomRecord, CadRecord
from matching.bom_cad_matcher import match_bom_to_cad
import pytest


def test_match_without_cad_part_numbers_and_case_insensitive_refs():
    cad=[CadRecord(ref="r1"),CadRecord(ref="C2"),CadRecord(ref="U3")]
    bom=[BomRecord(ref="R1",mpn="ABC"),BomRecord(ref="c2",mpn="XYZ"),
         BomRecord(ref="J4",mpn="ONLY-BOM")]
    result=match_bom_to_cad(cad,bom)
    assert [c.mpn for c in cad]==["ABC","XYZ",""]
    assert result=={"matched":{"R1","C2"},"bom_only":{"J4"},"cad_only":{"U3"}}


def test_reimport_clears_old_bom_part_numbers():
    cad=[CadRecord(ref="R1"),CadRecord(ref="C2")]
    match_bom_to_cad(cad,[BomRecord(ref="R1",mpn="OLD"),BomRecord(ref="C2",mpn="P2")])
    result=match_bom_to_cad(cad,[BomRecord(ref="R1",mpn="NEW")])
    assert [c.mpn for c in cad]==["NEW",""]
    assert result["cad_only"]=={"C2"}


def test_conflicting_bom_reference_does_not_change_cad():
    cad=[CadRecord(ref="R1",mpn="PREVIOUS")]
    with pytest.raises(ValueError,match="Conflicting BOM part numbers"):
        match_bom_to_cad(cad,[BomRecord(ref="R1",mpn="P1"),BomRecord(ref="r1",mpn="P2")])
    assert cad[0].mpn=="PREVIOUS"


def test_duplicate_cad_reference_rejected():
    with pytest.raises(ValueError,match="Duplicate CAD reference"):
        match_bom_to_cad([CadRecord(ref="R1"),CadRecord(ref="r1")],[])
