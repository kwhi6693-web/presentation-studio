from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Request:
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


def normalize_request(raw: dict[str, Any]) -> Request:
    if not isinstance(raw, dict):
        raise ValueError("request: top-level value must be an object")

    def text(field: str, default: str = "") -> str:
        if field not in raw:
            return default
        value = raw[field]
        if not isinstance(value, str):
            raise ValueError(f"request.{field}: must be a string")
        return value.strip().lower()

    def collection(field: str, *, strip_dot: bool = False) -> tuple[str, ...]:
        if field not in raw:
            return ()
        value = raw[field]
        if isinstance(value, str):
            values = (value,)
        elif isinstance(value, (list, tuple)):
            values = value
        else:
            raise ValueError(f"request.{field}: must be a string or list of strings")
        normalized: list[str] = []
        for index, entry in enumerate(values):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"request.{field}[{index}]: must be a non-empty string")
            item = entry.strip().lower()
            if strip_dot:
                item = item.lstrip(".")
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

    kind = text("kind", "presentation") or "presentation"
    inputs = collection("inputs")
    outputs = collection("outputs", strip_dot=True)
    if not outputs:
        outputs = {
            "diagram": ("svg",),
            "infographic": ("png",),
            "cover": ("png",),
            "image": ("png",),
        }.get(kind, ("pptx",))
    return Request(
        kind=kind,
        inputs=inputs,
        outputs=outputs,
        editable=boolean("editable"),
        style=text("style"),
        assets=collection("assets"),
        presenter=boolean("presenter"),
        single_file=boolean("single_file"),
        product=text("product"),
        has_exact_data=boolean("has_exact_data"),
        topic=text("topic"),
        audience=text("audience"),
        purpose=text("purpose"),
        tone=text("tone"),
        channel=text("channel"),
        density=text("density"),
        data_forms=collection("data_forms"),
    )
