from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import load_products, load_styles
from .data_binding import has_data_binding_contract
from .request import Request, normalize_request


RetrievalRequest = Request


_ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STYLE_WEIGHTS = {
    "topic": 0.25,
    "audience": 0.20,
    "purpose": 0.15,
    "tone": 0.20,
    "density": 0.10,
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
_READINESS_AVAILABLE = "available"
_READINESS_UNAVAILABLE = "unavailable"
_READINESS_UNKNOWN = "unknown"
_READINESS_STATES = frozenset({
    _READINESS_AVAILABLE,
    _READINESS_UNAVAILABLE,
    _READINESS_UNKNOWN,
})
_LEGACY_READINESS_KEYS = frozenset({
    "python",
    "node",
    "office_renderer",
    "chromium",
    "image_provider",
})
_LEGACY_CAPABILITY_ASSERTIONS = {
    "pptx_core": "python",
    "baoyu_core": "node",
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
_CJK_TOKEN_SYNONYMS = {
    "人工智能": "ai",
    "产品": "product",
    "战略": "strategy",
    "投资者": "investors",
    "融资": "fundraising",
    "路演": "investor-pitch",
    "专业": "professional",
    "会议": "meeting",
    "中等": "medium",
    "高管": "executives",
    "董事会": "board",
    "财务": "finance",
    "数据": "data",
    "技术": "technology",
    "架构": "architecture",
    "工程师": "engineers",
    "教育": "education",
    "学习": "learning",
}


def _phrase(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _is_han(character: str) -> bool:
    name = unicodedata.name(character, "")
    return name.startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH"))


def _tokens(value: str) -> frozenset[str]:
    tokens: set[str] = set()
    text = _phrase(value)
    index = 0
    while index < len(text):
        if _is_han(text[index]):
            end = index + 1
            while end < len(text) and _is_han(text[end]):
                end += 1
            span = text[index:end]
            tokens.add(span)
            tokens.update(span)
            tokens.update(span[offset : offset + 2] for offset in range(len(span) - 1))
            for phrase, signal in _CJK_TOKEN_SYNONYMS.items():
                if phrase in span:
                    tokens.update((phrase, signal))
            index = end
            continue
        match = _ASCII_TOKEN_PATTERN.match(text, index)
        if match is not None:
            token = match.group()
            tokens.add(_TOKEN_SYNONYMS.get(token, token))
            index = match.end()
            continue
        index += 1
    return frozenset(tokens)


def _overlap(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _tag_overlap(value: str, tags: list[str]) -> float:
    return _overlap(_tokens(value), _tokens(" ".join(tags)))


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


def _infer_style(request: Request, styles: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    if request.style:
        selected = next((style for style in styles if style["id"] == request.style), None)
        if selected is None and request.style_source != "freeform":
            raise ValueError(
                f"Unknown catalog style: {request.style}. Set style_source to 'freeform' to use it."
            )
        return {
            "selected": request.style,
            "source": "freeform" if selected is None else "explicit",
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


def _supports_catalog_mode(product: dict[str, Any], field: str, use_case: str) -> bool:
    return bool(product.get(field, use_case in product["intended_uses"]))


def _supports_request(product: dict[str, Any], request: Request) -> bool:
    if product["kind"] != request.kind:
        return False
    if request.outputs and not set(request.outputs).issubset(product["outputs"]):
        return False
    if request.presenter and not _supports_catalog_mode(product, "presenter", "presenter-mode"):
        return False
    if request.single_file and not _supports_catalog_mode(
        product, "single_file", "single-file-presentation"
    ):
        return False
    if request.aspect_ratio and request.aspect_ratio not in product["aspect_ratios"]:
        return False
    if request.editable:
        if request.outputs and not set(request.outputs).intersection(product["editable_outputs"]):
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
    products: tuple[dict[str, Any], ...], request: Request
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
            "presenter",
            lambda product: not request.presenter
            or _supports_catalog_mode(product, "presenter", "presenter-mode"),
            "presenter: no surviving product supports presenter mode",
            "presenter=true",
        ),
        (
            "single_file",
            lambda product: not request.single_file
            or _supports_catalog_mode(product, "single_file", "single-file-presentation"),
            "single_file: no surviving product supports single-file delivery",
            "single_file=true",
        ),
        (
            "aspect_ratio",
            lambda product: not request.aspect_ratio
            or request.aspect_ratio in product["aspect_ratios"],
            f"aspect_ratio: no surviving product supports {request.aspect_ratio}",
            f"aspect_ratio={request.aspect_ratio}",
        ),
        (
            "editable",
            lambda product: not request.editable or (
                bool(set(request.outputs).intersection(product["editable_outputs"]))
                if request.outputs else product["editable"]
            ),
            "editable: no surviving product provides an editable requested output",
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


def _validate_readiness(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("request.readiness: must be an object of readiness values")
    result: dict[str, str] = {}
    for key, available in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("request.readiness: keys must be non-empty strings")
        if isinstance(available, bool):
            result[key] = _READINESS_AVAILABLE if available else _READINESS_UNAVAILABLE
        elif isinstance(available, str) and available in _READINESS_STATES:
            result[key] = available
        else:
            raise ValueError(
                f"request.readiness.{key}: must be a boolean or one of "
                "available, unavailable, unknown"
            )
    if set(result) == _LEGACY_READINESS_KEYS:
        result.update(
            {
                capability: result[runtime]
                for capability, runtime in _LEGACY_CAPABILITY_ASSERTIONS.items()
            }
        )
    return result


def _readiness_state(readiness: dict[str, str], prerequisite: str) -> str:
    return readiness.get(prerequisite, _READINESS_UNKNOWN)


def _missing_prerequisites(
    product: dict[str, Any], readiness: dict[str, str], field: str
) -> tuple[str, ...]:
    return tuple(
        name
        for name in product[field]
        if _readiness_state(readiness, name) != _READINESS_AVAILABLE
    )


def _product_score(
    product: dict[str, Any],
    request: Request,
    style: dict[str, Any],
    readiness: dict[str, str],
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
        else sum(
            _readiness_state(readiness, name) == _READINESS_AVAILABLE
            for name in required
        )
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
    request: Request,
    style: dict[str, Any],
    readiness: dict[str, str],
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
    request: Request,
    readiness: dict[str, str],
) -> dict[str, Any] | None:
    by_id = {item["id"]: item for item in products}
    current = product
    visited = {product["id"]}
    candidates: list[dict[str, Any]] = []
    while current.get("fallback"):
        fallback_id = current["fallback"]
        if fallback_id in visited:
            return None
        visited.add(fallback_id)
        declared = by_id.get(fallback_id)
        if declared is None or not _supports_request(declared, request):
            return None
        candidates.append(declared)
        current = declared
    return next(
        (
            candidate
            for candidate in candidates
            if not _missing_prerequisites(candidate, readiness, "required_prerequisites")
        ),
        None,
    )


def _failed_recommendation(
    *,
    request: Request,
    style: dict[str, Any],
    reasons: tuple[str, ...],
    missing_prerequisites: tuple[str, ...],
) -> Recommendation:
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
        reasons=reasons,
        conflicts=(),
        missing_prerequisites=missing_prerequisites,
    )


def recommend_product(
    raw: dict[str, Any],
    *,
    catalog_root: Path | None = None,
    readiness: dict[str, bool | str] | None = None,
) -> Recommendation:
    request = normalize_request(raw)
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
    reasons = filter_evidence + score_reasons + (
        f"selected {product['id']} with deterministic catalog scoring",
    )

    if missing_required:
        declared = _fallback_product(products, product, request, effective_readiness)
        if declared is not None:
            fallback_score, fallback_breakdown, fallback_reasons = _product_score(
                declared, request, style, effective_readiness
            )
            fallback_missing_optional = _missing_prerequisites(
                declared, effective_readiness, "optional_prerequisites"
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
                    "required prerequisites unavailable; compatible catalog fallback selected",
                ),
                conflicts=(),
                missing_prerequisites=tuple(
                    dict.fromkeys((*missing_required, *fallback_missing_optional))
                ),
            )
        return _failed_recommendation(
            request=request,
            style=style,
            reasons=reasons + (
                "required prerequisites unavailable and no runnable catalog fallback exists",
            ),
            missing_prerequisites=missing_required + missing_optional,
        )

    if missing_optional:
        reasons += (f"missing optional prerequisites: {', '.join(missing_optional)}",)
    return Recommendation(
        product_id=product["id"],
        deliverables=tuple(request.outputs or product["outputs"]),
        style=style,
        engine_chain=tuple(product["engine_chain"]),
        score=score,
        score_breakdown=breakdown,
        data_fidelity_gate="exact-match" if request.has_exact_data else None,
        fallback=product.get("fallback"),
        status="PARTIAL" if missing_optional else "PASS",
        reasons=reasons,
        conflicts=(),
        missing_prerequisites=missing_optional,
    )
