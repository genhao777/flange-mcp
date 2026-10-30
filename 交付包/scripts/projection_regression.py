"""Regression proving drawings follow B-rep topology rather than requested text."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flange_mcp.core import FlangeSpec, _build123d_shape
from flange_mcp.drawing import _make_views, _measure_shape


def main() -> int:
    shape_three = _build123d_shape(FlangeSpec(bolt_count=3))
    shape_four = _build123d_shape(FlangeSpec(bolt_count=4))
    measured_three = _measure_shape(shape_three)
    measured_four = _measure_shape(shape_four)
    top_three = _make_views(shape_three)[1].visible.edges()
    top_four = _make_views(shape_four)[1].visible.edges()
    assert measured_three["bolt_count"] == 3
    assert measured_four["bolt_count"] == 4
    assert len(top_three) == 5
    assert len(top_four) == 6
    print("projection regression ok: 3-hole top has 5 visible edges; 4-hole top has 6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
