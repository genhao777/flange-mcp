"""Deterministic flange geometry and verification core."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import cos, hypot, pi, sin
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class FlangeSpec:
    od: float = 120.0
    thickness: float = 15.0
    center_hole: float = 40.0
    bolt_count: int = 4
    bolt_diameter: float = 12.0
    pcd: float = 90.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "FlangeSpec":
        """Build a spec from JSON-like values using the public parameter names."""
        allowed = {
            "od",
            "thickness",
            "center_hole",
            "bolt_count",
            "bolt_diameter",
            "pcd",
        }
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"unknown parameter(s): {', '.join(unknown)}")
        data = dict(values)
        for name in ("od", "thickness", "center_hole", "bolt_diameter", "pcd"):
            if name in data:
                data[name] = float(data[name])
        if "bolt_count" in data:
            raw_count = data["bolt_count"]
            try:
                parsed_count = int(raw_count)
            except (TypeError, ValueError) as exc:
                raise ValueError("bolt_count must be an integer") from exc
            if float(raw_count) != parsed_count:
                raise ValueError("bolt_count must be an integer")
            data["bolt_count"] = parsed_count
        return cls(**data)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GasketSpec:
    """A flat annular gasket used at a flange-to-pipe interface."""

    outer_diameter: float = 88.0
    inner_diameter: float = 42.0
    thickness: float = 3.0
    material: str = "非金属密封垫"

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any] | None,
        flange_spec: FlangeSpec,
        pipe_od: float,
    ) -> "GasketSpec":
        raw = dict(values or {})
        allowed = {"outer_diameter", "inner_diameter", "thickness", "material"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown gasket parameter(s): {', '.join(unknown)}")
        default_outer = min(
            flange_spec.pcd - flange_spec.bolt_diameter,
            max(flange_spec.center_hole + 10.0, flange_spec.od - 10.0),
        )
        data: dict[str, Any] = {
            "outer_diameter": default_outer,
            "inner_diameter": pipe_od + 2.0,
            "thickness": 3.0,
            "material": "非金属密封垫",
        }
        data.update(raw)
        for name in ("outer_diameter", "inner_diameter", "thickness"):
            data[name] = float(data[name])
        if not isinstance(data["material"], str) or not data["material"].strip():
            raise ValueError("gasket material must be text")
        result = cls(**data)
        validate_gasket(result, flange_spec, pipe_od)
        return result

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlangedSpoolSpec:
    """A small, deterministic assembly joining two matching flanges.

    This is intentionally a constrained demo assembly: the pipe is coaxial
    with the flange bore, both end faces are flush, and the second flange uses
    the same bolt pattern.  It is not a general mating or constraint solver.
    """

    pipe_od: float = 40.0
    pipe_id: float = 28.0
    pipe_length: float = 120.0
    include_end_flange: bool = True
    include_gaskets: bool = False
    gasket: GasketSpec | None = None

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any] | None,
        flange_spec: FlangeSpec,
    ) -> "FlangedSpoolSpec":
        raw = dict(values or {})
        allowed = {
            "pipe_od",
            "pipe_id",
            "pipe_length",
            "include_end_flange",
            "include_gaskets",
            "gasket",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown assembly parameter(s): {', '.join(unknown)}")
        data: dict[str, Any] = {
            "pipe_od": flange_spec.center_hole,
            "pipe_id": flange_spec.center_hole * 0.7,
            "pipe_length": max(flange_spec.od * 0.85, 80.0),
            "include_end_flange": True,
        }
        data.update(raw)
        for name in ("pipe_od", "pipe_id", "pipe_length"):
            data[name] = float(data[name])
        if not isinstance(data["include_end_flange"], bool):
            raise ValueError("include_end_flange must be a boolean")
        if not isinstance(data.get("include_gaskets", False), bool):
            raise ValueError("include_gaskets must be a boolean")
        gasket_raw = data.pop("gasket", None)
        if gasket_raw is not None and not isinstance(gasket_raw, Mapping):
            raise ValueError("gasket must be an object")
        if gasket_raw is not None and "include_gaskets" not in raw:
            data["include_gaskets"] = True
        if gasket_raw is not None and not data["include_gaskets"]:
            raise ValueError("gasket requires include_gaskets to be true")
        if data.get("include_gaskets") and "pipe_od" not in raw:
            # Leave a small radial clearance so the default gasket assembly is
            # usable without forcing the caller to repeat pipe dimensions.
            data["pipe_od"] = max(flange_spec.center_hole - 5.0, flange_spec.center_hole * 0.5)
        data["pipe_od"] = float(data["pipe_od"])
        gasket = (
            GasketSpec.from_mapping(gasket_raw, flange_spec, data["pipe_od"])
            if data.get("include_gaskets")
            else None
        )
        result = cls(**data, gasket=gasket)
        validate_flanged_spool(result, flange_spec)
        return result

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_spec(spec: FlangeSpec) -> None:
    if not isinstance(spec.bolt_count, int) or isinstance(spec.bolt_count, bool):
        raise ValueError("bolt_count must be an integer")
    values = {
        "od": spec.od,
        "thickness": spec.thickness,
        "center_hole": spec.center_hole,
        "bolt_diameter": spec.bolt_diameter,
        "pcd": spec.pcd,
    }
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than 0")
    if spec.bolt_count < 1:
        raise ValueError("bolt_count must be at least 1")
    if spec.center_hole >= spec.od:
        raise ValueError("center_hole must be smaller than od")
    if spec.pcd + spec.bolt_diameter >= spec.od:
        raise ValueError("bolt holes must stay inside the flange outer edge")
    if spec.bolt_diameter >= spec.pcd:
        raise ValueError("bolt_diameter must be smaller than pcd")
    if spec.center_hole + spec.bolt_diameter >= spec.pcd:
        raise ValueError("center hole and bolt holes overlap")


def validate_flanged_spool(assembly: FlangedSpoolSpec, flange: FlangeSpec) -> None:
    """Validate the constrained flange-pipe-flange demo assembly."""
    validate_spec(flange)
    for name in ("pipe_od", "pipe_id", "pipe_length"):
        if getattr(assembly, name) <= 0:
            raise ValueError(f"{name} must be greater than 0")
    if assembly.pipe_od > flange.center_hole:
        raise ValueError("pipe_od must not exceed the flange center_hole")
    if assembly.pipe_id >= assembly.pipe_od:
        raise ValueError("pipe_id must be smaller than pipe_od")
    if not assembly.include_end_flange:
        raise ValueError("include_end_flange must be true for the demo assembly")
    if assembly.include_gaskets:
        if assembly.gasket is None:
            raise ValueError("gasket specification is required when include_gaskets is true")
        validate_gasket(assembly.gasket, flange, assembly.pipe_od)


def validate_gasket(gasket: GasketSpec, flange: FlangeSpec, pipe_od: float) -> None:
    """Validate that a gasket can sit between this flange and pipe."""
    for name in ("outer_diameter", "inner_diameter", "thickness"):
        if getattr(gasket, name) <= 0:
            raise ValueError(f"gasket_{name} must be greater than 0")
    if gasket.inner_diameter <= pipe_od:
        raise ValueError("gasket_inner_diameter must exceed pipe_od for clearance")
    if gasket.inner_diameter >= gasket.outer_diameter:
        raise ValueError("gasket_inner_diameter must be smaller than gasket_outer_diameter")
    if gasket.outer_diameter > flange.od:
        raise ValueError("gasket_outer_diameter must not exceed flange od")
    max_outer = flange.pcd - flange.bolt_diameter
    if gasket.outer_diameter > max_outer:
        raise ValueError(
            f"gasket_outer_diameter ({gasket.outer_diameter:g}) must not exceed "
            f"pcd - bolt_diameter ({max_outer:g}); the gasket would cover the bolt holes"
        )
    if gasket.outer_diameter <= flange.center_hole:
        raise ValueError("gasket_outer_diameter must extend beyond the flange center hole")
    if gasket.inner_diameter > flange.center_hole:
        raise ValueError("gasket_inner_diameter must fit inside the flange center hole")


def design_issues(spec: FlangeSpec) -> list[dict[str, Any]]:
    """Return transparent screening checks for a generated flange.

    These are demo-level geometry checks, not a claim of API/ASME/GB
    compliance.  Hard invalid geometry is rejected by :func:`validate_spec`;
    the softer warnings help an engineer notice tight clearances.
    """
    validate_spec(spec)
    edge_distance = (spec.od - spec.pcd - spec.bolt_diameter) / 2
    center_clearance = (spec.pcd - spec.center_hole - spec.bolt_diameter) / 2
    adjacent_center_distance = spec.pcd * sin(pi / spec.bolt_count)
    adjacent_clearance = adjacent_center_distance - spec.bolt_diameter
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str, actual: float, threshold: float) -> None:
        issues.append(
            {
                "fault_type": code,
                "severity": severity,
                "message": message,
                "actual_mm": round(actual, 6),
                "screening_threshold_mm": round(threshold, 6),
            }
        )

    if edge_distance < max(3.0, spec.bolt_diameter * 0.5):
        add(
            "BOLT_EDGE_DISTANCE_TIGHT",
            "warning",
            "bolt holes are close to the outside edge",
            edge_distance,
            max(3.0, spec.bolt_diameter * 0.5),
        )
    if center_clearance < max(3.0, spec.bolt_diameter * 0.25):
        add(
            "CENTER_BOLT_CLEARANCE_TIGHT",
            "warning",
            "center hole is close to the bolt-hole circle",
            center_clearance,
            max(3.0, spec.bolt_diameter * 0.25),
        )
    if adjacent_clearance < max(3.0, spec.bolt_diameter * 0.25):
        add(
            "BOLT_PITCH_CLEARANCE_TIGHT",
            "warning",
            "adjacent bolt holes have a small ligament",
            adjacent_clearance,
            max(3.0, spec.bolt_diameter * 0.25),
        )
    return issues


def fault_type_for_error(message: str) -> str:
    """Map a validation message to a stable demo-facing fault type."""
    text = message.lower()
    if "pipe_od" in text:
        return "ASSEMBLY_PIPE_OD_INVALID"
    if "pipe_id" in text:
        return "ASSEMBLY_PIPE_ID_INVALID"
    if "pipe_length" in text:
        return "ASSEMBLY_PIPE_LENGTH_INVALID"
    if "cover the bolt holes" in text:
        return "GASKET_COVERS_BOLT_HOLES"
    if "gasket" in text:
        return "GASKET_INTERFACE_INVALID"
    if "include_end_flange" in text:
        return "ASSEMBLY_ENDPOINT_INVALID"
    if "center hole" in text and "smaller" in text:
        return "CENTER_HOLE_OUTSIDE_BOUNDARY"
    if "bolt holes must stay" in text:
        return "BOLT_EDGE_DISTANCE_INVALID"
    if "overlap" in text:
        return "CENTER_BOLT_OVERLAP"
    if "bolt_count" in text:
        return "BOLT_COUNT_INVALID"
    if "pcd" in text:
        return "PCD_INVALID"
    if "greater than 0" in text:
        return "DIMENSION_NON_POSITIVE"
    return "SPEC_INVALID"


def expected_volume(spec: FlangeSpec) -> float:
    """Analytic volume in mm^3 for a flat flange with through holes."""
    validate_spec(spec)
    outer = pi * (spec.od / 2) ** 2 * spec.thickness
    center = pi * (spec.center_hole / 2) ** 2 * spec.thickness
    bolts = (
        spec.bolt_count
        * pi
        * (spec.bolt_diameter / 2) ** 2
        * spec.thickness
    )
    return outer - center - bolts


def _build123d_shape(spec: FlangeSpec) -> Any:
    try:
        from build123d import Cylinder, Pos
    except ImportError as exc:
        raise RuntimeError(
            "build123d is not installed; run pip install -r requirements.txt"
        ) from exc

    shape = Cylinder(spec.od / 2, spec.thickness)
    shape = shape - Cylinder(spec.center_hole / 2, spec.thickness)
    radius = spec.pcd / 2
    for index in range(spec.bolt_count):
        angle = 2 * pi * index / spec.bolt_count
        x = radius * cos(angle)
        y = radius * sin(angle)
        shape = shape - Pos(x, y, 0) * Cylinder(
            spec.bolt_diameter / 2, spec.thickness
        )
    return shape


def flanged_spool_component_shapes(
    flange_shape: Any,
    flange_spec: FlangeSpec,
    assembly: FlangedSpoolSpec,
) -> list[tuple[str, Any]]:
    """Return the named B-rep components in assembly order."""
    validate_flanged_spool(assembly, flange_spec)
    from build123d import Cylinder, Pos

    gasket_thickness = assembly.gasket.thickness if assembly.gasket else 0.0
    pipe_center_z = flange_spec.thickness / 2 + gasket_thickness + assembly.pipe_length / 2
    pipe = Pos(0, 0, pipe_center_z) * (
        Cylinder(assembly.pipe_od / 2, assembly.pipe_length)
        - Cylinder(assembly.pipe_id / 2, assembly.pipe_length)
    )
    end_flange_z = flange_spec.thickness + assembly.pipe_length + 2 * gasket_thickness
    end_flange = Pos(0, 0, end_flange_z) * flange_shape

    component_shapes: list[tuple[str, Any]] = [("front_flange", flange_shape)]
    if assembly.gasket is not None:
        gasket_shape = (
            Cylinder(assembly.gasket.outer_diameter / 2, assembly.gasket.thickness)
            - Cylinder(assembly.gasket.inner_diameter / 2, assembly.gasket.thickness)
        )
        front_gasket_z = flange_spec.thickness / 2 + assembly.gasket.thickness / 2
        end_gasket_z = (
            flange_spec.thickness / 2
            + assembly.gasket.thickness
            + assembly.pipe_length
            + assembly.gasket.thickness / 2
        )
        component_shapes.append(("front_gasket", Pos(0, 0, front_gasket_z) * gasket_shape))
    component_shapes.append(("pipe_spool", pipe))
    if assembly.gasket is not None:
        component_shapes.append(("end_gasket", Pos(0, 0, end_gasket_z) * gasket_shape))
    component_shapes.append(("end_flange", end_flange))
    return component_shapes


def make_flanged_spool(
    flange_shape: Any,
    flange_spec: FlangeSpec,
    assembly: FlangedSpoolSpec,
) -> tuple[Any, dict[str, Any]]:
    """Build a coaxial flange-pipe-flange composite for the demo viewer.

    When requested, two annular gaskets are inserted at the flange faces.  All
    assembly flags below are read back from the component B-reps and their
    bounding boxes; they are not unconditional claims about the template.
    """
    validate_flanged_spool(assembly, flange_spec)
    from build123d import Compound
    component_shapes = flanged_spool_component_shapes(flange_shape, flange_spec, assembly)
    composite = Compound.make_composite([shape for _, shape in component_shapes])
    component_map = dict(component_shapes)
    pipe = component_map["pipe_spool"]
    end_flange = component_shapes[-1][1]

    tolerance = 1e-4

    def component_geometry(name: str, component: Any) -> dict[str, Any]:
        bbox = component.bounding_box()
        min_z = float(bbox.min.Z)
        max_z = float(bbox.max.Z)
        return {
            "name": name,
            "bbox_mm": {
                "x": float(bbox.size.X),
                "y": float(bbox.size.Y),
                "z": float(bbox.size.Z),
                "min_z": min_z,
                "max_z": max_z,
            },
            "center_mm": {
                "x": float((bbox.min.X + bbox.max.X) / 2),
                "y": float((bbox.min.Y + bbox.max.Y) / 2),
                "z": float((bbox.min.Z + bbox.max.Z) / 2),
            },
        }

    component_geometry_rows = [component_geometry(name, shape) for name, shape in component_shapes]
    interface_rows = []
    for first, second in zip(component_geometry_rows, component_geometry_rows[1:]):
        # Keep the sign: a positive value is a real gap, while a negative
        # value means that the two B-reps overlap.  Using abs() here would
        # incorrectly report an overlap as a zero-gap interface.
        gap = second["bbox_mm"]["min_z"] - first["bbox_mm"]["max_z"]
        interface_rows.append(
            {
                "from": first["name"],
                "to": second["name"],
                "gap_mm": round(gap, 6),
                "pass": abs(gap) <= tolerance,
            }
        )

    def cylindrical_faces(component: Any) -> list[dict[str, float]]:
        rows: list[dict[str, float]] = []
        for face in component.faces():
            if not str(getattr(face, "geom_type", "")).upper().endswith("CYLINDER"):
                continue
            axis = face.axis_of_rotation
            direction = axis.direction
            rows.append(
                {
                    "radius": float(face.radius),
                    "x": float(axis.position.X),
                    "y": float(axis.position.Y),
                    "z": float(axis.position.Z),
                    "dx": float(direction.X),
                    "dy": float(direction.Y),
                    "dz": float(direction.Z),
                }
            )
        return rows

    def central_bore(cylinders: list[dict[str, float]]) -> dict[str, float]:
        candidates = [row for row in cylinders if row["radius"] < flange_spec.od / 2 - tolerance]
        if not candidates:
            raise ValueError("flange B-rep has no central cylindrical bore")
        return min(candidates, key=lambda row: abs(row["radius"] - flange_spec.center_hole / 2))

    def axis_distance(first: dict[str, float], second: dict[str, float]) -> float:
        return hypot(first["x"] - second["x"], first["y"] - second["y"])

    def axes_parallel(first: dict[str, float], second: dict[str, float]) -> bool:
        dot = first["dx"] * second["dx"] + first["dy"] * second["dy"] + first["dz"] * second["dz"]
        return abs(abs(dot) - 1.0) <= tolerance

    front_cylinders = cylindrical_faces(flange_shape)
    end_cylinders = cylindrical_faces(end_flange)
    pipe_cylinders = cylindrical_faces(pipe)
    front_bore_axis = central_bore(front_cylinders)
    end_bore_axis = central_bore(end_cylinders)
    pipe_outer = max(pipe_cylinders, key=lambda row: row["radius"])
    pipe_inner = min(pipe_cylinders, key=lambda row: row["radius"])

    representative_axes = [("front_flange", front_bore_axis), ("pipe_spool", pipe_outer), ("end_flange", end_bore_axis)]
    if assembly.gasket is not None:
        representative_axes.extend(
            (name, max(cylindrical_faces(shape), key=lambda row: row["radius"]))
            for name, shape in component_shapes
            if "gasket" in name
        )
    reference_axis = front_bore_axis
    axis_offsets = [axis_distance(reference_axis, axis) for _, axis in representative_axes]
    axis_directions_ok = all(axes_parallel(reference_axis, axis) for _, axis in representative_axes)
    coaxial = axis_directions_ok and max(axis_offsets, default=0.0) <= tolerance
    end_faces_flush = all(row["pass"] for row in interface_rows)

    def bolt_centers(cylinders: list[dict[str, float]], bore_axis: dict[str, float]) -> list[tuple[float, float]]:
        holes = [
            row
            for row in cylinders
            if abs(row["radius"] - flange_spec.bolt_diameter / 2) <= tolerance
        ]
        return sorted(
            (round(row["x"] - bore_axis["x"], 6), round(row["y"] - bore_axis["y"], 6))
            for row in holes
        )

    front_bolts = bolt_centers(front_cylinders, front_bore_axis)
    end_bolts = bolt_centers(end_cylinders, end_bore_axis)
    bolt_centers_match = len(front_bolts) == len(end_bolts) and all(
        hypot(x1 - x2, y1 - y2) <= tolerance
        for (x1, y1), (x2, y2) in zip(front_bolts, end_bolts)
    )
    bolt_pcd_measured = (
        2 * sum(hypot(x, y) for x, y in front_bolts) / len(front_bolts)
        if front_bolts
        else 0.0
    )
    bolt_diameter_measured = (
        2 * sum(row["radius"] for row in front_cylinders if abs(row["radius"] - flange_spec.bolt_diameter / 2) <= tolerance)
        / max(len(front_bolts), 1)
    )
    bolt_count_pass = len(front_bolts) == flange_spec.bolt_count and len(end_bolts) == flange_spec.bolt_count
    bolt_diameter_pass = abs(bolt_diameter_measured - flange_spec.bolt_diameter) <= tolerance
    bolt_pcd_pass = abs(bolt_pcd_measured - flange_spec.pcd) <= tolerance
    bolt_pattern_aligned = bolt_count_pass and bolt_diameter_pass and bolt_pcd_pass and bolt_centers_match
    pipe_bbox = pipe.bounding_box()
    actual_pipe_od = 2 * pipe_outer["radius"]
    actual_pipe_id = 2 * pipe_inner["radius"]
    actual_pipe_length = float(pipe_bbox.size.Z)
    actual_wall_thickness = (actual_pipe_od - actual_pipe_id) / 2
    requested_wall_thickness = (assembly.pipe_od - assembly.pipe_id) / 2
    bore_clearance = 2 * front_bore_axis["radius"] - actual_pipe_od
    gasket_clearance = None
    if assembly.gasket is not None:
        gasket_clearance = min(
            2 * min(cylindrical_faces(shape), key=lambda row: row["radius"])["radius"] - actual_pipe_od
            for name, shape in component_shapes
            if "gasket" in name
        )

    bore_segments: list[dict[str, Any]] = []
    for name, shape in component_shapes:
        cylinders = cylindrical_faces(shape)
        if "flange" in name:
            inner = central_bore(cylinders)
        else:
            inner = min(cylinders, key=lambda row: row["radius"])
        bbox = shape.bounding_box()
        bore_segments.append(
            {
                "component": name,
                "inner_diameter_mm": round(2 * inner["radius"], 6),
                "min_z": float(bbox.min.Z),
                "max_z": float(bbox.max.Z),
                "axis_offset_mm": round(axis_distance(reference_axis, inner), 6),
            }
        )

    interface_gap_max = max((abs(row["gap_mm"]) for row in interface_rows), default=0.0)
    pipe_dimensions_pass = (
        abs(actual_pipe_od - assembly.pipe_od) <= tolerance
        and abs(actual_pipe_id - assembly.pipe_id) <= tolerance
        and abs(actual_pipe_length - assembly.pipe_length) <= tolerance
        and abs(actual_wall_thickness - requested_wall_thickness) <= tolerance
    )
    bore_continuous = (
        actual_pipe_id > tolerance
        and actual_pipe_od > actual_pipe_id + tolerance
        and all(segment["axis_offset_mm"] <= tolerance for segment in bore_segments)
        and all(segment["inner_diameter_mm"] + tolerance >= actual_pipe_od for segment in bore_segments if segment["component"] != "pipe_spool")
        and end_faces_flush
    )
    min_bore = min((segment["inner_diameter_mm"] for segment in bore_segments), default=0.0)
    axis_continuous = all(segment["axis_offset_mm"] <= tolerance for segment in bore_segments)

    geometry_checks = {
        "coaxial": coaxial,
        "end_faces_flush": end_faces_flush,
        "bolt_pattern_aligned": bolt_pattern_aligned,
        "bore_continuous": bore_continuous,
        "axis_continuous": axis_continuous,
        "axis_offset_max_mm": round(max(axis_offsets, default=0.0), 6),
        "bore_clearance_mm": round(bore_clearance, 6),
        "flange_pipe_clearance_mm": round(bore_clearance, 6),
        "min_bore_mm": round(min_bore, 6),
        "gasket_clearance_mm": round(gasket_clearance, 6) if gasket_clearance is not None else None,
        "interface_gap_max_mm": round(interface_gap_max, 6),
        "pipe_dimensions_pass": pipe_dimensions_pass,
        "measured_pipe_od_mm": round(actual_pipe_od, 6),
        "measured_pipe_id_mm": round(actual_pipe_id, 6),
        "measured_wall_thickness_mm": round(actual_wall_thickness, 6),
        "measured_pipe_length_mm": round(actual_pipe_length, 6),
        "requested_wall_thickness_mm": round(requested_wall_thickness, 6),
        "bolt_pattern": {
            "front_centers_mm": front_bolts,
            "end_centers_mm": end_bolts,
            "measured_count": len(front_bolts),
            "measured_pcd_mm": round(bolt_pcd_measured, 6),
            "measured_diameter_mm": round(bolt_diameter_measured, 6),
            "count_pass": bolt_count_pass,
            "diameter_pass": bolt_diameter_pass,
            "pcd_pass": bolt_pcd_pass,
            "centers_match": bolt_centers_match,
        },
        "bore_segments": bore_segments,
        "interfaces": interface_rows,
        "components": component_geometry_rows,
    }
    component_names = [name for name, _ in component_shapes]
    metadata = {
        "assembly_type": "flanged_spool",
        "component_count": len(component_shapes),
        "components": component_names,
        "interface_count": len(interface_rows),
        "coaxial": coaxial,
        "end_faces_flush": end_faces_flush,
        "bolt_pattern_aligned": bolt_pattern_aligned,
        "bore_continuous": bore_continuous,
        "axis_continuous": axis_continuous,
        "geometry_checks": geometry_checks,
        "pipe_od": assembly.pipe_od,
        "pipe_id": assembly.pipe_id,
        "pipe_length": assembly.pipe_length,
        "include_end_flange": assembly.include_end_flange,
        "include_gaskets": assembly.include_gaskets,
        "gasket": assembly.gasket.as_dict() if assembly.gasket else None,
        "flange_spec": flange_spec.as_dict(),
    }
    return composite, metadata


def build_flange(
    spec: FlangeSpec,
    output_dir: str | Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Build the solid and return it with measured metadata."""
    validate_spec(spec)
    shape = _build123d_shape(spec)

    metadata: dict[str, Any] = {
        "spec": spec.as_dict(),
        "expected_volume_mm3": expected_volume(spec),
        "volume_mm3": float(shape.volume),
        "bbox_mm": {
            "x": float(shape.bounding_box().size.X),
            "y": float(shape.bounding_box().size.Y),
            "z": float(shape.bounding_box().size.Z),
        },
        "is_valid": bool(getattr(shape, "is_valid", False)),
        "design_issues": design_issues(spec),
    }

    try:
        metadata["solid_count"] = len(shape.solids())
    except AttributeError:
        metadata["solid_count"] = None

    metadata["cylindrical_face_count"] = sum(
        1
        for face in shape.faces()
        if str(getattr(face, "geom_type", "")).upper().endswith("CYLINDER")
    )

    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        from build123d import export_step, export_stl

        export_step(shape, str(output / "flange.step"))
        export_stl(shape, str(output / "flange.stl"))
        import json

        (output / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return shape, metadata



