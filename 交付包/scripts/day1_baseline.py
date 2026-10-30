"""Day 1 acceptance check for the flange geometry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flange_mcp import FlangeSpec, build_flange, expected_volume


def main() -> int:
    spec = FlangeSpec()
    output_dir = ROOT / "out" / "flange_day1"
    try:
        _, metadata = build_flange(spec, output_dir)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    actual = metadata["volume_mm3"]
    expected = expected_volume(spec)
    volume_error = abs(actual - expected) / expected
    bbox = metadata["bbox_mm"]
    items = [
        {
            "name": "volume_mm3",
            "expected": expected,
            "actual": actual,
            "pass": volume_error <= 1e-6,
        },
        {
            "name": "bbox_mm",
            "expected": {"x": 120.0, "y": 120.0, "z": 15.0},
            "actual": bbox,
            "pass": all(
                abs(bbox[key] - value) <= 1e-6
                for key, value in {"x": 120.0, "y": 120.0, "z": 15.0}.items()
            ),
        },
        {
            "name": "solid_count",
            "expected": 1,
            "actual": metadata.get("solid_count"),
            "pass": metadata.get("solid_count") == 1,
        },
        {
            "name": "cylindrical_face_count",
            "expected": 6,
            "actual": metadata.get("cylindrical_face_count"),
            "pass": metadata.get("cylindrical_face_count") == 6,
        },
    ]
    result = {
        "ok": all(item["pass"] for item in items),
        "volume_relative_error": volume_error,
        "items": items,
        "metadata": metadata,
        "output_dir": str(output_dir),
    }
    (output_dir / "check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())



