from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


_SUPPORTED_TYPES = frozenset({"number", "string"})
_SUPPORTED_SOURCE_FORMS = frozenset({"table", "csv", "xlsx", "json", "markdown-table"})


@dataclass(frozen=True)
class DataField:
    name: str
    value_type: str
    concrete_types: tuple[str, ...]
    values: tuple[Any, ...]
    missing_positions: tuple[int, ...]
    unit: str = ""
    period: str = ""
    label: str = ""


@dataclass(frozen=True)
class DataTransformation:
    name: str
    documentation: str
    approved: bool
    parameters_json: str = "{}"

    @property
    def parameters(self) -> dict[str, Any]:
        value = json.loads(self.parameters_json)
        if not isinstance(value, dict):
            raise ValueError("transformation parameters must be an object")
        return value


@dataclass(frozen=True)
class DataManifest:
    source: str
    source_form: str
    provenance: str
    fields: tuple[DataField, ...]
    transformations: tuple[DataTransformation, ...]
    findings: tuple[str, ...]
    record_ids: tuple[Any, ...]
    duplicate_record_ids: tuple[Any, ...]


@dataclass(frozen=True)
class DataFidelityReport:
    status: str
    mismatches: tuple[str, ...]
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BindingContract:
    engine: str
    target_types: tuple[str, ...]
    render_mode: str
    manual_redraw_allowed: bool


@dataclass(frozen=True)
class EnginePayload:
    product_id: str
    engine: str
    target_types: tuple[str, ...]
    render_mode: str
    manual_redraw_allowed: bool
    manifest: DataManifest
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_engine_payload(self)

    @property
    def binding_targets(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (field.name, _target_type_for_product(self.product_id, field))
            for field in self.manifest.fields
        )


@dataclass(frozen=True)
class DataBinding:
    field: DataField
    product_id: str
    engine: str
    target_type: str
    payload: EnginePayload
    field_index: int

    def __post_init__(self) -> None:
        validate_data_binding(self)


@dataclass(frozen=True)
class ObservedDataContract:
    source: Any
    source_form: Any
    provenance: Any
    fields: Any
    transformations: Any
    findings: Any
    record_ids: Any
    duplicate_record_ids: Any


_PRODUCT_BINDING_CONTRACTS = {
    "native-data-deck": BindingContract(
        engine="ppt-master",
        target_types=("native-chart", "native-table"),
        render_mode="native-objects",
        manual_redraw_allowed=False,
    ),
    "data-image": BindingContract(
        engine="baoyu",
        target_types=("data-image",),
        render_mode="structured-data-image",
        manual_redraw_allowed=False,
    ),
    "infographic-image": BindingContract(
        engine="baoyu",
        target_types=("infographic",),
        render_mode="structured-infographic",
        manual_redraw_allowed=False,
    ),
}


def build_data_manifest(raw: dict[str, Any]) -> DataManifest:
    if type(raw) is not dict:
        raise ValueError("manifest: must be an object")
    source = _required_text(raw, "source")
    source_form = _required_text(raw, "source_form")
    if source_form not in _SUPPORTED_SOURCE_FORMS:
        raise ValueError(
            f"source_form: unsupported value {source_form!r}; expected one of "
            f"{', '.join(sorted(_SUPPORTED_SOURCE_FORMS))}"
        )
    provenance = _required_text(raw, "provenance")

    transformations = _build_transformations(raw.get("transformations", []))
    supplied_findings = raw.get("findings", [])
    if type(supplied_findings) is not list or not all(
        type(item) is str and item.strip() for item in supplied_findings
    ):
        raise ValueError("findings: must be a list of non-empty strings")
    findings = list(supplied_findings)

    fields_raw = raw.get("fields")
    if type(fields_raw) is not list or not fields_raw:
        raise ValueError("fields: must be a non-empty list")
    fields: list[DataField] = []
    names: set[str] = set()
    for index, field_raw in enumerate(fields_raw):
        path = f"fields[{index}]"
        if type(field_raw) is not dict:
            raise ValueError(f"{path}: must be an object")
        name = _required_text(field_raw, "name", path)
        if name in names:
            raise ValueError(f"{path}.name: duplicate field name {name!r}")
        names.add(name)
        value_type = field_raw.get("type")
        if type(value_type) is not str or value_type not in _SUPPORTED_TYPES:
            raise ValueError(f"{path}.type: unsupported field type {value_type!r}")
        values = field_raw.get("values")
        if type(values) is not list or not values:
            raise ValueError(f"{path}.values: must be a non-empty list")
        _validate_values(value_type, values, path)
        missing_positions = tuple(
            position for position, value in enumerate(values) if value is None
        )
        if missing_positions:
            findings.append(
                f"{path}.values: missing values at positions "
                + ", ".join(str(position) for position in missing_positions)
            )
        fields.append(DataField(
            name=name,
            value_type=value_type,
            concrete_types=tuple(type(value).__name__ for value in values),
            values=tuple(values),
            missing_positions=missing_positions,
            unit=_optional_text(field_raw, "unit", path),
            period=_optional_text(field_raw, "period", path),
            label=_optional_text(field_raw, "label", path),
        ))

    expected_length = len(fields[0].values)
    for index, field in enumerate(fields[1:], start=1):
        if len(field.values) != expected_length:
            findings.append(
                f"fields[{index}].values: length {len(field.values)} differs from "
                f"fields[0] length {expected_length}"
            )

    record_ids_raw = raw.get("record_ids", [])
    if type(record_ids_raw) is not list:
        raise ValueError("record_ids: must be a list")
    for index, record_id in enumerate(record_ids_raw):
        if type(record_id) not in (str, int):
            raise ValueError(f"record_ids[{index}]: must be a string or integer")
        if type(record_id) is str and not record_id.strip():
            raise ValueError(f"record_ids[{index}]: must not be empty")
    record_ids = tuple(record_ids_raw)
    duplicate_record_ids = _find_duplicates(record_ids)
    if duplicate_record_ids:
        findings.append(
            "record_ids: duplicate record IDs "
            + ", ".join(repr(record_id) for record_id in duplicate_record_ids)
        )
    if record_ids and len(record_ids) != expected_length:
        findings.append(
            f"record_ids: length {len(record_ids)} differs from fields[0] length "
            f"{expected_length}"
        )

    manifest = DataManifest(
        source=source,
        source_form=source_form,
        provenance=provenance,
        fields=tuple(fields),
        transformations=transformations,
        findings=tuple(findings),
        record_ids=record_ids,
        duplicate_record_ids=duplicate_record_ids,
    )
    validate_data_manifest(manifest)
    return manifest


def validate_data_manifest(manifest: DataManifest) -> None:
    if type(manifest) is not DataManifest:
        raise ValueError("manifest: must be a DataManifest")
    _validate_manifest_text(manifest.source, "source", required=True)
    _validate_manifest_text(manifest.provenance, "provenance", required=True)
    _validate_manifest_text(manifest.source_form, "source_form", required=True)
    if manifest.source_form not in _SUPPORTED_SOURCE_FORMS:
        raise ValueError(f"source_form: unsupported value {manifest.source_form!r}")
    if type(manifest.fields) is not tuple or not manifest.fields:
        raise ValueError("fields: must be a non-empty tuple")

    names: set[str] = set()
    for index, field in enumerate(manifest.fields):
        path = f"fields[{index}]"
        if type(field) is not DataField:
            raise ValueError(f"{path}: must be a DataField")
        _validate_manifest_text(field.name, f"{path}.name", required=True)
        if field.name in names:
            raise ValueError(f"{path}.name: duplicate field name {field.name!r}")
        names.add(field.name)
        if type(field.value_type) is not str or field.value_type not in _SUPPORTED_TYPES:
            raise ValueError(f"{path}.type: unsupported field type {field.value_type!r}")
        if type(field.values) is not tuple or not field.values:
            raise ValueError(f"{path}.values: must be a non-empty tuple")
        _validate_values(field.value_type, list(field.values), path)
        expected_types = tuple(type(value).__name__ for value in field.values)
        if type(field.concrete_types) is not tuple or any(
            type(value) is not str for value in field.concrete_types
        ) or field.concrete_types != expected_types:
            raise ValueError(
                f"{path}.concrete_types: expected {expected_types!r}, got "
                f"{field.concrete_types!r}"
            )
        expected_missing = tuple(
            position for position, value in enumerate(field.values) if value is None
        )
        if type(field.missing_positions) is not tuple or any(
            type(value) is not int for value in field.missing_positions
        ) or field.missing_positions != expected_missing:
            raise ValueError(
                f"{path}.missing_positions: expected {expected_missing!r}, got "
                f"{field.missing_positions!r}"
            )
        for key, value in (
            ("unit", field.unit),
            ("period", field.period),
            ("label", field.label),
        ):
            _validate_manifest_text(value, f"{path}.{key}", required=False)

    if type(manifest.record_ids) is not tuple:
        raise ValueError("record_ids: must be a tuple")
    for index, record_id in enumerate(manifest.record_ids):
        if type(record_id) not in (str, int):
            raise ValueError(f"record_ids[{index}]: must be a string or integer")
        if type(record_id) is str and not record_id.strip():
            raise ValueError(f"record_ids[{index}]: must not be empty")
    expected_duplicates = _find_duplicates(manifest.record_ids)
    if type(manifest.duplicate_record_ids) is not tuple or (
        manifest.duplicate_record_ids != expected_duplicates
    ):
        raise ValueError(
            "duplicate_record_ids: does not match duplicates derived from record_ids"
        )

    if type(manifest.findings) is not tuple or not all(
        type(item) is str and item.strip() for item in manifest.findings
    ):
        raise ValueError("findings: must be a tuple of non-empty strings")
    required_findings = _derived_findings(
        manifest.fields, manifest.record_ids, manifest.duplicate_record_ids
    )
    for finding in required_findings:
        if finding not in manifest.findings:
            raise ValueError(f"findings: missing required validation finding {finding!r}")

    if type(manifest.transformations) is not tuple:
        raise ValueError("transformations: must be a tuple")
    for index, transformation in enumerate(manifest.transformations):
        path = f"transformations[{index}]"
        if type(transformation) is not DataTransformation:
            raise ValueError(f"{path}: must be a DataTransformation")
        _validate_manifest_text(transformation.name, f"{path}.name", required=True)
        _validate_manifest_text(
            transformation.documentation, f"{path}.documentation", required=True
        )
        if transformation.approved is not True:
            raise ValueError(f"{path}.approved: must be true")
        if type(transformation.parameters_json) is not str:
            raise ValueError(f"{path}.parameters: canonical JSON must be a string")
        parameters = transformation.parameters
        if _canonical_parameters(parameters) != transformation.parameters_json:
            raise ValueError(f"{path}.parameters: must use canonical JSON")


def has_data_binding_contract(product_id: str) -> bool:
    return type(product_id) is str and product_id in _PRODUCT_BINDING_CONTRACTS


def validate_engine_payload(payload: EnginePayload) -> None:
    if type(payload) is not EnginePayload:
        raise ValueError("payload: must be an exact EnginePayload")
    if type(payload.product_id) is not str:
        raise ValueError("product_id: must be an exact string")
    contract = _PRODUCT_BINDING_CONTRACTS.get(payload.product_id)
    if contract is None:
        raise ValueError(f"unsupported data-binding product: {payload.product_id}")
    if type(payload.engine) is not str or payload.engine != contract.engine:
        raise ValueError(
            f"engine: expected exact {contract.engine!r} for {payload.product_id}"
        )
    if type(payload.target_types) is not tuple or any(
        type(target) is not str for target in payload.target_types
    ):
        raise ValueError("target_types: must be an immutable tuple of exact strings")
    if payload.target_types != contract.target_types:
        raise ValueError(
            f"target_types: expected {contract.target_types!r} for {payload.product_id}"
        )
    if type(payload.render_mode) is not str or payload.render_mode != contract.render_mode:
        raise ValueError(
            f"render_mode: expected exact {contract.render_mode!r} for {payload.product_id}"
        )
    if type(payload.manual_redraw_allowed) is not bool or (
        payload.manual_redraw_allowed != contract.manual_redraw_allowed
    ):
        raise ValueError(
            f"manual_redraw_allowed: expected {contract.manual_redraw_allowed!r} "
            f"for {payload.product_id}"
        )
    validate_data_manifest(payload.manifest)
    if type(payload.labels) is not tuple or any(
        type(label) is not str for label in payload.labels
    ):
        raise ValueError("labels: must be an immutable tuple of exact strings")
    expected_labels = tuple(field.label for field in payload.manifest.fields)
    if payload.labels != expected_labels:
        raise ValueError(f"labels: expected exact manifest labels {expected_labels!r}")


def validate_data_binding(binding: DataBinding) -> None:
    if type(binding) is not DataBinding:
        raise ValueError("binding: must be an exact DataBinding")
    if type(binding.payload) is not EnginePayload:
        raise ValueError("payload: must be an exact EnginePayload")
    validate_engine_payload(binding.payload)
    if type(binding.field) is not DataField:
        raise ValueError("field: must be an exact DataField")
    if type(binding.product_id) is not str or binding.product_id != binding.payload.product_id:
        raise ValueError("product_id: must be an exact string matching payload product")
    if type(binding.engine) is not str or binding.engine != binding.payload.engine:
        raise ValueError("engine: must be an exact string matching payload engine")
    if type(binding.target_type) is not str:
        raise ValueError("target_type: must be an exact string")
    if type(binding.field_index) is not int:
        raise ValueError("field_index: must be an integer")
    if binding.field_index < 0 or binding.field_index >= len(binding.payload.manifest.fields):
        raise ValueError("field_index: outside manifest field range")
    expected_field = binding.payload.manifest.fields[binding.field_index]
    if binding.field is not expected_field:
        raise ValueError("field: must be the indexed field from payload manifest")
    expected_name, expected_target = binding.payload.binding_targets[binding.field_index]
    if binding.field.name != expected_name or binding.target_type != expected_target:
        raise ValueError("target_type: must match the indexed product binding target")


def build_engine_payload(manifest: DataManifest, product_id: str) -> EnginePayload:
    validate_data_manifest(manifest)
    if type(product_id) is not str:
        raise ValueError("product_id: must be an exact string")
    contract = _PRODUCT_BINDING_CONTRACTS.get(product_id)
    if contract is None:
        raise ValueError(f"unsupported data-binding product: {product_id}")
    return EnginePayload(
        product_id=product_id,
        engine=contract.engine,
        target_types=contract.target_types,
        render_mode=contract.render_mode,
        manual_redraw_allowed=contract.manual_redraw_allowed,
        manifest=manifest,
        labels=tuple(field.label for field in manifest.fields),
    )


def bind_data(manifest: DataManifest, product_id: str) -> tuple[DataBinding, ...]:
    payload = build_engine_payload(manifest, product_id)
    bindings = tuple(
        DataBinding(
            field=field,
            product_id=product_id,
            engine=payload.engine,
            target_type=_target_type_for_field(payload, field),
            payload=payload,
            field_index=index,
        )
        for index, field in enumerate(manifest.fields)
    )
    validate_data_bindings(bindings)
    return bindings


def validate_data_bindings(bindings: tuple[DataBinding, ...]) -> None:
    if type(bindings) is not tuple:
        raise ValueError("bindings: must be an immutable tuple")
    if not bindings:
        raise ValueError("bindings: missing all manifest bindings")
    first = bindings[0]
    if type(first) is not DataBinding:
        raise ValueError("bindings[0]: must be an exact DataBinding")
    validate_data_binding(first)
    expected_count = len(first.payload.manifest.fields)
    if len(bindings) < expected_count:
        raise ValueError(
            f"bindings: missing {expected_count - len(bindings)} manifest binding(s)"
        )
    if len(bindings) > expected_count:
        raise ValueError(
            f"bindings: extra {len(bindings) - expected_count} manifest binding(s)"
        )
    for index, binding in enumerate(bindings):
        if type(binding) is not DataBinding:
            raise ValueError(f"bindings[{index}]: must be an exact DataBinding")
        validate_data_binding(binding)
        if binding.payload is not first.payload:
            raise ValueError("bindings: every binding must share one payload object")
        if binding.field_index != index:
            raise ValueError("bindings: must cover manifest fields once in exact order")


def build_observed_contract(raw: dict[str, Any]) -> ObservedDataContract:
    if type(raw) is not dict:
        raise ValueError("observed contract: must be an object")
    return ObservedDataContract(
        source=raw.get("source"),
        source_form=raw.get("source_form"),
        provenance=raw.get("provenance"),
        fields=raw.get("fields"),
        transformations=raw.get("transformations"),
        findings=raw.get("findings"),
        record_ids=raw.get("record_ids"),
        duplicate_record_ids=raw.get("duplicate_record_ids"),
    )


def compare_bound_values(
    manifest: DataManifest,
    observed: ObservedDataContract | dict[str, Any],
) -> DataFidelityReport:
    validate_data_manifest(manifest)
    contract = (
        observed
        if type(observed) is ObservedDataContract
        else build_observed_contract(observed)
    )
    mismatches: list[str] = []
    for key, expected, actual in (
        ("source", manifest.source, contract.source),
        ("source_form", manifest.source_form, contract.source_form),
        ("provenance", manifest.provenance, contract.provenance),
    ):
        if type(expected) is not type(actual) or expected != actual:
            mismatches.append(f"{key}: expected {expected!r}, observed {actual!r}")

    _compare_fields(manifest.fields, contract.fields, mismatches)
    _compare_sequence("record_ids", manifest.record_ids, contract.record_ids, mismatches)
    _compare_sequence(
        "duplicate_record_ids",
        manifest.duplicate_record_ids,
        contract.duplicate_record_ids,
        mismatches,
    )
    _compare_sequence("findings", manifest.findings, contract.findings, mismatches)
    _compare_transformations(manifest.transformations, contract.transformations, mismatches)
    status = "FAIL" if mismatches else ("PARTIAL" if manifest.findings else "PASS")
    return DataFidelityReport(status, tuple(mismatches), manifest.findings)


def _required_text(raw: dict[str, Any], key: str, prefix: str = "") -> str:
    path = f"{prefix}.{key}" if prefix else key
    value = raw.get(key)
    if type(value) is not str or not value.strip():
        raise ValueError(f"{path}: must be a non-empty string")
    return value


def _optional_text(raw: dict[str, Any], key: str, prefix: str) -> str:
    value = raw.get(key, "")
    if type(value) is not str:
        raise ValueError(f"{prefix}.{key}: must be a string")
    return value


def _build_transformations(raw: Any) -> tuple[DataTransformation, ...]:
    if type(raw) is not list:
        raise ValueError("transformations: must be a list")
    transformations: list[DataTransformation] = []
    for index, item in enumerate(raw):
        path = f"transformations[{index}]"
        if type(item) is not dict:
            raise ValueError(f"{path}: transformation must be an object")
        unknown_keys = set(item) - {"name", "documentation", "approved", "parameters"}
        if unknown_keys:
            raise ValueError(
                f"{path}: unknown transformation keys {', '.join(sorted(unknown_keys))}"
            )
        name = _required_text(item, "name", path)
        documentation = _required_text(item, "documentation", path)
        approved = item.get("approved")
        if approved is not True:
            raise ValueError(f"{path}.approved: transformation must be explicitly approved")
        parameters_json = _canonical_parameters(item.get("parameters", {}), path)
        transformations.append(
            DataTransformation(name, documentation, approved, parameters_json)
        )
    return tuple(transformations)


def _canonical_parameters(value: Any, path: str = "transformation") -> str:
    if type(value) is not dict or not all(
        type(key) is str and key for key in value
    ):
        raise ValueError(f"{path}.parameters: must be an object with non-empty string keys")
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}.parameters: must contain JSON-compatible values") from exc


def _validate_values(value_type: str, values: list[Any], path: str) -> None:
    for index, value in enumerate(values):
        if value is None:
            continue
        if value_type == "number" and type(value) not in (int, float):
            raise ValueError(f"{path}.values[{index}]: must be an integer, float, or null")
        if value_type == "string" and type(value) is not str:
            raise ValueError(f"{path}.values[{index}]: must be a string or null")


def _find_duplicates(values: tuple[Any, ...]) -> tuple[Any, ...]:
    unique: list[Any] = []
    duplicates: list[Any] = []
    for value in values:
        if any(type(value) is type(seen) and value == seen for seen in unique):
            if not any(type(value) is type(seen) and value == seen for seen in duplicates):
                duplicates.append(value)
        else:
            unique.append(value)
    return tuple(duplicates)


def _derived_findings(
    fields: tuple[DataField, ...],
    record_ids: tuple[Any, ...],
    duplicate_record_ids: tuple[Any, ...],
) -> tuple[str, ...]:
    findings: list[str] = []
    for index, field in enumerate(fields):
        if field.missing_positions:
            findings.append(
                f"fields[{index}].values: missing values at positions "
                + ", ".join(str(position) for position in field.missing_positions)
            )
    expected_length = len(fields[0].values)
    for index, field in enumerate(fields[1:], start=1):
        if len(field.values) != expected_length:
            findings.append(
                f"fields[{index}].values: length {len(field.values)} differs from "
                f"fields[0] length {expected_length}"
            )
    if duplicate_record_ids:
        findings.append(
            "record_ids: duplicate record IDs "
            + ", ".join(repr(record_id) for record_id in duplicate_record_ids)
        )
    if record_ids and len(record_ids) != expected_length:
        findings.append(
            f"record_ids: length {len(record_ids)} differs from fields[0] length "
            f"{expected_length}"
        )
    return tuple(findings)


def _validate_manifest_text(value: Any, path: str, *, required: bool) -> None:
    if type(value) is not str or (required and not value.strip()):
        qualifier = "non-empty " if required else ""
        raise ValueError(f"{path}: must be a {qualifier}string")


def _target_type_for_field(payload: EnginePayload, field: DataField) -> str:
    return _target_type_for_product(payload.product_id, field)


def _target_type_for_product(product_id: str, field: DataField) -> str:
    if product_id == "native-data-deck":
        return "native-chart" if field.value_type == "number" else "native-table"
    contract = _PRODUCT_BINDING_CONTRACTS[product_id]
    return contract.target_types[0]


def _compare_fields(
    expected_fields: tuple[DataField, ...], actual_fields: Any, mismatches: list[str]
) -> None:
    if type(actual_fields) is not list:
        mismatches.append(f"fields: expected a list, observed {actual_fields!r}")
        return
    if len(expected_fields) != len(actual_fields):
        mismatches.append(
            f"fields: expected {len(expected_fields)} field(s), observed {len(actual_fields)}"
        )
    for index, expected in enumerate(expected_fields):
        actual = actual_fields[index] if index < len(actual_fields) else None
        if type(actual) is not dict:
            mismatches.append(f"fields[{index}]: expected an object, observed {actual!r}")
            continue
        for key, expected_value in (
            ("name", expected.name),
            ("type", expected.value_type),
            ("unit", expected.unit),
            ("period", expected.period),
            ("label", expected.label),
        ):
            actual_value = actual.get(key)
            if type(expected_value) is not type(actual_value) or expected_value != actual_value:
                mismatches.append(
                    f"fields[{index}].{key}: expected {expected_value!r}, observed "
                    f"{actual_value!r}"
                )
        _compare_sequence(
            f"fields[{index}].concrete_types",
            expected.concrete_types,
            actual.get("concrete_types"),
            mismatches,
        )
        _compare_sequence(
            f"fields[{index}].values", expected.values, actual.get("values"), mismatches
        )
        _compare_sequence(
            f"fields[{index}].missing_positions",
            expected.missing_positions,
            actual.get("missing_positions"),
            mismatches,
        )


def _compare_sequence(
    path: str, expected: tuple[Any, ...], actual: Any, mismatches: list[str]
) -> None:
    if type(actual) is not list or len(expected) != len(actual) or any(
        not _exact_value_equal(want, got)
        for want, got in zip(expected, actual if type(actual) is list else [])
    ):
        mismatches.append(f"{path}: expected {list(expected)!r}, observed {actual!r}")


def _compare_transformations(
    expected: tuple[DataTransformation, ...], actual: Any, mismatches: list[str]
) -> None:
    expected_raw = [
        {
            "name": item.name,
            "documentation": item.documentation,
            "approved": item.approved,
            "parameters": item.parameters,
        }
        for item in expected
    ]
    if type(actual) is not list or len(expected_raw) != len(actual):
        mismatches.append(
            f"transformations: expected {expected_raw!r}, observed {actual!r}"
        )
        return
    for index, (want, got) in enumerate(zip(expected_raw, actual)):
        if not _exact_value_equal(want, got):
            mismatches.append(
                f"transformations[{index}]: expected {want!r}, observed {got!r}"
            )


def _exact_value_equal(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, float):
        if expected == 0.0 and actual == 0.0:
            return math.copysign(1.0, expected) == math.copysign(1.0, actual)
        return expected == actual
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            _exact_value_equal(want, got) for want, got in zip(expected, actual)
        )
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(
            _exact_value_equal(expected[key], actual[key]) for key in expected
        )
    return expected == actual
