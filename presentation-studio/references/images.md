# Image Intelligence

1. Measure the actual image slot before generation.
2. Record slot ratio, subject, composition, camera, lighting, style, palette, negative constraints, focal point, and text-safe region.
3. Choose a provider/model that supports the required ratio and reference behavior. Map unsupported ratios to the closest safe size and record the error; do not silently fall back to 1:1.
4. Prefer the first available compatible provider, then fail over. Retry only errors classified as retryable.
5. If every provider is unavailable, switch to an intentional typographic, diagram, or source-image layout and mark the imagery requirement PARTIAL.

Use the selected capability under `engines/baoyu/skills/`: image generation, cover, article illustration, or slide images. Load only that Skill and its chosen provider/style reference.

Never log credential values. Keep prompt/cache metadata task-scoped. Inspect final crops at full-slide size; reject stretching, face/text crop, low resolution, watermarks, and inconsistent art direction.
