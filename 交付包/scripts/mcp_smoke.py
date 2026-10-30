"""MCP stdio smoke test."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


async def main() -> None:
    print("smoke: start", flush=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    params = StdioServerParameters(
        command=str(PYTHON),
        args=["-m", "flange_mcp.server"],
        env=env,
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("smoke: initialized", flush=True)
            listed = await session.list_tools()
            names = [tool.name for tool in listed.tools]
            catalog = await session.call_tool("part_catalog", {})
            catalog_payload = catalog.structuredContent or {}
            if catalog.isError or not catalog_payload.get("assemblies"):
                raise RuntimeError(f"part_catalog did not expose the assembly template: {catalog_payload}")
            created = await session.call_tool(
                "part_create",
                {
                    "params": {
                        "od": 140,
                        "thickness": 18,
                        "center_hole": 45,
                        "bolt_count": 4,
                        "bolt_diameter": 12,
                        "pcd": 100,
                        "context": {
                            "line_id": "L-101",
                            "service": "pressure test",
                            "material": "A105",
                        },
                    }
                },
            )
            print("smoke: flange created", flush=True)
            payload = created.structuredContent or {}
            part_id = payload.get("part_id")
            checked = await session.call_tool("part_check", {"part_id": part_id})
            check_payload = checked.structuredContent or {}
            if checked.isError or not check_payload.get("ok"):
                raise RuntimeError(
                    "part_check did not validate the created non-default flange: "
                    f"{check_payload}"
                )
            if check_payload.get("warnings"):
                raise RuntimeError(f"unexpected design warnings for smoke spec: {check_payload}")
            drawn = await session.call_tool(
                "drawing_make",
                {"part_id": part_id, "formats": ["dxf", "pdf", "png", "render", "viewer"]},
            )
            print("smoke: flange drawings", flush=True)
            drawing_payload = drawn.structuredContent or {}
            if drawn.isError:
                raise RuntimeError(f"drawing_make failed: {drawing_payload}")
            if drawing_payload.get("projection_source") != "delivered STEP B-rep via build123d.Drawing":
                raise RuntimeError(f"drawing source is not the delivered STEP B-rep: {drawing_payload}")
            readback = drawing_payload.get("readback") or {}
            if readback.get("view_count") != 3:
                raise RuntimeError(f"drawing did not produce three projected views: {drawing_payload}")
            if readback.get("dimension_count") != 5:
                raise RuntimeError(f"DXF did not contain five native dimensions: {drawing_payload}")
            if drawing_payload.get("render_source") != "delivered STEP B-rep tessellation":
                raise RuntimeError(f"presentation preview is not derived from the B-rep: {drawing_payload}")
            if drawing_payload.get("viewer_source") != "delivered STEP B-rep tessellation with offline canvas controls":
                raise RuntimeError(f"interactive viewer is not derived from the B-rep: {drawing_payload}")
            if drawing_payload.get("context", {}).get("line_id") != "L-101":
                raise RuntimeError(f"drawing did not retain oilfield context: {drawing_payload}")
            measured = drawing_payload.get("measured_dimensions") or {}
            if measured != check_payload.get("spec"):
                raise RuntimeError(
                    "drawing measurements do not match the stored request: "
                    f"measured={measured}, spec={check_payload.get('spec')}"
                )
            manifest_path = Path(payload.get("artifacts", {}).get("run_manifest", ""))
            if not manifest_path.is_file():
                raise RuntimeError(f"run manifest missing: {manifest_path}")
            delivery_manifest = drawing_payload.get("paths", {}).get("delivery_manifest")
            if not delivery_manifest or not Path(delivery_manifest).is_file():
                raise RuntimeError(f"delivery manifest missing: {delivery_manifest}")

            assembled = await session.call_tool(
                "drawing_make",
                {
                    "part_id": part_id,
                    "formats": ["dxf", "pdf", "png", "render", "viewer", "assembly"],
                    "assembly": {
                        "pipe_od": 45,
                        "pipe_id": 32,
                        "pipe_length": 120,
                        "include_end_flange": True,
                    },
                },
            )
            print("smoke: spool assembly", flush=True)
            assembly_payload = assembled.structuredContent or {}
            assembly_check = assembly_payload.get("assembly") or {}
            if assembled.isError or not assembly_payload.get("ok"):
                raise RuntimeError(f"flanged spool assembly failed: {assembly_payload}")
            expected_assembly = {
                "component_count": 3,
                "interface_count": 2,
                "coaxial": True,
                "end_faces_flush": True,
                "bolt_pattern_aligned": True,
                "bore_continuous": True,
            }
            if any(assembly_check.get(key) != value for key, value in expected_assembly.items()):
                raise RuntimeError(f"assembly checks did not pass: {assembly_payload}")
            for key in ("assembly_step", "assembly_stl", "assembly_viewer", "assembly_report"):
                artifact = assembly_payload.get("paths", {}).get(key)
                if not artifact or not Path(artifact).is_file():
                    raise RuntimeError(f"assembly artifact missing: {artifact}")

            gasket_assembled = await session.call_tool(
                "drawing_make",
                {
                    "part_id": part_id,
                    "formats": ["assembly", "viewer"],
                    "assembly": {
                        "pipe_od": 40,
                        "pipe_id": 32,
                        "pipe_length": 120,
                        "include_end_flange": True,
                        "include_gaskets": True,
                        "gasket": {
                            "outer_diameter": 88,
                            "inner_diameter": 42,
                            "thickness": 3,
                            "material": "PTFE",
                        },
                    },
                },
            )
            print("smoke: gasket assembly", flush=True)
            gasket_payload = gasket_assembled.structuredContent or {}
            gasket_check = gasket_payload.get("assembly") or {}
            expected_gasket = {
                "component_count": 5,
                "interface_count": 4,
                "coaxial": True,
                "end_faces_flush": True,
                "bolt_pattern_aligned": True,
                "bore_continuous": True,
                "include_gaskets": True,
            }
            if gasket_assembled.isError or not gasket_payload.get("ok"):
                raise RuntimeError(f"gasket assembly failed: {gasket_payload}")
            if any(gasket_check.get(key) != value for key, value in expected_gasket.items()):
                raise RuntimeError(f"gasket assembly checks did not pass: {gasket_payload}")
            for key in ("assembly_step", "assembly_stl", "assembly_viewer", "assembly_report", "delivery_manifest"):
                artifact = gasket_payload.get("paths", {}).get(key)
                if not artifact or not Path(artifact).is_file():
                    raise RuntimeError(f"gasket assembly artifact missing: {artifact}")
            invalid_gasket = await session.call_tool(
                "drawing_make",
                {
                    "part_id": part_id,
                    "formats": ["assembly"],
                    "assembly": {
                        "pipe_od": 40,
                        "pipe_id": 32,
                        "pipe_length": 120,
                        "include_end_flange": True,
                        "include_gaskets": True,
                        "gasket": {"outer_diameter": 130, "inner_diameter": 42, "thickness": 3},
                    },
                },
            )
            invalid_gasket_payload = invalid_gasket.structuredContent or {}
            if invalid_gasket_payload.get("fault_type") != "GASKET_COVERS_BOLT_HOLES":
                raise RuntimeError(f"invalid gasket had the wrong fault type: {invalid_gasket_payload}")

            standalone_gasket = await session.call_tool(
                "part_create",
                {
                    "params": {
                        "part_type": "gasket",
                        "outer_diameter": 88,
                        "inner_diameter": 42,
                        "thickness": 3,
                        "material": "PTFE",
                    }
                },
            )
            print("smoke: standalone gasket", flush=True)
            standalone_payload = standalone_gasket.structuredContent or {}
            if standalone_gasket.isError or not standalone_payload.get("ok"):
                raise RuntimeError(f"standalone gasket creation failed: {standalone_payload}")
            standalone_check = await session.call_tool(
                "part_check", {"part_id": standalone_payload.get("part_id")}
            )
            standalone_check_payload = standalone_check.structuredContent or {}
            if standalone_check.isError or not standalone_check_payload.get("ok"):
                raise RuntimeError(f"standalone gasket check failed: {standalone_check_payload}")
            if standalone_check_payload.get("items", [])[0].get("expected") is None:
                raise RuntimeError(f"standalone gasket lacks analytic volume check: {standalone_check_payload}")
            standalone_drawn = await session.call_tool(
                "drawing_make",
                {"part_id": standalone_payload.get("part_id"), "formats": ["dxf", "pdf", "png"]},
            )
            standalone_drawing_payload = standalone_drawn.structuredContent or {}
            if standalone_drawn.isError or not standalone_drawing_payload.get("ok"):
                raise RuntimeError(f"standalone gasket drawing failed: {standalone_drawing_payload}")
            if standalone_drawing_payload.get("readback", {}).get("dimension_count") != 2:
                raise RuntimeError(f"standalone gasket drawing dimensions missing: {standalone_drawing_payload}")
            for artifact in standalone_drawing_payload.get("paths", {}).values():
                if not Path(artifact).is_file():
                    raise RuntimeError(f"standalone gasket artifact missing: {artifact}")
            invalid_assembly = await session.call_tool(
                "drawing_make",
                {
                    "part_id": part_id,
                    "formats": ["assembly"],
                    "assembly": {"pipe_od": 50, "pipe_id": 32, "pipe_length": 120},
                },
            )
            invalid_assembly_payload = invalid_assembly.structuredContent or {}
            if invalid_assembly_payload.get("fault_type") != "ASSEMBLY_PIPE_OD_INVALID":
                raise RuntimeError(f"invalid assembly had the wrong fault type: {invalid_assembly_payload}")

            inch_created = await session.call_tool(
                "part_create",
                {
                    "params": {
                        "od": 5.511811,
                        "thickness": 0.708661,
                        "center_hole": 1.771654,
                        "bolt_count": 4,
                        "bolt_diameter": 0.472441,
                        "pcd": 3.937008,
                        "units": "in",
                        "context": {
                            "line_id": "L-101",
                            "service": "pressure test",
                            "material": "A105",
                        },
                    }
                },
            )
            print("smoke: inch case", flush=True)
            inch_payload = inch_created.structuredContent or {}
            inch_spec = inch_payload.get("resolved_spec") or {}
            if inch_created.isError or inch_payload.get("input_units") != "in":
                raise RuntimeError(f"inch input was not normalized: {inch_payload}")
            if abs(float(inch_spec.get("od", 0)) - 140.0) > 1e-3:
                raise RuntimeError(f"inch conversion produced the wrong OD: {inch_payload}")
            if inch_payload.get("context", {}).get("line_id") != "L-101":
                raise RuntimeError(f"oilfield context was not retained: {inch_payload}")

            invalid_created = await session.call_tool(
                "part_create",
                {"params": {"od": 100, "pcd": 110, "bolt_diameter": 20}},
            )
            invalid_payload = invalid_created.structuredContent or {}
            if invalid_created.isError or invalid_payload.get("ok") is not False:
                raise RuntimeError(f"invalid input was not rejected structurally: {invalid_payload}")
            if invalid_payload.get("fault_type") != "BOLT_EDGE_DISTANCE_INVALID":
                raise RuntimeError(f"invalid input had the wrong fault type: {invalid_payload}")
            for artifact in drawing_payload.get("paths", {}).values():
                if not Path(artifact).is_file():
                    raise RuntimeError(f"drawing artifact missing: {artifact}")
            print(
                json.dumps(
                    {
                        "tools": names,
                        "catalog_assembly": catalog_payload.get("assemblies", [])[0].get("name"),
                        "part_id": part_id,
                        "create_is_error": created.isError,
                        "check_is_error": checked.isError,
                        "check_ok": check_payload.get("ok"),
                        "check_spec": check_payload.get("spec"),
                        "check_spec_source": check_payload.get("spec_source"),
                        "drawing_is_error": drawn.isError,
                        "drawing_projection_source": drawing_payload.get("projection_source"),
                        "drawing_view_count": readback.get("view_count"),
                        "drawing_dimension_count": readback.get("dimension_count"),
                        "drawing_measured_dimensions": measured,
                        "drawing_render_source": drawing_payload.get("render_source"),
                        "drawing_viewer_source": drawing_payload.get("viewer_source"),
                        "drawing_context": drawing_payload.get("context"),
                        "assembly": assembly_check,
                        "gasket_assembly": gasket_check,
                        "standalone_gasket": standalone_check_payload,
                        "invalid_assembly_fault_type": invalid_assembly_payload.get("fault_type"),
                        "run_manifest": str(manifest_path),
                        "inch_input_units": inch_payload.get("input_units"),
                        "inch_context": inch_payload.get("context"),
                        "invalid_fault_type": invalid_payload.get("fault_type"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )


if __name__ == "__main__":
    asyncio.run(main())

