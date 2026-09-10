"""Offline GT-01 contract checks; no network or Godot spawn."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "toolchain.lock.json"
FIXTURE = ROOT / "fixtures/sample-game"
lock = json.loads(LOCK.read_text(encoding="utf-8"))
assert lock["schema"] == "HH-STUDIO-TOOLCHAIN-LOCK-2"
assert lock["status"] == "CANDIDATE"
godot = lock["godot"]
assert godot["version"] == "4.7.2-stable"
assert godot["source_commit"] == "ed1daf0bf001b61586d9930840f2f1394092c079"
assert len(godot["console_sha256"]) == len(godot["gui_sha256"]) == 64
def portable(value):
    if isinstance(value, dict):
        for item in value.values(): portable(item)
    elif isinstance(value, list):
        for item in value: portable(item)
    elif isinstance(value, str):
        assert not re.match(r"^[A-Za-z]:|^[/\\]", value), "absolute host path in lock"
portable(lock)
assert lock["export_templates"]["version"] == godot["version"]
assert lock["export_templates"]["state"] in {"PINNED_NOT_DOWNLOADED", "ARCHIVE_VERIFIED_NOT_INSTALLED"}
assert lock["android"]["state"] == "GAP_UNTIL_GT08"
for rel in ["project.godot", "main.tscn", "scripts/main.gd", "scripts/trace.gd"]:
    p = FIXTURE / rel
    assert p.is_file(), rel
    assert p.resolve().is_relative_to(FIXTURE.resolve())
print("GT01_STATIC_CHECK=PASS")
