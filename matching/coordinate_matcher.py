from dataclasses import dataclass
from typing import Optional

def angular_delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)

@dataclass
class CoordinateVerification:
    delta_x: Optional[float]
    delta_y: Optional[float]
    delta_rotation: Optional[float]
    status: str

def compare_coordinates(cad_x, cad_y, cad_rotation, derived_x, derived_y, derived_rotation,
                        position_tolerance=0.10, rotation_tolerance=1.0):
    if None in (cad_x,cad_y,derived_x,derived_y):
        return CoordinateVerification(None,None,None,'NOT AVAILABLE')
    dx,dy=abs(float(cad_x)-float(derived_x)),abs(float(cad_y)-float(derived_y))
    dr=None if cad_rotation is None or derived_rotation is None else angular_delta(float(cad_rotation),float(derived_rotation))
    if dx>position_tolerance or dy>position_tolerance or (dr is not None and dr>rotation_tolerance):
        status='FAIL'
    elif dr is None:
        status='WARNING'
    else:
        status='PASS'
    return CoordinateVerification(dx,dy,dr,status)
