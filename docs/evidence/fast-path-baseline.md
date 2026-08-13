# Fast Path Baseline

Date: 2026-08-13

## Scenario

Create a five-slide bilingual strategy deck as editable PPTX, standalone HTML, and PDF within a short deadline. The brief is complete, one generated hero image is allowed, and routine questions should not block execution.

## Baseline observation

The source-locked Skill had no observable Fast Path entry, no short-deadline predicate, and no explicit escalation boundary. Its root correctly required runtime resolution, preflight, recommendation, routing, narrative planning, rendering, every-page inspection, and repair, but it did not state how to keep context route-scoped or reuse one manifest across native and web renderers.

The repository contract test failed with `Fast Path reference is missing`. This is the controlled baseline failure: a worker could still produce a good result, but the Skill did not reliably shape the requested short-time execution pattern.

## Required change

Add one route-scoped Fast Path that preserves every mandatory gate and escalates to the complete workflow for exact data, template reconstruction, advanced animation, narration, complex provider work, or material ambiguity.
