"""Parametric oilfield flange MCP demo core."""

from .core import (
    FlangeSpec,
    FlangedSpoolSpec,
    GasketSpec,
    build_flange,
    expected_volume,
    flanged_spool_component_shapes,
    make_flanged_spool,
    validate_flanged_spool,
    validate_gasket,
    validate_spec,
)
from .gasket_part import GasketPartSpec, build_gasket_part, expected_gasket_volume, validate_gasket_part

__all__ = [
    "FlangeSpec",
    "FlangedSpoolSpec",
    "GasketSpec",
    "build_flange",
    "expected_volume",
    "flanged_spool_component_shapes",
    "make_flanged_spool",
    "validate_flanged_spool",
    "validate_gasket",
    "validate_spec",
    "GasketPartSpec",
    "build_gasket_part",
    "expected_gasket_volume",
    "validate_gasket_part",
]

