from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .status import FAIL, PASS


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    objects: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationReport:
    status: str
    issues: tuple[Issue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "issues": [
                {"code": issue.code, "message": issue.message, "objects": list(issue.objects)}
                for issue in self.issues
            ],
        }


def _overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        float(left["x"]) < float(right["x"]) + float(right["width"])
        and float(left["x"]) + float(left["width"]) > float(right["x"])
        and float(left["y"]) < float(right["y"]) + float(right["height"])
        and float(left["y"]) + float(left["height"]) > float(right["y"])
    )


def validate_manifest(manifest: dict[str, Any], *, ratio_tolerance: float = 0.02) -> ValidationReport:
    canvas = manifest.get("canvas") or {}
    width = float(canvas.get("width") or 0)
    height = float(canvas.get("height") or 0)
    margin = float(canvas.get("safe_margin") or 0)
    issues: list[Issue] = []
    objects = list(manifest.get("objects") or ())

    for obj in objects:
        name = str(obj.get("id") or "unnamed")
        x = float(obj.get("x") or 0)
        y = float(obj.get("y") or 0)
        right = x + float(obj.get("width") or 0)
        bottom = y + float(obj.get("height") or 0)
        if x < margin or y < margin or right > width - margin or bottom > height - margin:
            issues.append(Issue("SAFE_MARGIN", f"{name} crosses the safe margin", (name,)))
        font_size = obj.get("font_size")
        if font_size is not None and float(font_size) < 16:
            issues.append(Issue("MIN_FONT", f"{name} uses {font_size}pt text below the 16pt floor", (name,)))

    for index, left in enumerate(objects):
        for right in objects[index + 1:]:
            if _overlap(left, right):
                left_id = str(left.get("id") or "unnamed")
                right_id = str(right.get("id") or "unnamed")
                issues.append(Issue("OVERLAP", f"{left_id} overlaps {right_id}", (left_id, right_id)))

    for slot in manifest.get("image_slots") or ():
        slot_width = float(slot.get("width") or 0)
        slot_height = float(slot.get("height") or 0)
        generated_width = float(slot.get("generated_width") or 0)
        generated_height = float(slot.get("generated_height") or 0)
        if min(slot_width, slot_height, generated_width, generated_height) <= 0:
            issues.append(Issue("IMAGE_RATIO", f"{slot.get('id', 'image')} has invalid dimensions"))
            continue
        slot_ratio = slot_width / slot_height
        generated_ratio = generated_width / generated_height
        relative_error = abs(slot_ratio - generated_ratio) / slot_ratio
        if relative_error > ratio_tolerance:
            name = str(slot.get("id") or "image")
            issues.append(Issue("IMAGE_RATIO", f"{name} generated ratio differs by {relative_error:.1%}", (name,)))

    return ValidationReport(FAIL if issues else PASS, tuple(issues))
