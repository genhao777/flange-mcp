"""Generate two MCP cases and write an A/B parameter comparison report."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


async def main() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    params = StdioServerParameters(
        command=str(PYTHON),
        args=["-m", "flange_mcp.server"],
        env=env,
        cwd=str(ROOT),
    )
    cases = {
        "A_default": {
            "od": 140,
            "thickness": 18,
            "center_hole": 45,
            "bolt_count": 4,
            "bolt_diameter": 12,
            "pcd": 100,
            "context": {"line_id": "L-101", "service": "pressure test"},
        },
        "B_six_bolt": {
            "od": 160,
            "thickness": 20,
            "center_hole": 50,
            "bolt_count": 6,
            "bolt_diameter": 14,
            "pcd": 120,
            "context": {"line_id": "L-101-B", "service": "pressure test"},
        },
    }
    records: dict[str, dict] = {}
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for name, spec in cases.items():
                created = await session.call_tool("part_create", {"params": spec})
                payload = created.structuredContent or {}
                if created.isError or not payload.get("ok"):
                    raise RuntimeError(f"case {name} failed: {payload}")
                checked = await session.call_tool(
                    "part_check", {"part_id": payload["part_id"]}
                )
                check = checked.structuredContent or {}
                if checked.isError or not check.get("ok"):
                    raise RuntimeError(f"case {name} did not validate: {check}")
                records[name] = {
                    "part_id": payload["part_id"],
                    "spec": check["spec"],
                    "volume_mm3": payload["metadata"]["volume_mm3"],
                    "artifacts": payload["artifacts"],
                }

    first = records["A_default"]
    second = records["B_six_bolt"]
    comparison = {
        "ok": True,
        "cases": records,
        "delta": {
            "od_mm": second["spec"]["od"] - first["spec"]["od"],
            "thickness_mm": second["spec"]["thickness"] - first["spec"]["thickness"],
            "bolt_count": second["spec"]["bolt_count"] - first["spec"]["bolt_count"],
            "volume_mm3": second["volume_mm3"] - first["volume_mm3"],
        },
    }
    output = ROOT / "out" / "compare_demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
