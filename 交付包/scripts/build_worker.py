"""Build worker used by the MCP server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flange_mcp import FlangeSpec, build_flange


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    spec = FlangeSpec.from_mapping(json.loads(args.spec_json))
    _, metadata = build_flange(spec, args.output_dir)
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

