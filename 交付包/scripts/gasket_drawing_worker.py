"""Standalone gasket drawing worker used by the MCP server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build123d import import_step
from flange_mcp.gasket_part import GasketPartSpec, make_gasket_drawing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--formats-json", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    spec = GasketPartSpec.from_mapping(json.loads(args.spec_json))
    shape = import_step(output / "gasket.step")
    result = make_gasket_drawing(shape, spec, output, json.loads(args.formats_json))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
