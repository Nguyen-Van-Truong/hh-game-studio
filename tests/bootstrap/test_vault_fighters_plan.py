#!/usr/bin/env python3
"""Validate scoped Vault Fighters product-plan routing (VF0-WP3).

Does not tick VF work packages. Does not change the frozen 20-8 platform
closeout. Stdlib only. Must keep PASSing as VF checkboxes tick in order.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS = REPO_ROOT / "AGENTS.md"
DECISIONS = REPO_ROOT / "docs" / "DECISIONS.md"
PRODUCT_PLAN = REPO_ROOT / "zdocs" / "29-8-vault-fighters-y8-parity-plan.txt"
PARENT_PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"

PRODUCT_MARKER = "PRODUCT_PLAN_AUTHORITY=1"
GLOBAL_MARKER = "AUTHORITATIVE_PLAN=1"
CURRENT_PARENT = "CURRENT_VALID_WP=R9-WP4"
PRODUCT_PLAN_REL = "zdocs/29-8-vault-fighters-y8-parity-plan.txt"
PRODUCT_SCOPE = "PLAN_SCOPE=godot/dogfood/superfighters"
PARENT_PLAN_REL = "zdocs/20-8-godot-agent-autopilot-plan.txt"
DECISION_ID = "GODOT-VF-PLAN-2026-08-29"
OWNER_DECISION_ID = "GODOT-VF-Y8-2026-08-28"
WP_HEADING = re.compile(r"^(VF\d+-WP\d+)\s+—.+\[([ xX])\]\s*$")
CURRENT_WP_LINE = re.compile(r"^CURRENT_VALID_WP=(\S+)\s*$")
OLD_SOLE_PLAN = "Kế hoạch quyền lực duy nhất"
OLD_FIRST_PRODUCT_WP = "WP sản phẩm đầu tiên của agent mới là R0-WP3"
FORBIDDEN_SUPERFIGHTER_START_LINES = (
    re.compile(r"(?i)^(do not|don't|does not) start (a )?superfighter"),
    re.compile(r"(?i)^superfighter is not started"),
    re.compile(r"^đừng start Superfighter"),
    re.compile(r"(?i)^không (được )?start superfighter"),
)
EXPECTED_GROUPS = {
    "VF0": 3,
    "VF1": 4,
    "VF2": 5,
    "VF3": 6,
    "VF4": 5,
    "VF5": 6,
    "VF6": 5,
    "VF7": 4,
    "VF8": 4,
    "VF9": 5,
    "VF10": 3,
}


def read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path.relative_to(REPO_ROOT)}: {exc}")
        return ""


def exact_lines(text: str, value: str) -> int:
    return sum(line.strip() == value for line in text.splitlines())


def parse_wp_headings(product: str) -> list[tuple[str, str]]:
    headings: list[tuple[str, str]] = []
    for line in product.splitlines():
        match = WP_HEADING.match(line)
        if match:
            headings.append((match.group(1), match.group(2)))
    return headings


def header_current_wp(product: str) -> str | None:
    for line in product.splitlines():
        match = CURRENT_WP_LINE.match(line.strip())
        if match:
            return match.group(1)
    return None


def first_unticked(headings: list[tuple[str, str]]) -> str | None:
    for wp_id, tick in headings:
        if tick.lower() != "x":
            return wp_id
    return None


def no_skip_errors(headings: list[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    seen_open = False
    for wp_id, tick in headings:
        ticked = tick.lower() == "x"
        if ticked and seen_open:
            errors.append(
                f"skip detected: {wp_id} is ticked after an earlier unticked VF WP"
            )
        if not ticked:
            seen_open = True
    return errors


def choose_next_product_wp(agents: str, product: str) -> tuple[str | None, list[str]]:
    """Next WP is the first unticked VF heading; parent R9/Snake are never next."""
    errors: list[str] = []
    if PRODUCT_PLAN_REL not in agents:
        errors.append("agent routing did not read the 29-8 product plan")
    headings = parse_wp_headings(product)
    nxt = first_unticked(headings)
    current = header_current_wp(product)
    if nxt is None:
        errors.append("no unticked VF WP remains")
        return None, errors
    if current is None:
        errors.append("product plan missing CURRENT_VALID_WP")
    elif not re.fullmatch(r"VF\d+-WP\d+", current):
        errors.append(
            f"CURRENT_VALID_WP={current} is not a VF work package "
            "(parent R9/Snake must not be product next)"
        )
    elif current != nxt:
        errors.append(
            f"CURRENT_VALID_WP={current} does not match first unticked {nxt}"
        )
    if nxt == "R9-WP4" or nxt.startswith("R9-"):
        errors.append(f"product next WP must not be parent closeout {nxt}")
    if "snake" in nxt.lower():
        errors.append("product next WP must not be Snake")
    if not re.fullmatch(r"VF\d+-WP\d+", nxt):
        errors.append(f"product next WP must be a VF work package, got {nxt}")
    return nxt, errors


def check_agents_product_route(agents: str, errors: list[str]) -> None:
    if PRODUCT_PLAN_REL not in agents:
        errors.append("AGENTS.md does not route product work to the 29-8 plan")
    if "Vault Fighters" not in agents:
        errors.append("AGENTS.md must name the product Vault Fighters")
    if "godot/dogfood/superfighters" not in agents:
        errors.append("AGENTS.md must name the product folder")
    if "WP đầu tiên chưa tick" not in agents:
        errors.append("AGENTS.md must send agents to the first unticked 29-8 WP")
    if "R9-WP4" not in agents:
        errors.append("AGENTS.md must freeze parent closeout at R9-WP4")
    if "Không tự mở hoặc tick" not in agents:
        errors.append("AGENTS.md must forbid opening/ticking parent R9-WP4")
    if "godot/plugin-project/snake/" not in agents:
        errors.append("AGENTS.md must keep Snake out of product scope")
    if OLD_SOLE_PLAN in agents:
        errors.append("AGENTS.md still names a sole 20-8 execution plan")
    if OLD_FIRST_PRODUCT_WP in agents:
        errors.append("AGENTS.md still sends new agents to R0-WP3")
    if PARENT_PLAN_REL in agents and PRODUCT_PLAN_REL not in agents:
        errors.append("AGENTS.md still routes only to the 20-8 parent plan")
    for line in agents.splitlines():
        stripped = line.strip()
        for pattern in FORBIDDEN_SUPERFIGHTER_START_LINES:
            if pattern.search(stripped):
                errors.append(
                    "AGENTS.md still forbids starting the Superfighter product path: "
                    f"{stripped}"
                )


def check_decisions(decisions: str, errors: list[str]) -> None:
    for required in (DECISION_ID, OWNER_DECISION_ID, PRODUCT_PLAN_REL, "59/60"):
        if required not in decisions:
            errors.append(f"DECISIONS.md missing {required}")
    vf_plan_idx = decisions.find(DECISION_ID)
    if vf_plan_idx < 0:
        return
    vf_block = decisions[vf_plan_idx:]
    next_heading = re.search(r"\n## ", vf_block)
    if next_heading:
        vf_block = vf_block[: next_heading.start()]
    for required in (
        "reason",
        "impact",
        "migration",
        "godot/dogfood/superfighters",
        PRODUCT_PLAN_REL,
        "R9-WP4",
        "59/60",
    ):
        if required not in vf_block:
            errors.append(f"VF-PLAN decision missing {required}")


def check_parent_freeze(parent: str, errors: list[str]) -> None:
    if exact_lines(parent, GLOBAL_MARKER) != 1:
        errors.append("parent 20-8 plan must retain the global authority marker")
    if exact_lines(parent, CURRENT_PARENT) != 1:
        errors.append("parent 20-8 closeout must remain at R9-WP4")
    if "Tiến độ tổng: [ ] 59/60 WP." not in parent:
        errors.append("parent 20-8 progress must remain 59/60")
    if re.search(r"^R9-WP4\b.*\[x\]", parent, re.MULTILINE | re.IGNORECASE):
        errors.append("parent R9-WP4 must remain unticked")
    if re.search(r"G6 RELEASE\s+\[x\]", parent):
        errors.append("parent G6 must remain unticked")
    if re.search(r"GX FORK\s+\[x\]", parent):
        errors.append("parent GX must remain unticked")
    if exact_lines(parent, PRODUCT_MARKER) != 0:
        errors.append("parent 20-8 must not own PRODUCT_PLAN_AUTHORITY")


def self_test_no_skip_and_routing() -> list[str]:
    """In-memory cases: skip, CURRENT mismatch, parent/Snake must not win."""
    errors: list[str] = []
    prefix_ok = [("VF0-WP1", "x"), ("VF0-WP2", "x"), ("VF0-WP3", " ")]
    if no_skip_errors(prefix_ok):
        errors.append("self-test: valid prefix was treated as skip")
    skipped = [("VF0-WP1", "x"), ("VF0-WP2", " "), ("VF0-WP3", "x")]
    if not no_skip_errors(skipped):
        errors.append("self-test: ticked WP after a gap was not a skip")

    agents = (
        "# route\n"
        f"Follow `{PRODUCT_PLAN_REL}`.\n"
        "WP đầu tiên chưa tick.\n"
        "Không tự mở hoặc tick R9-WP4.\n"
        "Vault Fighters in godot/dogfood/superfighters.\n"
        "Do not touch godot/plugin-project/snake/.\n"
    )
    product = (
        f"{PRODUCT_SCOPE}\n"
        f"{PRODUCT_MARKER}\n"
        "CURRENT_VALID_WP=VF0-WP3\n"
        "VF0-WP1 — freeze [x]\n"
        "VF0-WP2 — hygiene [x]\n"
        "VF0-WP3 — routing [ ]\n"
        "VF1-WP1 — ledger [ ]\n"
    )
    nxt, choose_errors = choose_next_product_wp(agents, product)
    if choose_errors:
        errors.extend(f"self-test routing: {item}" for item in choose_errors)
    if nxt != "VF0-WP3":
        errors.append(f"self-test: expected next VF0-WP3, got {nxt}")
    if nxt in {"R9-WP4", "snake"}:
        errors.append("self-test: next WP selected Snake or R9")

    parent_as_product = product.replace(
        "CURRENT_VALID_WP=VF0-WP3", "CURRENT_VALID_WP=R9-WP4"
    )
    _nxt, parent_errors = choose_next_product_wp(agents, parent_as_product)
    if not parent_errors:
        errors.append("self-test: CURRENT_VALID_WP=R9-WP4 was accepted as product next")
    return errors


def main() -> int:
    errors: list[str] = []
    agents = read(AGENTS, errors)
    decisions = read(DECISIONS, errors)
    product = read(PRODUCT_PLAN, errors)
    parent = read(PARENT_PLAN, errors)

    errors.extend(self_test_no_skip_and_routing())

    if exact_lines(product, PRODUCT_MARKER) != 1:
        errors.append(f"product plan must contain exactly one {PRODUCT_MARKER}")
    if exact_lines(product, PRODUCT_SCOPE) != 1:
        errors.append(f"product plan must contain exactly one {PRODUCT_SCOPE}")
    if exact_lines(product, GLOBAL_MARKER) != 0:
        errors.append("scoped product plan must not own the global authority marker")
    if PARENT_PLAN_REL not in product:
        errors.append("product plan must name the parent 20-8 plan")

    headings = parse_wp_headings(product)
    ids = [wp_id for wp_id, _tick in headings]
    duplicates = sorted(wp_id for wp_id, count in Counter(ids).items() if count > 1)
    if len(ids) != 50:
        errors.append(f"expected 50 VF WP headings, found {len(ids)}")
    if duplicates:
        errors.append(f"duplicate VF WP ids: {duplicates}")
    errors.extend(no_skip_errors(headings))

    actual_groups = Counter(wp_id.split("-", 1)[0] for wp_id in ids)
    if dict(actual_groups) != EXPECTED_GROUPS:
        errors.append(
            f"VF group counts drifted: {dict(actual_groups)} != {EXPECTED_GROUPS}"
        )

    nxt, choose_errors = choose_next_product_wp(agents, product)
    errors.extend(choose_errors)
    ticked = [wp_id for wp_id, tick in headings if tick.lower() == "x"]

    check_agents_product_route(agents, errors)
    check_decisions(decisions, errors)
    check_parent_freeze(parent, errors)

    if errors:
        print("FAIL: Vault Fighters scoped product plan", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        "PASS: Vault Fighters product routing; "
        f"50 unique VF WPs; no-skip; next={nxt}; "
        f"ticked={','.join(ticked) if ticked else '(none)'}; "
        "parent 20-8 remains authoritative and frozen at 59/60 R9-WP4"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
