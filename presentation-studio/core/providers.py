from __future__ import annotations

from dataclasses import dataclass

from .status import PARTIAL, PASS


@dataclass(frozen=True)
class ProviderState:
    name: str
    available: bool
    supports_reference: bool
    reason: str = ""


@dataclass(frozen=True)
class ProviderDecision:
    provider: str | None
    status: str
    fallback: str | None
    warnings: tuple[str, ...]


def select_provider(
    providers: list[ProviderState],
    *,
    needs_reference: bool = False,
) -> ProviderDecision:
    warnings: list[str] = []
    for provider in providers:
        if not provider.available:
            warnings.append(f"{provider.name} unavailable: {provider.reason or 'preflight failed'}")
            continue
        if needs_reference and not provider.supports_reference:
            warnings.append(f"{provider.name} skipped: reference images unsupported")
            continue
        return ProviderDecision(provider.name, PASS, None, tuple(warnings))
    warnings.append("No compatible image provider; use an intentional no-AI-image layout.")
    return ProviderDecision(None, PARTIAL, "intentional-no-ai-image-layout", tuple(warnings))
