# Error System

## Severity

- WARNING: quality concern that does not invalidate the artifact; repair when safe.
- RECOVERABLE: one provider/tool/asset path failed but an explicit fallback can satisfy or partially satisfy the request.
- FATAL: required input is unreadable, required native output cannot be produced, package integrity is invalid, or continuing would overwrite/escape the authorized output boundary.

## Recovery order

1. Repair the owning source artifact.
2. Retry only classified transient errors with a bounded count.
3. Switch to another compatible provider or renderer adapter.
4. Use an intentional degraded design that remains coherent.
5. Stop only when the user-required capability has no valid fallback.

Never hide a fallback. A no-image or raster fallback is PARTIAL when the user required AI imagery or native editability. Do not preserve partial files as formal output unless they pass the stated delivery gate.
