# Exact-data binding

Use this authority whenever `has_exact_data` is true. Exact values are source data, not design suggestions: preserve their value, concrete type, order, units, periods, labels, source form, source identifier, and provenance.

## Bind before render

1. Build `DataManifest` with `build_data_manifest` before slide, chart, table, or image rendering. Require non-empty `source`, `source_form` (`table`, `csv`, `xlsx`, `json`, or `markdown-table`), non-empty `provenance`, and at least one validated field.
2. Preserve ordered field `name`, declared `type`, concrete types, values, `unit`, `period`, and `label`. Preserve `None` and record its zero-based `missing_positions`; never fill, round, aggregate, or convert it.
3. Supply `record_ids` when record identity exists. Record duplicate IDs and field/record length inconsistencies in `findings`. A finding is evidence, not permission to alter data.
4. Keep `transformations` empty unless every entry has a non-empty name and documentation plus explicit `approved: true`. Unapproved or undocumented transformations fail closed.
5. Call `build_engine_payload`/`bind_data` for the selected exact-data product. `native-data-deck` feeds the full manifest and exact labels to `ppt-master` native charts/tables; never use screenshots or manual redraw. `data-image` and `infographic-image` feed the full manifest to their Baoyu structured targets.
6. Actual rendering happens later in that selected engine. The binding payload proves only the required input contract; it does not claim that an artifact was rendered or inspected.
7. Require the renderer to return the structured observed contract and compare it with `compare_bound_values`. Compare source, source form, provenance, field order/name/declared type/concrete types/values/unit/period/label, transformations, missing positions, record IDs, duplicate IDs, and findings.
8. Run the selected engine's chart/table or image validation and the normal render-inspect-repair loop after comparison.

## Fidelity record and stopping rule

Record the manifest location or inline manifest, bound target, comparison result, mismatches, and the selected `data_fidelity_gate`.

- `PASS`: validated manifest, selected-product engine payload, observed contract, and exact comparison all exist; every compared dimension matches and there are no findings; required engine validation also passed.
- `PARTIAL`: values/contracts match but the manifest records missing values, duplicates, length inconsistencies, or other material findings; or a required environment/render validation did not run. State every unexecuted check as `PARTIAL / NOT EXECUTED`.
- `FAIL`: any observed mismatch, empty/invalid manifest, undocumented or unapproved transformation, missing field, unsupported binding, or missing required contract exists. Repair or request a material data decision before completion.

Use only `PASS`, `PARTIAL`, or `FAIL` for the fidelity record.
