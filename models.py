from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class BomRecord:
    ref: str
    mpn: str
    raw: dict = field(default_factory=dict)

@dataclass
class UniquePart:
    mpn: str
    refs: list[str]
    representative_ref: str

@dataclass
class CadRecord:
    ref: str
    mpn: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    rotation: Optional[float] = None
    layer: str = ""
    raw: dict = field(default_factory=dict)

@dataclass
class ProjectState:
    name: str = "Untitled Project"
    bom_path: Optional[Path] = None
    cad_path: Optional[Path] = None
    odb_path: Optional[Path] = None
    gerber_paths: list[Path] = field(default_factory=list)
    bom_records: list[BomRecord] = field(default_factory=list)
    unique_parts: list[UniquePart] = field(default_factory=list)
    cad_records: list[CadRecord] = field(default_factory=list)
    gerber_documents: list = field(default_factory=list)
    dimension_results: dict = field(default_factory=dict)\n    mpn_lookup_results: dict = field(default_factory=dict)
    manual_gerber_matches: dict = field(default_factory=dict)
