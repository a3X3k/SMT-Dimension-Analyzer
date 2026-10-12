"""Production CAD acceptance: never import spreadsheet errors or duplicate RefDes."""
import pytest
from parsers.cad_parser import parse_cad


@pytest.mark.parametrize("bad_ref", ["#NAME?", "#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NUM!", "#NULL!"])
def test_spreadsheet_error_reference_rejected(tmp_path, bad_ref):
    path = tmp_path / "cad.csv"
    path.write_text(f"Reference,X location,Y location,Angle\nR1,1,2,0\n{bad_ref},3,4,90\n", encoding="utf-8")
    with pytest.raises(ValueError, match="spreadsheet-error CAD reference"):
        parse_cad(path)


def test_duplicate_reference_rejected_case_insensitively(tmp_path):
    path = tmp_path / "cad.csv"
    path.write_text("Reference,X location,Y location,Angle\nR1,1,2,0\nr1,3,4,90\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate CAD reference"):
        parse_cad(path)


def test_clean_cad_still_imports(tmp_path):
    path = tmp_path / "cad.csv"
    path.write_text("Reference,X location,Y location,Angle\nR1,1,2,0\nC1,3,4,90\n", encoding="utf-8")
    assert [r.ref for r in parse_cad(path)] == ["R1", "C1"]
