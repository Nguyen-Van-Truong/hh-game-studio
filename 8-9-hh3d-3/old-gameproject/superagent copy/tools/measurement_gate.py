"""Numeric portion of the SA5 ledger. Empty targets are work, never proof.

Raw sample values live beside the ledger in core-measurements.json. A group
can contain several quantities; a mean for only one cannot stand in for all.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean

TARGETS = {
    "A01": {"walk_speed": "H/s", "acceleration_time": "s", "braking_distance": "H"},
    "A02": {"sprint_speed": "H/s", "stamina_drain_time": "s", "idle_refill_time": "s", "walking_refill_time": "s"},
    "A03": {"jump_height": "H", "jump_airtime": "s", "walking_jump_distance": "H", "sprint_jump_distance": "H"},
    "A04": {"terminal_fall_speed": "H/s", "fall_damage_height": "H", "fatal_fall_height": "H"},
    "A05": {"climb_up_speed": "H/s", "climb_down_speed": "H/s"},
    "A06": {"roll_distance": "H", "roll_duration": "s", "dive_distance": "H", "dive_duration": "s"},
    "A07": {"punch_interval": "s", "punches_to_defeat": "count"},
    "A08": {"jump_kicks_to_defeat": "count", "punch_knockback": "H", "kick_knockback": "H"},
    "A09": {"pistol_interval": "s", "pistol_shots_to_defeat": "count", "pistol_ammo": "count", "pistol_bullet_speed": "H/s"},
    "A10": {"gun_1_interval": "s", "gun_1_shots_to_defeat": "count", "gun_1_ammo": "count", "gun_2_interval": "s", "gun_2_shots_to_defeat": "count", "gun_2_ammo": "count"},
    "A11": {"grenade_fuse": "s", "standing_throw_distance": "H", "running_throw_distance": "H", "blast_radius": "H", "center_damage": "HP", "starting_grenades": "count"},
    "A12": {"knockdown_duration": "s", "recovery_immunity": "s"},
    "A13": {"vs_round_delay": "s", "stage_round_delay": "s", "survival_end_delay": "s"},
    "A14": {"power_5_duration": "s", "power_10_duration": "s", "owner_time_ratio": "ratio", "other_time_ratio": "ratio"},
    "A15": {"pill_healing": "HP_ratio", "medkit_healing": "HP_ratio"},
    "A16": {"item_spawn_interval": "s"},
    "A17": {"viewport_aspect": "ratio", "character_view_height": "ratio"},
}

# Broad existing rows can refer to more than one numeric group. Their behavior
# clauses still need scenario/owner review; assigning A does not waive those.
ROW_TARGETS = {
    "R02-01": ["A01"], "R02-02": ["A03"], "R02-04": ["A05"],
    "R02-06": ["A02", "A06"], "R03-01": ["A07"], "R03-02": ["A08"],
    "R03-03": ["A08", "A12"], "R04-03": ["A09", "A10"],
    "R04-04": ["A09", "A10"], "R05-01": ["A11"], "R05-02": ["A11"],
    "R06-01": ["A07", "A08", "A09", "A10", "A15"],
    "R06-03": ["A04", "A13"], "R06-04": ["A12"], "R07-03": ["A09", "A10"],
    "R08-01": ["A15"], "R08-03": ["A14"], "R12-05": ["A13"],
    "R14-01": ["A17"], "R14-02": ["A17"], "R14-03": ["A14"],
}


def template() -> dict:
    return {"schema": "sa5.measurements.v1", "groups": {
        group: {metric: {"unit": unit, "reference": None, "product": None}
                for metric, unit in metrics.items()}
        for group, metrics in TARGETS.items()}}


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _samples(record, label: str) -> tuple[list[float], list[str]]:
    if not isinstance(record, dict):
        return [], [f"{label}: missing measurements"]
    values = record.get("samples")
    if not isinstance(values, list) or len(values) < 3 or not all(_number(v) for v in values):
        return [], [f"{label}: requires at least 3 finite nonnegative samples"]
    if not isinstance(record.get("source"), str) or not record["source"].strip():
        return [], [f"{label}: missing observation/source record"]
    if not _number(record.get("uncertainty")):
        return [], [f"{label}: missing finite measurement uncertainty"]
    return values, []


def errors(path: Path, groups: list[str], *, compare: bool = False) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"measurement file unavailable: {path.name} ({type(exc).__name__})"]
    if not isinstance(data, dict) or data.get("schema") != "sa5.measurements.v1" or not isinstance(data.get("groups"), dict):
        return ["unsupported measurement schema"]
    result: list[str] = []
    for group in sorted(set(groups)):
        if group not in TARGETS:
            result.append(f"unknown measurement group {group}")
            continue
        block = data["groups"].get(group, {})
        if not isinstance(block, dict):
            result.append(f"{group}: expected metric object")
            continue
        for metric, unit in TARGETS[group].items():
            label = f"{group}.{metric}"
            entry = block.get(metric)
            if not isinstance(entry, dict) or entry.get("unit") != unit:
                result.append(f"{label}: missing target or incorrect unit {unit}")
                continue
            # Conditional absence must be evidenced, not encoded as a zero.
            if entry.get("not_applicable"):
                proof = entry.get("not_applicable")
                if not isinstance(proof, dict) or not proof.get("source") or not proof.get("reason"):
                    result.append(f"{label}: conditional absence requires source and reason")
                continue
            reference, missing = _samples(entry.get("reference"), f"{label}.reference")
            result.extend(missing)
            if missing:
                continue
            average = mean(reference)
            tolerance = 0.0 if unit == "count" else max(average * 0.05, 1.0 / 60 if unit == "s" else 0.0)
            uncertainty = entry["reference"]["uncertainty"]
            if (unit == "count" and (uncertainty != 0 or any(v != int(v) for v in reference))) or (unit != "count" and uncertainty >= tolerance):
                result.append(f"{label}: reference uncertainty must fit tolerance")
            if compare:
                product, missing = _samples(entry.get("product"), f"{label}.product")
                result.extend(missing)
                if missing:
                    continue
                product_error = entry["product"]["uncertainty"]
                if unit == "count":
                    matched = product_error == 0 and len(set(reference + product)) == 1
                else:
                    matched = product_error < tolerance and abs(mean(product) - average) + uncertainty + product_error <= tolerance
                if not matched:
                    result.append(f"{label}: product does not match within measurement tolerance")
    return result
