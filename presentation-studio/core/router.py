from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .catalog import load_products, load_styles
from .request import normalize_request


_EXACT_DATA_QUALITY_GATE = "data-fidelity"
_KIND_CAPABILITIES = {
    "image": "image-gen",
    "cover": "cover",
    "diagram": "diagram",
    "infographic": "infographic",
    "illustration": "article-illustrator",
}


def _supports_catalog_mode(product: dict[str, Any], field: str, use_case: str) -> bool:
    return bool(product.get(field, use_case in product["intended_uses"]))


@dataclass(frozen=True)
class RoutePlan:
    outputs: tuple[str, ...]
    engines: tuple[str, ...]
    capabilities: dict[str, tuple[str, ...]]
    references: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "outputs": list(self.outputs),
            "engines": list(self.engines),
            "capabilities": {key: list(value) for key, value in self.capabilities.items()},
            "references": list(self.references),
        }


def route_request(raw: dict[str, Any]) -> RoutePlan:
    request = normalize_request(raw)
    root = Path(__file__).resolve().parents[1]
    products = load_products(root)
    styles = load_styles(root)
    selected_style = next(
        (style for style in styles if style["id"] == request.style),
        None,
    )
    if request.style and selected_style is None and request.style_source != "freeform":
        raise ValueError(
            f"Unknown catalog style: {request.style}. Set style_source to 'freeform' to use it."
        )
    selected_product = next(
        (
            product
            for product in products
            if product["id"] == request.product
        ),
        None,
    ) if request.product else None
    if request.product and selected_product is None:
        raise ValueError(f"Unknown product: {request.product}")
    if selected_product is not None:
        has_explicit_kind = bool(raw.get("kind"))
        has_explicit_outputs = bool(raw.get("outputs"))
        conflicts: list[str] = []
        if has_explicit_kind and request.kind != selected_product["kind"]:
            conflicts.append(f"kind: {request.kind}")
        if has_explicit_outputs:
            unsupported_outputs = tuple(
                output for output in request.outputs if output not in selected_product["outputs"]
            )
            if unsupported_outputs:
                conflicts.append(f"outputs: {', '.join(unsupported_outputs)}")
        if request.aspect_ratio and request.aspect_ratio not in selected_product["aspect_ratios"]:
            conflicts.append(f"aspect_ratio: {request.aspect_ratio}")
        if request.presenter and not _supports_catalog_mode(
            selected_product, "presenter", "presenter-mode"
        ):
            conflicts.append("presenter: selected product does not support presenter mode")
        if request.single_file and not _supports_catalog_mode(
            selected_product, "single_file", "single-file-presentation"
        ):
            conflicts.append("single_file: selected product does not support single-file delivery")
        if request.editable:
            requested_outputs = (
                request.outputs if has_explicit_outputs else tuple(selected_product["outputs"])
            )
            editable_requested_outputs = set(requested_outputs).intersection(
                selected_product["editable_outputs"]
            )
            if not selected_product["editable"] or not editable_requested_outputs:
                conflicts.append("editable: no requested output is natively editable")
        unsupported_data_forms = tuple(
            form
            for form in request.data_forms
            if form not in selected_product["supported_data_forms"]
        )
        if unsupported_data_forms:
            conflicts.append(f"data_forms: {', '.join(unsupported_data_forms)}")
        if request.has_exact_data and _EXACT_DATA_QUALITY_GATE not in selected_product[
            "quality_gates"
        ]:
            conflicts.append("has_exact_data: true")
        if conflicts:
            raise ValueError(
                f"Selected product {selected_product['id']} conflicts: {', '.join(conflicts)}"
            )
        request = replace(
            request,
            kind=request.kind if has_explicit_kind else selected_product["kind"],
            outputs=request.outputs if has_explicit_outputs else tuple(selected_product["outputs"]),
        )
        capabilities = {
            engine: tuple(selected_product["capabilities"][engine])
            for engine in selected_product["engine_chain"]
        }
        shared_references = ["product-retrieval"]
        if request.has_exact_data:
            shared_references.append("data-binding")
        shared_references.extend(("qa", "error-system"))
        references = tuple(
            dict.fromkeys([*selected_product["references"], *shared_references])
        )
        return RoutePlan(
            request.outputs,
            tuple(selected_product["engine_chain"]),
            capabilities,
            references,
        )
    needs_pptx = request.editable or "pptx" in request.outputs
    needs_html = "html" in request.outputs or "pdf" in request.outputs
    preferred_authority = (
        selected_style["preferred_design_authority"] if selected_style else ""
    )
    visual_style = (
        request.style in {"swiss", "editorial", "magazine", "e-ink", "guizang"}
        or preferred_authority == "guizang"
    )

    engines: list[str] = []
    capabilities: dict[str, tuple[str, ...]] = {}

    if visual_style or request.presenter:
        engines.append("guizang")
        guizang = []
        if visual_style:
            guizang.append(
                "design-system" if selected_style is not None else request.style or "editorial"
            )
        if request.presenter:
            guizang.append("presenter-mode")
        capabilities["guizang"] = tuple(guizang)

    baoyu_capabilities: list[str] = []
    if request.kind in _KIND_CAPABILITIES:
        baoyu_capabilities.append(_KIND_CAPABILITIES[request.kind])
    asset_map = {
        "image": "image-gen",
        "illustration": "article-illustrator",
        "cover": "cover",
        "diagram": "diagram",
        "infographic": "infographic",
    }
    for asset in request.assets:
        capability = asset_map.get(asset)
        if capability and capability not in baoyu_capabilities:
            baoyu_capabilities.append(capability)
    if baoyu_capabilities:
        engines.append("baoyu")
        capabilities["baoyu"] = tuple(baoyu_capabilities)

    if needs_pptx:
        engines.append("ppt-master")
        ppt_capabilities = []
        if "chart" in request.assets:
            ppt_capabilities.append("native-chart")
        ppt_capabilities.append("native-pptx")
        capabilities["ppt-master"] = tuple(ppt_capabilities)

    if needs_html:
        engines.append("frontend-slides")
        html_capabilities = ["html-slides"]
        if "pdf" in request.outputs:
            html_capabilities.append("html-pdf")
        capabilities["frontend-slides"] = tuple(html_capabilities)

    if not engines:
        if request.kind == "presentation":
            engines.append("ppt-master")
            capabilities["ppt-master"] = ("native-pptx",)
        else:
            engines.append("baoyu")
            capabilities["baoyu"] = (_KIND_CAPABILITIES.get(request.kind, request.kind),)

    active_refs: set[str] = {"qa", "error-system"}
    if request.product:
        active_refs.add("product-retrieval")
    if request.has_exact_data:
        active_refs.add("data-binding")
    if "ppt-master" in engines:
        active_refs.add("native-pptx")
    if "frontend-slides" in engines or request.presenter:
        active_refs.add("html-presenter")
    if "guizang" in engines:
        active_refs.add("design-systems")
    final_baoyu_capabilities = capabilities.get("baoyu", ())
    if any(name in final_baoyu_capabilities for name in ("image-gen", "article-illustrator", "cover")):
        active_refs.add("images")
    if any(name in final_baoyu_capabilities for name in ("diagram", "infographic")):
        active_refs.add("diagrams-infographics")
    ref_order = (
        "native-pptx",
        "html-presenter",
        "design-systems",
        "images",
        "diagrams-infographics",
        "product-retrieval",
        "data-binding",
        "qa",
        "error-system",
    )
    references = tuple(item for item in ref_order if item in active_refs)
    return RoutePlan(request.outputs, tuple(engines), capabilities, references)
