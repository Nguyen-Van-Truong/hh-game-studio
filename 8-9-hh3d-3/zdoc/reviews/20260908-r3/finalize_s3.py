from pathlib import Path
import hashlib, json, os, tempfile

ROOT = Path(__file__).resolve().parents[3]
Z = ROOT / "zdoc"
GAME = Z / "8-9-hh-world-gameplay-viet-nam-plan.txt"
TOOLS = Z / "8-9-godot-blender-agent-studio-plan.txt"
OUT = Path(__file__).resolve().parent

def atomic(p, s):
    fd, n = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(s); f.flush(); os.fsync(f.fileno())
        os.replace(n, p)
    finally:
        if os.path.exists(n): os.unlink(n)

g = GAME.read_text(encoding="utf-8-sig")
for old, new in (("EX01–EX36", "EX01–EX39"), ("EX01–EX36,", "EX01–EX39,")):
    g = g.replace(old, new)
atomic(GAME, g)

def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest = {"revision":"S3", "files":[{"path":p.name,"sha256":h(p),"bytes":p.stat().st_size} for p in (TOOLS,GAME)]}
(OUT / "s3-freeze.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
