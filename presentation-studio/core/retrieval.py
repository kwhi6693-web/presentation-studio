from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import load_products, load_styles
from .data_binding import has_data_binding_contract


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STYLE_WEIGHTS = {
    "topic": 0.30,
    "audience": 0.25,
    "purpose": 0.20,
    "density": 0.15,
    "channel": 0.10,
}
_PRODUCT_WEIGHTS = {
    "use_case": 0.25,
    "audience": 0.15,
    "purpose": 0.15,
    "density": 0.10,
    "style": 0.10,
    "channel": 0.10,
    "data": 0.10,
    "readiness": 0.05,
}
_SCORE_DIMENSIONS = tuple(_PRODUCT_WEIGHTS)
_EXACT_DATA_QUALITY_GATE = "data-fidelity"
_NEUTRAL_STYLE_ID = "swiss-editorial"
_LOW_STYLE_SIGNAL = 0.06
_KIND_ALIASES = {
    "presentation": "presentation",
    "deck": "presentation",
    "slide deck": "presentation",
    "slides": "presentation",
    "ppt": "presentation",
    "pptx": "presentation",
    "powerpoint": "presentation",
    "powerpoint deck": "presentation",
    "investor pitch deck": "presentation",
    "pitch deck": "presentation",
    "data deck": "presentation",
    "technical deck": "presentation",
    "image slide deck": "presentation",
    "cover": "cover",
    "cover image": "cover",
    "article cover": "cover",
    "illustration": "illustration",
    "article illustration": "illustration",
    "infographic": "infographic",
    "infographic image": "infographic",
    "diagram": "diagram",
    "technical diagram": "diagram",
    "architecture diagram": "diagram",
    "image": "image",
    "data image": "image",
    "png": "image",
}
_KIND_CONTEXT = {
    "investor pitch deck": {
        "audience": "investors",
        "purpose": "investor pitch fundraising",
        "topic": "business finance",
    },
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
_KIND_OUTPUTS = {
    "ppt": "pptx",
    "pptx": "pptx",
    "powerpoint": "pptx",
    "powerpoint deck": "pptx",
    "png": "png",
}
_OUTPUT_ALIASES = {
    "ppt": "pptx",
    "pptx": "pptx",
    "powerpoint": "pptx",
    "slides": "pptx",
    "slide deck": "pptx",
    "web": "html",
    "web presentation": "html",
    "html": "html",
    "pdf": "pdf",
    "png": "png",
    "image": "png",
    "jpg": "png",
    "jpeg": "png",
    "svg": "svg",
    "vector": "svg",
}
_DATA_FORM_ALIASES = {
    "table": "table",
    "csv": "csv",
    "xlsx": "xlsx",
    "excel": "xlsx",
    "json": "json",
    "markdown table": "markdown-table",
    "markdown-table": "markdown-table",
    "text": "text",
    "image": "image",
}
_TOKEN_SYNONYMS = {
    "investor": "investors",
    "executive": "executives",
    "engineer": "engineers",
    "developer": "developers",
    "financial": "finance",
    "fundraise": "fundraising",
    "fundraiser": "fundraising",
    "analytic": "analytics",
    "analytical": "analytics",
}


def _phrase(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _tokens(value: str) -> set[str]:
    return {
        _TOKEN_SYNONYMS.get(token, token)
        for token in _TOKEN_PATTERN.findall(_phrase(value))
    }


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _tag_overlap(value: str, tags: list[str]) -> float:
    return _overlap(_tokens(value), _tokens(" ".join(tags)))


@dataclass(frozen=True)
class RetrievalRequest:
    kind: str
    outputs: tuple[str, ...]
    editable: bool
    has_exact_data: bool
    topic: str
    audience: str
    purpose: str
    tone: str
    channel: str
    density: str
    style: str
    assets: tuple[str, ...]
    data_forms: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RetrievalRequest:
        if not isinstance(raw, dict):
            raise ValueError("request: top-level value must be an object")

        def text(field: str) -> str:
            if field not in raw:
                return ""
            value = raw[field]
            if not isinstance(value, str):
                raise ValueError(f"request.{field}: must be a string")
            return _phrase(value)

        def values(field: str, aliases: dict[str, str] | None = None) -> tuple[str, ...]:
            if field not in raw:
                return ()
            value = raw[field]
            if isinstance(value, str):
                value = (value,)
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"request.{field}: must be a string or list of strings")
            normalized: list[str] = []
            for index, entry in enumerate(value):
                if not isinstance(entry, str) or not entry.strip():
                    raise ValueError(f"request.{field}[{index}]: must be a non-empty string")
                phrase = _phrase(entry)
                canonical = aliases.get(phrase, phrase) if aliases else phrase
                if canonical not in normalized:
                    normalized.append(canonical)
            return tuple(normalized)

        def boolean(field: str) -> bool:
            value = raw.get(field, False)
            if not isinstance(value, bool):
                raise ValueError(f"request.{field}: must be a boolean")
            return value

        raw_kind = text("kind") or "presentation"
        kind = _KIND_ALIASES.get(raw_kind, raw_kind)
        context = _KIND_CONTEXT.get(raw_kind, {})
        outputs = list(values("outputs", _OUTPUT_ALIASES))
        inferred_output = _KIND_OUTPUTS.get(raw_kind)
        if inferred_output and not outputs:
            outputs.append(inferred_output)
        assets = list(values("assets"))
        contextual_asset = context.get("assets")
        if contextual_asset and contextual_asset not in assets:
            assets.append(contextual_asset)
        style_value = raw.get("style", "")
        if not isinstance(style_value, str):
            raise ValueError("request.style: must be a string")
        style = _phrase(style_value).replace(" ", "-")
        return cls(
            kind=kind,
            outputs=tuple(outputs),
            editable=boolean("editable"),
            has_exact_data=boolean("has_exact_data"),
            topic=text("topic") or context.get("topic", ""),
            audience=text("audience") or context.get("audience", ""),
            purpose=text("purpose") or context.get("purpose", ""),
            tone=text("tone"),
            channel=text("channel") or context.get("channel", ""),
            density=text("density") or context.get("density", ""),
            style=style,
            assets=tuple(assets),
            data_forms=values("data_forms", _DATA_FORM_ALIASES),
        )


@dataclass(frozen=True)
class Recommendation:
    product_id: str | None
    deliverables: tuple[str, ...]
    style: dict[str, Any]
    engine_chain: tuple[str, ...]
    score: float
    score_breakdown: dict[str, float]
    data_fidelity_gate: str | None
    fallback: str | None
    status: str
    reasons: tuple[str, ...]
    conflicts: tuple[str, ...]
    missing_prerequisites: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "deliverables": list(self.deliverables),
            "style": dict(self.style),
            "engine_chain": list(self.engine_chain),
            "score": self.score,
            "score_breakdown": dict(self.score_breakdown),
            "data_fidelity_gate": self.data_fidelity_gate,
            "fallback": self.fallback,
            "status": self.status,
            "reasons": list(self.reasons),
            "conflicts": list(self.conflicts),
            "missing_prerequisites": list(self.missing_prerequisites),
        }


def _style_confidence(score: float) -> str:
    if score >= 0.35:
        return "high"
    if score >= 0.15:
        return "medium"
    return "low"


def _infer_style(request: RetrievalRequest, styles: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    if request.style:
        selected = next((style for style in styles if style["id"] == request.style), None)
        return {
            "selected": request.style,
            "source": "explicit",
            "score": 1.0,
            "confidence": "high",
            "preferred_design_authority": (
                selected["preferred_design_authority"] if selected is not None else None
            ),
            "reasons": ["explicit user style preserved"],
        }

    def score_style(style: dict[str, Any]) -> tuple[float, dict[str, float]]:
        raw_scores = {
            field: _tag_overlap(getattr(request, field), style[f"{field}_tags"])
            for field in _STYLE_WEIGHTS
        }
        breakdown = {
            field: round(raw_scores[field] * weight, 6)
            for field, weight in _STYLE_WEIGHTS.items()
        }
        return round(sum(breakdown.values()), 6), breakdown

    candidates: list[tuple[float, dict[str, float], dict[str, Any]]] = []
    for style in styles:
        score, breakdown = score_style(style)
        candidates.append((score, breakdown, style))
    best_index = max(range(len(candidates)), key=lambda index: candidates[index][0])
    score, breakdown, selected = candidates[best_index]
    reasons = [
        f"matched style {field} signal"
        for field, value in breakdown.items()
        if value > 0
    ]
    if request.tone and _tag_overlap(request.tone, selected["tone_tags"]) > 0:
        reasons.append("tone agrees with the selected catalog style")
    if score < _LOW_STYLE_SIGNAL:
        selected = next(
            (style for style in styles if style["id"] == _NEUTRAL_STYLE_ID),
            styles[0],
        )
        score, breakdown = score_style(selected)
        reasons = ["low style signal; selected neutral catalog fallback"]
    return {
        "selected": selected["id"],
        "source": "inferred",
        "score": score,
        "confidence": _style_confidence(score),
        "preferred_design_authority": selected["preferred_design_authority"],
        "reasons": reasons,
        "score_breakdown": breakdown,
    }


def _supports_request(product: dict[str, Any], request: RetrievalRequest) -> bool:
    if product["kind"] != request.kind:
        return False
    if request.outputs and not set(request.outputs).issubset(product["outputs"]):
        return False
    if request.editable:
        if request.outputs and not set(request.outputs).issubset(product["editable_outputs"]):
            return False
        if not request.outputs and not product["editable"]:
            return False
    if request.has_exact_data:
        if _EXACT_DATA_QUALITY_GATE not in product["quality_gates"]:
            return False
        if not has_data_binding_contract(product["id"]):
            return False
        if request.data_forms and not set(request.data_forms).issubset(product["supported_data_forms"]):
            return False
    return True


def _hard_filter(
    products: tuple[dict[str, Any], ...], request: RetrievalRequest
) -> tuple[list[dict[str, Any]], tuple[str, ...], tuple[str, ...]]:
    candidates = list(products)
    evidence: list[str] = []
    filters: list[tuple[str, Any, str, str]] = [
        (
            "kind",
            lambda product: product["kind"] == request.kind,
            f"kind: no catalog product supports {request.kind}",
            f"kind={request.kind}",
        ),
        (
            "outputs",
            lambda product: not request.outputs or set(request.outputs).issubset(product["outputs"]),
            f"outputs: no {request.kind} product supports {', '.join(request.outputs)}",
            f"outputs={','.join(request.outputs)}",
        ),
        (
            "editable",
            lambda product: not request.editable or (
                set(request.outputs).issubset(product["editable_outputs"])
                if request.outputs else product["editable"]
            ),
            "editable: no surviving product provides native editability for the requested outputs",
            "editable=true",
        ),
        (
            "has_exact_data",
            lambda product: not request.has_exact_data or (
                _EXACT_DATA_QUALITY_GATE in product["quality_gates"]
                and has_data_binding_contract(product["id"])
                and (
                    not request.data_forms
                    or set(request.data_forms).issubset(product["supported_data_forms"])
                )
            ),
            "has_exact_data: no surviving product has a binding contract for the requested exact data forms",
            (
                f"has_exact_data=true; data_forms={','.join(request.data_forms)}"
                if request.data_forms else "has_exact_data=true"
            ),
        ),
    ]
    for field, predicate, conflict, requested_value in filters:
        survivors = [product for product in candidates if predicate(product)]
        rejected = [product for product in candidates if not predicate(product)]
        evidence.extend(
            f"{product['id']} rejected: {requested_value}"
            for product in rejected
        )
        if not survivors:
            return [], tuple(evidence), (conflict,)
        candidates = survivors
    return candidates, tuple(evidence), ()


def _validate_readiness(value: Any) -> dict[str, bool] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("request.readiness: must be an object of boolean values")
    result: dict[str, bool] = {}
    for key, available in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("request.readiness: keys must be non-empty strings")
        if not isinstance(available, bool):
            raise ValueError(f"request.readiness.{key}: must be a boolean")
        result[key] = available
    return result


def _missing_prerequisites(
    product: dict[str, Any], readiness: dict[str, bool] | None, field: str
) -> tuple[str, ...]:
    if readiness is None:
        return ()
    return tuple(name for name in product[field] if readiness.get(name) is False)


def _product_score(
    product: dict[str, Any],
    request: RetrievalRequest,
    style: dict[str, Any],
    readiness: dict[str, bool] | None,
) -> tuple[float, dict[str, float], tuple[str, ...]]:
    use_case_signal = " ".join((request.topic, *request.assets))
    if request.has_exact_data:
        if request.data_forms:
            data_score = _tag_overlap(" ".join(request.data_forms), product["supported_data_forms"])
        else:
            data_score = 1.0
    elif request.data_forms:
        data_score = _tag_overlap(" ".join(request.data_forms), product["supported_data_forms"])
    else:
        data_score = 0.0
    required = product["required_prerequisites"]
    readiness_score = (
        0.0
        if not required
        else sum(readiness is not None and readiness.get(name) is True for name in required)
        / len(required)
    )
    raw_scores = {
        "use_case": _tag_overlap(use_case_signal, product["intended_uses"]),
        "audience": _tag_overlap(request.audience, product["audience_tags"]),
        "purpose": _tag_overlap(request.purpose, product["purpose_tags"]),
        "density": _tag_overlap(request.density, product["density_tags"]),
        "style": _tag_overlap(style["selected"], product["style_tags"]),
        "channel": _tag_overlap(request.channel, product["channel_tags"]),
        "data": data_score,
        "readiness": readiness_score,
    }
    breakdown = {
        field: round(raw_scores[field] * weight, 6)
        for field, weight in _PRODUCT_WEIGHTS.items()
    }
    reasons = tuple(
        f"matched {field.replace('_', ' ')} signal"
        for field in _SCORE_DIMENSIONS
        if field != "readiness" and breakdown[field] > 0
    )
    return round(sum(breakdown.values()), 6), breakdown, reasons


def _rank_products(
    products: list[dict[str, Any]],
    request: RetrievalRequest,
    style: dict[str, Any],
    readiness: dict[str, bool] | None,
) -> tuple[dict[str, Any], float, dict[str, float], tuple[str, ...]]:
    scored = [
        (*_product_score(product, request, style, readiness), product)
        for product in products
    ]
    best_index = max(
        range(len(scored)),
        key=lambda index: (
            scored[index][0],
            -len(_missing_prerequisites(scored[index][3], readiness, "optional_prerequisites")),
            -index,
        ),
    )
    score, breakdown, reasons, product = scored[best_index]
    return product, score, breakdown, reasons


def _fallback_product(
    products: tuple[dict[str, Any], ...],
    product: dict[str, Any],
    request: RetrievalRequest,
    readiness: dict[str, bool] | None,
) -> dict[str, Any] | None:
    fallback_id = product.get("fallback")
    declared = next((item for item in products if item["id"] == fallback_id), None)
    if declared is None or not _supports_request(declared, request):
        return None
    missing = _missing_prerequisites(declared, readiness, "required_prerequisites")
    missing += _missing_prerequisites(declared, readiness, "optional_prerequisites")
    return None if missing else declared


def recommend_product(
    raw: dict[str, Any],
    *,
    catalog_root: Path | None = None,
    readiness: dict[str, bool] | None = None,
) -> Recommendation:
    request = RetrievalRequest.from_dict(raw)
    effective_readiness = _validate_readiness(
        readiness if readiness is not None else raw.get("readiness")
    )
    root = catalog_root or Path(__file__).resolve().parents[1]
    products = load_products(root)
    styles = load_styles(root)
    style = _infer_style(request, styles)
    eligible, filter_evidence, conflicts = _hard_filter(products, request)
    if not eligible:
        return Recommendation(
            product_id=None,
            deliverables=request.outputs,
            style=style,
            engine_chain=(),
            score=0.0,
            score_breakdown={field: 0.0 for field in _SCORE_DIMENSIONS},
            data_fidelity_gate="exact-match" if request.has_exact_data else None,
            fallback=None,
            status="FAIL",
            reasons=filter_evidence + ("no catalog product survived hard constraints",),
            conflicts=conflicts,
            missing_prerequisites=(),
        )

    product, score, breakdown, score_reasons = _rank_products(
        eligible, request, style, effective_readiness
    )
    missing_required = _missing_prerequisites(
        product, effective_readiness, "required_prerequisites"
    )
    missing_optional = _missing_prerequisites(
        product, effective_readiness, "optional_prerequisites"
    )
    missing = missing_required + missing_optional
    reasons = filter_evidence + score_reasons + (
        f"selected {product['id']} with deterministic catalog scoring",
    )

    if "image_provider" in missing_optional and "baoyu" in product["engine_chain"]:
        declared = _fallback_product(products, product, request, effective_readiness)
        if declared is not None:
            fallback_score, fallback_breakdown, fallback_reasons = _product_score(
                declared, request, style, effective_readiness
            )
            return Recommendation(
                product_id=declared["id"],
                deliverables=tuple(request.outputs or declared["outputs"]),
                style=style,
                engine_chain=tuple(declared["engine_chain"]),
                score=fallback_score,
                score_breakdown=fallback_breakdown,
                data_fidelity_gate="exact-match" if request.has_exact_data else None,
                fallback=declared["id"],
                status="PARTIAL",
                reasons=reasons + fallback_reasons + (
                    "image provider unavailable; compatible catalog fallback selected",
                ),
                conflicts=(),
                missing_prerequisites=("image_provider",),
            )
        ready_candidates = [
            candidate
            for candidate in eligible
            if candidate["id"] != product["id"]
            and not _missing_prerequisites(candidate, effective_readiness, "required_prerequisites")
            and not _missing_prerequisites(candidate, effective_readiness, "optional_prerequisites")
        ]
        if ready_candidates:
            fallback_product, fallback_score, fallback_breakdown, fallback_reasons = _rank_products(
                ready_candidates, request, style, effective_readiness
            )
            return Recommendation(
                product_id=fallback_product["id"],
                deliverables=tuple(request.outputs or fallback_product["outputs"]),
                style=style,
                engine_chain=tuple(fallback_product["engine_chain"]),
                score=fallback_score,
                score_breakdown=fallback_breakdown,
                data_fidelity_gate="exact-match" if request.has_exact_data else None,
                fallback=fallback_product["id"],
                status="PARTIAL",
                reasons=reasons + fallback_reasons + (
                    "image provider unavailable; compatible runnable candidate selected",
                ),
                conflicts=(),
                missing_prerequisites=("image_provider",),
            )
        return Recommendation(
            product_id=None,
            deliverables=tuple(request.outputs or product["outputs"]),
            style=style,
            engine_chain=(),
            score=0.0,
            score_breakdown={field: 0.0 for field in _SCORE_DIMENSIONS},
            data_fidelity_gate="exact-match" if request.has_exact_data else None,
            fallback="intentional-no-ai-image-layout",
            status="PARTIAL",
            reasons=reasons + (
                "image provider unavailable; use intentional no-AI-image layout",
            ),
            conflicts=(),
            missing_prerequisites=("image_provider",),
        )

    if missing:
        reasons += (f"missing prerequisites: {', '.join(missing)}",)
    return Recommendation(
        product_id=product["id"],
        deliverables=tuple(request.outputs or product["outputs"]),
        style=style,
        engine_chain=tuple(product["engine_chain"]),
        score=score,
        score_breakdown=breakdown,
        data_fidelity_gate="exact-match" if request.has_exact_data else None,
        fallback=product.get("fallback"),
        status="PARTIAL" if missing else "PASS",
        reasons=reasons,
        conflicts=(),
        missing_prerequisites=missing,
    )
