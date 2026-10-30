"""Drawing worker used by the MCP server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build123d import import_step
from flange_mcp import FlangeSpec, FlangedSpoolSpec
from flange_mcp.drawing import make_drawing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--formats-json", required=True)
    parser.add_argument("--context-json", default="{}")
    parser.add_argument("--assembly-json", default="null")
    args = parser.parse_args()
    spec = FlangeSpec.from_mapping(json.loads(args.spec_json))
    shape = import_step(Path(args.output_dir) / "flange.step")
    raw_assembly = json.loads(args.assembly_json)
    assembly = (
        FlangedSpoolSpec.from_mapping(raw_assembly, spec)
        if raw_assembly is not None
        else None
    )
    result = make_drawing(
        shape,
        spec,
        args.output_dir,
        json.loads(args.formats_json),
        json.loads(args.context_json),
        assembly,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

