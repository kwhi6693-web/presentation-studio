from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .status import FAIL, PASS


# Explicit role floors replace the former universal 16pt rule.  Captions and
# footnotes have lower, stable floors while ordinary presentation text remains 16pt.
FONT_FLOORS = {"text": 16, "caption": 12, "footnote": 10}
_TEXT_ROLES = frozenset({"text", "body", "body_text", "title", "heading"})
_ROLE_FLOORS = {role: FONT_FLOORS["text"] for role in _TEXT_ROLES} | {
    "caption": FONT_FLOORS["caption"],
    "footnote": FONT_FLOORS["footnote"],
}
_RECOGNIZED_ROLES = frozenset(_ROLE_FLOORS) | frozenset(
    {"image", "shape", "chart", "table", "media"}
)


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


def validate_manifest(manifest: dict[str, Any], *, ratio_tolerance: float = 0.02) -> ValidationReport:
    """Validate a layout manifest in schema-first, exception-free order."""
    if type(manifest) is not dict:
        return _report([Issue("SCHEMA_TOP_LEVEL", "manifest must be an object")])
    if not _finite_number(ratio_tolerance) or ratio_tolerance < 0:
        return _report([Issue("SCHEMA_RATIO_TOLERANCE", "ratio_tolerance must be finite and non-negative")])
    issues: list[Issue] = []
    canvas = manifest.get("canvas")
    object_records = _validate_objects(manifest.get("objects"), issues)
    canvas_valid = _validate_canvas(canvas, issues)
    _validate_overlap_references(object_records, issues)
    image_records = _validate_image_slots(manifest.get("image_slots"), issues)
    if canvas_valid:
        assert type(canvas) is dict
        _validate_geometry(canvas, object_records, issues)
    _validate_image_ratios(image_records, ratio_tolerance, issues)
    return _report(issues)


def _report(issues: list[Issue]) -> ValidationReport:
    return ValidationReport(FAIL if issues else PASS, tuple(issues))


def _validate_canvas(canvas: Any, issues: list[Issue]) -> bool:
    if type(canvas) is not dict:
        issues.append(Issue("SCHEMA_CANVAS", "canvas must be an object"))
        return False
    values: dict[str, float] = {}
    valid = True
    for key in ("width", "height", "safe_margin"):
        value = canvas.get(key)
        converted = _safe_number(value)
        if converted is None:
            issues.append(Issue("SCHEMA_CANVAS", f"canvas.{key} must be a finite number"))
            valid = False
        else:
            values[key] = converted
    if not valid:
        return False
    if values["width"] <= 0 or values["height"] <= 0:
        issues.append(Issue("SCHEMA_CANVAS", "canvas width and height must be positive"))
        valid = False
    if values["safe_margin"] < 0:
        issues.append(Issue("SCHEMA_CANVAS", "canvas.safe_margin must be non-negative"))
        valid = False
    doubled_margin = _safe_multiply(values["safe_margin"], 2.0) if valid else None
    if valid and doubled_margin is None:
        issues.append(Issue("SCHEMA_CANVAS", "canvas.safe_margin geometry is not representable"))
        valid = False
    if valid and (doubled_margin >= values["width"] or doubled_margin >= values["height"]):
        issues.append(Issue("SCHEMA_CANVAS", "canvas.safe_margin leaves no drawable area"))
        valid = False
    return valid


def _validate_objects(objects: Any, issues: list[Issue]) -> list[dict[str, Any]]:
    if type(objects) is not list:
        issues.append(Issue("SCHEMA_OBJECTS", "objects must be a list"))
        return []
    records: list[dict[str, Any]] = []
    ids: dict[str, int] = {}
    for index, obj in enumerate(objects):
        name = _object_name(obj, index)
        valid = type(obj) is dict
        if not valid:
            issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}] must be an object", (name,)))
            continue
        for key in ("id", "page_id"):
            if type(obj.get(key)) is not str or not obj[key].strip():
                issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].{key} must be a non-empty string", (name,)))
                valid = False
        role = obj.get("role")
        if type(role) is not str or role not in _RECOGNIZED_ROLES:
            issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].role is not recognized", (name,)))
            valid = False
        group_id = obj.get("group_id")
        if group_id is not None and (type(group_id) is not str or not group_id.strip()):
            issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].group_id must be a non-empty string when present", (name,)))
            valid = False
        for key in ("x", "y", "width", "height"):
            value = obj.get(key)
            if not _finite_number(value):
                issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].{key} must be a finite number", (name,)))
                valid = False
            elif key in {"width", "height"} and value <= 0:
                issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].{key} must be positive", (name,)))
                valid = False
        if type(obj.get("z_index")) is not int:
            issues.append(Issue("SCHEMA_OBJECT", f"objects[{index}].z_index must be an integer", (name,)))
            valid = False
        allowed = obj.get("allowed_overlap")
        if type(allowed) is not list or any(type(item) is not str or not item.strip() for item in allowed):
            issues.append(Issue("SCHEMA_ALLOWED_OVERLAP", f"objects[{index}].allowed_overlap must be a list of non-empty IDs", (name,)))
            valid = False
        elif len(set(allowed)) != len(allowed):
            issues.append(Issue("SCHEMA_ALLOWED_OVERLAP", f"objects[{index}].allowed_overlap must not contain duplicates", (name,)))
            valid = False
        if role in _ROLE_FLOORS:
            font_size = obj.get("font_size")
            if not _finite_number(font_size) or font_size <= 0:
                issues.append(Issue("SCHEMA_FONT", f"objects[{index}].font_size must be a positive finite number", (name,)))
                valid = False
        elif "font_size" in obj and (not _finite_number(obj["font_size"]) or obj["font_size"] <= 0):
            issues.append(Issue("SCHEMA_FONT", f"objects[{index}].font_size must be a positive finite number", (name,)))
            valid = False
        if type(obj.get("id")) is str and obj["id"].strip():
            ids[obj["id"]] = ids.get(obj["id"], 0) + 1
        records.append({"index": index, "object": obj, "name": name, "valid": valid})
    duplicates = {name for name, count in ids.items() if count > 1}
    for record in records:
        if record["name"] in duplicates:
            issues.append(Issue("SCHEMA_OBJECT", f"object id {record['name']!r} is not unique", (record["name"],)))
            record["valid"] = False
    return records


def _validate_overlap_references(records: list[dict[str, Any]], issues: list[Issue]) -> None:
    by_id = {record["name"]: record for record in records if record["valid"]}
    for record in records:
        if not record["valid"]:
            continue
        obj = record["object"]
        for target in obj["allowed_overlap"]:
            other = by_id.get(target)
            if target == record["name"]:
                issues.append(Issue("SCHEMA_ALLOWED_OVERLAP", f"{record['name']} cannot authorize itself", (record["name"],)))
                record["valid"] = False
            elif other is None:
                issues.append(Issue("SCHEMA_ALLOWED_OVERLAP", f"{record['name']} references unknown object {target}", (record["name"], target)))
                record["valid"] = False
            elif other["object"]["page_id"] != obj["page_id"]:
                issues.append(Issue("SCHEMA_ALLOWED_OVERLAP", f"{record['name']} references cross-page object {target}", (record["name"], target)))
                record["valid"] = False


def _validate_image_slots(image_slots: Any, issues: list[Issue]) -> list[dict[str, Any]]:
    if type(image_slots) is not list:
        issues.append(Issue("SCHEMA_IMAGE_SLOTS", "image_slots must be a list"))
        return []
    records: list[dict[str, Any]] = []
    for index, slot in enumerate(image_slots):
        name = _object_name(slot, index, prefix="image")
        valid = type(slot) is dict
        if not valid:
            issues.append(Issue("SCHEMA_IMAGE_SLOT", f"image_slots[{index}] must be an object", (name,)))
            continue
        if type(slot.get("id")) is not str or not slot["id"].strip():
            issues.append(Issue("SCHEMA_IMAGE_SLOT", f"image_slots[{index}].id must be a non-empty string", (name,)))
            valid = False
        for key in ("width", "height", "generated_width", "generated_height"):
            value = slot.get(key)
            if not _finite_number(value) or value <= 0:
                issues.append(Issue("SCHEMA_IMAGE_SLOT", f"image_slots[{index}].{key} must be a positive finite number", (name,)))
                valid = False
        records.append({"slot": slot, "name": name, "valid": valid})
    return records


def _validate_geometry(canvas: dict[str, Any], records: list[dict[str, Any]], issues: list[Issue]) -> None:
    width, height, margin = (_safe_number(canvas[key]) for key in ("width", "height", "safe_margin"))
    assert width is not None and height is not None and margin is not None
    ordered = sorted(
        (record for record in records if record["valid"]),
        key=lambda record: (record["object"]["page_id"], record["object"]["z_index"], record["name"]),
    )
    for record in ordered:
        obj = record["object"]
        x, y, object_width, object_height = (_safe_number(obj[key]) for key in ("x", "y", "width", "height"))
        assert x is not None and y is not None and object_width is not None and object_height is not None
        right = _safe_add(x, object_width)
        bottom = _safe_add(y, object_height)
        right_limit = _safe_add(width, -margin)
        bottom_limit = _safe_add(height, -margin)
        if None in (right, bottom, right_limit, bottom_limit):
            issues.append(Issue("SCHEMA_OBJECT", f"{record['name']} geometry is not representable", (record["name"],)))
            continue
        if x < margin or y < margin or right > right_limit or bottom > bottom_limit:
            issues.append(Issue("SAFE_MARGIN", f"{record['name']} crosses the safe margin", (record["name"],)))
        floor = _ROLE_FLOORS.get(obj["role"])
        if floor is not None and float(obj["font_size"]) < floor:
            issues.append(Issue("MIN_FONT", f"{record['name']} uses {obj['font_size']}pt text below the {floor}pt floor", (record["name"],)))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            if left["object"]["page_id"] != right["object"]["page_id"]:
                continue
            if _overlap(left["object"], right["object"]) and not _overlap_authorized(left, right):
                issues.append(Issue("OVERLAP", f"{left['name']} overlaps {right['name']}", (left["name"], right["name"])))


def _validate_image_ratios(records: list[dict[str, Any]], ratio_tolerance: float, issues: list[Issue]) -> None:
    for record in records:
        if not record["valid"]:
            continue
        slot = record["slot"]
        slot_ratio = _safe_ratio(slot["width"], slot["height"])
        generated_ratio = _safe_ratio(slot["generated_width"], slot["generated_height"])
        if slot_ratio is None or generated_ratio is None:
            issues.append(Issue("SCHEMA_IMAGE_SLOT", f"{record['name']} ratio is not representable", (record["name"],)))
            continue
        relative_error = abs(slot_ratio - generated_ratio) / slot_ratio
        if relative_error > ratio_tolerance:
            issues.append(Issue("IMAGE_RATIO", f"{record['name']} generated ratio differs by {relative_error:.1%}", (record["name"],)))


def _overlap_authorized(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return right["name"] in left["object"]["allowed_overlap"] or left["name"] in right["object"]["allowed_overlap"]


def _overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        float(left["x"]) < float(right["x"]) + float(right["width"])
        and float(left["x"]) + float(left["width"]) > float(right["x"])
        and float(left["y"]) < float(right["y"]) + float(right["height"])
        and float(left["y"]) + float(left["height"]) > float(right["y"])
    )


def _finite_number(value: Any) -> bool:
    return _safe_number(value) is not None


def _safe_number(value: Any) -> float | None:
    """Convert only exact JSON numbers and reject non-finite or unrepresentable values."""
    if type(value) not in (int, float):
        return None
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _safe_add(left: float, right: float) -> float | None:
    value = left + right
    return value if math.isfinite(value) else None


def _safe_multiply(left: float, right: float) -> float | None:
    value = left * right
    return value if math.isfinite(value) else None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    left = _safe_number(numerator)
    right = _safe_number(denominator)
    if left is None or right is None or right <= 0:
        return None
    try:
        value = left / right
    except (OverflowError, TypeError, ValueError, ZeroDivisionError):
        return None
    return value if math.isfinite(value) else None


def _object_name(value: Any, index: int, *, prefix: str = "object") -> str:
    if type(value) is dict and type(value.get("id")) is str and value["id"].strip():
        return value["id"]
    return f"{prefix}[{index}]"
