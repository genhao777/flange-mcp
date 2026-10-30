"""MCP stdio server for the oilfield flange demo."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from .core import (
    FlangeSpec,
    FlangedSpoolSpec,
    design_issues,
    expected_volume,
    fault_type_for_error,
    validate_spec,
)
from .drawing import make_drawing
from .gasket_part import GasketPartSpec, expected_gasket_volume

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "out"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PART_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PART_DIRS: dict[str, Path] = {}

mcp = FastMCP("oilfield-flange")


class FlangeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    od: float = Field(120.0, gt=0, description="Outer diameter in mm")
    thickness: float = Field(15.0, gt=0, description="Thickness in mm")
    center_hole: float = Field(40.0, gt=0, description="Center hole diameter in mm")
    bolt_count: int = Field(4, ge=1, description="Number of equally spaced bolt holes")
    bolt_diameter: float = Field(12.0, gt=0, description="Bolt hole diameter in mm")
    pcd: float = Field(90.0, gt=0, description="Bolt pitch circle diameter in mm")
    units: str = Field("mm", description="Input length units: mm or in")


def _resolve_output_dir(output_dir: str | None) -> Path:
    if not output_dir:
        return OUTPUT_ROOT
    path = Path(str(output_dir)).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _part_dir(part_id: str, output_dir: str | None = None) -> Path:
    if not PART_ID_RE.fullmatch(part_id):
        raise ValueError("invalid part_id")
    if output_dir:
        exact = _resolve_output_dir(output_dir)
        if (exact / "metadata.json").is_file():
            return exact
        for name in (f"flange_{part_id}", f"gasket_{part_id}"):
            candidate = exact / name
            if (candidate / "metadata.json").is_file():
                return candidate
    registered = PART_DIRS.get(part_id)
    if registered and (registered / "metadata.json").is_file():
        return registered
    for name in (f"flange_{part_id}", f"gasket_{part_id}"):
        candidate = OUTPUT_ROOT / name
        if (candidate / "metadata.json").is_file():
            return candidate
    raise FileNotFoundError(f"part not found: {part_id}")


def _resolve_values(values: dict[str, Any] | None) -> tuple[FlangeSpec, str, dict[str, Any]]:
    original = dict(values or {})
    raw = dict(original)
    raw.pop("part_type", None)
    context = raw.pop("context", None)
    if context is not None:
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        allowed_context = {"line_id", "service", "nominal_size", "pressure_class", "material"}
        unknown_context = sorted(set(context) - allowed_context)
        if unknown_context:
            raise ValueError(f"unknown context field(s): {', '.join(unknown_context)}")
        for key, value in context.items():
            if not isinstance(value, (str, int, float)):
                raise ValueError(f"context.{key} must be text or a number")
    unit_value = str(raw.pop("units", "mm")).strip().lower()
    unit_aliases = {
        "mm": "mm",
        "millimeter": "mm",
        "millimeters": "mm",
        "毫米": "mm",
        "in": "in",
        "inch": "in",
        "inches": "in",
        "英寸": "in",
    }
    if unit_value not in unit_aliases:
        raise ValueError("units must be mm or in")
    resolved_unit = unit_aliases[unit_value]
    if resolved_unit == "in":
        for name in ("od", "thickness", "center_hole", "bolt_diameter", "pcd"):
            if name in raw:
                raw[name] = float(raw[name]) * 25.4
    model = FlangeParams.model_validate({**raw, "units": resolved_unit})
    model_values = model.model_dump()
    model_values.pop("units", None)
    spec = FlangeSpec.from_mapping(model_values)
    validate_spec(spec)
    return spec, resolved_unit, original


def _spec_from_values(values: dict[str, Any] | None) -> FlangeSpec:
    return _resolve_values(values)[0]


def _resolve_gasket_values(values: dict[str, Any] | None) -> tuple[GasketPartSpec, str, dict[str, Any]]:
    original = dict(values or {})
    raw = dict(original)
    unit_value = str(raw.pop("units", "mm")).strip().lower()
    unit_aliases = {
        "mm": "mm",
        "millimeter": "mm",
        "millimeters": "mm",
        "毫米": "mm",
        "in": "in",
        "inch": "in",
        "inches": "in",
        "英寸": "in",
    }
    if unit_value not in unit_aliases:
        raise ValueError("units must be mm or in")
    resolved_unit = unit_aliases[unit_value]
    if resolved_unit == "in":
        for name in ("outer_diameter", "inner_diameter", "thickness"):
            if name in raw:
                raw[name] = float(raw[name]) * 25.4
    spec = GasketPartSpec.from_mapping(raw)
    return spec, resolved_unit, original


def _artifact_manifest(
    part_dir: Path,
    exclude_names: set[str] | None = None,
) -> dict[str, Any]:
    excluded = {"run.json"} | set(exclude_names or set())
    artifacts: dict[str, Any] = {}
    for path in sorted(part_dir.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts[path.name] = {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}
    return artifacts


def _write_delivery_manifest(
    part_dir: Path,
    part_id: str,
    metadata: dict[str, Any],
    drawing_result: dict[str, Any],
) -> Path:
    """Write the review-ready engineering handoff manifest."""
    manifest_path = part_dir / "delivery_manifest.json"
    payload = {
        "schema_version": "1.0",
        "part_id": part_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": metadata.get("request", {}),
        "input_units": metadata.get("input_units", "mm"),
        "resolved_spec": metadata.get("spec", {}),
        "context": metadata.get("context", {}),
        "geometry": {
            "requested": drawing_result.get("requested_spec", {}),
            "measured": drawing_result.get("measured_dimensions", {}),
            "projection_source": drawing_result.get("projection_source"),
        },
        "checks": {
            "part": json.loads((part_dir / "check.json").read_text(encoding="utf-8"))
            if (part_dir / "check.json").is_file()
            else None,
            "assembly": drawing_result.get("assembly"),
            "drawing_readback": drawing_result.get("readback", {}),
        },
        "artifacts": _artifact_manifest(part_dir, {"delivery_manifest.json"}),
        "notes": [
            "尺寸和投影来自已交付 STEP B-rep；最终加工前仍需人工工程审核。",
            "本清单记录本次生成的输入、实测结果、检查结果和文件哈希。",
        ],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _write_run_manifest(
    part_dir: Path,
    part_id: str,
    request: dict[str, Any],
    input_units: str,
    resolved_spec: FlangeSpec,
    metadata: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> None:
    manifest = {
        "part_id": part_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "input_units": input_units,
        "resolved_spec": resolved_spec.as_dict(),
        "context": context or {},
        "geometry": {
            "volume_mm3": metadata.get("volume_mm3"),
            "bbox_mm": metadata.get("bbox_mm"),
            "solid_count": metadata.get("solid_count"),
            "cylindrical_face_count": metadata.get("cylindrical_face_count"),
            "design_issues": metadata.get("design_issues", []),
        },
        "toolchain": {"python": sys.version.split()[0], "service": "oilfield-flange"},
        "artifacts": _artifact_manifest(part_dir),
    }
    (part_dir / "run.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_gasket_run_manifest(
    part_dir: Path,
    part_id: str,
    request: dict[str, Any],
    input_units: str,
    spec: GasketPartSpec,
    metadata: dict[str, Any],
) -> None:
    manifest = {
        "part_id": part_id,
        "part_type": "gasket",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "input_units": input_units,
        "resolved_spec": spec.as_dict(),
        "geometry": {
            "volume_mm3": metadata.get("volume_mm3"),
            "expected_volume_mm3": metadata.get("expected_volume_mm3"),
            "bbox_mm": metadata.get("bbox_mm"),
            "solid_count": metadata.get("solid_count"),
            "cylindrical_face_count": metadata.get("cylindrical_face_count"),
        },
        "toolchain": {"python": sys.version.split()[0], "service": "oilfield-flange"},
        "artifacts": _artifact_manifest(part_dir),
    }
    (part_dir / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


async def _build_in_worker(spec: FlangeSpec, output_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    process = await asyncio.create_subprocess_exec(
        str(PYTHON),
        str(ROOT / "scripts" / "build_worker.py"),
        "--spec-json",
        json.dumps(spec.as_dict(), ensure_ascii=False),
        "--output-dir",
        str(output_dir),
        cwd=str(ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("geometry worker timed out after 120 seconds") from exc
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"geometry worker failed with code {process.returncode}")
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"geometry worker returned invalid JSON: {message}") from exc


async def _build_gasket_in_worker(spec: GasketPartSpec, output_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    process = await asyncio.create_subprocess_exec(
        str(PYTHON),
        str(ROOT / "scripts" / "gasket_worker.py"),
        "--spec-json",
        json.dumps(spec.as_dict(), ensure_ascii=False),
        "--output-dir",
        str(output_dir),
        cwd=str(ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("gasket worker timed out after 120 seconds") from exc
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"gasket worker failed with code {process.returncode}")
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"gasket worker returned invalid JSON: {message}") from exc


async def _gasket_drawing_in_worker(
    spec: GasketPartSpec,
    output_dir: Path,
    formats: list[str],
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    process = await asyncio.create_subprocess_exec(
        str(PYTHON),
        str(ROOT / "scripts" / "gasket_drawing_worker.py"),
        "--spec-json",
        json.dumps(spec.as_dict(), ensure_ascii=False),
        "--output-dir",
        str(output_dir),
        "--formats-json",
        json.dumps(formats, ensure_ascii=False),
        cwd=str(ROOT),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("gasket drawing worker timed out after 120 seconds") from exc
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"gasket drawing worker failed with code {process.returncode}")
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"gasket drawing worker returned invalid JSON: {message}") from exc


async def _drawing_in_worker(
    spec: FlangeSpec,
    output_dir: Path,
    formats: list[str],
    context: dict[str, Any] | None = None,
    assembly: FlangedSpoolSpec | None = None,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    process = await asyncio.create_subprocess_exec(
        str(PYTHON),
        str(ROOT / "scripts" / "drawing_worker.py"),
        "--spec-json",
        json.dumps(spec.as_dict(), ensure_ascii=False),
        "--output-dir",
        str(output_dir),
        "--formats-json",
        json.dumps(formats, ensure_ascii=False),
        "--context-json",
        json.dumps(context or {}, ensure_ascii=False),
        "--assembly-json",
        json.dumps(assembly.as_dict() if assembly else None, ensure_ascii=False),
        cwd=str(ROOT),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("drawing worker timed out after 60 seconds") from exc
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"drawing worker failed with code {process.returncode}")
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"drawing worker returned invalid JSON: {message}") from exc


@mcp.tool()
def part_catalog() -> dict[str, Any]:
    """Return supported part types and their parameter ranges."""
    return {
        "part_types": [
            {
                "name": "perforated_flange",
                "description": "Flat circular flange with a center hole and equally spaced bolt holes",
                "parameters": {
                    "od": {"unit": "mm", "min": 1, "default": 120},
                    "thickness": {"unit": "mm", "min": 1, "default": 15},
                    "center_hole": {"unit": "mm", "min": 0.1, "default": 40},
                    "bolt_count": {"unit": "count", "min": 1, "integer": True, "default": 4},
                    "bolt_diameter": {"unit": "mm", "min": 0.1, "default": 12},
                    "pcd": {"unit": "mm", "min": 0.1, "default": 90},
                    "units": {"unit": "enum", "values": ["mm", "in"], "default": "mm"},
                    "context": {
                        "unit": "object",
                        "optional_fields": [
                            "line_id",
                            "service",
                            "nominal_size",
                            "pressure_class",
                            "material",
                        ],
                    },
                    "output_dir": {
                        "unit": "path",
                        "optional": True,
                        "description": "Exact directory where this request writes its generated files",
                    },
                },
            },
            {
                "name": "gasket",
                "description": "Standalone flat annular sealing gasket or gasket used by the flanged spool assembly",
                "creation_mode": "part_create part_type=gasket",
                "parameters": {
                    "outer_diameter": {"unit": "mm", "default": 88},
                    "inner_diameter": {"unit": "mm", "default": 42},
                    "thickness": {"unit": "mm", "default": 3},
                    "material": {"unit": "text", "default": "非金属密封垫"},
                    "output_dir": {
                        "unit": "path",
                        "optional": True,
                        "description": "Exact directory where this request writes its generated files",
                    },
                },
            },
        ],
        "assemblies": [
            {
                "name": "flanged_spool",
                "description": "Two matching flanges joined by a coaxial pipe spool, optionally sealed by two gaskets",
                "parameters": {
                    "pipe_od": {"unit": "mm", "default": "center_hole (or center_hole - 5 when gaskets are enabled)"},
                    "pipe_id": {"unit": "mm", "default": "pipe_od * 0.7"},
                    "pipe_length": {"unit": "mm", "default": "max(OD * 0.85, 80)"},
                    "include_end_flange": {"unit": "boolean", "default": True},
                    "include_gaskets": {"unit": "boolean", "default": False},
                    "gasket": {"unit": "object", "optional": True},
                },
                "checks": ["component_count", "interface_count", "coaxial", "end_faces_flush", "bolt_pattern_aligned", "axis_continuous", "min_bore_mm", "interface_gap_max_mm"],
            }
        ],
    }


@mcp.tool()
async def part_create(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a flange or standalone gasket and return measured geometry metadata."""
    request_params = dict(params or {})
    requested_type = str(request_params.get("part_type", "perforated_flange")).strip().lower()
    requested_output_dir = request_params.pop("output_dir", None)
    if requested_type == "gasket":
        try:
            spec, input_units, request = _resolve_gasket_values(request_params)
        except (TypeError, ValueError) as exc:
            message = str(exc)
            return {
                "ok": False,
                "fault_type": fault_type_for_error(message),
                "error": message,
                "request": params or {},
            }
        part_id = uuid4().hex[:8]
        output_dir = (
            _resolve_output_dir(requested_output_dir)
            if requested_output_dir
            else OUTPUT_ROOT / f"gasket_{part_id}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        PART_DIRS[part_id] = output_dir
        request["output_dir"] = str(output_dir)
        metadata = await _build_gasket_in_worker(spec, output_dir)
        metadata["request"] = request
        metadata["input_units"] = input_units
        metadata["resolved_spec"] = spec.as_dict()
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _write_gasket_run_manifest(output_dir, part_id, request, input_units, spec, metadata)
        return {
            "ok": True,
            "part_type": "gasket",
            "part_id": part_id,
            "artifacts": {
                "step": str(output_dir / "gasket.step"),
                "stl": str(output_dir / "gasket.stl"),
                "metadata": str(output_dir / "metadata.json"),
                "run_manifest": str(output_dir / "run.json"),
            },
            "request": request,
            "input_units": input_units,
            "resolved_spec": spec.as_dict(),
            "output_dir": str(output_dir),
            "metadata": metadata,
        }
    if requested_type != "perforated_flange":
        message = f"unsupported part_type: {requested_type}"
        return {
            "ok": False,
            "fault_type": "PART_TYPE_UNSUPPORTED",
            "error": message,
            "request": params or {},
        }
    try:
        spec, input_units, request = _resolve_values(request_params)
    except (TypeError, ValueError) as exc:
        message = str(exc)
        return {
            "ok": False,
            "fault_type": fault_type_for_error(message),
            "error": message,
            "request": params or {},
        }
    part_id = uuid4().hex[:8]
    output_dir = (
        _resolve_output_dir(requested_output_dir)
        if requested_output_dir
        else OUTPUT_ROOT / f"flange_{part_id}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    PART_DIRS[part_id] = output_dir
    request["output_dir"] = str(output_dir)
    metadata = await _build_in_worker(spec, output_dir)
    metadata["request"] = request
    metadata["input_units"] = input_units
    metadata["resolved_spec"] = spec.as_dict()
    metadata["context"] = request.get("context", {})
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_run_manifest(
        output_dir,
        part_id,
        request,
        input_units,
        spec,
        metadata,
        context=metadata["context"],
    )
    return {
        "ok": True,
        "part_id": part_id,
        "artifacts": {
            "step": str(output_dir / "flange.step"),
            "stl": str(output_dir / "flange.stl"),
            "metadata": str(output_dir / "metadata.json"),
            "run_manifest": str(output_dir / "run.json"),
        },
        "request": request,
        "input_units": input_units,
        "context": metadata["context"],
        "resolved_spec": spec.as_dict(),
        "output_dir": str(output_dir),
        "metadata": metadata,
    }


@mcp.tool()
def part_check(
    part_id: str,
    spec: dict[str, Any] | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Check a generated flange against its request specification.

    With no ``spec`` argument, the resolved specification stored by
    :func:`part_create` is used.  Passing ``spec`` is an explicit comparison
    against another expected specification and is useful for negative tests.
    """
    part_dir = _part_dir(part_id, output_dir)
    metadata = json.loads((part_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("part_type") == "gasket":
        try:
            actual_spec = GasketPartSpec.from_mapping(spec or metadata.get("spec", {}))
        except (TypeError, ValueError) as exc:
            message = str(exc)
            result = {
                "ok": False,
                "spec_source": "provided" if spec is not None else "stored",
                "fault_type": fault_type_for_error(message),
                "error": message,
                "items": [],
                "warnings": [],
            }
            (part_dir / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        expected = expected_gasket_volume(actual_spec)
        actual = float(metadata.get("volume_mm3", 0.0))
        bbox = metadata.get("bbox_mm", {})
        items = [
            {"name": "volume_mm3", "expected": expected, "actual": actual, "pass": abs(actual - expected) / expected <= 1e-6},
            {"name": "bbox_mm", "expected": {"x": actual_spec.outer_diameter, "y": actual_spec.outer_diameter, "z": actual_spec.thickness}, "actual": bbox, "pass": all(abs(float(bbox.get(axis, 0.0)) - value) <= 1e-6 for axis, value in {"x": actual_spec.outer_diameter, "y": actual_spec.outer_diameter, "z": actual_spec.thickness}.items())},
            {"name": "solid_count", "expected": 1, "actual": metadata.get("solid_count"), "pass": metadata.get("solid_count") == 1},
            {"name": "cylindrical_face_count", "expected": 2, "actual": metadata.get("cylindrical_face_count"), "pass": metadata.get("cylindrical_face_count") == 2},
            {"name": "is_valid", "expected": True, "actual": metadata.get("is_valid"), "pass": metadata.get("is_valid") is True},
        ]
        result = {
            "ok": all(item["pass"] for item in items),
            "part_type": "gasket",
            "spec": actual_spec.as_dict(),
            "spec_source": "provided" if spec is not None else "stored",
            "items": items,
            "fault_type": None,
            "warnings": [],
        }
        (part_dir / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    # A create request stores the fully resolved specification in metadata.json.
    # When the caller does not provide an explicit expectation, check against
    # that stored request instead of silently falling back to the 120 mm demo
    # defaults.  This keeps a changed-parameter run green and ties the report
    # to the geometry that was actually created.
    if spec is None:
        try:
            actual_spec = FlangeSpec.from_mapping(metadata["spec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                "generated part metadata is missing a valid stored specification"
            ) from exc
        spec_source = "stored"
    else:
        try:
            actual_spec = _spec_from_values(spec)
        except (TypeError, ValueError) as exc:
            message = str(exc)
            result = {
                "ok": False,
                "spec_source": "provided",
                "fault_type": fault_type_for_error(message),
                "error": message,
                "items": [],
                "warnings": [],
            }
            (part_dir / "check.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return result
        spec_source = "provided"
    expected = expected_volume(actual_spec)
    actual = float(metadata["volume_mm3"])
    bbox = metadata["bbox_mm"]
    items = [
        {
            "name": "volume_mm3",
            "expected": expected,
            "actual": actual,
            "pass": abs(actual - expected) / expected <= 1e-6,
        },
        {
            "name": "bbox_mm",
            "expected": {"x": actual_spec.od, "y": actual_spec.od, "z": actual_spec.thickness},
            "actual": bbox,
            "pass": all(
                abs(bbox[axis] - value) <= 1e-6
                for axis, value in {"x": actual_spec.od, "y": actual_spec.od, "z": actual_spec.thickness}.items()
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
            "expected": actual_spec.bolt_count + 2,
            "actual": metadata.get("cylindrical_face_count"),
            "pass": metadata.get("cylindrical_face_count") == actual_spec.bolt_count + 2,
        },
        {
            "name": "is_valid",
            "expected": True,
            "actual": metadata.get("is_valid"),
            "pass": metadata.get("is_valid") is True,
        },
    ]
    result = {
        "ok": all(item["pass"] for item in items),
        "spec": actual_spec.as_dict(),
        "spec_source": spec_source,
        "items": items,
        "fault_type": None,
        "warnings": design_issues(actual_spec),
    }
    (part_dir / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = part_dir / "run.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["check"] = {
            "ok": result["ok"],
            "spec_source": spec_source,
            "fault_type": result["fault_type"],
            "warnings": result["warnings"],
        }
        manifest["artifacts"] = _artifact_manifest(part_dir)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


@mcp.tool()
async def drawing_make(
    part_id: str,
    formats: list[str] | None = None,
    assembly: dict[str, Any] | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Create drawings, previews, or a constrained flange-pipe-flange assembly."""
    part_dir = _part_dir(part_id, output_dir)
    metadata = json.loads((part_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("part_type") == "gasket":
        spec = GasketPartSpec.from_mapping(metadata.get("spec", {}))
        requested = set(formats or ["dxf", "pdf", "png"])
        unsupported = sorted(requested - {"dxf", "pdf", "png"})
        if unsupported:
            raise ValueError(f"unsupported gasket drawing format(s): {', '.join(unsupported)}")
        result = await _gasket_drawing_in_worker(spec, part_dir, sorted(requested))
        delivery_manifest = _write_delivery_manifest(part_dir, part_id, metadata, result)
        result.setdefault("paths", {})["delivery_manifest"] = str(delivery_manifest)
        return result
    spec = FlangeSpec.from_mapping(metadata["spec"])
    requested = set(formats or ["dxf", "pdf", "png", "render", "viewer"])
    if assembly is not None:
        requested.add("assembly")
    unsupported = sorted(set(requested) - {"dxf", "pdf", "png", "render", "viewer", "assembly"})
    if unsupported:
        raise ValueError(f"unsupported drawing format(s): {', '.join(unsupported)}")
    context = metadata.get("context", {})
    try:
        assembly_spec = (
            FlangedSpoolSpec.from_mapping(assembly, spec)
            if "assembly" in requested
            else None
        )
    except (TypeError, ValueError) as exc:
        message = str(exc)
        return {
            "ok": False,
            "fault_type": fault_type_for_error(message),
            "error": message,
            "formats": sorted(requested),
            "assembly": assembly or {},
        }
    result = await _drawing_in_worker(spec, part_dir, sorted(requested), context, assembly_spec)
    delivery_manifest = _write_delivery_manifest(part_dir, part_id, metadata, result)
    result.setdefault("paths", {})["delivery_manifest"] = str(delivery_manifest)
    drawing_json_path = part_dir / "drawing.json"
    if drawing_json_path.is_file():
        drawing_manifest = json.loads(drawing_json_path.read_text(encoding="utf-8"))
        drawing_manifest.setdefault("paths", {})["delivery_manifest"] = str(delivery_manifest)
        drawing_json_path.write_text(
            json.dumps(drawing_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    manifest_path = part_dir / "run.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["drawing"] = {
            "formats": result.get("formats", []),
            "projection_source": result.get("projection_source"),
            "render_source": result.get("render_source"),
            "assembly_source": result.get("assembly_source"),
            "assembly": result.get("assembly"),
        }
        manifest["delivery_manifest"] = {
            "path": str(delivery_manifest),
            "schema_version": "1.0",
        }
        manifest["artifacts"] = _artifact_manifest(part_dir)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")




