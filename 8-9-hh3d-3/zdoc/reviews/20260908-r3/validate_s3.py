from pathlib import Path
import hashlib, json, re, sys
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
Z = ROOT / "zdoc"
FILES = [
    (Z / "8-9-godot-blender-agent-studio-plan.txt", "GT-\\d{2}", 10, "TX", 14, "TOOLS"),
    (Z / "8-9-hh-world-gameplay-viet-nam-plan.txt", "H2-P\\d-\\d{2}", 32, "EX", 39, "GAME"),
]
errors = []
stats = []
for path, wp_pattern, wp_count, ex_prefix, ex_count, kind in FILES:
    if not path.exists():
        errors.append(f"missing {path}")
        continue
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 {path}: {exc}")
        continue
    if "\r" in text:
        errors.append(f"CRLF present {path}")
    rows = re.findall(rf"(?m)^\d{{2}} \| ({wp_pattern}) \| [^\n|]+ \| ([^\n|]+) \| PLANNED$", text)
    specs = re.findall(rf"(?m)^### ({wp_pattern}) — ", text)
    ex = re.findall(rf"(?m)^{ex_prefix}(\d{{2}}) — ", text)
    if len(rows) != wp_count: errors.append(f"{path.name}: table count {len(rows)} != {wp_count}")
    if len(specs) != wp_count: errors.append(f"{path.name}: spec count {len(specs)} != {wp_count}")
    nums = [int(x) for x in ex]
    if nums != list(range(1, ex_count + 1)):
        errors.append(f"{path.name}: exception sequence is {nums[:4]}...{nums[-4:] if nums else []}")
    current = re.search(r"(?m)^CURRENT_VALID_WP=(.+)$", text)
    if not current or not rows or current.group(1) != rows[0][0]: errors.append(f"{path.name}: current WP mismatch")
    for marker in ["PLAN_REVISION=S3", "EXECUTION_AUTHORIZATION=PLAN_ONLY", "IMPLEMENTATION=NOT_STARTED", "RUNTIME_ACCEPTANCE=NONE", "HUMAN_ACCEPTANCE=NONE", f"END_OF_{kind}_PLAN"]:
        if marker not in text: errors.append(f"{path.name}: missing {marker}")
    if kind == "GAME":
        forbidden = ["ST-", "GT-TOOL-HISTORY", "END_OF_UNIFIED", "hh-3d/hh-3d-2", "EX01–EX36"]
        for token in forbidden:
            if token in text: errors.append(f"{path.name}: stale/wrong-scope token {token}")
        for token in ["GT-10", "3.2.1 PHẠM VI QUY MÔ", "32 người/room", "32 người/room → 100 → 300 → 1.000 → 10.000", "hàng trăm triệu", "RSS/heap/GC", "cache/CDN", "privacy/telemetry profile", "16 KB"]:
            if token not in text: errors.append(f"{path.name}: missing required control {token}")
    else:
        for token in ["studio/fixtures/sample-game", "GT-10", "canonicalize JSON", "SSRF", "signed package", "last-good package"]:
            if token not in text: errors.append(f"{path.name}: missing required control {token}")
    stats.append({"path":path.name,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"wp":len(rows),"exceptions":len(ex)})

freeze_path = Path(__file__).resolve().parent / "s3-freeze.json"
if not freeze_path.exists(): errors.append("missing s3-freeze.json")
else:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    by_path = {x["path"]: x for x in freeze.get("files", [])}
    for item in stats:
        f = by_path.get(item["path"])
        if not f or f.get("sha256") != item["sha256"] or f.get("bytes") != item["bytes"]:
            errors.append(f"freeze mismatch {item['path']}")

result = {"kind":"STATIC_PLAN_CHECK_NOT_RUNTIME", "revision":"S3", "result":"FAIL" if errors else "PASS_STATIC_ONLY", "plans":stats, "errors":errors}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if errors else 0)
