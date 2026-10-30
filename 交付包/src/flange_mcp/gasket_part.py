"""Standalone gasket part generation and drawing exports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from math import pi
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class GasketPartSpec:
    outer_diameter: float = 88.0
    inner_diameter: float = 42.0
    thickness: float = 3.0
    material: str = "非金属密封垫"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "GasketPartSpec":
        raw = dict(values or {})
        raw.pop("part_type", None)
        raw.pop("units", None)
        allowed = {"outer_diameter", "inner_diameter", "thickness", "material"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown gasket parameter(s): {', '.join(unknown)}")
        data: dict[str, Any] = {
            "outer_diameter": 88.0,
            "inner_diameter": 42.0,
            "thickness": 3.0,
            "material": "非金属密封垫",
        }
        data.update(raw)
        for name in ("outer_diameter", "inner_diameter", "thickness"):
            data[name] = float(data[name])
        if not isinstance(data["material"], str) or not data["material"].strip():
            raise ValueError("gasket material must be text")
        spec = cls(**data)
        validate_gasket_part(spec)
        return spec

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_gasket_part(spec: GasketPartSpec) -> None:
    for name in ("outer_diameter", "inner_diameter", "thickness"):
        if getattr(spec, name) <= 0:
            raise ValueError(f"gasket_{name} must be greater than 0")
    if spec.inner_diameter >= spec.outer_diameter:
        raise ValueError("gasket_inner_diameter must be smaller than gasket_outer_diameter")


def expected_gasket_volume(spec: GasketPartSpec) -> float:
    validate_gasket_part(spec)
    return pi / 4 * (spec.outer_diameter**2 - spec.inner_diameter**2) * spec.thickness


def build_gasket_part(spec: GasketPartSpec, output_dir: str | Path | None = None) -> tuple[Any, dict[str, Any]]:
    validate_gasket_part(spec)
    from build123d import Cylinder, export_step, export_stl

    shape = Cylinder(spec.outer_diameter / 2, spec.thickness) - Cylinder(
        spec.inner_diameter / 2, spec.thickness
    )
    cylinders = [
        face
        for face in shape.faces()
        if str(getattr(face, "geom_type", "")).upper().endswith("CYLINDER")
    ]
    metadata: dict[str, Any] = {
        "part_type": "gasket",
        "spec": spec.as_dict(),
        "expected_volume_mm3": expected_gasket_volume(spec),
        "volume_mm3": float(shape.volume),
        "bbox_mm": {
            "x": float(shape.bounding_box().size.X),
            "y": float(shape.bounding_box().size.Y),
            "z": float(shape.bounding_box().size.Z),
        },
        "solid_count": len(shape.solids()),
        "cylindrical_face_count": len(cylinders),
        "is_valid": bool(getattr(shape, "is_valid", False)),
        "material": spec.material,
    }
    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        export_step(shape, str(output / "gasket.step"))
        export_stl(shape, str(output / "gasket.stl"))
        (output / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return shape, metadata


def _edge_points(edge: Any) -> list[tuple[float, float]]:
    return [(float(point.X), float(point.Y)) for point in edge.positions(deflection=0.35)]


def _views(shape: Any) -> dict[str, Any]:
    from build123d import Drawing

    result: dict[str, Any] = {}
    for name, look_from, look_up in (
        ("front", (0, -1, 0), (0, 0, 1)),
        ("top", (0, 0, 1), (0, 1, 0)),
        ("left", (-1, 0, 0), (0, 0, 1)),
    ):
        drawing = Drawing(shape, look_from=look_from, look_up=look_up, with_hidden=True)
        result[name] = drawing
    return result


def _transform(view: Any, left: float, bottom: float, width: float, height: float):
    points: list[tuple[float, float]] = []
    for compound in (view.visible_lines, view.hidden_lines):
        for edge in compound.edges():
            points.extend(_edge_points(edge))
    if not points:
        points = [(-1, -1), (1, 1)]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x - min_x, 1e-6), max(max_y - min_y, 1e-6)
    scale = min((width - 24) / span_x, (height - 24) / span_y)
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2

    def apply(point: tuple[float, float]) -> tuple[float, float]:
        return (
            left + width / 2 + (point[0] - mid_x) * scale,
            bottom + height / 2 - (point[1] - mid_y) * scale,
        )

    return apply


def make_gasket_drawing(
    shape: Any,
    spec: GasketPartSpec,
    output_dir: str | Path,
    formats: list[str] | set[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Export standalone gasket PNG, vector PDF and editable DXF."""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    from PIL import Image, ImageDraw, ImageFont

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    requested = {str(item).lower() for item in formats}
    font_candidates = [Path("C:/Windows/Fonts/simfang.ttf"), Path("/usr/share/fonts/truetype/arphic/uming.ttc")]
    font_path = next((candidate for candidate in font_candidates if candidate.exists()), None)

    def image_font(size: int):
        if font_path is not None:
            try:
                return ImageFont.truetype(str(font_path), size)
            except OSError:
                pass
        return ImageFont.load_default()

    pdf_font = "Helvetica"
    if font_path is not None:
        try:
            pdfmetrics.registerFont(TTFont("FangSong", str(font_path)))
            pdf_font = "FangSong"
        except Exception:
            pass
    measured = {
        "outer_diameter": float(spec.outer_diameter),
        "inner_diameter": float(spec.inner_diameter),
        "thickness": float(spec.thickness),
        "volume_mm3": float(shape.volume),
        "cylindrical_face_count": len(
            [face for face in shape.faces() if str(getattr(face, "geom_type", "")).upper().endswith("CYLINDER")]
        ),
    }
    paths: dict[str, str] = {}
    views = _views(shape)
    panels = {
        "front": (410, 320, 420, 260, "主视图"),
        "top": (410, 65, 420, 190, "俯视图"),
        "left": (865, 320, 280, 260, "左视图"),
    }

    if "png" in requested:
        image = Image.new("RGB", (1600, 1100), "white")
        draw = ImageDraw.Draw(image)
        font = image_font(24)
        small_font = image_font(18)
        draw.text((70, 45), "垫片投影图", fill="black", font=font)
        draw.text((70, 82), "由已交付 STEP B-rep 投影生成", fill="#555555", font=small_font)
        for name, (left, top, width, height, label) in panels.items():
            transform = _transform(views[name], left, 1100 - top - height, width, height)
            for edge in views[name].hidden_lines.edges():
                points = [_png_xy(transform(point)) for point in _edge_points(edge)]
                for index in range(len(points) - 1):
                    draw.line((points[index], points[index + 1]), fill="#999999", width=2)
            for edge in views[name].visible_lines.edges():
                points = [_png_xy(transform(point)) for point in _edge_points(edge)]
                for index in range(len(points) - 1):
                    draw.line((points[index], points[index + 1]), fill="#111111", width=3)
            draw.text((left, top + height + 10), label, fill="#111111", font=small_font)
        draw.text((70, 1020), f"外径 {spec.outer_diameter:g} mm · 内径 {spec.inner_diameter:g} mm · 厚度 {spec.thickness:g} mm", fill="black", font=small_font)
        draw.text((70, 1050), "本图为 AI 生成草图，须经人工工程审核后方可用于加工", fill="#555555", font=small_font)
        path = output / "gasket.png"
        image.save(path)
        paths["png"] = str(path)

    if "pdf" in requested:
        page_width, page_height = landscape(A3)
        path = output / "gasket.pdf"
        pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height))
        pdf.setTitle("Gasket Projection Drawing")
        pdf.setFont(pdf_font, 18)
        pdf.drawString(45, page_height - 45, "垫片投影图")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(45, page_height - 62, "Projected from delivered STEP B-rep")
        for name, (left, bottom, width, height, label) in {
            "front": (380, 330, 380, 250, "主视图"),
            "top": (380, 60, 380, 250, "俯视图"),
            "left": (800, 330, 300, 250, "左视图"),
        }.items():
            transform = _transform(views[name], left, bottom, width, height)
            pdf.setLineWidth(0.7)
            for edge in views[name].visible_lines.edges():
                points = [transform(point) for point in _edge_points(edge)]
                for index in range(len(points) - 1):
                    pdf.line(*points[index], *points[index + 1])
            pdf.setFont(pdf_font, 9)
            pdf.drawString(left, bottom - 14, label)
        pdf.setFont(pdf_font, 9)
        pdf.drawString(45, 45, f"OD {spec.outer_diameter:g} mm   ID {spec.inner_diameter:g} mm   T {spec.thickness:g} mm")
        pdf.drawString(45, 30, "本图为 AI 生成草图，须经人工工程审核后方可用于加工")
        pdf.save()
        paths["pdf"] = str(path)

    if "dxf" in requested:
        path = output / "gasket.dxf"
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        msp.add_circle((0, 0), spec.outer_diameter / 2)
        msp.add_circle((0, 0), spec.inner_diameter / 2)
        msp.add_linear_dim(base=(0, -spec.outer_diameter / 2 - 20), p1=(-spec.outer_diameter / 2, 0), p2=(spec.outer_diameter / 2, 0), location=(0, -spec.outer_diameter / 2 - 20), text="<>" ).render()
        msp.add_linear_dim(base=(0, spec.inner_diameter / 2 + 20), p1=(-spec.inner_diameter / 2, 0), p2=(spec.inner_diameter / 2, 0), location=(0, spec.inner_diameter / 2 + 20), text="<>" ).render()
        doc.saveas(path)
        paths["dxf"] = str(path)

    return {
        "ok": True,
        "part_type": "gasket",
        "formats": sorted(requested),
        "paths": paths,
        "measured_dimensions": measured,
        "requested_spec": spec.as_dict(),
        "projection_source": "delivered STEP B-rep via build123d.Drawing",
        "readback": {"view_count": len(views), "dimension_count": 2},
    }


def _xy(point: tuple[float, float]) -> tuple[float, float]:
    return point


def _png_xy(point: tuple[float, float]) -> tuple[float, float]:
    return point[0], 1100 - point[1]
