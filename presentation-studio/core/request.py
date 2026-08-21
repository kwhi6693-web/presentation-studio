from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


_KIND_ALIASES = {
    "presentation": "presentation", "deck": "presentation", "slide deck": "presentation",
    "slides": "presentation", "ppt": "presentation", "pptx": "presentation",
    "powerpoint": "presentation", "powerpoint deck": "presentation",
    "investor pitch deck": "presentation", "pitch deck": "presentation",
    "data deck": "presentation", "technical deck": "presentation",
    "image slide deck": "presentation", "cover": "cover", "cover image": "cover",
    "article cover": "cover", "illustration": "illustration",
    "article illustration": "illustration", "infographic": "infographic",
    "infographic image": "infographic", "diagram": "diagram",
    "technical diagram": "diagram", "architecture diagram": "diagram", "image": "image",
    "data image": "image", "png": "image",
}
_KIND_CONTEXT = {
    "investor pitch deck": {"audience": "investors", "purpose": "investor pitch fundraising", "topic": "business finance"},
    "pitch deck": {"purpose": "investor pitch"},
    "data deck": {"topic": "data metrics", "density": "high"},
    "technical deck": {"topic": "technical architecture", "audience": "engineers"},
    "technical diagram": {"topic": "technical architecture"},
    "architecture diagram": {"topic": "technical architecture"},
    "image slide deck": {"purpose": "visual storytelling", "assets": "image"},
    "cover image": {"purpose": "cover"},
    "article cover": {"purpose": "article cover", "channel": "article"},
    "data image": {"topic": "data metrics", "density": "high"},
}
_KIND_OUTPUTS = {"ppt": "pptx", "pptx": "pptx", "powerpoint": "pptx", "powerpoint deck": "pptx", "png": "png"}
_OUTPUT_ALIASES = {
    "ppt": "pptx", "pptx": "pptx", "powerpoint": "pptx", "slides": "pptx",
    "slide deck": "pptx", "web": "html", "web presentation": "html", "html": "html",
    "pdf": "pdf", "png": "png", "image": "png", "jpg": "png", "jpeg": "png",
    "svg": "svg", "vector": "svg",
}
_DATA_FORM_ALIASES = {
    "table": "table", "csv": "csv", "xlsx": "xlsx", "excel": "xlsx", "json": "json",
    "markdown table": "markdown-table", "markdown-table": "markdown-table", "text": "text", "image": "image",
}


@dataclass(frozen=True)
class Request:
    raw_text: str
    kind: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    editable: bool
    style: str
    assets: tuple[str, ...]
    presenter: bool
    single_file: bool
    product: str = ""
    has_exact_data: bool = False
    topic: str = ""
    audience: str = ""
    purpose: str = ""
    tone: str = ""
    channel: str = ""
    density: str = ""
    data_forms: tuple[str, ...] = ()
    aspect_ratio: str = ""
    deadline: str = ""
    brief_completeness: str = ""
    style_source: str = "catalog"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Request:
        return normalize_request(raw)


def normalize_request(raw: dict[str, Any]) -> Request:
    if not isinstance(raw, dict):
        raise ValueError("request: top-level value must be an object")

    def phrase(value: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", value).strip().lower().replace("_", " ").split())

    def text(field: str, default: str = "") -> str:
        if field not in raw:
            return default
        value = raw[field]
        if not isinstance(value, str):
            raise ValueError(f"request.{field}: must be a string")
        return phrase(value)

    def collection(field: str, *, strip_dot: bool = False, aliases: dict[str, str] | None = None) -> tuple[str, ...]:
        if field not in raw:
            return ()
        value = raw[field]
        values = (value,) if isinstance(value, str) else value
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"request.{field}: must be a string or list of strings")
        normalized: list[str] = []
        for index, entry in enumerate(values):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"request.{field}[{index}]: must be a non-empty string")
            item = phrase(entry).lstrip(".") if strip_dot else phrase(entry)
            if aliases:
                item = aliases.get(item, item)
            if not item:
                raise ValueError(f"request.{field}[{index}]: must be a non-empty string")
            if item not in normalized:
                normalized.append(item)
        return tuple(normalized)

    def boolean(field: str) -> bool:
        if field not in raw:
            return False
        value = raw[field]
        if not isinstance(value, bool):
            raise ValueError(f"request.{field}: must be a boolean")
        return value

    raw_text = raw.get("raw_text", raw.get("text", raw.get("brief", raw.get("topic", ""))))
    if not isinstance(raw_text, str):
        raise ValueError("request.raw_text: must be a string")
    raw_kind = text("kind", "presentation") or "presentation"
    kind = _KIND_ALIASES.get(raw_kind, raw_kind)
    context = _KIND_CONTEXT.get(raw_kind, {})
    outputs = list(collection("outputs", strip_dot=True, aliases=_OUTPUT_ALIASES))
    inferred_output = _KIND_OUTPUTS.get(raw_kind)
    if inferred_output and not outputs:
        outputs.append(inferred_output)
    if not outputs:
        outputs = list({"diagram": ("svg",), "infographic": ("png",), "cover": ("png",), "image": ("png",)}.get(kind, ("pptx",)))
    assets = list(collection("assets"))
    contextual_asset = context.get("assets")
    if contextual_asset and contextual_asset not in assets:
        assets.append(contextual_asset)
    style_source = text("style_source", "catalog") or "catalog"
    if style_source not in {"catalog", "freeform"}:
        raise ValueError("request.style_source: must be 'catalog' or 'freeform'")
    return Request(
        raw_text=raw_text,
        kind=kind,
        inputs=collection("inputs"),
        outputs=tuple(outputs),
        editable=boolean("editable"),
        style=text("style").replace(" ", "-"),
        assets=tuple(assets),
        presenter=boolean("presenter"),
        single_file=boolean("single_file"),
        product=text("product"),
        has_exact_data=boolean("has_exact_data"),
        topic=text("topic") or context.get("topic", ""),
        audience=text("audience") or context.get("audience", ""),
        purpose=text("purpose") or context.get("purpose", ""),
        tone=text("tone"),
        channel=text("channel") or context.get("channel", ""),
        density=text("density") or context.get("density", ""),
        data_forms=collection("data_forms", aliases=_DATA_FORM_ALIASES),
        aspect_ratio=text("aspect_ratio"),
        deadline=text("deadline"),
        brief_completeness=text("brief_completeness"),
        style_source=style_source,
    )
