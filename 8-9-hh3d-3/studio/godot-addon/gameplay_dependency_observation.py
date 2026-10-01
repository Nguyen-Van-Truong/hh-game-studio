"""Parse a Godot dependency marker and bind it to the fail-closed contract.

This is a candidate observation helper for ``AUTHORITY=0``.  It does not
discover files, prove a complete runtime dependency closure, or grant public
authority.  The Godot process must emit exactly one line beginning with
``HH_PROBE_DEPENDENCY ``; the JSON payload is then validated against the
caller-supplied immutable file bytes by
``gameplay_dependency_evidence.validate_dependency_observation``.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from collections.abc import Mapping


MARKER = "HH_PROBE_DEPENDENCY "
_AUTHORITY_KEYS = frozenset({
    "authority",
    "dependency_closure_verified",
    "native_observation_verified",
    "public_ack",
})


class DependencyObservationMarkerError(ValueError):
    """The process output did not contain one safe dependency observation."""


def _load_validator():
    """Load the sibling validator in both script and test-import contexts."""
    try:
        from gameplay_dependency_evidence import (  # type: ignore
            DependencyEvidenceError,
            validate_dependency_observation,
        )
        return DependencyEvidenceError, validate_dependency_observation
    except ModuleNotFoundError:
        path = Path(__file__).with_name("gameplay_dependency_evidence.py")
        spec = importlib.util.spec_from_file_location(
            "gameplay_dependency_evidence_for_observation", path)
        if spec is None or spec.loader is None:
            raise ImportError("DEPENDENCY_VALIDATOR_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return (module.DependencyEvidenceError,
                module.validate_dependency_observation)


def _text(stdout: str | bytes) -> str:
    if type(stdout) is str:
        return stdout
    if type(stdout) is bytes:
        try:
            return stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DependencyObservationMarkerError(
                "DEPENDENCY_MARKER_ENCODING") from exc
    raise DependencyObservationMarkerError("DEPENDENCY_MARKER_OUTPUT_TYPE")


def _reject_authority_keys(value: object) -> None:
    """Reject authority-looking fields before the validator sees the data."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if type(key) is str and key.casefold() in _AUTHORITY_KEYS:
                raise DependencyObservationMarkerError(
                    "DEPENDENCY_MARKER_AUTHORITY_CLAIM")
            _reject_authority_keys(child)
    elif type(value) is list:
        for child in value:
            _reject_authority_keys(child)


def parse_dependency_observation(stdout: str | bytes, files: Mapping,
                                 *, reopened_stdout: str | bytes | None = None,
                                 reopened_files: Mapping | None = None) -> dict:
    """Parse one marker and validate its graph against ``files``.

    ``reopened_stdout`` and ``reopened_files`` may be supplied together to
    exercise the validator's close/reopen equality check.  A marker is a
    transport envelope only; this function always returns the validator's
    authority-zero report and never turns native output into acceptance.
    """
    _, validate = _load_validator()

    def parse_one(raw: str | bytes) -> dict:
        lines = [line for line in _text(raw).splitlines()
                 if line.startswith(MARKER)]
        if not lines:
            raise DependencyObservationMarkerError(
                "DEPENDENCY_MARKER_MISSING")
        if len(lines) != 1:
            raise DependencyObservationMarkerError(
                "DEPENDENCY_MARKER_DUPLICATE")
        payload = lines[0][len(MARKER):]
        try:
            value = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DependencyObservationMarkerError(
                "DEPENDENCY_MARKER_JSON") from exc
        if not isinstance(value, Mapping):
            raise DependencyObservationMarkerError(
                "DEPENDENCY_MARKER_OBJECT")
        _reject_authority_keys(value)
        return dict(value)

    observation = parse_one(stdout)
    if (reopened_stdout is None) != (reopened_files is None):
        raise DependencyObservationMarkerError(
            "DEPENDENCY_MARKER_REOPEN_BINDING")
    if reopened_stdout is None:
        report = validate(files, observation)
        reopened = None
    else:
        reopened = parse_one(reopened_stdout)
        report = validate(files, observation,
                          reopened_files=reopened_files,
                          reopened_observation=reopened)
    result = dict(report)
    result.update({
        "marker": MARKER.rstrip(),
        "marker_count": 1,
        "observation": observation,
    })
    if reopened is not None:
        result["reopened_observation"] = reopened
    return result


__all__ = ["MARKER", "DependencyObservationMarkerError",
           "parse_dependency_observation"]
