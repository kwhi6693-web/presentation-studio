# Product retrieval

Use this authority before routing when the user leaves the output, catalog product, or visual style unspecified. Product-recipe retrieval is local-only: use the bundled catalog and do not web search for this decision. Browse only when the presentation independently requires current external evidence. This turns a complete brief into a catalog-backed recommendation; it does not override an explicit user constraint.

## Recommend before route

1. Before any Python, Node, or Git probe or CLI call, use the host's documented dependency/runtime resolver when available and retain its absolute Python, Node, and Git executables.
2. If no host resolver is available or it fails, run the exact PowerShell block in [dependencies.md](dependencies.md) with the already-absolute Skill root and in-memory normalized request: explicit-path resolver; exit and `PASS` checks; preflight before the final recommendation; task-local request JSON carrying only safe readiness booleans; recommend; preserve nonblank explicit `product` and `style` while filling blanks; task-local route JSON; route. Every script uses the resolved absolute Python. Never probe PATH or invoke bare `python`/`py`/`node`/`git`; a WindowsApps Python alias is not runtime evidence.
3. Mark runtime `PARTIAL / NOT EXECUTED` only if both the host resolver and checked-in resolver fail with recorded evidence.
4. Normalize `kind`, `outputs`, `editable`, `has_exact_data`, audience, purpose, topic, tone, channel, density, style, and assets.
5. `scripts/preflight.py` must actually execute first. Attach all of its redacted `readiness` booleans (`python`, `node`, `office_renderer`, `chromium`, and `image_provider`) to the task-local request, then `scripts/recommend.py --json-file <task-local-request-json>` must actually execute with the resolved absolute Python before stating a recommendation or routing. Omitted optional renderer paths are reported explicitly as `false`; never infer their availability from PATH. When the caller has a renderer, pass only its independently resolved absolute file path through `--office-renderer` or `--chromium`. Use resolved absolute Node and Git wherever later provenance or selected-engine steps require them. Do not reconstruct the recommendation by inspecting the catalog or place user JSON in PowerShell source.
6. Treat its `product_id`, `deliverables`, `engine_chain`, and selected style as the router inputs. Follow the returned engine chain exactly using vendored `engines/<name>` authorities.
7. If the request explicitly names an output, product, or style, preserve that value. Run the recommender only to expose compatibility conflicts and evidence; do not silently replace the constraint.
8. Stop before rendering when the result is `FAIL` or its conflicts cannot be resolved without a material user decision.

## Required recommendation record

Report the following fields before production, using the recommendation result rather than free-form selection:

| Field | Record |
|---|---|
| Product evidence | `product_id`, `deliverables`, `reasons`, and `conflicts` from catalog retrieval |
| Retrieval score and confidence | `score` and `score_breakdown`; describe `score` as the recommendation confidence signal, not a guarantee |
| Style evidence | `style.selected`, `style.source` (`explicit` or `inferred`), `style.score`, and `style.preferred_design_authority` |
| Production authority | the exact returned `engine_chain` |
| Data requirement | `data_fidelity_gate`, when returned |
| Runtime evidence | `missing_prerequisites`; never infer readiness from an engine name |
| Completion state | only `PASS`, `PARTIAL`, or `FAIL` |

`PARTIAL` requires the stated fallback and recoverable limit. `FAIL` requires the conflicts. Never invent a catalog ID, candidate evidence, score, style source, engine chain, or status.
