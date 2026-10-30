"""Day 2 parameter, variation, and invalid-input checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flange_mcp import FlangeSpec, build_flange, expected_volume


def valid_case(name: str, values: dict, expected_bbox: dict[str, float]) -> dict:
    spec = FlangeSpec.from_mapping(values)
    output_dir = ROOT / "out" / f"flange_day2_{name}"
    _, metadata = build_flange(spec, output_dir)
    expected = expected_volume(spec)
    volume_error = abs(metadata["volume_mm3"] - expected) / expected
    bbox_ok = all(
        abs(metadata["bbox_mm"][axis] - value) <= 1e-6
        for axis, value in expected_bbox.items()
    )
    checks = {
        "volume": volume_error <= 1e-6,
        "bbox": bbox_ok,
        "is_valid": metadata["is_valid"],
        "solid_count": metadata["solid_count"] == 1,
        "cylindrical_face_count": metadata["cylindrical_face_count"]
        == spec.bolt_count + 2,
    }
    return {
        "name": name,
        "kind": "valid",
        "ok": all(checks.values()),
        "spec": spec.as_dict(),
        "checks": checks,
        "volume_relative_error": volume_error,
        "metadata": metadata,
        "output_dir": str(output_dir),
    }


def invalid_case(name: str, values: dict) -> dict:
    try:
        spec = FlangeSpec.from_mapping(values)
        build_flange(spec)
    except (TypeError, ValueError, RuntimeError) as exc:
        return {
            "name": name,
            "kind": "invalid",
            "ok": True,
            "values": values,
            "error": str(exc),
        }
    return {
        "name": name,
        "kind": "invalid",
        "ok": False,
        "values": values,
        "error": "invalid input was accepted",
    }


def main() -> int:
    cases = [
        valid_case(
            "default",
            {},
            {"x": 120.0, "y": 120.0, "z": 15.0},
        ),
        valid_case(
            "larger_six_bolt",
            {
                "od": 160,
                "thickness": 20,
                "center_hole": 50,
                "bolt_count": 6,
                "bolt_diameter": 14,
                "pcd": 120,
            },
            {"x": 160.0, "y": 160.0, "z": 20.0},
        ),
        invalid_case("center_hole_too_large", {"center_hole": 120}),
        invalid_case("bolt_circle_outside", {"pcd": 115}),
        invalid_case("zero_bolts", {"bolt_count": 0}),
        invalid_case("fractional_bolts", {"bolt_count": 4.5}),
    ]
    result = {"ok": all(case["ok"] for case in cases), "cases": cases}
    output_dir = ROOT / "out" / "day2_cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


