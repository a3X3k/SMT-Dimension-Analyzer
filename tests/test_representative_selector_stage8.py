from models import BomRecord, CadRecord
from parsers.bom_parser import group_unique_parts
from matching.representative_selector import select_cad_aware_representatives
from matching.reference_matcher import match_representatives

def test_selects_later_bom_ref_when_first_is_missing_from_cad():
    parts = group_unique_parts([BomRecord('MISSING1', 'PN-A'), BomRecord('C102', 'PN-A'), BomRecord('C103', 'PN-A')])
    summary = select_cad_aware_representatives(parts, [CadRecord('c102', x=1, y=2)])
    assert parts[0].refs == ['MISSING1', 'C102', 'C103']
    assert parts[0].representative_ref == 'C102'
    assert summary.cad_selected == 1
    assert match_representatives(parts, [CadRecord('c102', x=1, y=2)])[0].status == 'MATCHED'

def test_preserves_bom_order_and_chooses_first_unique_cad_match():
    parts = group_unique_parts([BomRecord('A1','P'), BomRecord('A2','P'), BomRecord('A3','P')])
    select_cad_aware_representatives(parts, [CadRecord('A3'), CadRecord('A2')])
    assert parts[0].representative_ref == 'A2'
    assert parts[0].refs == ['A1','A2','A3']

def test_duplicate_cad_ref_is_not_auto_selected():
    parts = group_unique_parts([BomRecord('A1','P'), BomRecord('A2','P')])
    summary = select_cad_aware_representatives(parts, [CadRecord('A2'), CadRecord('a2')])
    assert parts[0].representative_ref == 'A1'
    assert summary.duplicate_only == 1

def test_no_cad_keeps_original_representative():
    parts = group_unique_parts([BomRecord('A1','P'), BomRecord('A2','P')])
    summary = select_cad_aware_representatives(parts, [])
    assert parts[0].representative_ref == 'A1'
    assert summary.retained_original == 1
