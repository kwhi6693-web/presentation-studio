from __future__ import annotations

import json
from pathlib import Path
from typing import Any


KNOWN_ENGINES = frozenset({"ppt-master", "guizang", "frontend-slides", "baoyu"})
ENGINE_OUTPUTS = {
    "ppt-master": frozenset({"pptx"}),
    "guizang": frozenset(),
    "frontend-slides": frozenset({"html", "pdf"}),
    "baoyu": frozenset({"png", "svg"}),
}
ENGINE_CAPABILITIES = {
    "ppt-master": frozenset({"native-pptx", "native-chart", "native-table"}),
    "guizang": frozenset({"design-system"}),
    "frontend-slides": frozenset({"html-slides", "html-pdf"}),
    "baoyu": frozenset({
        "cover",
        "article-illustrator",
        "infographic",
        "diagram",
        "data-image",
        "image-slide-deck",
    }),
}
ENGINE_REFERENCES = {
    "ppt-master": frozenset({"native-pptx"}),
    "guizang": frozenset({"design-systems"}),
    "frontend-slides": frozenset({"html-presenter"}),
    "baoyu": frozenset({"images", "diagrams-infographics"}),
}
OUTPUT_CAPABILITY_REQUIREMENTS = {
    "pptx": (("ppt-master", "native-pptx"),),
    "html": (("frontend-slides", "html-slides"),),
    "pdf": (("frontend-slides", "html-pdf"),),
    "svg": (("baoyu", "diagram"),),
    "png": (
        ("baoyu", "cover"),
        ("baoyu", "article-illustrator"),
        ("baoyu", "infographic"),
        ("baoyu", "data-image"),
    ),
}
KNOWN_PREREQUISITES = frozenset({
    "python",
    "node",
    "office_renderer",
    "chromium",
    "image_provider",
})
PRODUCT_REQUIRED_FIELDS = (
    "id",
    "engine_chain",
    "category",
    "kind",
    "intended_uses",
    "audience_tags",
    "purpose_tags",
    "density_tags",
    "channel_tags",
    "outputs",
    "editable",
    "editable_outputs",
    "native_editability",
    "supported_data_forms",
    "style_tags",
    "aspect_ratios",
    "required_prerequisites",
    "optional_prerequisites",
    "capabilities",
    "references",
    "quality_gates",
    "fallback",
)
STYLE_REQUIRED_FIELDS = (
    "id",
    "name",
    "description",
    "topic_tags",
    "audience_tags",
    "purpose_tags",
    "tone_tags",
    "density_tags",
    "channel_tags",
    "preferred_design_authority",
)
_STYLE_TAG_FIELDS = (
    "topic_tags",
    "audience_tags",
    "purpose_tags",
    "tone_tags",
    "density_tags",
    "channel_tags",
)
_PRODUCT_LIST_FIELDS = (
    "intended_uses",
    "audience_tags",
    "purpose_tags",
    "density_tags",
    "channel_tags",
    "outputs",
    "editable_outputs",
    "supported_data_forms",
    "style_tags",
    "aspect_ratios",
    "required_prerequisites",
    "optional_prerequisites",
    "references",
    "quality_gates",
)


class CatalogError(ValueError):
    pass


def _load_json(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path.name}: unable to load JSON: {exc}") from exc
    if not isinstance(value, list):
        raise CatalogError(f"{path.name}: top-level value must be a list")
    if not all(isinstance(item, dict) for item in value):
        raise CatalogError(f"{path.name}: every item must be an object")
    return value


def _validate_ids(items: list[dict[str, Any]], required: tuple[str, ...], label: str) -> None:
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise CatalogError(f"{label}: must be a list of objects")
    ids: set[str] = set()
    for index, item in enumerate(items):
        missing = next((field for field in required if field not in item), None)
        if missing is not None:
            raise CatalogError(f"{label}[{index}]: missing field {missing}")
        item_id = item["id"]
        if not isinstance(item_id, str) or not item_id.strip():
            raise CatalogError(f"{label}[{index}].id: must be a non-empty string")
        if item_id in ids:
            raise CatalogError(f"{label}[{index}].id: duplicate ID {item_id}")
        ids.add(item_id)


def _require_string(item: dict[str, Any], field: str, path: str) -> str:
    value = item[field]
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{path}.{field}: must be a non-empty string")
    return value


def _require_string_list(
    item: dict[str, Any], field: str, path: str, *, allow_empty: bool = False
) -> list[str]:
    value = item[field]
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "" if allow_empty else " non-empty"
        raise CatalogError(f"{path}.{field}: must be a{qualifier} list of strings")
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise CatalogError(f"{path}.{field}[{index}]: must be a non-empty string")
    if len(set(value)) != len(value):
        raise CatalogError(f"{path}.{field}: duplicate values are not allowed")
    return value


def _require_bool(item: dict[str, Any], field: str, path: str) -> bool:
    value = item[field]
    if not isinstance(value, bool):
        raise CatalogError(f"{path}.{field}: must be a boolean")
    return value


def _validate_capabilities(item: dict[str, Any], engines: list[str], path: str) -> None:
    value = item["capabilities"]
    if not isinstance(value, dict) or not value:
        raise CatalogError(f"{path}.capabilities: must be a non-empty object")
    if set(value) != set(engines):
        raise CatalogError(f"{path}.capabilities: must declare every engine in engine_chain")
    for engine, capabilities in value.items():
        if not isinstance(engine, str) or engine not in engines:
            raise CatalogError(f"{path}.capabilities: engine key must belong to engine_chain")
        if not isinstance(capabilities, list) or not capabilities:
            raise CatalogError(f"{path}.capabilities.{engine}: must be a non-empty list of strings")
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, str) or capability not in ENGINE_CAPABILITIES[engine]:
                raise CatalogError(
                    f"{path}.capabilities.{engine}[{index}]: unsupported capability"
                )


def validate_products(
    items: list[dict[str, Any]], *, style_ids: frozenset[str] | set[str] | None = None
) -> tuple[dict[str, Any], ...]:
    _validate_ids(items, PRODUCT_REQUIRED_FIELDS, "products")
    by_id = {item["id"]: item for item in items}
    for item in items:
        item_id = item["id"]
        path = f"products.{item_id}"
        _require_string(item, "category", path)
        _require_string(item, "kind", path)
        for field in _PRODUCT_LIST_FIELDS:
            _require_string_list(
                item,
                field,
                path,
                allow_empty=field in {"editable_outputs", "required_prerequisites", "optional_prerequisites"},
            )
        engines = _require_string_list(item, "engine_chain", path)
        for index, engine in enumerate(engines):
            if engine not in KNOWN_ENGINES:
                raise CatalogError(f"{path}.engine_chain[{index}]: unknown engine {engine}")
        outputs = item["outputs"]
        supported_outputs = set().union(*(ENGINE_OUTPUTS[engine] for engine in engines))
        unsupported_outputs = [output for output in outputs if output not in supported_outputs]
        if unsupported_outputs:
            raise CatalogError(
                f"{path}.outputs: no engine in engine_chain supports {unsupported_outputs[0]}"
            )
        editable = _require_bool(item, "editable", path)
        editable_outputs = item["editable_outputs"]
        if not set(editable_outputs).issubset(outputs):
            raise CatalogError(f"{path}.editable_outputs: must be a subset of outputs")
        if editable != bool(editable_outputs):
            raise CatalogError(f"{path}.editable: must match whether editable_outputs is non-empty")
        native_editability = _require_string(item, "native_editability", path)
        expected_editability = (
            "none" if not editable_outputs
            else "full" if set(editable_outputs) == set(outputs)
            else "partial"
        )
        if native_editability != expected_editability:
            raise CatalogError(
                f"{path}.native_editability: expected {expected_editability} for editable_outputs"
            )
        for field in ("required_prerequisites", "optional_prerequisites"):
            unknown = [name for name in item[field] if name not in KNOWN_PREREQUISITES]
            if unknown:
                raise CatalogError(f"{path}.{field}: unknown prerequisite {unknown[0]}")
        if set(item["required_prerequisites"]) & set(item["optional_prerequisites"]):
            raise CatalogError(f"{path}.optional_prerequisites: prerequisite cannot also be required")
        _validate_capabilities(item, engines, path)
        for output in outputs:
            requirements = OUTPUT_CAPABILITY_REQUIREMENTS.get(output, ())
            if not any(
                engine in engines and capability in item["capabilities"].get(engine, ())
                for engine, capability in requirements
            ):
                raise CatalogError(
                    f"{path}.outputs: {output} has no matching output-capable engine/capability"
                )
        if style_ids is not None:
            unknown_styles = [tag for tag in item["style_tags"] if tag not in style_ids]
            if unknown_styles:
                raise CatalogError(
                    f"{path}.style_tags: unresolved style {unknown_styles[0]}"
                )
        supported_references = set().union(*(ENGINE_REFERENCES[engine] for engine in engines))
        unsupported_references = [
            reference for reference in item["references"] if reference not in supported_references
        ]
        if unsupported_references:
            raise CatalogError(
                f"{path}.references: no engine in engine_chain supports {unsupported_references[0]}"
            )
        for engine in engines:
            if not set(item["references"]).intersection(ENGINE_REFERENCES[engine]):
                raise CatalogError(
                    f"{path}.references: missing authority reference for engine {engine}"
                )
        fallback = item["fallback"]
        if fallback is not None and (not isinstance(fallback, str) or not fallback):
            raise CatalogError(f"{path}.fallback: must be null or a non-empty product ID")

    for item in items:
        fallback = item["fallback"]
        if fallback is None:
            continue
        path = f"products.{item['id']}"
        target = by_id.get(fallback)
        if target is None:
            raise CatalogError(f"{path}.fallback: unresolved product {fallback}")
        if target["kind"] != item["kind"] or not set(item["outputs"]).issubset(target["outputs"]):
            raise CatalogError(f"{path}.fallback: target must preserve kind and outputs")
    return tuple(items)


def validate_styles(items: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    _validate_ids(items, STYLE_REQUIRED_FIELDS, "styles")
    for item in items:
        path = f"styles.{item['id']}"
        _require_string(item, "name", path)
        _require_string(item, "description", path)
        for field in _STYLE_TAG_FIELDS:
            _require_string_list(item, field, path)
        authority = _require_string(item, "preferred_design_authority", path)
        if authority not in KNOWN_ENGINES:
            raise CatalogError(f"{path}.preferred_design_authority: unknown engine {authority}")
    return tuple(items)


def load_products(root: Path) -> tuple[dict[str, Any], ...]:
    styles = validate_styles(_load_json(root / "catalog" / "styles.json"))
    style_ids = frozenset(style["id"] for style in styles)
    return validate_products(
        _load_json(root / "catalog" / "products.json"), style_ids=style_ids
    )


def load_styles(root: Path) -> tuple[dict[str, Any], ...]:
    return validate_styles(_load_json(root / "catalog" / "styles.json"))
