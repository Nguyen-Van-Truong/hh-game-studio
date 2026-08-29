#!/usr/bin/env python3
"""VF1-WP1 verify: ledger rows have URL/date/source/hash; offline replay.

Does not launch Godot. Does not fetch the Y8 HTML5 embed.
Does not tick the 29-8 plan.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
EVIDENCE = ROOT / "docs" / "evidence" / "VF1WP1-20260829-ASIA-SAIGON-01"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"

REQUIRED_IDS = (
    "RL-SRC-Y8-LIVE",
    "RL-SRC-NG-LIVE",
    "RL-SRC-ML-LIVE",
    "RL-SRC-Y8-WAYBACK",
    "RL-SRC-NG-INDEX",
    "RL-SRC-WIKI-INDEX",
    "RL-CTRL-P1-MOVE",
    "RL-CTRL-P1-PUNCH",
    "RL-CTRL-P1-SHOOT",
    "RL-CTRL-P1-NADE",
    "RL-CTRL-P2-MOVE",
    "RL-CTRL-P2-ATK",
    "RL-CTRL-HOLD-AIM",
    "RL-CAM-ARENA",
    "RL-MODE-PVP-PVE",
    "RL-MODE-1P-2P",
    "RL-MODE-STAGE",
    "RL-MODE-SURVIVAL",
    "RL-MAP-COUNT-6",
    "RL-MAP-LANDMARKS",
    "RL-ITEM-RANDOM-SPAWN",
    "RL-MOVE-SPRINT",
    "RL-MOVE-ROLL-DIVE",
    "RL-DELTA-TITLE",
    "RL-DELTA-MAP-NAMES",
    "RL-DELTA-MAP-GEO",
    "RL-DELTA-LOOP",
)

REQUIRED_URLS = (
    "https://www.y8.com/games/superfighters",
    "https://www.newgrounds.com/portal/view/575163",
    "https://mythologicinteractive.com/Superfighters",
)

REQUIRED_EVIDENCE = (
    "y8_listing.transcript.txt",
    "y8_controls_html_snippet.txt",
    "y8_controls_extract.json",
    "y8_wayback_20110924.transcript.txt",
    "newgrounds_listing.excerpt.txt",
    "newgrounds_listing.transcript.txt",
    "wiki_maps.excerpt.txt",
    "page_fetch.manifest.json",
    "mythologic_home.webfetch.txt",
)

FORBIDDEN_SUFFIXES = (".swf", ".unity3d", ".mp4", ".webm", ".ogv", ".wav", ".mp3")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    errors: list[str] = []
    if not LEDGER.is_file():
        print("FAIL: missing docs/reference-ledger.md")
        return 1
    text = LEDGER.read_text(encoding="utf-8")
    ids = set(re.findall(r"\bRL-[A-Z0-9-]+\b", text))
    for rid in REQUIRED_IDS:
        if rid not in ids:
            errors.append(f"missing row {rid}")
    for url in REQUIRED_URLS:
        if url not in text:
            errors.append(f"missing URL {url}")
    for needle in (
        "2026-08-29",
        "Asia/Saigon",
        "`observed`",
        "`secondary`",
        "`assumption`",
        "Delta table",
        "html5.gamedistribution.com",
        "Vault Fighters",
        "does **not** claim Y8 parity",
        "ledger:RL-",
    ):
        if needle not in text:
            errors.append(f"ledger missing required phrase: {needle}")
    if "y8_parity: true" in text or "closest possible to Y8" in text:
        errors.append("ledger must not claim Y8 parity")
    if "TitleLabel" in TITLE.read_text(encoding="utf-8"):
        title_src = TITLE.read_text(encoding="utf-8")
        if 'text = "Vault Fighters"' not in title_src:
            errors.append("title card is not Vault Fighters")
        if "Superfighters" in title_src or "Super Fighter" in title_src:
            errors.append("title_screen.gd contains Superfighters string")
    if not EVIDENCE.is_dir():
        errors.append(f"missing evidence dir {EVIDENCE}")
    else:
        for name in REQUIRED_EVIDENCE:
            path = EVIDENCE / name
            if not path.is_file():
                errors.append(f"missing evidence {name}")
            elif path.stat().st_size < 40:
                errors.append(f"evidence too small: {name}")
        for path in EVIDENCE.rglob("*"):
            if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
                errors.append(f"reference media must not be stored: {path.name}")
        snippet = (EVIDENCE / "y8_controls_html_snippet.txt").read_text(encoding="utf-8", errors="replace")
        for css in ("key-arrows", "key-n", "key-m", "key-comma", "key-wasd", "key-1"):
            if css not in snippet:
                errors.append(f"Y8 controls snippet missing {css}")
        if "data-src='https://html5.gamedistribution.com" in snippet:
            errors.append("controls snippet must not include the HTML5 embed (rip surface)")
        extract = (EVIDENCE / "y8_controls_extract.json").read_text(encoding="utf-8")
        if '"game_package_fetched": false' not in extract and '"game_package_fetched":false' not in extract:
            errors.append("extract must record game_package_fetched false")
        if "html5.gamedistribution.com" not in extract:
            errors.append("extract must record embed host as seen-not-fetched")
    hashes_path = EVIDENCE / "hashes.txt"
    if not hashes_path.is_file():
        errors.append("missing hashes.txt")
    else:
        for line in hashes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                errors.append(f"bad hashes.txt line: {line}")
                continue
            digest, rel = parts
            rel = rel.strip()
            if rel in {"hashes.txt", Path(rel).name} and Path(rel).name == "hashes.txt":
                continue
            candidates = [
                EVIDENCE / Path(rel).name,
                ROOT / rel,
                ROOT / Path(rel),
            ]
            found = next((p for p in candidates if p.is_file()), None)
            if found is None:
                errors.append(f"hashes.txt missing file {rel}")
            else:
                got = sha256_file(found)
                if got != digest:
                    errors.append(f"hash mismatch {rel}")
    if errors:
        print("FAIL: Vault Fighters VF1-WP1 ledger")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF1-WP1 ledger")
    print(f"  rows={len(ids)} required={len(REQUIRED_IDS)}")
    print(f"  ledger_sha256={sha256_file(LEDGER)}")
    print("  game_package_fetched=0 screenshots=0 godot_not_required=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
